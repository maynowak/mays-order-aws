"""SQS-Worker: Statusuebergaenge + Processing-Lifecycle (MO-RC4-P02C/P02E/P02G-B).

Zwei Handler-Klassen (siehe order_handlers.py):

- **Status-Handler** (`generic`): unveraendertes P02E-Verhalten — der Worker
  fuehrt nach der Handler-Ausfuehrung den Statusuebergang aus (P02C-Condition).

- **Processing-Handler** (`processing=True`): der Worker setzt vor der
  Ausfuehrung einen atomaren Claim (`processingState=running`,
  `processingAttemptId`, `processingClaimedAt`), ruft den Handler mit Kontext
  auf und uebernimmt das Ergebnis atomar:
      succeeded -> result + completedAt
      failed    -> processingError + completedAt
  Bedingungen schuetzen gegen konkurrierende Versuche, Storno, Anonymisierung
  (`attribute_exists(subjectId)`) und Doppelabschluss.

Idempotenzgrenzen:
- SQS: at-least-once.
- Claim: genau ein aktiver Versuch (Lease).
- Ergebnisuebernahme: genau einmal pro `processingAttemptId`.
- Fachliche Seiteneffekte: Verantwortung des Handlers (keine MO-Garantie).
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import boto3

from order_handlers import ProcessingFailure, get_handler_spec
from order_service import is_conditional_check_failed, now_iso
from order_types import DEFAULT_ORDER_TYPE, ORDER_ID_PREFIX, ORDER_SK
from processing_result import validate_processing_error, validate_processing_result
from state_machine import can_transition

_dynamodb_client = None
_sqs_client = None

# Processing-Lease: unterscheidet sich von SQS-Visibility (60 s) und der
# P02F-Delivery-Lease (300 s). Nur ein abgelaufener Claim darf neu versucht
# werden; die Anzahl der Versuche ist begrenzt.
PROCESSING_LEASE_SECONDS = 300
MAX_PROCESSING_ATTEMPTS = 2

_STATUS_RANK = {
    "PENDING": 0,
    "CONFIRMED": 1,
    "PROCESSING": 2,
    "SHIPPED": 3,
    "DELIVERED": 4,
}

# Outcomes
OUTCOME_PROCESSED = "processed"
OUTCOME_NOOP = "noop"
OUTCOME_STALE = "stale"
OUTCOME_REJECTED = "rejected"
OUTCOME_MISSING = "missing"
OUTCOME_UNKNOWN_TYPE = "unknown_type"
OUTCOME_HANDLER_FAILED = "handler_failed"

OUTCOME_PROCESSING_SUCCEEDED = "processing_succeeded"
OUTCOME_PROCESSING_FAILED = "processing_failed"
OUTCOME_PROCESSING_SKIPPED = "processing_skipped"
OUTCOME_PROCESSING_REJECTED = "processing_rejected"

# Alles, was die Nachricht als erledigt quittiert (kein Retry/DLQ).
_SUCCESS_OUTCOMES = (
    OUTCOME_PROCESSED,
    OUTCOME_NOOP,
    OUTCOME_STALE,
    OUTCOME_PROCESSING_SUCCEEDED,
    OUTCOME_PROCESSING_FAILED,
    OUTCOME_PROCESSING_SKIPPED,
    OUTCOME_PROCESSING_REJECTED,
)

_PROCESSING_SUCCEEDED = "succeeded"
_PROCESSING_FAILED = "failed"
_PROCESSING_RUNNING = "running"
_PROCESSING_PENDING = "pending"


def _get_dynamodb_client():
    global _dynamodb_client
    if _dynamodb_client is None:
        _dynamodb_client = boto3.client(
            "dynamodb", region_name=os.environ.get("AWS_REGION", "eu-central-1")
        )
    return _dynamodb_client


def _get_sqs_client():
    global _sqs_client
    if _sqs_client is None:
        _sqs_client = boto3.client(
            "sqs", region_name=os.environ.get("AWS_REGION", "eu-central-1")
        )
    return _sqs_client


def _get_table_name():
    return os.environ.get("ORDERS_TABLE")


def _current_status(item: Dict[str, Any]) -> str:
    return item.get("status", {}).get("S", "PENDING")


def _is_stale(current_status: str, target_status: str) -> bool:
    if current_status not in _STATUS_RANK or target_status not in _STATUS_RANK:
        return False
    return _STATUS_RANK[target_status] < _STATUS_RANK[current_status]


def _resolve_order_type(item: Dict[str, Any]) -> str:
    raw = item.get("orderType")
    if raw is None:
        return DEFAULT_ORDER_TYPE
    value = raw.get("S") if isinstance(raw, dict) else raw
    if not isinstance(value, str):
        return ""
    return value.strip()


def _read_item(dynamodb, table_name: str, order_id: str) -> Optional[Dict[str, Any]]:
    result = dynamodb.get_item(
        TableName=table_name,
        ConsistentRead=True,
        Key={"pk": {"S": f"{ORDER_ID_PREFIX}{order_id}"}, "sk": {"S": ORDER_SK}},
    )
    return result.get("Item")


def _classify_after_conflict(
    dynamodb, table_name: str, order_id: str, target_status: str
) -> str:
    item = _read_item(dynamodb, table_name, order_id)
    if item is None:
        return OUTCOME_MISSING
    current = _current_status(item)
    if current == target_status:
        return OUTCOME_NOOP
    if _is_stale(current, target_status):
        return OUTCOME_STALE
    return OUTCOME_REJECTED


def _iso(moment: datetime) -> str:
    return f"{moment:%Y-%m-%dT%H:%M:%S}.{moment.microsecond // 1000:03d}Z"


def _lease_expiry_text(now: datetime) -> str:
    return _iso(now - timedelta(seconds=PROCESSING_LEASE_SECONDS))


def _processing_state(item: Dict[str, Any]) -> Optional[str]:
    value = item.get("processingState")
    return value.get("S") if isinstance(value, dict) else value


def _order_version(item: Dict[str, Any]) -> Optional[int]:
    raw = item.get("version")
    if isinstance(raw, dict):
        raw = raw.get("N")
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    records = event.get("Records", [])
    batch_item_failures = []
    processed = 0
    failed = 0

    for record in records:
        message_id = record.get("messageId")
        try:
            body = record.get("body")
            if not body:
                print("Worker: message without body")
                failed += 1
                batch_item_failures.append({"itemIdentifier": message_id})
                continue

            try:
                message = json.loads(body)
            except (ValueError, TypeError) as exc:
                print(f"Worker: unparseable message ({exc})")
                failed += 1
                batch_item_failures.append({"itemIdentifier": message_id})
                continue

            order_id = message.get("orderId")
            status = message.get("status")
            payload = message.get("payload", {})
            if not order_id or not status:
                print("Worker: invalid message format (missing orderId or status)")
                failed += 1
                batch_item_failures.append({"itemIdentifier": message_id})
                continue

            print(f"Worker processing: order_id={order_id}, status={status}")
            outcome = _process_order(order_id, status, payload)
            if outcome in _SUCCESS_OUTCOMES:
                processed += 1
            else:
                failed += 1
                batch_item_failures.append({"itemIdentifier": message_id})
        except Exception as exc:
            print(f"Worker: technical error for message {message_id}: {exc}")
            failed += 1
            batch_item_failures.append({"itemIdentifier": message_id})

    if failed and not any(entry.get("itemIdentifier") for entry in batch_item_failures):
        raise RuntimeError("Worker: batch failures without messageId; retrying batch")

    print(f"Worker batch done: processed={processed}, failed={failed}, total={len(records)}")
    return {"batchItemFailures": batch_item_failures}


# ---------------------------------------------------------------------------
# Status-Pfad (unveraendert zu P02E/P02C)
# ---------------------------------------------------------------------------

def _apply_status_transition(
    dynamodb, table_name: str, order_id: str, item: Dict[str, Any], status: str
) -> Optional[str]:
    """Fuehrt den Statusuebergang aus. None = erfolgreich (oder bereits erreicht)."""
    current_status = _current_status(item)
    if current_status == status:
        return None
    if not can_transition(current_status, status):
        if _is_stale(current_status, status):
            print(f"Stale message for {order_id}: {current_status} is ahead of {status}")
            return OUTCOME_STALE
        print(f"Invalid transition: {current_status} -> {status}")
        return OUTCOME_REJECTED

    try:
        dynamodb.update_item(
            TableName=table_name,
            Key={"pk": {"S": f"{ORDER_ID_PREFIX}{order_id}"}, "sk": {"S": ORDER_SK}},
            ConditionExpression="attribute_exists(pk) AND #status = :currentStatus",
            UpdateExpression=(
                "SET #status = :newStatus, updatedAt = :now, "
                "#version = if_not_exists(#version, :zero) + :one"
            ),
            ExpressionAttributeNames={"#status": "status", "#version": "version"},
            ExpressionAttributeValues={
                ":newStatus": {"S": status},
                ":currentStatus": {"S": current_status},
                ":now": {"S": now_iso()},
                ":zero": {"N": "0"},
                ":one": {"N": "1"},
            },
        )
    except Exception as err:
        if is_conditional_check_failed(err):
            outcome = _classify_after_conflict(dynamodb, table_name, order_id, status)
            print(f"Conditional update lost for {order_id}; classified as {outcome}")
            return outcome
        raise
    print(f"Order {order_id} transitioned {current_status} -> {status}")
    return None


# ---------------------------------------------------------------------------
# Processing-Pfad (P02G-B)
# ---------------------------------------------------------------------------

def _claim_processing(dynamodb, table_name: str, order_id: str, item: Dict[str, Any]) -> Optional[str]:
    """Setzt den Processing-Claim atomar. Rueckgabe: attemptId oder None."""
    attempt_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    now_text = _iso(now)

    condition = (
        "attribute_exists(pk) AND attribute_exists(subjectId) AND #status <> :cancelled "
        "AND (attribute_not_exists(processingState) "
        "     OR processingState = :pending "
        "     OR (processingState = :running "
        "         AND (attribute_not_exists(processingClaimedAt) "
        "              OR processingClaimedAt < :leaseExpiry))) "
        "AND (attribute_not_exists(processingAttempts) OR processingAttempts < :maxAttempts) "
        "AND ((attribute_not_exists(#version)) OR #version = :version)"
    )
    values = {
        ":cancelled": {"S": "CANCELLED"},
        ":pending": {"S": _PROCESSING_PENDING},
        ":running": {"S": _PROCESSING_RUNNING},
        ":now": {"S": now_text},
        ":leaseExpiry": {"S": _lease_expiry_text(now)},
        ":attempt": {"S": attempt_id},
        ":maxAttempts": {"N": str(MAX_PROCESSING_ATTEMPTS)},
        ":zero": {"N": "0"},
        ":one": {"N": "1"},
    }
    version = _order_version(item)
    if version is not None:
        values[":version"] = {"N": str(version)}

    try:
        dynamodb.update_item(
            TableName=table_name,
            Key={"pk": {"S": f"{ORDER_ID_PREFIX}{order_id}"}, "sk": {"S": ORDER_SK}},
            ConditionExpression=condition,
            UpdateExpression=(
                "SET processingState = :running, processingAttemptId = :attempt, "
                "processingClaimedAt = :now, "
                "processingAttempts = if_not_exists(processingAttempts, :zero) + :one"
            ),
            ExpressionAttributeNames={"#status": "status", "#version": "version"},
            ExpressionAttributeValues=values,
        )
    except Exception as err:
        if is_conditional_check_failed(err):
            return None
        raise
    return attempt_id


def _classify_claim_failure(dynamodb, table_name: str, order_id: str) -> str:
    item = _read_item(dynamodb, table_name, order_id)
    if item is None:
        return OUTCOME_MISSING
    if _current_status(item) == "CANCELLED":
        return OUTCOME_PROCESSING_REJECTED
    if item.get("subjectId") is None:
        # Anonymisiert: kein neuer Processing-Versuch
        return OUTCOME_PROCESSING_REJECTED
    state = _processing_state(item)
    if state in (_PROCESSING_SUCCEEDED, _PROCESSING_FAILED, _PROCESSING_RUNNING):
        # bereits abgeschlossen / anderer Versuch aktiv / terminal fehlgeschlagen
        return OUTCOME_PROCESSING_SKIPPED
    # Versuchsbudget erschoepft oder Zustaendigkeit unklar
    return OUTCOME_PROCESSING_SKIPPED


def _complete_processing(
    dynamodb,
    table_name: str,
    order_id: str,
    attempt_id: str,
    *,
    success: bool,
    result: Any = None,
    error: Optional[Dict[str, Any]] = None,
) -> str:
    now_text = now_iso()
    if success:
        update = (
            "SET processingState = :succeeded, #result = :result, "
            "completedAt = :now, updatedAt = :now, "
            "#version = if_not_exists(#version, :zero) + :one "
            "REMOVE processingError, processingClaimedAt"
        )
        names = {"#result": "result", "#version": "version"}
        values = {
            ":succeeded": {"S": _PROCESSING_SUCCEEDED},
            ":result": _to_dynamodb(result),
            ":now": {"S": now_text},
            ":zero": {"N": "0"},
            ":one": {"N": "1"},
        }
    else:
        update = (
            "SET processingState = :failed, processingError = :error, "
            "completedAt = :now, updatedAt = :now, "
            "#version = if_not_exists(#version, :zero) + :one "
            "REMOVE #result, processingClaimedAt"
        )
        names = {"#result": "result", "#version": "version"}
        values = {
            ":failed": {"S": _PROCESSING_FAILED},
            ":error": _to_dynamodb(error or {}),
            ":now": {"S": now_text},
            ":zero": {"N": "0"},
            ":one": {"N": "1"},
        }

    try:
        dynamodb.update_item(
            TableName=table_name,
            Key={"pk": {"S": f"{ORDER_ID_PREFIX}{order_id}"}, "sk": {"S": ORDER_SK}},
            # Datenschutz-Guard IM SELBEN Update: anonymisierte Orders
            # (subjectId entfernt) koennen kein Ergebnis mehr erhalten.
            ConditionExpression=(
                "attribute_exists(pk) AND attribute_exists(subjectId) "
                "AND #status <> :cancelled "
                "AND processingState = :running "
                "AND processingAttemptId = :attempt"
            ),
            UpdateExpression=update,
            ExpressionAttributeNames={**names, "#status": "status"},
            ExpressionAttributeValues={
                **values,
                ":cancelled": {"S": "CANCELLED"},
                ":running": {"S": _PROCESSING_RUNNING},
                ":attempt": {"S": attempt_id},
            },
        )
    except Exception as err:
        if is_conditional_check_failed(err):
            return _classify_completion_failure(dynamodb, table_name, order_id)
        raise

    print(f"Order {order_id} processing {'succeeded' if success else 'failed'} (attempt {attempt_id})")
    return OUTCOME_PROCESSING_SUCCEEDED if success else OUTCOME_PROCESSING_FAILED


def _classify_completion_failure(dynamodb, table_name: str, order_id: str) -> str:
    item = _read_item(dynamodb, table_name, order_id)
    if item is None:
        return OUTCOME_MISSING
    if item.get("subjectId") is None:
        print(f"Processing completion rejected for {order_id}: order anonymized")
        return OUTCOME_PROCESSING_REJECTED
    if _current_status(item) == "CANCELLED":
        print(f"Processing completion rejected for {order_id}: order cancelled")
        return OUTCOME_PROCESSING_REJECTED
    if _processing_state(item) == _PROCESSING_SUCCEEDED:
        return OUTCOME_NOOP
    print(f"Processing completion rejected for {order_id}: attempt/state conflict")
    return OUTCOME_PROCESSING_SKIPPED


def _release_claim(dynamodb, table_name: str, order_id: str, attempt_id: str) -> None:
    """Gibt den Claim nach einem technischen Fehler frei (begrenzter Retry)."""
    try:
        dynamodb.update_item(
            TableName=table_name,
            Key={"pk": {"S": f"{ORDER_ID_PREFIX}{order_id}"}, "sk": {"S": ORDER_SK}},
            ConditionExpression=(
                "processingState = :running AND processingAttemptId = :attempt"
            ),
            UpdateExpression="SET processingState = :pending REMOVE processingClaimedAt",
            ExpressionAttributeValues={
                ":running": {"S": _PROCESSING_RUNNING},
                ":pending": {"S": _PROCESSING_PENDING},
                ":attempt": {"S": attempt_id},
            },
        )
    except Exception as exc:
        print(f"Worker: could not release processing claim for {order_id}: {exc}")


def _to_dynamodb(value: Any) -> Dict[str, Any]:
    """Kleine JSON-Werte in DynamoDB-Attributform (Map/Liste/Skalar)."""
    if isinstance(value, dict):
        return {"M": {key: _to_dynamodb(entry) for key, entry in value.items()}}
    if isinstance(value, list):
        return {"L": [_to_dynamodb(entry) for entry in value]}
    if isinstance(value, str):
        return {"S": value}
    if isinstance(value, bool):
        return {"BOOL": value}
    if isinstance(value, (int, float)):
        return {"N": str(value)}
    if value is None:
        return {"NULL": True}
    raise TypeError(f"unsupported result value: {type(value).__name__}")


def _process_order(order_id: str, status: str, payload: Dict[str, Any]) -> str:
    table_name = _get_table_name()
    if not table_name:
        raise ValueError("ORDERS_TABLE environment variable not set")

    dynamodb = _get_dynamodb_client()

    item = _read_item(dynamodb, table_name, order_id)
    if item is None:
        print(f"Order not found for processing: {order_id}")
        return OUTCOME_MISSING

    order_type = _resolve_order_type(item)
    spec = get_handler_spec(order_type)
    if spec is None:
        print(f"Unknown orderType '{order_type}' for {order_id} (no handler registered)")
        return OUTCOME_UNKNOWN_TYPE

    # ---------- Status-Handler: bisheriges Verhalten unveraendert ----------
    # Reihenfolge wie P02E: Idempotenz -> Uebergangspruefung -> Handler ->
    # bedingtes Statusupdate. Ein Handler-Fehler hinterlaesst KEINEN Statuswrite.
    if not spec.processing:
        current_status = _current_status(item)
        if current_status == status:
            print(f"Order {order_id} already in status {status} (idempotent)")
            return OUTCOME_NOOP
        if not can_transition(current_status, status):
            if _is_stale(current_status, status):
                print(f"Stale message for {order_id}: {current_status} is ahead of {status}")
                return OUTCOME_STALE
            print(f"Invalid transition: {current_status} -> {status}")
            return OUTCOME_REJECTED
        try:
            spec.handler(item, payload)
        except Exception as exc:
            print(f"Handler for orderType '{order_type}' failed for {order_id}: {exc}")
            return OUTCOME_HANDLER_FAILED
        outcome = _apply_status_transition(dynamodb, table_name, order_id, item, status)
        return OUTCOME_PROCESSED if outcome is None else outcome

    # ---------- Processing-Handler ----------
    if _processing_state(item) == _PROCESSING_SUCCEEDED:
        print(f"Order {order_id} processing already succeeded (idempotent)")
        return OUTCOME_NOOP

    outcome = _apply_status_transition(dynamodb, table_name, order_id, item, status)
    # NOOP = Zielstatus bereits erreicht (z. B. durch parallelen Worker) -> mit
    # der fachlichen Verarbeitung fortfahren; andere Ergebnisse brechen ab.
    if outcome is not None and outcome != OUTCOME_NOOP:
        return outcome

    # Nach dem Statuswechsel frisch lesen (Version/State fuer den Claim).
    item = _read_item(dynamodb, table_name, order_id)
    if item is None:
        return OUTCOME_MISSING
    if _processing_state(item) == _PROCESSING_SUCCEEDED:
        return OUTCOME_NOOP

    attempt_id = _claim_processing(dynamodb, table_name, order_id, item)
    if attempt_id is None:
        return _classify_claim_failure(dynamodb, table_name, order_id)

    context = {"attemptId": attempt_id, "orderType": order_type}
    try:
        result = spec.handler(item, payload, context)
    except ProcessingFailure as failure:
        try:
            error = validate_processing_error({"code": failure.code, "message": failure.message})
        except Exception:
            error = {"code": "PROCESSING_FAILED", "message": "controlled processing failure"}
        return _complete_processing(
            dynamodb, table_name, order_id, attempt_id, success=False, error=error
        )
    except Exception as exc:
        # Technischer Fehler: Claim freigeben, Nachricht erneut zustellen.
        print(f"Processing handler for '{order_type}' failed technically for {order_id}: {exc}")
        _release_claim(dynamodb, table_name, order_id, attempt_id)
        raise

    # Vertrag: Handler liefern das Ergebnis direkt; das im Auftrag gezeigte
    # Format {"result": ...} wird ebenfalls akzeptiert (einzelner Wrapper-Key).
    if isinstance(result, dict) and set(result.keys()) == {"result"}:
        result = result["result"]

    try:
        validate_processing_result(result)
    except Exception as exc:
        print(f"Invalid processing result for {order_id}: {exc}")
        _release_claim(dynamodb, table_name, order_id, attempt_id)
        return OUTCOME_HANDLER_FAILED

    return _complete_processing(
        dynamodb, table_name, order_id, attempt_id, success=True, result=result
    )
