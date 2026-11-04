"""MO-ORDER-BACKUP-ORCHESTRATION-P3A-01: DynamoDB On-Demand-Backup fuer Orders.

Rein lokal testbar: Der DynamoDB-Client wird injiziert, Zeit/Sleep sind
injizierbar. Dieses Modul importiert bewusst kein boto3 und fuehrt ohne
uebergebenen Client keinen AWS-Aufruf aus.

Sicherheitsprinzipien:
- Tabellenidentitaet wird gegen einen verifizierten Deployment-Kontext geprueft,
  nicht gegen einen frei uebergebenen Tabellennamen.
- Ein `CreateBackup`-HTTP-Erfolg ist kein Nachweis; nur `AVAILABLE` zaehlt.
- PITR wird zur Laufzeit ueber `DescribeContinuousBackups` geprueft, nicht aus
  Terraform abgeleitet.
- Evidenz enthaelt keine Order-Inhalte, keine PII und keine Roh-Fehlerantworten.
"""

from __future__ import annotations

import json
import re
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

EVIDENCE_JSON = "order-backup-evidence.json"
EVIDENCE_MD = "order-backup-evidence.md"
PLAN_JSON = "order-backup-plan.json"
PLAN_MD = "order-backup-plan.md"
EVIDENCE_SCHEMA_VERSION = 1

# -- Statuswerte ---------------------------------------------------------
BACKUP_REQUESTED = "REQUESTED"
BACKUP_CREATING = "CREATING"
BACKUP_AVAILABLE = "AVAILABLE"
BACKUP_FAILED = "FAILED"
BACKUP_TIMEOUT = "TIMEOUT"
BACKUP_UNKNOWN = "UNKNOWN"

PITR_ENABLED = "ENABLED"
PITR_DISABLED = "DISABLED"
PITR_UNKNOWN = "UNKNOWN"

OVERALL_VERIFIED = "VERIFIED"
OVERALL_PARTIAL = "PARTIAL"
OVERALL_FAILED = "FAILED"
OVERALL_UNVERIFIED = "UNVERIFIED"

# -- Fehlercodes ---------------------------------------------------------
CODE_IDENTITY_MISMATCH = "ORDER_BACKUP_TABLE_IDENTITY_MISMATCH"
CODE_TABLE_NOT_FOUND = "ORDER_BACKUP_TABLE_NOT_FOUND"
CODE_TABLE_NOT_ACTIVE = "ORDER_BACKUP_TABLE_NOT_ACTIVE"
CODE_ACCESS_DENIED = "ORDER_BACKUP_ACCESS_DENIED"
CODE_DESCRIBE_FAILED = "ORDER_BACKUP_DESCRIBE_FAILED"
CODE_CREATE_FAILED = "ORDER_BACKUP_CREATE_FAILED"
CODE_NAME_INVALID = "ORDER_BACKUP_NAME_INVALID"
CODE_NAME_CONFLICT = "ORDER_BACKUP_NAME_CONFLICT"
CODE_ARN_MISSING = "ORDER_BACKUP_ARN_MISSING"
CODE_BACKUP_IDENTITY_MISMATCH = "ORDER_BACKUP_IDENTITY_MISMATCH"
CODE_TIMEOUT = "ORDER_BACKUP_TIMEOUT"
CODE_BACKUP_FAILED = "ORDER_BACKUP_FAILED"
CODE_PITR_UNVERIFIED = "ORDER_BACKUP_PITR_UNVERIFIED"
CODE_STATE_BASELINE_REQUIRED = "ORDER_BACKUP_STATE_BASELINE_REQUIRED"
CODE_EVIDENCE_MISMATCH = "ORDER_BACKUP_EVIDENCE_MISMATCH"
CODE_EXECUTION_BLOCKED = "ORDER_BACKUP_EXECUTION_BLOCKED"

_TABLE_ARN_RE = re.compile(
    r"^arn:(?P<partition>aws[a-z-]*):dynamodb:(?P<region>[a-z0-9-]+):"
    r"(?P<account>\d{12}):table/(?P<table>.+)$"
)
_ACCOUNT_RE = re.compile(r"^\d{12}$")
_REGION_RE = re.compile(r"^[a-z]{2}(-gov)?-[a-z]+-\d$")
_BACKUP_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,255}$")
_UNSAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


class OrderBackupError(Exception):
    """Klassifizierter Fehler; Roh-AWS-Antworten werden nicht weitergereicht."""

    def __init__(self, code: str, message: str, *, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {"errorCode": self.code, "message": self.message, "details": self.details}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _parse_iso(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _client_error_code(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        error = response.get("Error") or {}
        code = error.get("Code")
        if isinstance(code, str):
            return code
    return ""


# -- Identitaet ----------------------------------------------------------

@dataclass(frozen=True)
class TableIdentity:
    """Erwartete oder tatsaechliche Order-Tabellenidentitaet."""

    project: str
    environment: str
    aws_account: str
    region: str
    table_name: str
    table_arn: str
    state_lineage: Optional[str] = None
    state_serial: Optional[int] = None
    state_fingerprint: Optional[str] = None
    state_fingerprint_version: Optional[str] = None
    state_baseline_status: Optional[str] = None
    captured_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project": self.project,
            "environment": self.environment,
            "awsAccount": self.aws_account,
            "region": self.region,
            "tableName": self.table_name,
            "tableArn": self.table_arn,
            "stateLineage": self.state_lineage,
            "stateSerial": self.state_serial,
            "stateFingerprint": self.state_fingerprint,
            "stateFingerprintVersion": self.state_fingerprint_version,
            "stateBaselineStatus": self.state_baseline_status,
            "capturedAt": self.captured_at,
        }


def expected_table_identity(
    *,
    project: str,
    environment: str,
    aws_account: Optional[str],
    region: str,
    state_baseline: Optional[Dict[str, Any]] = None,
    captured_at: Optional[str] = None,
) -> TableIdentity:
    """Bildet die erwartete Identitaet ausschliesslich aus dem Deployment-Kontext.

    Die Terraform-Konvention ist `name = var.project_name`; der Tabellenname
    wird daher aus dem Projekt abgeleitet und ist nicht frei waehlbar.
    Ohne verifizierten Account bleibt `table_arn` leer (fail-closed).
    """
    project = (project or "").strip()
    environment = (environment or "").strip()
    region = (region or "").strip()
    if not project:
        raise OrderBackupError(CODE_IDENTITY_MISMATCH, "Projektname fehlt")
    if not environment:
        raise OrderBackupError(CODE_IDENTITY_MISMATCH, "Environment fehlt")
    if not _REGION_RE.match(region):
        raise OrderBackupError(CODE_IDENTITY_MISMATCH, "Ungueltige AWS-Region")
    if aws_account is not None and not _ACCOUNT_RE.match(str(aws_account)):
        raise OrderBackupError(CODE_IDENTITY_MISMATCH, "Ungueltige AWS-Account-ID")

    table_name = project
    table_arn = (
        f"arn:aws:dynamodb:{region}:{aws_account}:table/{table_name}"
        if aws_account
        else ""
    )
    baseline = state_baseline or {}
    serial = baseline.get("serial")
    if serial is not None and not isinstance(serial, int):
        raise OrderBackupError(CODE_STATE_BASELINE_REQUIRED, "State-Serial ist ungueltig")
    return TableIdentity(
        project=project,
        environment=environment,
        aws_account=str(aws_account) if aws_account else "",
        region=region,
        table_name=table_name,
        table_arn=table_arn,
        state_lineage=baseline.get("lineage"),
        state_serial=serial,
        state_fingerprint=baseline.get("fingerprint"),
        state_fingerprint_version=(
            baseline.get("fingerprintVersion") or baseline.get("fingerprint_version")
        ),
        state_baseline_status=baseline.get("status"),
        captured_at=captured_at or (baseline.get("captured_at") or ""),
    )


def _require_complete_identity(expected: TableIdentity) -> None:
    missing = [
        name
        for name, value in (
            ("project", expected.project),
            ("environment", expected.environment),
            ("awsAccount", expected.aws_account),
            ("region", expected.region),
            ("tableName", expected.table_name),
            ("tableArn", expected.table_arn),
        )
        if not value
    ]
    if missing:
        raise OrderBackupError(
            CODE_IDENTITY_MISMATCH,
            "Erwartete Tabellenidentitaet ist unvollstaendig",
            details={"missing": missing},
        )
    # Die Tabelle wird aus dem Projekt abgeleitet (Terraform: name = project_name);
    # ein frei gewaehlter Tabellenname ist kein gueltiger Deployment-Kontext.
    if expected.table_name != expected.project:
        raise OrderBackupError(
            CODE_IDENTITY_MISMATCH,
            "Tabellenname ist nicht aus dem Projekt abgeleitet",
        )
    if not _BACKUP_NAME_RE.match(expected.table_name):
        raise OrderBackupError(CODE_IDENTITY_MISMATCH, "Tabellenname ist ungueltig")
    expected_arn = (
        f"arn:aws:dynamodb:{expected.region}:{expected.aws_account}:table/{expected.project}"
    )
    if expected.table_arn != expected_arn:
        raise OrderBackupError(CODE_IDENTITY_MISMATCH, "Erwartete Tabellen-ARN ist inkonsistent")


def _require_verified_state_baseline(expected: TableIdentity) -> None:
    if (
        expected.state_baseline_status != "VERIFIED"
        or not expected.state_lineage
        or not isinstance(expected.state_serial, int)
        or not expected.state_fingerprint
        or not expected.state_fingerprint_version
    ):
        raise OrderBackupError(
            CODE_STATE_BASELINE_REQUIRED,
            "Verifizierte Terraform-State-Baseline (Lineage/Serial/Fingerprint) fehlt",
        )


def verify_table_identity(client: Any, expected: TableIdentity) -> Dict[str, Any]:
    """Prueft DescribeTable gegen die erwartete Identitaet (fail-closed)."""
    _require_complete_identity(expected)
    try:
        response = client.describe_table(TableName=expected.table_name)
    except Exception as exc:  # noqa: BLE001 - klassifiziert, Rohantwort bleibt intern
        code = _client_error_code(exc)
        if code == "ResourceNotFoundException":
            raise OrderBackupError(CODE_TABLE_NOT_FOUND, "Order-Tabelle existiert nicht") from exc
        if code in ("AccessDeniedException", "UnauthorizedOperation"):
            raise OrderBackupError(CODE_ACCESS_DENIED, "Keine Berechtigung fuer DescribeTable") from exc
        raise OrderBackupError(CODE_DESCRIBE_FAILED, "DescribeTable fehlgeschlagen") from exc

    table = (response or {}).get("Table") or {}
    actual_name = table.get("TableName")
    actual_arn = table.get("TableArn")
    actual_status = table.get("TableStatus")
    if not isinstance(actual_name, str) or not isinstance(actual_arn, str):
        raise OrderBackupError(
            CODE_IDENTITY_MISMATCH, "DescribeTable liefert keine vollstaendige Identitaet"
        )
    parsed = _TABLE_ARN_RE.match(actual_arn)
    if not parsed:
        raise OrderBackupError(CODE_IDENTITY_MISMATCH, "Tabellen-ARN ist nicht parsebar")

    actual = TableIdentity(
        project=expected.project,
        environment=expected.environment,
        aws_account=parsed.group("account"),
        region=parsed.group("region"),
        table_name=actual_name,
        table_arn=actual_arn,
        state_lineage=expected.state_lineage,
        state_serial=expected.state_serial,
        state_fingerprint=expected.state_fingerprint,
        state_baseline_status=expected.state_baseline_status,
        captured_at=expected.captured_at,
    )

    mismatches: List[str] = []
    if actual_name != expected.table_name:
        mismatches.append("tableName")
    if actual_arn != expected.table_arn:
        mismatches.append("tableArn")
    if parsed.group("region") != expected.region:
        mismatches.append("region")
    if parsed.group("account") != expected.aws_account:
        mismatches.append("awsAccount")
    if mismatches:
        raise OrderBackupError(
            CODE_IDENTITY_MISMATCH,
            "Tatsaechliche Order-Tabelle weicht vom Deployment-Kontext ab",
            details={"mismatchedFields": mismatches},
        )
    if actual_status != "ACTIVE":
        raise OrderBackupError(
            CODE_TABLE_NOT_ACTIVE, "Order-Tabelle ist nicht ACTIVE",
            details={"tableStatus": actual_status},
        )
    return {
        "identity": actual,
        "tableStatus": actual_status,
        "verifiedAt": _iso(_utc_now()),
    }


# -- Backup-Name ---------------------------------------------------------

def build_backup_name(
    project: str,
    environment: str,
    *,
    now: Optional[datetime] = None,
    suffix: str = "",
) -> str:
    """DynamoDB-konformer, kollisionsarmer Backup-Name.

    Erlaubte Zeichen: `[A-Za-z0-9_.-]`, Laenge 3-255. Ein vorhandenes Backup
    wird nie ueberschrieben; Namenskollisionen werden als Fehler behandelt.
    """
    if not (project or "").strip() or not (environment or "").strip():
        raise OrderBackupError(CODE_NAME_INVALID, "Projekt und Environment sind erforderlich")
    base = _UNSAFE_NAME_RE.sub("-", f"{project}-{environment}-orders-preupgrade")
    base = base.strip(".-_")
    stamp = (now or _utc_now()).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parts = [base, stamp]
    if suffix:
        clean_suffix = _UNSAFE_NAME_RE.sub("", suffix)
        if clean_suffix:
            parts.append(clean_suffix)
    name = "-".join(part for part in parts if part)[:255].strip(".-_")
    if len(name) < 3 or not _BACKUP_NAME_RE.match(name):
        raise OrderBackupError(CODE_NAME_INVALID, "Backup-Name ist ungueltig")
    return name


# -- PITR ----------------------------------------------------------------

@dataclass(frozen=True)
class PitrEvidence:
    status: str
    earliest_restorable_at: Optional[str] = None
    latest_restorable_at: Optional[str] = None
    checked_at: str = ""
    error_code: Optional[str] = None

    @property
    def verified(self) -> bool:
        return self.status == PITR_ENABLED and self.error_code is None


def check_pitr(client: Any, expected: TableIdentity, *, checked_at: Optional[str] = None) -> PitrEvidence:
    """Liest den tatsaechlichen PITR-Status; Terraform ist kein Nachweis."""
    try:
        response = client.describe_continuous_backups(TableName=expected.table_name)
    except Exception as exc:  # noqa: BLE001
        code = _client_error_code(exc)
        if code in ("AccessDeniedException", "UnauthorizedOperation"):
            raise OrderBackupError(CODE_ACCESS_DENIED, "Keine Berechtigung fuer PITR-Status") from exc
        raise OrderBackupError(CODE_DESCRIBE_FAILED, "DescribeContinuousBackups fehlgeschlagen") from exc

    description = (response or {}).get("ContinuousBackupsDescription") or {}
    overall = description.get("ContinuousBackupsStatus")
    pitr = description.get("PointInTimeRecoveryDescription") or {}
    status = pitr.get("PointInTimeRecoveryStatus")
    timestamp = checked_at or _iso(_utc_now())

    if status == "DISABLED":
        return PitrEvidence(status=PITR_DISABLED, checked_at=timestamp)
    if status != "ENABLED" or overall not in ("ENABLED", None):
        return PitrEvidence(
            status=PITR_UNKNOWN, checked_at=timestamp, error_code=CODE_PITR_UNVERIFIED
        )

    earliest_raw = pitr.get("EarliestRestorableDateTime")
    latest_raw = pitr.get("LatestRestorableDateTime")
    earliest = _parse_iso(earliest_raw)
    latest = _parse_iso(latest_raw)
    if earliest is None or latest is None or earliest > latest:
        return PitrEvidence(
            status=PITR_UNKNOWN, checked_at=timestamp, error_code=CODE_PITR_UNVERIFIED
        )
    return PitrEvidence(
        status=PITR_ENABLED,
        earliest_restorable_at=_iso(earliest),
        latest_restorable_at=_iso(latest),
        checked_at=timestamp,
    )


# -- Backup-Ausfuehrung ---------------------------------------------------

@dataclass
class BackupEvidence:
    schema_version: int
    project: str
    environment: str
    aws_account: str
    region: str
    table_name: str
    table_arn: str
    backup_name: str
    backup_arn: Optional[str]
    backup_status: str
    backup_verified_at: Optional[str]
    pitr_status: str
    earliest_restorable_at: Optional[str]
    latest_restorable_at: Optional[str]
    overall_status: str
    identity_verified: bool
    identity_verified_at: Optional[str] = None
    pitr_checked_at: Optional[str] = None
    state_lineage: Optional[str] = None
    state_serial: Optional[int] = None
    state_fingerprint: Optional[str] = None
    state_fingerprint_version: Optional[str] = None
    generated_at: str = ""
    error_code: Optional[str] = None
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "project": self.project,
            "environment": self.environment,
            "awsAccount": self.aws_account,
            "region": self.region,
            "tableName": self.table_name,
            "tableArn": self.table_arn,
            "backupName": self.backup_name,
            "backupArn": self.backup_arn,
            "backupStatus": self.backup_status,
            "backupVerifiedAt": self.backup_verified_at,
            "pitrStatus": self.pitr_status,
            "earliestRestorableAt": self.earliest_restorable_at,
            "latestRestorableAt": self.latest_restorable_at,
            "overallStatus": self.overall_status,
            "identityVerified": self.identity_verified,
            "identityVerifiedAt": self.identity_verified_at,
            "pitrCheckedAt": self.pitr_checked_at,
            "stateLineage": self.state_lineage,
            "stateSerial": self.state_serial,
            "stateFingerprint": self.state_fingerprint,
            "stateFingerprintVersion": self.state_fingerprint_version,
            "generatedAt": self.generated_at,
            "errorCode": self.error_code,
            "limitations": list(self.limitations),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def _backup_details(response: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    description = (response or {}).get("BackupDescription") or {}
    details = description.get("BackupDetails") or {}
    source = description.get("SourceTableDetails") or {}
    return details, source


def _check_backup_identity(
    details: Dict[str, Any],
    source: Dict[str, Any],
    *,
    backup_arn: str,
    backup_name: str,
    expected: TableIdentity,
) -> None:
    if not source:
        raise OrderBackupError(CODE_BACKUP_IDENTITY_MISMATCH, "Quelltabellen-Identitaet fehlt")
    if details.get("BackupArn") != backup_arn:
        raise OrderBackupError(CODE_BACKUP_IDENTITY_MISMATCH, "Backup-ARN weicht ab")
    if details.get("BackupName") != backup_name:
        raise OrderBackupError(CODE_BACKUP_IDENTITY_MISMATCH, "Backup-Name weicht ab")
    if source.get("TableArn") != expected.table_arn:
        raise OrderBackupError(CODE_BACKUP_IDENTITY_MISMATCH, "Quelltabelle weicht ab")
    if source.get("TableName") != expected.table_name:
        raise OrderBackupError(CODE_BACKUP_IDENTITY_MISMATCH, "Quelltabellenname weicht ab")


def wait_for_backup(
    client: Any,
    expected: TableIdentity,
    *,
    backup_arn: str,
    backup_name: str,
    now_fn: Callable[[], float],
    sleep_fn: Callable[[float], None],
    poll_interval: float = 10.0,
    timeout_seconds: float = 900.0,
    max_attempts: int = 90,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Pollt DescribeBackup bis AVAILABLE/FAILED/Timeout. Kein Erfolg ohne AVAILABLE."""
    if poll_interval <= 0 or timeout_seconds <= 0 or max_attempts <= 0:
        raise ValueError("Polling-Parameter muessen positiv sein")
    deadline = now_fn() + timeout_seconds
    attempts = 0
    last_details: Optional[Dict[str, Any]] = None

    while attempts < max_attempts:
        attempts += 1
        try:
            response = client.describe_backup(BackupArn=backup_arn)
        except Exception as exc:  # noqa: BLE001
            code = _client_error_code(exc)
            if code == "ResourceNotFoundException":
                # Eventuelle Konsistenz direkt nach CreateBackup: bis Timeout warten.
                pass
            elif code in ("AccessDeniedException", "UnauthorizedOperation"):
                raise OrderBackupError(CODE_ACCESS_DENIED, "Keine Berechtigung fuer DescribeBackup") from exc
            else:
                raise OrderBackupError(CODE_DESCRIBE_FAILED, "DescribeBackup fehlgeschlagen") from exc
        else:
            details, source = _backup_details(response)
            if not details.get("BackupArn"):
                raise OrderBackupError(CODE_ARN_MISSING, "DescribeBackup liefert keinen Backup-ARN")
            _check_backup_identity(
                details, source,
                backup_arn=backup_arn, backup_name=backup_name, expected=expected,
            )
            last_details = details
            status = details.get("BackupStatus")
            if status == BACKUP_AVAILABLE:
                return BACKUP_AVAILABLE, details
            if status == BACKUP_FAILED:
                return BACKUP_FAILED, details
            if status not in (BACKUP_CREATING, BACKUP_REQUESTED):
                return BACKUP_UNKNOWN, details

        if attempts >= max_attempts:
            break
        remaining = deadline - now_fn()
        if remaining <= 0:
            break
        sleep_fn(min(poll_interval, remaining))

    if now_fn() >= deadline:
        return BACKUP_TIMEOUT, last_details
    return BACKUP_TIMEOUT, last_details


def execute_order_backup(
    client: Any,
    expected: TableIdentity,
    *,
    now_fn: Callable[[], float] = time.monotonic,
    sleep_fn: Callable[[float], None] = time.sleep,
    wall_clock: Callable[[], datetime] = _utc_now,
    poll_interval: float = 10.0,
    timeout_seconds: float = 900.0,
    max_attempts: int = 90,
    suffix: Optional[str] = None,
) -> BackupEvidence:
    """Fuehrt Identitaetspruefung, CreateBackup, Polling und PITR-Pruefung aus.

    Der Aufrufer muss einen echten oder Fake-DynamoDB-Client uebergeben.
    """
    _require_verified_state_baseline(expected)
    verify_table_identity(client, expected)
    backup_name = build_backup_name(
        expected.project,
        expected.environment,
        now=wall_clock(),
        suffix=secrets.token_hex(3) if suffix is None else suffix,
    )

    try:
        created = client.create_backup(TableName=expected.table_name, BackupName=backup_name)
    except Exception as exc:  # noqa: BLE001
        code = _client_error_code(exc)
        if code in ("AccessDeniedException", "UnauthorizedOperation"):
            raise OrderBackupError(CODE_ACCESS_DENIED, "Keine Berechtigung fuer CreateBackup") from exc
        if code in ("BackupInUseException", "ContinuousBackupsUnavailableException"):
            raise OrderBackupError(CODE_NAME_CONFLICT, "Backup-Name ist bereits belegt") from exc
        raise OrderBackupError(CODE_CREATE_FAILED, "CreateBackup fehlgeschlagen") from exc

    details = (created or {}).get("BackupDetails") or {}
    backup_arn = details.get("BackupArn")
    if not isinstance(backup_arn, str) or not backup_arn:
        raise OrderBackupError(CODE_ARN_MISSING, "CreateBackup liefert keinen Backup-ARN")
    if details.get("BackupName") != backup_name:
        raise OrderBackupError(CODE_BACKUP_IDENTITY_MISMATCH, "CreateBackup-Name weicht ab")

    status, final_details = wait_for_backup(
        client,
        expected,
        backup_arn=backup_arn,
        backup_name=backup_name,
        now_fn=now_fn,
        sleep_fn=sleep_fn,
        poll_interval=poll_interval,
        timeout_seconds=timeout_seconds,
        max_attempts=max_attempts,
    )

    try:
        pitr = check_pitr(client, expected, checked_at=_iso(wall_clock()))
    except OrderBackupError:
        # Ein PITR-Lesefehler darf ein bereits verifiziertes Backup nicht
        # verschwinden lassen: getrennt als UNKNOWN ausweisen.
        pitr = PitrEvidence(
            status=PITR_UNKNOWN,
            checked_at=_iso(wall_clock()),
            error_code=CODE_PITR_UNVERIFIED,
        )
    if status == BACKUP_AVAILABLE:
        overall = OVERALL_VERIFIED if pitr.verified else OVERALL_PARTIAL
    else:
        overall = OVERALL_FAILED

    return BackupEvidence(
        schema_version=EVIDENCE_SCHEMA_VERSION,
        project=expected.project,
        environment=expected.environment,
        aws_account=expected.aws_account,
        region=expected.region,
        table_name=expected.table_name,
        table_arn=expected.table_arn,
        backup_name=backup_name,
        backup_arn=backup_arn,
        backup_status=status,
        backup_verified_at=_iso(wall_clock()) if status == BACKUP_AVAILABLE else None,
        pitr_status=pitr.status,
        earliest_restorable_at=pitr.earliest_restorable_at,
        latest_restorable_at=pitr.latest_restorable_at,
        overall_status=overall,
        identity_verified=True,
        identity_verified_at=_iso(wall_clock()),
        pitr_checked_at=pitr.checked_at,
        state_lineage=expected.state_lineage,
        state_serial=expected.state_serial,
        state_fingerprint=expected.state_fingerprint,
        state_fingerprint_version=expected.state_fingerprint_version,
        generated_at=_iso(wall_clock()),
        error_code=(
            pitr.error_code
            if status == BACKUP_AVAILABLE
            else (CODE_TIMEOUT if status == BACKUP_TIMEOUT else CODE_BACKUP_FAILED)
        ),
        limitations=_LIMITATIONS,
    )


_LIMITATIONS = [
    "On-Demand-Backup verifiziert nur die Existenz; ein Restore wurde nicht getestet.",
    "PITR-Fenster ist zeitlich begrenzt und kein DSGVO-Wiederherstellungsnachweis.",
    "Backups koennen personenbezogene Daten enthalten, die nach dem Sicherungszeitpunkt geloescht wurden.",
    "Keine kryptografische Signatur; Evidenz ist an Deployment-/State-Kontext gebunden, nicht signiert.",
]


# -- Dry-Run -------------------------------------------------------------

@dataclass
class BackupPlan:
    project: str
    environment: str
    aws_account: Optional[str]
    region: str
    table_name: str
    table_arn: Optional[str]
    backup_name: str
    generated_at: str
    state_baseline_status: Optional[str]
    state_lineage: Optional[str]
    state_serial: Optional[int]
    steps: List[str] = field(default_factory=list)
    required_permissions: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schemaVersion": EVIDENCE_SCHEMA_VERSION,
            "mode": "DRY_RUN",
            "overallStatus": OVERALL_UNVERIFIED,
            "identityVerified": False,
            "pitrStatus": PITR_UNKNOWN,
            "project": self.project,
            "environment": self.environment,
            "awsAccount": self.aws_account,
            "region": self.region,
            "tableName": self.table_name,
            "tableArn": self.table_arn,
            "backupName": self.backup_name,
            "generatedAt": self.generated_at,
            "stateBaselineStatus": self.state_baseline_status,
            "stateLineage": self.state_lineage,
            "stateSerial": self.state_serial,
            "steps": list(self.steps),
            "requiredPermissions": list(self.required_permissions),
            "limitations": list(self.limitations),
        }


def plan_order_backup(
    *,
    project: str,
    environment: str,
    aws_account: Optional[str],
    region: str,
    state_baseline: Optional[Dict[str, Any]] = None,
    wall_clock: Callable[[], datetime] = _utc_now,
    suffix: str = "",
) -> BackupPlan:
    """Offline-Planung ohne Client und ohne AWS-Aufruf.

    Behauptet weder Tabellenidentitaet noch PITR-Status; alles bleibt UNVERIFIED.
    """
    identity = expected_table_identity(
        project=project,
        environment=environment,
        aws_account=aws_account,
        region=region,
        state_baseline=state_baseline,
    )
    now = wall_clock()
    name = build_backup_name(project, environment, now=now, suffix=suffix)
    return BackupPlan(
        project=identity.project,
        environment=identity.environment,
        aws_account=identity.aws_account or None,
        region=identity.region,
        table_name=identity.table_name,
        table_arn=identity.table_arn or None,
        backup_name=name,
        generated_at=_iso(now),
        state_baseline_status=identity.state_baseline_status,
        state_lineage=identity.state_lineage,
        state_serial=identity.state_serial,
        steps=[
            "DescribeTable: Tabellenname/ARN/Account/Region gegen Deployment-Kontext pruefen",
            "CreateBackup mit eindeutigem Namen",
            "DescribeBackup pollen bis AVAILABLE (kein Erfolg bei CREATING/FAILED/Timeout)",
            "DescribeContinuousBackups: PITR-Status und Wiederherstellungsfenster lesen",
            "Evidenz schreiben (nur Metadaten, keine Order-Inhalte)",
        ],
        required_permissions=[
            "dynamodb:DescribeTable",
            "dynamodb:CreateBackup",
            "dynamodb:DescribeBackup",
            "dynamodb:DescribeContinuousBackups",
        ],
        limitations=_LIMITATIONS,
    )


# -- Evidenz schreiben ----------------------------------------------------

def validate_evidence_binding(evidence: BackupEvidence, expected: TableIdentity) -> None:
    """Prueft, ob Evidenz zum erwarteten Deployment-Kontext gehoert."""
    mismatches: List[str] = []
    checks = {
        "project": (evidence.project, expected.project),
        "environment": (evidence.environment, expected.environment),
        "awsAccount": (evidence.aws_account, expected.aws_account),
        "region": (evidence.region, expected.region),
        "tableName": (evidence.table_name, expected.table_name),
        "tableArn": (evidence.table_arn, expected.table_arn),
        "stateLineage": (evidence.state_lineage, expected.state_lineage),
        "stateSerial": (evidence.state_serial, expected.state_serial),
        "stateFingerprint": (evidence.state_fingerprint, expected.state_fingerprint),
        "stateFingerprintVersion": (
            evidence.state_fingerprint_version,
            expected.state_fingerprint_version,
        ),
    }
    for field_name, (actual, wanted) in checks.items():
        if actual != wanted:
            mismatches.append(field_name)
    if not evidence.backup_arn:
        mismatches.append("backupArn")
    if evidence.overall_status == OVERALL_VERIFIED and evidence.backup_status != BACKUP_AVAILABLE:
        mismatches.append("overallStatus")
    if mismatches:
        raise OrderBackupError(
            CODE_EVIDENCE_MISMATCH,
            "Backup-Evidenz passt nicht zum Deployment-Kontext",
            details={"mismatchedFields": mismatches},
        )


def write_evidence(run_dir: str | Path, evidence: BackupEvidence) -> Tuple[Path, Path]:
    target = Path(run_dir)
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / EVIDENCE_JSON
    md_path = target / EVIDENCE_MD
    json_path.write_text(evidence.to_json(), encoding="utf-8")
    md_path.write_text(_render_evidence_md(evidence), encoding="utf-8")
    return json_path, md_path


def write_plan(run_dir: str | Path, plan: BackupPlan) -> Tuple[Path, Path]:
    target = Path(run_dir)
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / PLAN_JSON
    md_path = target / PLAN_MD
    json_path.write_text(json.dumps(plan.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_render_plan_md(plan), encoding="utf-8")
    return json_path, md_path


def _render_evidence_md(evidence: BackupEvidence) -> str:
    lines = [
        "# Order-Backup-Evidenz (P3A)",
        "",
        f"**Overall:** `{evidence.overall_status}`",
        f"**Backup:** `{evidence.backup_status}`",
        f"**PITR:** `{evidence.pitr_status}`",
        "",
        "| Feld | Wert |",
        "|---|---|",
        f"| Projekt | `{evidence.project}` |",
        f"| Environment | `{evidence.environment}` |",
        f"| AWS-Account | `{evidence.aws_account}` |",
        f"| Region | `{evidence.region}` |",
        f"| Tabelle | `{evidence.table_name}` |",
        f"| Tabellen-ARN | `{evidence.table_arn}` |",
        f"| Backup-Name | `{evidence.backup_name}` |",
        f"| Backup-ARN | `{evidence.backup_arn or '-'}` |",
        f"| Backup verifiziert am | `{evidence.backup_verified_at or '-'}` |",
        f"| PITR fruehester Zeitpunkt | `{evidence.earliest_restorable_at or '-'}` |",
        f"| PITR spaetester Zeitpunkt | `{evidence.latest_restorable_at or '-'}` |",
        f"| State-Lineage | `{evidence.state_lineage or '-'}` |",
        f"| State-Serial | `{evidence.state_serial if evidence.state_serial is not None else '-'}` |",
        f"| Fehlercode | `{evidence.error_code or '-'}` |",
        "",
        "## Grenzen",
        "",
    ]
    lines.extend(f"- {item}" for item in evidence.limitations)
    lines.append("")
    return "\n".join(lines)


def _render_plan_md(plan: BackupPlan) -> str:
    lines = [
        "# Order-Backup-Plan (Dry-Run, P3A)",
        "",
        "**Overall:** `UNVERIFIED` — keine Tabellenidentitaet und kein PITR-Status geprueft.",
        "",
        "| Feld | Wert |",
        "|---|---|",
        f"| Projekt | `{plan.project}` |",
        f"| Environment | `{plan.environment}` |",
        f"| AWS-Account | `{plan.aws_account or 'UNVERIFIED'}` |",
        f"| Region | `{plan.region}` |",
        f"| Tabelle | `{plan.table_name}` |",
        f"| Backup-Name | `{plan.backup_name}` |",
        f"| State-Baseline | `{plan.state_baseline_status or 'MISSING'}` |",
        "",
        "## Geplante Schritte",
        "",
    ]
    lines.extend(f"{index}. {step}" for index, step in enumerate(plan.steps, 1))
    lines.extend(["", "## Erwartete Berechtigungen", ""])
    lines.extend(f"- `{permission}`" for permission in plan.required_permissions)
    lines.extend(["", "## Grenzen", ""])
    lines.extend(f"- {item}" for item in plan.limitations)
    lines.append("")
    return "\n".join(lines)
