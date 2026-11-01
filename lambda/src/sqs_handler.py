"""SQS-Worker: kontrollierte Statusuebergaenge (MO-RC4-P02C).

Die Abschlussroutine `_process_order` ist die EINZIGE Stelle, an der der Worker
den Bestellstatus schreibt. Sie ist jetzt kollisionssicher:

- Der Uebergang wird weiterhin gegen die State Machine geprueft (state_machine).
- Geschrieben wird nur, wenn der Status noch dem gelesenen Ausgangsstatus
  entspricht (ConditionExpression). Zwei Worker koennen denselben Auftrag
  daher nicht doppelt bzw. widerspruechlich abschliessen.
- `version` wird atomar erhoeht (if_not_exists fuer Legacy-Items ohne Version).
- Owner-/Consumer-/Actor-Attribute werden nie beruehrt.
- ConditionalCheckFailed wird ausgewertet: bereits abgeschlossen (idempotent)
  vs. ueberholt (stale) vs. endgueltig abgelehnt (z. B. CANCELLED -> CONFIRMED).

Batch-Fehlerbehandlung: Der Handler meldet fehlgeschlagene Nachrichten einzeln
ueber `batchItemFailures` (Event-Source-Mapping: ReportBatchItemFailures), damit
erfolgreiche Nachrichten eines Batches nicht erneut zugestellt werden.
"""

import json
import os
from typing import Any, Dict, Optional

import boto3

from order_service import generate_order_id, is_conditional_check_failed, now_iso
from order_types import ORDER_ID_PREFIX, ORDER_SK
from state_machine import can_transition

_dynamodb_client = None
_sqs_client = None

# Reihenfolge des linearen Lebenszyklus (CANCELLED ist ein Sonder-Endzustand).
_STATUS_RANK = {
    "PENDING": 0,
    "CONFIRMED": 1,
    "PROCESSING": 2,
    "SHIPPED": 3,
    "DELIVERED": 4,
}

# Ergebnisse von _process_order
OUTCOME_PROCESSED = "processed"   # Uebergang erfolgreich geschrieben
OUTCOME_NOOP = "noop"             # Zielzustand war bereits erreicht -> idempotent
OUTCOME_STALE = "stale"           # Nachricht ueberholt (Bestellung weiter fortgeschritten)
OUTCOME_REJECTED = "rejected"     # Uebergang unzulaessig (z. B. CANCELLED -> CONFIRMED)
OUTCOME_MISSING = "missing"       # Bestellung existiert nicht (mehr)

_SUCCESS_OUTCOMES = (OUTCOME_PROCESSED, OUTCOME_NOOP, OUTCOME_STALE)


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
    """True, wenn die Bestellung bereits weiter ist als das Nachrichtenziel."""
    if current_status not in _STATUS_RANK or target_status not in _STATUS_RANK:
        return False
    return _STATUS_RANK[target_status] < _STATUS_RANK[current_status]


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
    """Bewertet ein ConditionalCheckFailed anhand des frisch gelesenen Zustands."""
    item = _read_item(dynamodb, table_name, order_id)
    if item is None:
        return OUTCOME_MISSING
    current = _current_status(item)
    if current == target_status:
        return OUTCOME_NOOP
    if _is_stale(current, target_status):
        return OUTCOME_STALE
    return OUTCOME_REJECTED


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
        except Exception as exc:  # technischer Fehler -> Nachricht erneut zustellen
            print(f"Worker: technical error for message {message_id}: {exc}")
            failed += 1
            batch_item_failures.append({"itemIdentifier": message_id})

    if failed and not any(entry.get("itemIdentifier") for entry in batch_item_failures):
        # Ohne messageId kann kein Einzelitem gemeldet werden -> Batch wiederholen.
        raise RuntimeError("Worker: batch failures without messageId; retrying batch")

    print(f"Worker batch done: processed={processed}, failed={failed}, total={len(records)}")
    return {"batchItemFailures": batch_item_failures}


def _process_order(order_id: str, status: str, payload: Dict[str, Any]) -> str:
    """Schliesst genau einen Auftrag ab (idempotent, kollisionssicher)."""
    table_name = _get_table_name()
    if not table_name:
        raise ValueError("ORDERS_TABLE environment variable not set")

    dynamodb = _get_dynamodb_client()

    item = _read_item(dynamodb, table_name, order_id)
    if item is None:
        print(f"Order not found for processing: {order_id}")
        return OUTCOME_MISSING

    current_status = _current_status(item)

    # Idempotenz: doppelte Nachricht / bereits abgeschlossen
    if current_status == status:
        print(f"Order {order_id} already in status {status} (idempotent)")
        return OUTCOME_NOOP

    if not can_transition(current_status, status):
        if _is_stale(current_status, status):
            print(f"Stale message for {order_id}: {current_status} is ahead of {status}")
            return OUTCOME_STALE
        print(f"Invalid transition: {current_status} -> {status}")
        return OUTCOME_REJECTED

    now = now_iso()
    try:
        dynamodb.update_item(
            TableName=table_name,
            Key={"pk": {"S": f"{ORDER_ID_PREFIX}{order_id}"}, "sk": {"S": ORDER_SK}},
            # Nur schreiben, wenn sich der Status seit dem Lesen nicht geaendert hat.
            # Verhindert Doppelabschluss und ueberschreibt niemals einen Cancel.
            ConditionExpression="attribute_exists(pk) AND #status = :currentStatus",
            # version wird atomar erhoeht; Legacy-Items ohne version starten bei 0.
            UpdateExpression=(
                "SET #status = :newStatus, updatedAt = :now, "
                "#version = if_not_exists(#version, :zero) + :one"
            ),
            ExpressionAttributeNames={"#status": "status", "#version": "version"},
            ExpressionAttributeValues={
                ":newStatus": {"S": status},
                ":currentStatus": {"S": current_status},
                ":now": {"S": now},
                ":zero": {"N": "0"},
                ":one": {"N": "1"},
            },
        )
    except Exception as err:
        if is_conditional_check_failed(err):
            outcome = _classify_after_conflict(dynamodb, table_name, order_id, status)
            print(
                f"Conditional update lost for {order_id} "
                f"(expected {current_status} -> {status}); classified as {outcome}"
            )
            return outcome
        raise

    print(f"Order {order_id} transitioned {current_status} -> {status}")
    return OUTCOME_PROCESSED
