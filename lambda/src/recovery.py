"""MO-RC4-P02F — PENDING-Recovery fuer nicht zugestellte Orders.

Problem: `POST /orders` persistiert die Order (PENDING) und sendet danach die
SQS-Nachricht. Schlaegt der Versand fehl (oder stirbt der Prozess dazwischen),
bleibt eine PENDING-Order ohne Nachricht zurueck — bisher unentdeckt.

Loesung (ohne neue Tabelle/GSI):
- Zustellzustand am Order-Item (`deliveryState`, `deliveryAttempts`,
  `lastDeliveryAt`, `deliveryClaimedAt`) getrennt vom fachlichen Status.
- Kandidatensuche ueber GSI1 mit Zeitfenster (Range-Query auf `gsi1sk`,
  KEIN Full-Table-Scan).
- Bedingter Claim (Lease) verhindert parallele Doppelzustellung; der
  Status-Write bleibt beim Worker (P02C).
- Keine fachliche Verarbeitung hier: Recovery sendet nur an die bestehende
  SQS-Queue; der normale Worker verarbeitet.
- `deliveryState == "sent"` wird NIE erneut eingereiht (DLQ-Faelle bleiben
  Betriebssache; kein automatisches DLQ-Redrive).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional

from order_service import (
    DELIVERY_FAILED,
    DELIVERY_SENDING,
    DELIVERY_SENT,
    is_conditional_check_failed,
)
from order_types import GSI1_PK, ORDER_ID_PREFIX, ORDER_SK

RECOVERY_ACTION = "recovery/scan"

DEFAULT_WINDOW_MINUTES = 60
DEFAULT_LIMIT = 50
DEFAULT_MIN_AGE_SECONDS = 60
DEFAULT_LEASE_SECONDS = 300
MAX_LIMIT = 200
MAX_WINDOW_MINUTES = 24 * 60

GSI1_NAME = "gsi1"


def _fmt(moment: datetime) -> str:
    return f"{moment:%Y-%m-%dT%H:%M:%S}.{moment.microsecond // 1000:03d}Z"


def _parse_iso(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def run_recovery(
    table: Any,
    send_message: Callable[[str], None],
    *,
    now: Optional[datetime] = None,
    window_minutes: int = DEFAULT_WINDOW_MINUTES,
    limit: int = DEFAULT_LIMIT,
    min_age_seconds: int = DEFAULT_MIN_AGE_SECONDS,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> Dict[str, Any]:
    """Fuehrt einen begrenzten Recovery-Lauf aus und liefert einen Report.

    `send_message(order_id)` muss bei Fehlern eine Exception werfen.
    """
    now_dt = now or datetime.now(timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)

    window_minutes = _bounded_int(window_minutes, DEFAULT_WINDOW_MINUTES, 1, MAX_WINDOW_MINUTES)
    limit = _bounded_int(limit, DEFAULT_LIMIT, 1, MAX_LIMIT)
    min_age_seconds = _bounded_int(min_age_seconds, DEFAULT_MIN_AGE_SECONDS, 0, 24 * 3600)
    lease_seconds = _bounded_int(lease_seconds, DEFAULT_LEASE_SECONDS, 30, 3600)

    now_text = _fmt(now_dt)
    since_text = _fmt(now_dt - timedelta(minutes=window_minutes))
    lease_expiry = _fmt(now_dt - timedelta(seconds=lease_seconds))
    min_age_cutoff = now_dt - timedelta(seconds=min_age_seconds)

    report: Dict[str, Any] = {
        "status": "COMPLETED",
        "runId": str(uuid.uuid4()),
        "windowMinutes": window_minutes,
        "limit": limit,
        "scanned": 0,
        "candidates": 0,
        "claimed": 0,
        "sent": 0,
        "failed": 0,
        "uncertain": 0,
        "skipped": {},
    }
    skipped = report["skipped"]

    def skip(reason: str) -> None:
        skipped[reason] = skipped.get(reason, 0) + 1

    # ---------- 1) Kandidaten ueber GSI1 (Zeitfenster, paginiert) ----------
    order_ids = []
    start_key = None
    while len(order_ids) < limit:
        query_kwargs: Dict[str, Any] = {
            "IndexName": GSI1_NAME,
            "KeyConditionExpression": "gsi1pk = :list AND gsi1sk >= :since",
            "ExpressionAttributeValues": {":list": GSI1_PK, ":since": since_text},
            "ScanIndexForward": True,  # aelteste zuerst
            "Limit": max(limit, 25),
        }
        if start_key:
            query_kwargs["ExclusiveStartKey"] = start_key
        page = table.query(**query_kwargs)
        for raw in page.get("Items", []):
            report["scanned"] += 1
            if raw.get("status") != "PENDING":
                skip("not_pending")
                continue
            created = _parse_iso(raw.get("createdAt"))
            if created is not None and created > min_age_cutoff:
                skip("too_young")
                continue
            order_id = raw.get("orderId")
            if not order_id:
                skip("missing_order_id")
                continue
            order_ids.append(order_id)
            if len(order_ids) >= limit:
                break
        start_key = page.get("LastEvaluatedKey")
        if not start_key:
            break

    report["candidates"] = len(order_ids)

    # ---------- 2) Claim + Zustellung ----------
    for order_id in order_ids:
        try:
            item = table.get_item(
                Key={"pk": f"{ORDER_ID_PREFIX}{order_id}", "sk": ORDER_SK},
                ConsistentRead=True,
            ).get("Item")
        except Exception:
            skip("read_error")
            continue

        if item is None:
            skip("order_missing")
            continue
        if item.get("status") != "PENDING":
            skip("not_pending")
            continue
        if item.get("deliveryState") == DELIVERY_SENT:
            # Bereits zugestellt (ggf. in der DLQ) -> NICHT erneut einreihen.
            skip("already_sent")
            continue

        try:
            table.update_item(
                Key={"pk": f"{ORDER_ID_PREFIX}{order_id}", "sk": ORDER_SK},
                UpdateExpression=(
                    "SET deliveryState = :sending, deliveryClaimedAt = :now, "
                    "lastDeliveryAt = :now, "
                    "deliveryAttempts = if_not_exists(deliveryAttempts, :zero) + :one"
                ),
                ConditionExpression=(
                    "#status = :pending AND "
                    "(attribute_not_exists(deliveryClaimedAt) OR deliveryClaimedAt < :leaseExpiry) AND "
                    "(attribute_not_exists(deliveryState) OR deliveryState <> :sent)"
                ),
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":sending": DELIVERY_SENDING,
                    ":pending": "PENDING",
                    ":sent": DELIVERY_SENT,
                    ":now": now_text,
                    ":leaseExpiry": lease_expiry,
                    ":zero": 0,
                    ":one": 1,
                },
            )
        except Exception as err:
            if is_conditional_check_failed(err):
                skip("claimed_or_changed")
            else:
                skip("claim_error")
            continue

        report["claimed"] += 1

        try:
            send_message(order_id)
        except Exception:
            report["failed"] += 1
            try:
                table.update_item(
                    Key={"pk": f"{ORDER_ID_PREFIX}{order_id}", "sk": ORDER_SK},
                    UpdateExpression=(
                        "SET deliveryState = :failed, lastDeliveryAt = :now "
                        "REMOVE deliveryClaimedAt"
                    ),
                    ExpressionAttributeValues={
                        ":failed": DELIVERY_FAILED,
                        ":now": now_text,
                    },
                )
            except Exception:
                skip("mark_failed_error")
            continue

        report["sent"] += 1
        try:
            table.update_item(
                Key={"pk": f"{ORDER_ID_PREFIX}{order_id}", "sk": ORDER_SK},
                UpdateExpression="SET deliveryState = :sent, lastDeliveryAt = :now REMOVE deliveryClaimedAt",
                ConditionExpression="deliveryClaimedAt = :now",
                ExpressionAttributeValues={":sent": DELIVERY_SENT, ":now": now_text},
            )
        except Exception:
            # Nach erfolgreichem Send keine Bestaetigung schreibbar: Zustand
            # ungewiss. Die Nachricht ist raus; ein spaeterer Lauf darf nach
            # Lease-Ablauf erneut senden (Worker bleibt idempotent).
            report["uncertain"] += 1

    if report["failed"] and not report["sent"]:
        report["status"] = "PARTIALLY_COMPLETED"
    return report
