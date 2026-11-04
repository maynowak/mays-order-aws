"""MO-RC4-UPGRADE-RELEASE-GATES-01: P3A-Backup-Evidenz als Upgrade-Gate.

Liest `order-backup-evidence.json` (P3A) und prueft Status, Deployment-Identitaet
und State-Bindung. Es werden keine AWS-Aufrufe gemacht und keine Evidenz erfunden.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from installer.core.order_backup import EVIDENCE_JSON, EVIDENCE_SCHEMA_VERSION
from installer.core.state_fingerprint import FINGERPRINT_VERSION

BACKUP_NOT_REQUIRED = "NOT_REQUIRED"
BACKUP_VERIFIED = "VERIFIED"
BACKUP_PARTIAL = "PARTIAL"
BACKUP_FAILED = "FAILED"
BACKUP_MISSING = "MISSING"
BACKUP_INVALID = "INVALID"
BACKUP_IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
BACKUP_STALE = "STALE"

BLOCKING_STATUSES = (
    BACKUP_PARTIAL,
    BACKUP_FAILED,
    BACKUP_MISSING,
    BACKUP_INVALID,
    BACKUP_IDENTITY_MISMATCH,
    BACKUP_STALE,
)

CODE_MISSING = "UPGRADE_BACKUP_EVIDENCE_MISSING"
CODE_UNREADABLE = "UPGRADE_BACKUP_EVIDENCE_UNREADABLE"
CODE_INVALID = "UPGRADE_BACKUP_EVIDENCE_INVALID"
CODE_NOT_VERIFIED = "UPGRADE_BACKUP_EVIDENCE_NOT_VERIFIED"
CODE_IDENTITY_MISMATCH = "UPGRADE_BACKUP_EVIDENCE_IDENTITY_MISMATCH"
CODE_STATE_MISMATCH = "UPGRADE_BACKUP_EVIDENCE_STATE_MISMATCH"
CODE_HASH_MISMATCH = "UPGRADE_BACKUP_EVIDENCE_HASH_MISMATCH"
CODE_FINGERPRINT_MISSING = "UPGRADE_BACKUP_EVIDENCE_FINGERPRINT_MISSING"
CODE_FINGERPRINT_VERSION_UNKNOWN = "UPGRADE_BACKUP_EVIDENCE_FINGERPRINT_VERSION_UNKNOWN"
CODE_FINGERPRINT_MISMATCH = "UPGRADE_BACKUP_EVIDENCE_FINGERPRINT_MISMATCH"


@dataclass(frozen=True)
class BackupEvidenceAssessment:
    status: str
    required: bool
    code: Optional[str]
    message: str
    path: Optional[str] = None
    sha256: Optional[str] = None
    backup_arn: Optional[str] = None
    backup_verified_at: Optional[str] = None
    pitr_status: Optional[str] = None
    overall_status: Optional[str] = None
    state_lineage: Optional[str] = None
    state_serial: Optional[int] = None
    state_fingerprint: Optional[str] = None
    state_fingerprint_version: Optional[str] = None

    @property
    def blocking(self) -> bool:
        return self.required and self.status in BLOCKING_STATUSES

    @property
    def verified(self) -> bool:
        return (not self.required) or self.status == BACKUP_VERIFIED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "required": self.required,
            "blocking": self.blocking,
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "sha256": self.sha256,
            "backupArn": self.backup_arn,
            "backupVerifiedAt": self.backup_verified_at,
            "pitrStatus": self.pitr_status,
            "overallStatus": self.overall_status,
            "stateLineage": self.state_lineage,
            "stateSerial": self.state_serial,
            "stateFingerprint": self.state_fingerprint,
            "stateFingerprintVersion": self.state_fingerprint_version,
        }

    def to_manifest(self) -> Dict[str, Any]:
        """Nur bindbare Metadaten; kein Evidenz-Inhalt, keine PII."""
        return {
            "status": self.status,
            "fileName": self.path,
            "sha256": self.sha256,
            "backupArn": self.backup_arn,
            "backupVerifiedAt": self.backup_verified_at,
            "pitrStatus": self.pitr_status,
            "overallStatus": self.overall_status,
            "stateLineage": self.state_lineage,
            "stateSerial": self.state_serial,
            "stateFingerprint": self.state_fingerprint,
            "stateFingerprintVersion": self.state_fingerprint_version,
        }


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def requires_backup(
    source_version: Optional[str],
    target_version: Optional[str],
    *,
    operation: str = "deploy",
) -> bool:
    if operation != "deploy":
        return False
    if not source_version or not target_version:
        return False
    return str(source_version) != str(target_version)


def copy_evidence_to_run_dir(source: str | Path, run_dir: str | Path) -> Path:
    src = Path(source)
    target = Path(run_dir) / EVIDENCE_JSON
    target.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != target.resolve():
        shutil.copy2(src, target)
    return target


def _assessment(
    status: str,
    *,
    required: bool,
    code: Optional[str],
    message: str,
    path: Optional[Path] = None,
    sha256: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> BackupEvidenceAssessment:
    data = data or {}
    return BackupEvidenceAssessment(
        status=status,
        required=required,
        code=code,
        message=message,
        path=path.name if path else None,
        sha256=sha256,
        backup_arn=data.get("backupArn"),
        backup_verified_at=data.get("backupVerifiedAt"),
        pitr_status=data.get("pitrStatus"),
        overall_status=data.get("overallStatus"),
        state_lineage=data.get("stateLineage"),
        state_serial=data.get("stateSerial"),
        state_fingerprint=data.get("stateFingerprint"),
        state_fingerprint_version=data.get("stateFingerprintVersion"),
    )


def assess_backup_evidence(
    evidence_path: Optional[str | Path],
    *,
    required: bool,
    expected_project: str,
    expected_environment: str,
    expected_account: str,
    expected_region: str,
    expected_table_name: Optional[str] = None,
    expected_table_arn: Optional[str] = None,
    state_lineage: Optional[str] = None,
    state_serial: Optional[int] = None,
    state_fingerprint: Optional[str] = None,
    state_fingerprint_version: str = FINGERPRINT_VERSION,
    expected_sha256: Optional[str] = None,
) -> BackupEvidenceAssessment:
    """Prueft P3A-Evidenz fail-closed; keine AWS-Aufrufe."""
    if not required:
        return BackupEvidenceAssessment(
            status=BACKUP_NOT_REQUIRED,
            required=False,
            code=None,
            message="Fuer diesen Plan ist keine Backup-Evidenz erforderlich.",
        )
    path = Path(evidence_path) if evidence_path else None
    if path is None or not path.exists():
        return BackupEvidenceAssessment(
            status=BACKUP_MISSING,
            required=True,
            code=CODE_MISSING,
            message="Backup-Evidenz fehlt (order-backup-evidence.json).",
            path=path.name if path else None,
        )
    try:
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
    except OSError:
        return BackupEvidenceAssessment(
            status=BACKUP_INVALID,
            required=True,
            code=CODE_UNREADABLE,
            message="Backup-Evidenz ist nicht lesbar.",
            path=path.name,
        )
    if expected_sha256 and digest != expected_sha256:
        return BackupEvidenceAssessment(
            status=BACKUP_INVALID,
            required=True,
            code=CODE_HASH_MISMATCH,
            message="Backup-Evidenz wurde nach der Manifest-Erstellung veraendert.",
            path=path.name,
            sha256=digest,
        )
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return BackupEvidenceAssessment(
            status=BACKUP_INVALID,
            required=True,
            code=CODE_INVALID,
            message="Backup-Evidenz ist kein gueltiges JSON.",
            path=path.name,
            sha256=digest,
        )
    if not isinstance(data, dict):
        return BackupEvidenceAssessment(
            status=BACKUP_INVALID,
            required=True,
            code=CODE_INVALID,
            message="Backup-Evidenz ist kein Objekt.",
            path=path.name,
            sha256=digest,
        )
    if data.get("schemaVersion") != EVIDENCE_SCHEMA_VERSION:
        return _assessment(
            BACKUP_INVALID, required=True, code=CODE_INVALID,
            message="Unbekannte Backup-Evidenz-Schema-Version.",
            path=path, sha256=digest, data=data,
        )
    required_fields = (
        "project", "environment", "awsAccount", "region", "tableName", "tableArn",
        "backupName", "backupArn", "backupStatus", "backupVerifiedAt",
        "pitrStatus", "overallStatus", "stateLineage", "stateSerial",
    )
    missing = [name for name in required_fields if not data.get(name)]
    if missing:
        return _assessment(
            BACKUP_INVALID, required=True, code=CODE_INVALID,
            message="Backup-Evidenz ist unvollstaendig.",
            path=path, sha256=digest, data=data,
        )

    table_name = expected_table_name or expected_project
    table_arn = expected_table_arn or (
        f"arn:aws:dynamodb:{expected_region}:{expected_account}:table/{table_name}"
    )
    identity_checks = {
        "project": (data.get("project"), expected_project),
        "environment": (data.get("environment"), expected_environment),
        "awsAccount": (data.get("awsAccount"), expected_account),
        "region": (data.get("region"), expected_region),
        "tableName": (data.get("tableName"), table_name),
        "tableArn": (data.get("tableArn"), table_arn),
    }
    mismatched = [name for name, (actual, wanted) in identity_checks.items() if actual != wanted]
    if mismatched:
        return _assessment(
            BACKUP_IDENTITY_MISMATCH, required=True, code=CODE_IDENTITY_MISMATCH,
            message="Backup-Evidenz passt nicht zum Deployment-Kontext: "
                    + ", ".join(mismatched),
            path=path, sha256=digest, data=data,
        )

    if state_lineage is not None and data.get("stateLineage") != state_lineage:
        return _assessment(
            BACKUP_STALE, required=True, code=CODE_STATE_MISMATCH,
            message="Backup-Evidenz gehoert zu einer anderen State-Lineage.",
            path=path, sha256=digest, data=data,
        )
    if state_serial is not None and data.get("stateSerial") != state_serial:
        return _assessment(
            BACKUP_STALE, required=True, code=CODE_STATE_MISMATCH,
            message="Backup-Evidenz gehoert zu einem anderen State-Serial.",
            path=path, sha256=digest, data=data,
        )
    if not data.get("stateFingerprint"):
        return _assessment(
            BACKUP_INVALID, required=True, code=CODE_FINGERPRINT_MISSING,
            message="Backup-Evidenz enthaelt keinen kanonischen State-Fingerprint.",
            path=path, sha256=digest, data=data,
        )
    if data.get("stateFingerprintVersion") != state_fingerprint_version:
        return _assessment(
            BACKUP_INVALID, required=True, code=CODE_FINGERPRINT_VERSION_UNKNOWN,
            message="State-Fingerprint-Version fehlt oder ist unbekannt "
                    f"(erwartet {state_fingerprint_version}).",
            path=path, sha256=digest, data=data,
        )
    if state_fingerprint is not None and data.get("stateFingerprint") != state_fingerprint:
        return _assessment(
            BACKUP_STALE, required=True, code=CODE_FINGERPRINT_MISMATCH,
            message="Backup-Evidenz gehoert zu einem anderen kanonischen State-Fingerprint.",
            path=path, sha256=digest, data=data,
        )

    if data.get("backupStatus") != "AVAILABLE":
        return _assessment(
            BACKUP_FAILED, required=True, code=CODE_NOT_VERIFIED,
            message="Backup ist nicht AVAILABLE.",
            path=path, sha256=digest, data=data,
        )
    if data.get("overallStatus") != "VERIFIED" or data.get("pitrStatus") != "ENABLED":
        status = BACKUP_PARTIAL if data.get("overallStatus") == "PARTIAL" else BACKUP_FAILED
        return _assessment(
            status, required=True, code=CODE_NOT_VERIFIED,
            message="Backup/PITR ist nicht vollstaendig VERIFIED.",
            path=path, sha256=digest, data=data,
        )
    if _parse_time(data.get("backupVerifiedAt")) is None:
        return _assessment(
            BACKUP_INVALID, required=True, code=CODE_INVALID,
            message="backupVerifiedAt ist kein gueltiger Zeitpunkt.",
            path=path, sha256=digest, data=data,
        )
    return _assessment(
        BACKUP_VERIFIED, required=True, code=None,
        message="Backup-Evidenz ist vollstaendig VERIFIED.",
        path=path, sha256=digest, data=data,
    )


def assess_manifest_evidence(
    plan_path: str | Path,
    summary: Optional[Dict[str, Any]],
    *,
    expected_project: str,
    expected_environment: str,
    expected_account: str,
    expected_region: str,
    state_lineage: Optional[str] = None,
    state_serial: Optional[int] = None,
    state_fingerprint: Optional[str] = None,
    state_fingerprint_version: str = FINGERPRINT_VERSION,
) -> BackupEvidenceAssessment:
    if not summary:
        return BackupEvidenceAssessment(
            status=BACKUP_MISSING,
            required=True,
            code=CODE_MISSING,
            message="Plan-Manifest enthaelt keine Backup-Evidenz.",
        )
    plan = Path(plan_path)
    file_name = summary.get("fileName") or EVIDENCE_JSON
    path = plan.parent / file_name
    return assess_backup_evidence(
        path,
        required=True,
        expected_project=expected_project,
        expected_environment=expected_environment,
        expected_account=expected_account,
        expected_region=expected_region,
        state_lineage=state_lineage,
        state_serial=state_serial,
        state_fingerprint=state_fingerprint,
        state_fingerprint_version=state_fingerprint_version,
        expected_sha256=summary.get("sha256"),
    )


def _parse_time(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
