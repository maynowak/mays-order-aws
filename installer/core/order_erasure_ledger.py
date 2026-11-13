"""MO-ORDER-ERASURE-LEDGER-P3E-01: lokales Ledger-Domainmodell und Reconciliation.

Kein AWS, keine Persistenz, keine Änderung an Order-Daten oder Lambda-Code.
Die Reconciliation erzeugt ausschließlich einen Plan; sie führt keine Löschung
oder Anonymisierung aus.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

LEDGER_SCHEMA_VERSION = 1
READINESS_SCHEMA_VERSION = 1
PLAN_SCHEMA_VERSION = 1

OP_ERASE = "ERASE"
OP_ANONYMIZE = "ANONYMIZE"
OP_RETAIN = "RETAIN"
OPERATIONS = (OP_ERASE, OP_ANONYMIZE, OP_RETAIN)

STATUS_COMPLETED = "COMPLETED"
STATUS_PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
STATUS_BLOCKED = "BLOCKED"
STATUS_FAILED = "FAILED"
EVENT_STATUSES = (
    STATUS_COMPLETED,
    STATUS_PARTIALLY_COMPLETED,
    STATUS_BLOCKED,
    STATUS_FAILED,
)
APPLIED_STATUSES = (STATUS_COMPLETED, STATUS_PARTIALLY_COMPLETED, STATUS_FAILED)

PLAN_VERIFIED = "PLAN_VERIFIED"
PLAN_BLOCKED = "BLOCKED"
PLAN_REVIEW_REQUIRED = "REVIEW_REQUIRED"
PLAN_UNKNOWN = "UNKNOWN"

READINESS_VERIFIED = "VERIFIED"
READINESS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
READINESS_BLOCKED = "BLOCKED"
READINESS_UNKNOWN = "UNKNOWN"

EXECUTION_NOT_VERIFIED = "EXECUTION_NOT_VERIFIED"
CUTOVER_BLOCKED = "CUTOVER_BLOCKED"

ACTION_DELETE = "DELETE"
ACTION_ANONYMIZE = "ANONYMIZE"
ACTION_RETAIN = "RETAIN"

CODE_LEDGER_MISSING = "ORDER_LEDGER_MISSING"
CODE_SCHEMA_UNKNOWN = "ORDER_LEDGER_SCHEMA_UNKNOWN"
CODE_INCOMPLETE = "ORDER_LEDGER_INCOMPLETE"
CODE_MISSING_FIELD = "ORDER_LEDGER_MISSING_FIELD"
CODE_INTEGRITY_MISSING = "ORDER_LEDGER_INTEGRITY_MISSING"
CODE_INTEGRITY_MISMATCH = "ORDER_LEDGER_INTEGRITY_MISMATCH"
CODE_DUPLICATE_CONFLICT = "ORDER_LEDGER_DUPLICATE_CONFLICT"
CODE_CONFLICTING_EVENTS = "ORDER_LEDGER_CONFLICTING_EVENTS"
CODE_INVALID_CHRONOLOGY = "ORDER_LEDGER_INVALID_CHRONOLOGY"
CODE_RESTORE_TIME_MISSING = "ORDER_LEDGER_RESTORE_TIME_MISSING"
CODE_RESTORE_IDENTITY_MISMATCH = "ORDER_RESTORE_IDENTITY_MISMATCH"
CODE_CONSUMER_UNKNOWN = "ORDER_LEDGER_CONSUMER_UNKNOWN"
CODE_ORDER_KEY_UNKNOWN = "ORDER_LEDGER_ORDER_KEY_UNKNOWN"
CODE_PARTIAL_APPLICATION = "ORDER_LEDGER_PARTIAL_APPLICATION"
CODE_NO_HISTORY = "ORDER_LEDGER_NO_HISTORY"
CODE_CUTOVER_BLOCKED = "ORDER_RESTORE_CUTOVER_BLOCKED"
CODE_WEAK_KEY = "ORDER_LEDGER_WEAK_KEY"

_ORDER_REF_RE = re.compile(r"^ord_[0-9a-f]{24}$")
_SUBJECT_REF_RE = re.compile(r"^hmac-sha256:[A-Za-z0-9_.-]{1,64}:[0-9a-f]{64}$")
_TABLE_ARN_RE = re.compile(
    r"^arn:(?P<partition>aws[a-z-]*):dynamodb:(?P<region>[a-z0-9-]+):"
    r"(?P<account>\d{12}):table/(?P<table>.+)$"
)


class ErasureLedgerError(Exception):
    def __init__(self, code: str, message: str, *, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {"errorCode": self.code, "message": self.message, "details": self.details}


# -- Zeit / Kanonisierung -------------------------------------------------

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


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _canonical(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# -- Pseudonymisierung ----------------------------------------------------

def pseudonymize_subject(subject_id: str, *, key: bytes, key_id: str) -> str:
    """Stabile, zweckgebundene Subject-Referenz per keyed HMAC-SHA256.

    Ohne Schlüssel keine Pseudonymisierung; ungesalzene Hashes werden bewusst
    nicht unterstützt. Der Schlüssel darf niemals im Ledger gespeichert werden.
    """
    if not isinstance(subject_id, str) or not subject_id.strip():
        raise ErasureLedgerError(CODE_MISSING_FIELD, "subjectId fehlt")
    if not isinstance(key, (bytes, bytearray)) or len(key) < 32:
        raise ErasureLedgerError(CODE_WEAK_KEY, "HMAC-Schluessel muss mindestens 32 Byte haben")
    if not isinstance(key_id, str) or not re.match(r"^[A-Za-z0-9_.-]{1,64}$", key_id):
        raise ErasureLedgerError(CODE_MISSING_FIELD, "keyId ist ungueltig")
    digest = hmac.new(bytes(key), subject_id.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"hmac-sha256:{key_id}:{digest}"


def subject_ref_key_id(subject_ref: str) -> Optional[str]:
    if not isinstance(subject_ref, str):
        return None
    match = re.match(r"^hmac-sha256:([A-Za-z0-9_.-]{1,64}):[0-9a-f]{64}$", subject_ref)
    return match.group(1) if match else None


# -- Event ----------------------------------------------------------------

@dataclass(frozen=True)
class ErasureEvent:
    event_id: str
    operation_id: str
    operation: str
    consumer_id: str
    subject_ref: str
    order_refs: Tuple[str, ...]
    decided_at: str
    applied_at: Optional[str]
    status: str
    idempotency_key: str
    affected_records: int = 0
    deleted_records: int = 0
    anonymized_records: int = 0
    retained_records: int = 0
    skipped_records: int = 0
    failed_records: int = 0
    integrity_sha256: str = ""

    def payload(self) -> Dict[str, Any]:
        return {
            "eventId": self.event_id,
            "operationId": self.operation_id,
            "operation": self.operation,
            "consumerId": self.consumer_id,
            "subjectRef": self.subject_ref,
            "orderRefs": list(self.order_refs),
            "decidedAt": self.decided_at,
            "appliedAt": self.applied_at,
            "status": self.status,
            "idempotencyKey": self.idempotency_key,
            "affectedRecords": self.affected_records,
            "deletedRecords": self.deleted_records,
            "anonymizedRecords": self.anonymized_records,
            "retainedRecords": self.retained_records,
            "skippedRecords": self.skipped_records,
            "failedRecords": self.failed_records,
        }

    def semantic_payload(self) -> Dict[str, Any]:
        """Fachlicher Inhalt ohne Event-ID/Integritaet fuer Idempotenzvergleiche."""
        payload = self.payload()
        payload.pop("eventId", None)
        return payload

    def compute_integrity(self) -> str:
        return _sha256(_canonical(self.payload()))

    def to_dict(self) -> Dict[str, Any]:
        data = self.payload()
        data["integritySha256"] = self.integrity_sha256 or self.compute_integrity()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ErasureEvent":
        if not isinstance(data, dict):
            raise ErasureLedgerError(CODE_MISSING_FIELD, "Event ist kein Objekt")
        required = (
            "eventId", "operationId", "operation", "consumerId", "subjectRef",
            "orderRefs", "decidedAt", "status", "idempotencyKey",
        )
        missing = [name for name in required if not data.get(name)]
        if missing:
            raise ErasureLedgerError(
                CODE_MISSING_FIELD, "Event-Felder fehlen", details={"missing": missing}
            )
        if not data.get("integritySha256"):
            raise ErasureLedgerError(CODE_INTEGRITY_MISSING, "Event-Integritaet fehlt")
        operation = str(data["operation"]).upper()
        if operation not in OPERATIONS:
            raise ErasureLedgerError(CODE_MISSING_FIELD, "Unbekannte Operation")
        status = str(data["status"]).upper()
        if status not in EVENT_STATUSES:
            raise ErasureLedgerError(CODE_MISSING_FIELD, "Unbekannter Event-Status")
        order_refs = data["orderRefs"]
        if not isinstance(order_refs, (list, tuple)) or not order_refs:
            raise ErasureLedgerError(CODE_MISSING_FIELD, "orderRefs fehlen")
        event = cls(
            event_id=str(data["eventId"]),
            operation_id=str(data["operationId"]),
            operation=operation,
            consumer_id=str(data["consumerId"]).strip(),
            subject_ref=str(data["subjectRef"]),
            order_refs=tuple(str(ref) for ref in order_refs),
            decided_at=str(data["decidedAt"]),
            applied_at=str(data["appliedAt"]) if data.get("appliedAt") else None,
            status=status,
            idempotency_key=str(data["idempotencyKey"]),
            affected_records=int(data.get("affectedRecords", 0)),
            deleted_records=int(data.get("deletedRecords", 0)),
            anonymized_records=int(data.get("anonymizedRecords", 0)),
            retained_records=int(data.get("retainedRecords", 0)),
            skipped_records=int(data.get("skippedRecords", 0)),
            failed_records=int(data.get("failedRecords", 0)),
            integrity_sha256=str(data["integritySha256"]),
        )
        event._validate()
        return event

    def _validate(self) -> None:
        if not self.event_id or not self.operation_id or not self.idempotency_key:
            raise ErasureLedgerError(CODE_MISSING_FIELD, "Event-ID/Operation-ID fehlt")
        if not self.consumer_id:
            raise ErasureLedgerError(CODE_CONSUMER_UNKNOWN, "Consumer-Scope fehlt")
        if not _SUBJECT_REF_RE.match(self.subject_ref):
            raise ErasureLedgerError(CODE_MISSING_FIELD, "subjectRef ist nicht HMAC-pseudonymisiert")
        for ref in self.order_refs:
            if not _ORDER_REF_RE.match(ref):
                raise ErasureLedgerError(
                    CODE_ORDER_KEY_UNKNOWN, "Order-Referenz entspricht nicht der Konvention"
                )
        decided = _parse_iso(self.decided_at)
        if decided is None:
            raise ErasureLedgerError(CODE_INVALID_CHRONOLOGY, "decidedAt ist ungueltig")
        if self.status in APPLIED_STATUSES:
            applied = _parse_iso(self.applied_at)
            if applied is None:
                raise ErasureLedgerError(CODE_INVALID_CHRONOLOGY, "appliedAt fehlt")
            if applied < decided:
                raise ErasureLedgerError(CODE_INVALID_CHRONOLOGY, "appliedAt liegt vor decidedAt")
        if self.status == STATUS_COMPLETED and self.failed_records > 0:
            raise ErasureLedgerError(CODE_INVALID_CHRONOLOGY, "COMPLETED mit failedRecords")
        if self.failed_records < 0 or self.deleted_records < 0:
            raise ErasureLedgerError(CODE_INVALID_CHRONOLOGY, "Negative Zaehler")
        expected = self.compute_integrity()
        if not hmac.compare_digest(expected, self.integrity_sha256):
            raise ErasureLedgerError(CODE_INTEGRITY_MISMATCH, "Event-Integritaet stimmt nicht")


# -- Ledger ---------------------------------------------------------------

@dataclass
class ErasureLedger:
    ledger_id: str
    source: str
    complete_history: bool
    covered_from: str
    covered_until: str
    events: Tuple[ErasureEvent, ...]
    schema_version: int = LEDGER_SCHEMA_VERSION
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "ledgerId": self.ledger_id,
            "source": self.source,
            "completeHistory": self.complete_history,
            "coveredFrom": self.covered_from,
            "coveredUntil": self.covered_until,
            "createdAt": self.created_at,
            "events": [event.to_dict() for event in self.events],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ErasureLedger":
        if not isinstance(data, dict):
            raise ErasureLedgerError(CODE_LEDGER_MISSING, "Ledger ist kein Objekt")
        version = data.get("schemaVersion")
        if version != LEDGER_SCHEMA_VERSION:
            raise ErasureLedgerError(
                CODE_SCHEMA_UNKNOWN, "Unbekannte Ledger-Schema-Version",
                details={"schemaVersion": version},
            )
        for name in ("ledgerId", "source", "coveredFrom", "coveredUntil"):
            if not data.get(name):
                raise ErasureLedgerError(CODE_MISSING_FIELD, f"{name} fehlt")
        if not isinstance(data.get("completeHistory"), bool):
            raise ErasureLedgerError(CODE_MISSING_FIELD, "completeHistory fehlt")
        raw_events = data.get("events")
        if not isinstance(raw_events, list):
            raise ErasureLedgerError(CODE_MISSING_FIELD, "events fehlen")

        events: List[ErasureEvent] = []
        by_id: Dict[str, ErasureEvent] = {}
        by_idempotency: Dict[str, ErasureEvent] = {}
        for raw in raw_events:
            event = ErasureEvent.from_dict(raw)
            existing = by_id.get(event.event_id)
            if existing is not None:
                if existing.compute_integrity() != event.compute_integrity():
                    raise ErasureLedgerError(
                        CODE_DUPLICATE_CONFLICT, "Event-ID mit widerspruechlichem Inhalt"
                    )
                continue
            other = by_idempotency.get(event.idempotency_key)
            if other is not None:
                if _canonical(other.semantic_payload()) != _canonical(event.semantic_payload()):
                    raise ErasureLedgerError(
                        CODE_DUPLICATE_CONFLICT, "Idempotenzschluessel mit widerspruechlichem Inhalt"
                    )
                continue
            by_id[event.event_id] = event
            by_idempotency[event.idempotency_key] = event
            events.append(event)

        covered_from = _parse_iso(data["coveredFrom"])
        covered_until = _parse_iso(data["coveredUntil"])
        if covered_from is None or covered_until is None or covered_from > covered_until:
            raise ErasureLedgerError(CODE_INVALID_CHRONOLOGY, "Ledger-Zeitfenster ist ungueltig")
        return cls(
            ledger_id=str(data["ledgerId"]),
            source=str(data["source"]),
            complete_history=bool(data["completeHistory"]),
            covered_from=_iso(covered_from),
            covered_until=_iso(covered_until),
            events=tuple(events),
            schema_version=version,
            created_at=str(data.get("createdAt") or ""),
        )


def load_ledger(data: Optional[Dict[str, Any]]) -> ErasureLedger:
    if data is None:
        raise ErasureLedgerError(CODE_LEDGER_MISSING, "Kein Ledger vorhanden")
    return ErasureLedger.from_dict(data)


# -- Restore-Kontext ------------------------------------------------------

@dataclass(frozen=True)
class RestoreContext:
    restore_table_name: str
    restore_table_arn: str
    aws_account: str
    region: str
    restore_at: str
    backup_created_at: str
    source_table_name: str = ""
    expected_restore_table_arn: Optional[str] = None

    @classmethod
    def create(
        cls,
        *,
        restore_table_name: str,
        restore_table_arn: str,
        aws_account: str,
        region: str,
        restore_at: Any,
        backup_created_at: Any,
        source_table_name: str = "",
        expected_restore_table_arn: Optional[str] = None,
    ) -> "RestoreContext":
        restore_dt = _parse_iso(restore_at)
        backup_dt = _parse_iso(backup_created_at)
        if restore_dt is None:
            raise ErasureLedgerError(CODE_RESTORE_TIME_MISSING, "Restore-Zeitpunkt fehlt")
        if backup_dt is None or backup_dt > restore_dt:
            raise ErasureLedgerError(CODE_INVALID_CHRONOLOGY, "Backup-Zeitpunkt ungueltig")
        parsed = _TABLE_ARN_RE.match(restore_table_arn or "")
        if not parsed:
            raise ErasureLedgerError(CODE_RESTORE_IDENTITY_MISMATCH, "Restore-Tabellen-ARN ungueltig")
        if parsed.group("account") != aws_account or parsed.group("region") != region:
            raise ErasureLedgerError(CODE_RESTORE_IDENTITY_MISMATCH, "Account/Region weicht ab")
        if parsed.group("table") != restore_table_name:
            raise ErasureLedgerError(CODE_RESTORE_IDENTITY_MISMATCH, "Tabellenname weicht ab")
        if expected_restore_table_arn and expected_restore_table_arn != restore_table_arn:
            raise ErasureLedgerError(CODE_RESTORE_IDENTITY_MISMATCH, "Erwartete ARN weicht ab")
        if "-restore-" not in restore_table_name:
            raise ErasureLedgerError(
                CODE_RESTORE_IDENTITY_MISMATCH, "Restore-Tabelle folgt nicht der Namenskonvention"
            )
        if source_table_name and not restore_table_name.startswith(f"{source_table_name}-restore-"):
            raise ErasureLedgerError(
                CODE_RESTORE_IDENTITY_MISMATCH, "Restore-Tabelle gehoert nicht zur Quelltabelle"
            )
        return cls(
            restore_table_name=restore_table_name,
            restore_table_arn=restore_table_arn,
            aws_account=aws_account,
            region=region,
            restore_at=_iso(restore_dt),
            backup_created_at=_iso(backup_dt),
            source_table_name=source_table_name,
            expected_restore_table_arn=expected_restore_table_arn,
        )


@dataclass(frozen=True)
class RestoredOrder:
    order_ref: str
    consumer_id: Optional[str]
    subject_ref: Optional[str]
    customer_anonymized: bool = False
    has_subject_link: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RestoredOrder":
        return cls(
            order_ref=str(data.get("orderRef", "")),
            consumer_id=data.get("consumerId"),
            subject_ref=data.get("subjectRef"),
            customer_anonymized=bool(data.get("customerAnonymized", False)),
            has_subject_link=bool(data.get("hasSubjectLink", True)),
        )


@dataclass(frozen=True)
class ReconcileAction:
    order_ref: str
    action: str
    consumer_id: str
    event_ids: Tuple[str, ...]
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "orderRef": self.order_ref,
            "action": self.action,
            "consumerId": self.consumer_id,
            "eventIds": list(self.event_ids),
            "reason": self.reason,
        }


@dataclass
class ReconciliationPlan:
    plan_status: str
    readiness_status: str
    execution_status: str
    cutover_status: str
    cutover_approved: bool
    restore_table_arn: Optional[str]
    restore_at: Optional[str]
    backup_created_at: Optional[str]
    ledger_id: Optional[str]
    ledger_source: Optional[str]
    actions: Tuple[ReconcileAction, ...] = ()
    conflicts: Tuple[str, ...] = ()
    blockers: Tuple[str, ...] = ()
    notes: Tuple[str, ...] = ()
    generated_at: str = ""
    schema_version: int = PLAN_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "planStatus": self.plan_status,
            "readinessStatus": self.readiness_status,
            "executionStatus": self.execution_status,
            "cutoverStatus": self.cutover_status,
            "cutoverApproved": False,
            "restoreTableArn": self.restore_table_arn,
            "restoreAt": self.restore_at,
            "backupCreatedAt": self.backup_created_at,
            "ledgerId": self.ledger_id,
            "ledgerSource": self.ledger_source,
            "actions": [action.to_dict() for action in self.actions],
            "conflicts": list(self.conflicts),
            "blockers": list(self.blockers),
            "notes": list(self.notes),
            "generatedAt": self.generated_at,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, ensure_ascii=False)


def _blocked_plan(
    *,
    code: str,
    message: str,
    restore: Optional[RestoreContext] = None,
    ledger: Optional[ErasureLedger] = None,
    conflicts: Sequence[str] = (),
    blockers: Sequence[str] = (),
    notes: Sequence[str] = (),
    now: Optional[datetime] = None,
) -> ReconciliationPlan:
    return ReconciliationPlan(
        plan_status=PLAN_BLOCKED,
        readiness_status=READINESS_BLOCKED,
        execution_status=EXECUTION_NOT_VERIFIED,
        cutover_status=CUTOVER_BLOCKED,
        cutover_approved=False,
        restore_table_arn=restore.restore_table_arn if restore else None,
        restore_at=restore.restore_at if restore else None,
        backup_created_at=restore.backup_created_at if restore else None,
        ledger_id=ledger.ledger_id if ledger else None,
        ledger_source=ledger.source if ledger else None,
        conflicts=tuple(conflicts),
        blockers=tuple(blockers) or (f"{code}: {message}",),
        notes=tuple(notes),
        generated_at=_iso(now or datetime.now(timezone.utc)),
    )


def _restore_context_error(restore: RestoreContext) -> Optional[Tuple[str, str]]:
    """Validiert auch manuell konstruierte RestoreContext-Objekte (fail-closed)."""
    restore_dt = _parse_iso(restore.restore_at)
    if restore_dt is None:
        return CODE_RESTORE_TIME_MISSING, "Restore-Zeitpunkt fehlt oder ist ungueltig"
    parsed = _TABLE_ARN_RE.match(restore.restore_table_arn or "")
    if not parsed:
        return CODE_RESTORE_IDENTITY_MISMATCH, "Restore-Tabellen-ARN ist ungueltig"
    if parsed.group("account") != restore.aws_account or parsed.group("region") != restore.region:
        return CODE_RESTORE_IDENTITY_MISMATCH, "Account/Region der Restore-Tabelle weicht ab"
    if parsed.group("table") != restore.restore_table_name:
        return CODE_RESTORE_IDENTITY_MISMATCH, "Restore-Tabellenname weicht ab"
    if "-restore-" not in restore.restore_table_name:
        return CODE_RESTORE_IDENTITY_MISMATCH, "Restore-Tabellenname folgt nicht der Konvention"
    if restore.source_table_name and not restore.restore_table_name.startswith(
        f"{restore.source_table_name}-restore-"
    ):
        return CODE_RESTORE_IDENTITY_MISMATCH, "Restore-Tabelle gehoert nicht zur Quelltabelle"
    backup_dt = _parse_iso(restore.backup_created_at)
    if backup_dt is None or backup_dt > restore_dt:
        return CODE_INVALID_CHRONOLOGY, "Backup-Zeitpunkt ist ungueltig"
    return None


def _coverage_ok(ledger: ErasureLedger, restore: RestoreContext) -> bool:
    restore_dt = _parse_iso(restore.restore_at)
    from_dt = _parse_iso(ledger.covered_from)
    until_dt = _parse_iso(ledger.covered_until)
    return (
        restore_dt is not None
        and from_dt is not None
        and until_dt is not None
        and from_dt <= restore_dt <= until_dt
    )


def plan_reconciliation(
    *,
    ledger_data: Optional[Dict[str, Any]],
    restore_context: RestoreContext,
    restored_orders: Iterable[RestoredOrder | Dict[str, Any]],
    now: Optional[datetime] = None,
) -> ReconciliationPlan:
    """Erzeugt einen Reconciliation-Plan; veraendert keine Daten.

    Fail-closed: fehlende/unvollstaendige/inkonsistente Historie blockiert.
    Ein PLAN_VERIFIED ist ausdruecklich kein Ausfuehrungs- oder Cutover-Nachweis.
    """
    context_error = _restore_context_error(restore_context)
    if context_error is not None:
        code, message = context_error
        return _blocked_plan(
            code=code, message=message, restore=restore_context, now=now,
        )
    try:
        ledger = load_ledger(ledger_data)
    except ErasureLedgerError as exc:
        return _blocked_plan(code=exc.code, message=exc.message, restore=restore_context, now=now)

    if not ledger.complete_history:
        return _blocked_plan(
            code=CODE_INCOMPLETE, message="Ledger-Historie ist unvollstaendig",
            restore=restore_context, ledger=ledger, now=now,
        )
    if not _coverage_ok(ledger, restore_context):
        return _blocked_plan(
            code=CODE_INCOMPLETE, message="Ledger deckt den Restore-Zeitpunkt nicht ab",
            restore=restore_context, ledger=ledger, now=now,
        )
    if not ledger.events:
        return _blocked_plan(
            code=CODE_NO_HISTORY, message="Leere Ledger-Historie ist kein Nachweis",
            restore=restore_context, ledger=ledger, now=now,
        )

    restored: List[RestoredOrder] = [
        item if isinstance(item, RestoredOrder) else RestoredOrder.from_dict(item)
        for item in restored_orders
    ]
    restored_by_ref = {item.order_ref: item for item in restored}

    blockers: List[str] = []
    conflicts: List[str] = []
    actions: List[ReconcileAction] = []
    notes: List[str] = []

    for item in restored:
        if not _ORDER_REF_RE.match(item.order_ref):
            blockers.append(f"{CODE_ORDER_KEY_UNKNOWN}: {item.order_ref}")
        if not item.consumer_id:
            blockers.append(f"{CODE_CONSUMER_UNKNOWN}: {item.order_ref}")

    pending: Dict[str, List[ErasureEvent]] = {}
    verified_events: Dict[str, List[ErasureEvent]] = {}

    for event in ledger.events:
        if event.status != STATUS_COMPLETED:
            blockers.append(
                f"{CODE_PARTIAL_APPLICATION}: event={event.event_id} status={event.status}"
            )
            continue
        applied = _parse_iso(event.applied_at)
        restore_dt = _parse_iso(restore_context.restore_at)
        if applied is None or restore_dt is None:
            blockers.append(f"{CODE_INVALID_CHRONOLOGY}: event={event.event_id}")
            continue
        # Gleichstand wird bewusst als "nach Restore" behandelt: erneutes
        # Anwenden ist idempotent und verhindert ein verpasstes Ereignis.
        target = pending if applied >= restore_dt else verified_events
        for order_ref in event.order_refs:
            target.setdefault(order_ref, []).append(event)

    # Ereignisse, die vor dem Restore-Zeitpunkt liegen, muessen im Restore
    # bereits sichtbar sein. Abweichungen werden nicht stillschweigend korrigiert.
    for order_ref, events in verified_events.items():
        item = restored_by_ref.get(order_ref)
        operations = {event.operation for event in events}
        if not item:
            if OP_RETAIN in operations or OP_ANONYMIZE in operations:
                conflicts.append(f"APPLIED_EVENT_BUT_ITEM_MISSING: {order_ref}")
            continue
        _check_scope_and_subject(item, events, order_ref, conflicts)
        if OP_ERASE in operations:
            conflicts.append(f"ERASE_APPLIED_BUT_ITEM_PRESENT: {order_ref}")
        if OP_ANONYMIZE in operations and (
            item.subject_ref is not None or item.has_subject_link or not item.customer_anonymized
        ):
            conflicts.append(f"ANONYMIZE_APPLIED_BUT_PII_PRESENT: {order_ref}")
        if OP_RETAIN in operations:
            notes.append(f"RETAIN_OBSERVED: {order_ref}")

    # Ereignisse nach dem Restore-Zeitpunkt: als Plan-Aktionen vormerken.
    for order_ref, events in pending.items():
        operations = {event.operation for event in events}
        if len(operations) > 1:
            conflicts.append(f"CONFLICTING_OPERATIONS: {order_ref}:{sorted(operations)}")
            continue
        operation = next(iter(operations))
        consumers = {event.consumer_id for event in events}
        if len(consumers) > 1:
            conflicts.append(f"CONFLICTING_CONSUMER_SCOPE: {order_ref}")
            continue
        subjects = {event.subject_ref for event in events}
        if len(subjects) > 1:
            conflicts.append(f"CONFLICTING_SUBJECT_SCOPE: {order_ref}")
            continue
        item = restored_by_ref.get(order_ref)
        if item:
            _check_scope_and_subject(item, events, order_ref, conflicts)
        if operation == OP_ERASE:
            actions.append(ReconcileAction(
                order_ref=order_ref, action=ACTION_DELETE, consumer_id=events[0].consumer_id,
                event_ids=tuple(event.event_id for event in events),
                reason="ERASE nach Restore-Zeitpunkt",
            ))
        elif operation == OP_ANONYMIZE:
            if item and item.customer_anonymized and not item.has_subject_link:
                notes.append(f"ALREADY_ANONYMIZED: {order_ref}")
            else:
                actions.append(ReconcileAction(
                    order_ref=order_ref, action=ACTION_ANONYMIZE, consumer_id=events[0].consumer_id,
                    event_ids=tuple(event.event_id for event in events),
                    reason="ANONYMIZE nach Restore-Zeitpunkt",
                ))
        elif operation == OP_RETAIN:
            actions.append(ReconcileAction(
                order_ref=order_ref, action=ACTION_RETAIN, consumer_id=events[0].consumer_id,
                event_ids=tuple(event.event_id for event in events),
                reason="RETAIN: keine Loeschung",
            ))

    if conflicts or blockers:
        return _blocked_plan(
            code=CODE_CONFLICTING_EVENTS if conflicts else CODE_ORDER_KEY_UNKNOWN,
            message="Reconciliation-Konflikte oder fehlende Voraussetzungen",
            restore=restore_context, ledger=ledger,
            conflicts=conflicts, blockers=blockers, notes=notes, now=now,
        )

    if not restored:
        notes.append("NO_RESTORED_ORDERS: keine automatische Freigabe")
        plan_status = PLAN_REVIEW_REQUIRED
    elif not actions:
        notes.append("NO_ACTIONS: keine automatische Freigabe")
        plan_status = PLAN_REVIEW_REQUIRED
    else:
        plan_status = PLAN_VERIFIED

    return ReconciliationPlan(
        plan_status=plan_status,
        readiness_status=READINESS_REVIEW_REQUIRED,
        execution_status=EXECUTION_NOT_VERIFIED,
        cutover_status=CUTOVER_BLOCKED,
        cutover_approved=False,
        restore_table_arn=restore_context.restore_table_arn,
        restore_at=restore_context.restore_at,
        backup_created_at=restore_context.backup_created_at,
        ledger_id=ledger.ledger_id,
        ledger_source=ledger.source,
        actions=tuple(actions),
        notes=tuple(notes),
        generated_at=_iso(now or datetime.now(timezone.utc)),
    )


def _check_scope_and_subject(
    item: RestoredOrder,
    events: Sequence[ErasureEvent],
    order_ref: str,
    conflicts: List[str],
) -> None:
    if not item.consumer_id:
        conflicts.append(f"CONSUMER_UNKNOWN: {order_ref}")
        return
    if any(event.consumer_id != item.consumer_id for event in events):
        conflicts.append(f"CONSUMER_SCOPE_MISMATCH: {order_ref}")
    subject_refs = {event.subject_ref for event in events}
    if any(event.operation == OP_ERASE for event in events):
        if item.subject_ref is None or not item.has_subject_link:
            conflicts.append(f"SUBJECT_REF_MISSING: {order_ref}")
        elif item.subject_ref not in subject_refs:
            conflicts.append(f"SUBJECT_REF_MISMATCH: {order_ref}")
    elif item.subject_ref is not None and item.subject_ref not in subject_refs:
        conflicts.append(f"SUBJECT_REF_MISMATCH: {order_ref}")


def build_privacy_readiness(plan: ReconciliationPlan) -> Dict[str, Any]:
    """OrderRestorePrivacyReadinessV1 — ohne P1-Gates zu veraendern."""
    status = READINESS_BLOCKED if plan.plan_status == PLAN_BLOCKED else READINESS_REVIEW_REQUIRED
    if plan.plan_status == PLAN_UNKNOWN:
        status = READINESS_UNKNOWN
    return {
        "schemaVersion": READINESS_SCHEMA_VERSION,
        "status": status,
        "planStatus": plan.plan_status,
        "executionStatus": EXECUTION_NOT_VERIFIED,
        "cutoverStatus": CUTOVER_BLOCKED,
        "cutoverApproved": False,
        "dataMigrationRequired": bool(plan.actions),
        "backupEvidence": "NOT_PROVIDED",
        "restorePrivacyReadiness": status,
        "blockers": list(plan.blockers),
        "conflicts": list(plan.conflicts),
        "actions": [action.to_dict() for action in plan.actions],
    }


def approve_cutover(plan: ReconciliationPlan) -> None:
    """Cutover bleibt bis zu einer separat nachgewiesenen Ausfuehrung gesperrt."""
    raise ErasureLedgerError(
        CODE_CUTOVER_BLOCKED,
        "Cutover kann ohne nachgewiesene Reconciliation-Ausfuehrung nicht freigegeben werden",
        details={
            "planStatus": plan.plan_status,
            "executionStatus": plan.execution_status,
            "cutoverStatus": plan.cutover_status,
        },
    )


def write_reconciliation_report(run_dir: str | Path, plan: ReconciliationPlan) -> Tuple[Path, Path]:
    target = Path(run_dir)
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / "order-restore-reconciliation.json"
    md_path = target / "order-restore-reconciliation.md"
    json_path.write_text(plan.to_json(), encoding="utf-8")
    md_path.write_text(_render_plan_md(plan), encoding="utf-8")
    return json_path, md_path


def _render_plan_md(plan: ReconciliationPlan) -> str:
    lines = [
        "# Order-Restore-Reconciliation (P3E-01)",
        "",
        f"**Plan:** `{plan.plan_status}`",
        f"**Readiness:** `{plan.readiness_status}`",
        f"**Execution:** `{plan.execution_status}`",
        f"**Cutover:** `{plan.cutover_status}`",
        "",
        "| Feld | Wert |",
        "|---|---|",
        f"| Restore-ARN | `{plan.restore_table_arn or '-'}` |",
        f"| Restore-Zeitpunkt | `{plan.restore_at or '-'}` |",
        f"| Backup-Zeitpunkt | `{plan.backup_created_at or '-'}` |",
        f"| Ledger | `{plan.ledger_id or '-'}` |",
        "",
        "## Aktionen (Plan, keine Ausfuehrung)",
        "",
    ]
    if plan.actions:
        lines.extend(
            f"- `{action.order_ref}`: **{action.action}** ({', '.join(action.event_ids)})"
            for action in plan.actions
        )
    else:
        lines.append("- keine")
    lines.extend(["", "## Blocker", ""])
    lines.extend(f"- {item}" for item in plan.blockers) if plan.blockers else lines.append("- keine")
    lines.extend(["", "## Konflikte", ""])
    lines.extend(f"- {item}" for item in plan.conflicts) if plan.conflicts else lines.append("- keine")
    lines.extend(["", "## Hinweise", ""])
    lines.extend(f"- {item}" for item in plan.notes) if plan.notes else lines.append("- keine")
    lines.append("")
    return "\n".join(lines)
