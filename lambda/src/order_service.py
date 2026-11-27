from __future__ import annotations

import base64
import json
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from errors import conflicted_update, invalid_transition, json_default, order_not_found, validation_error
from processing_result import (
    FIELD_PROCESSING_ATTEMPT_ID,
    FIELD_PROCESSING_ERROR,
    FIELD_PROCESSING_STATE,
    FIELD_RESULT,
    PROCESSING_FIELDS,
    processing_summary,
)
from identity import (
    IDENTITY_ITEM_FIELDS,
    OwnerIdentity,
    OrderIdentity,
    OWNER_TYPE_USER,
    authorize_order_access,
    item_in_privacy_scope,
    privacy_scope_consumer,
)
from state_machine import can_transition
from order_types import GSI1_PK, GSI2_NAME, GSI2_PK_PREFIX, ORDER_ID_PREFIX, ORDER_SK, TABLE_INDEX_NAME
from secret_provider import (
    SecretProvider,
    SecretProviderError,
    configured_provider_name,
    get_default_secret_provider,
    log_secret_provider_failure,
)
from validation import validate_create_order
from agent_order import ORDER_TYPE_AGENT, fingerprint as agent_order_fingerprint, validate_agent_order
from dispatch import DispatchRejected, build_dispatch_envelope, new_work_id
from result_envelope import ORDER_RESULT, ResultRejected

# version = Optimistic-Locking-Feld (intern); isTestData = reiner Seed-Marker,
# darf in API-Antworten niemals auftauchen (nur Demo-Seed setzt es).
INTERNAL_FIELDS = {
    "pk", "sk", "gsi1pk", "gsi1sk", "gsi2pk", "gsi2sk", "version", "isTestData", "subjectId",
    "agentOrder", "agentOrderFingerprint", "expectedWorkId", "dispatch",
    "resultMessageId", "resultIdempotencyKey", "resultWorkId", "resultAttempt",
    "processing",
} | set(IDENTITY_ITEM_FIELDS) | set(PROCESSING_FIELDS)

# MO-RC4-P02: Eigentuemer-Identitaet ist Pflicht. Der Wert stammt aus dem
# verifizierten JWT-Kontext (index.extract_subject_id) und wird hier erneut
# geprueft (Defense in Depth, damit kein interner Aufruf ohne Eigentuemer
# durchkommt).
MAX_SUBJECT_ID_LENGTH = 256

# Schutz vor unbegrenzten Query-Schleifen bei starker Filterung (P02H-A).
MAX_LIST_PAGES = 10

# MO-RC4-P02F: Zustellzustand (additiv, KEIN fachlicher Order-Status).
DELIVERY_PENDING = "pending"
DELIVERY_SENDING = "sending"
DELIVERY_SENT = "sent"
DELIVERY_FAILED = "failed"
DELIVERY_STATES = (DELIVERY_PENDING, DELIVERY_SENDING, DELIVERY_SENT, DELIVERY_FAILED)


def _require_valid_subject_id(subject_id: Any) -> str:
    if not isinstance(subject_id, str):
        raise validation_error("Missing order owner identity")
    candidate = subject_id.strip()
    if not candidate or len(candidate) > MAX_SUBJECT_ID_LENGTH:
        raise validation_error("Invalid order owner identity")
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in candidate):
        raise validation_error("Invalid order owner identity")
    return candidate

_dynamodb_resource = None


def _get_dynamodb_resource():
    """Boto3-Ressource lazy erzeugen und über Warm-Starts hinweg wiederverwenden.

    Der Import von boto3 erfolgt bewusst erst hier (Lambda-Runtime stellt boto3
    bereit; die Unit-Tests injizieren einen Fake-Client und brauchen boto3 nicht).
    """
    global _dynamodb_resource
    if _dynamodb_resource is None:
        import boto3  # type: ignore[reportMissingImports]  # von der Lambda-Runtime bereitgestellt, lokal nicht installiert

        _dynamodb_resource = boto3.resource(
            "dynamodb", region_name=os.environ.get("AWS_REGION", "eu-central-1")
        )
    return _dynamodb_resource


def generate_order_id() -> str:
    return f"{ORDER_ID_PREFIX}{secrets.token_hex(12)}"


def now_iso() -> str:
    now = datetime.now(timezone.utc)
    return f"{now:%Y-%m-%dT%H:%M:%S}.{now.microsecond // 1000:03d}Z"


def to_public_order(item: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in item.items() if key not in INTERNAL_FIELDS}


def to_public_agent_order(value: Any) -> Dict[str, Any]:
    """Fail-closed owner projection; metadata references and execution internals stay private."""
    try:
        agent_order = validate_agent_order(value)
    except Exception:
        return {}
    metadata = agent_order.get("metadata", {})
    return {
        "schemaVersion": agent_order["schemaVersion"],
        "target": agent_order["target"],
        "input": agent_order["input"],
        "metadata": {
            key: metadata[key]
            for key in ("source", "requestId")
            if metadata.get(key) is not None
        },
        "resultContract": agent_order["resultContract"],
    }


def to_public_processing(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result: Dict[str, Any] = {}
    for key in ("status", "attempt", "completedAt"):
        if value.get(key) is not None:
            result[key] = value[key]
    if isinstance(value.get("result"), dict):
        result["result"] = value["result"]
    error = value.get("error")
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        result["error"] = {"message": error["message"][:500]}
    return result


def to_list_item(item: Dict[str, Any]) -> Dict[str, Any]:
    if item.get("orderType") == ORDER_TYPE_AGENT:
        return {
            "orderId": item["orderId"],
            "orderType": item["orderType"],
            "status": item["status"],
            "createdAt": item["createdAt"],
            "updatedAt": item["updatedAt"],
        }
    return {
        "orderId": item["orderId"],
        "status": item["status"],
        "customer": {"name": item["customer"]["name"]},
        "totalAmount": item["totalAmount"],
        "createdAt": item["createdAt"],
        "updatedAt": item["updatedAt"],
    }


def encode_next_token(last_evaluated_key: Optional[Dict[str, Any]]) -> Optional[str]:
    if not last_evaluated_key:
        return None
    raw = json.dumps(last_evaluated_key, separators=(",", ":"), default=json_default)
    return base64.b64encode(raw.encode("utf-8")).decode("utf-8")


def decode_next_token(next_token: str) -> Dict[str, Any]:
    try:
        raw = base64.b64decode(next_token.encode("utf-8")).decode("utf-8")
        parsed: Any = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("not an object")
        return parsed
    except Exception as exc:
        raise validation_error(
            "Query parameter 'nextToken' is not a valid pagination token",
            {"path": "nextToken"},
        ) from exc


def is_client_error(err: Any, code: str) -> bool:
    return hasattr(err, "response") and err.response.get("Error", {}).get("Code") == code


def is_conditional_check_failed(err: Any) -> bool:
    return is_client_error(err, "ConditionalCheckFailedException")


def is_validation_exception(err: Any) -> bool:
    return is_client_error(err, "ValidationException")


MAX_INTERNAL_TOKEN_LENGTH = 1024


def _constant_time_token_match(token: Any, secret: Any) -> bool:
    """Compare internal tokens without leaking a Python TypeError.

    Python's compare_digest rejects non-ASCII strings. Provider material may
    come from Secrets Manager, so the boundary must fail closed instead of
    allowing an unhandled TypeError to become HTTP 500.
    """
    try:
        token_text = str(token)
        secret_text = str(secret)
    except Exception:
        return False
    if not token_text or not secret_text:
        return False
    if len(token_text) > MAX_INTERNAL_TOKEN_LENGTH:
        return False
    if len(secret_text) > MAX_INTERNAL_TOKEN_LENGTH:
        return False
    if not token_text.isascii() or not secret_text.isascii():
        return False
    try:
        return secrets.compare_digest(token_text, secret_text)
    except (TypeError, ValueError):
        return False


class OrderService:
    def __init__(
        self,
        table_name: str,
        client: Any = None,
        secret_provider: Optional[SecretProvider] = None,
    ) -> None:
        self._table_name = table_name
        self._table = client if client is not None else _get_dynamodb_resource().Table(table_name)
        self._secret_provider = secret_provider

    def _resolve_privacy_secret(self) -> str:
        """Resolve the internal privacy secret through the process-wide provider.

        Provider selection comes only from configuration, never from request
        data. The default provider/cache survives multiple invocations in the
        same Lambda execution environment; injected providers remain scoped to
        their service instance. Provider errors map to the fail-closed 400 path.
        """
        try:
            provider = self._secret_provider
            if provider is None:
                provider = get_default_secret_provider()
                self._secret_provider = provider
            material = provider.resolve()
        except SecretProviderError as exc:
            log_secret_provider_failure(exc, configured_provider_name())
            raise validation_error(exc.public_message) from None
        if not material.value:
            raise validation_error("Internal secret not configured")
        return material.value

    def _require_privacy_auth(self, context: Optional[Dict[str, Any]], permission: str) -> None:
        if not context or not context.get("project"):
            raise validation_error("Missing project context")
        expected_project = os.environ.get("ORDERS_PROJECT_NAME")
        if not expected_project:
            raise validation_error("Project not configured")
        if context.get("project") != expected_project:
            raise validation_error("Project mismatch")
        if not context.get("authorized"):
            raise validation_error("Unauthorized privacy operation")
        if not context.get(permission):
            raise validation_error(f"Missing permission {permission}")
        # Internal trust boundary: secret must be configured and token must match.
        # The provider remains ENV by default; no request field can select it.
        internal_secret = self._resolve_privacy_secret()
        token = context.get("internal_token")
        if not token:
            raise validation_error("Internal token missing")
        # Use the existing constant-time privacy contract, with a fail-closed
        # ASCII/length guard for provider-supplied material.
        if not _constant_time_token_match(token, internal_secret):
            raise validation_error("Internal trust boundary violation")

    def create_order(
        self,
        raw_body: Any,
        subject_id: Optional[str] = None,
        identity: Optional[OrderIdentity] = None,
    ) -> Dict[str, Any]:
        # MO-RC4-P02: Jede Bestellung gehoert genau einem verifizierten Benutzer.
        # Der Body kann die Zuordnung nicht setzen (validate_create_order lehnt
        # Fremdfelder wie "subjectId" mit 400 ab).
        # MO-RC4-P02A: Aufgeloeste Identitaet (Consumer/Owner/Actor) ist optional
        # additiv; ohne sie bleibt der P02-Vertrag (nur subjectId) gueltig.
        identity_fields: Dict[str, Any] = {}
        # Compatibility for internal Mays/RIS application harnesses. The HTTP
        # handler never accepts this object from a request; it resolves JWT
        # claims itself and supplies the canonical OrderIdentity explicitly.
        if isinstance(subject_id, OwnerIdentity) and identity is None:
            identity = subject_id
            subject_id = identity.owner_id
        if identity is not None:
            if identity.owner_type != OWNER_TYPE_USER:
                raise validation_error(
                    f"Unsupported order owner type '{identity.owner_type}'"
                )
            if subject_id is not None and subject_id != identity.owner_id:
                raise validation_error("Order owner identity mismatch")
            subject_id = identity.owner_id
            identity_fields = identity.to_item_fields()
        subject_id = _require_valid_subject_id(subject_id)
        input_data = validate_create_order(raw_body)
        now = now_iso()
        order_id = generate_order_id()

        if input_data.get("orderType") == ORDER_TYPE_AGENT:
            agent_order = input_data["agentOrder"]
            item: Dict[str, Any] = {
                "pk": f"{ORDER_ID_PREFIX}{order_id}",
                "sk": ORDER_SK,
                "orderId": order_id,
                "status": "PENDING",
                "orderType": ORDER_TYPE_AGENT,
                "agentOrder": agent_order,
                "agentOrderFingerprint": agent_order_fingerprint(agent_order),
                "createdAt": now,
                "updatedAt": now,
                "version": 1,
                "gsi1pk": GSI1_PK,
                "gsi1sk": now,
                "deliveryState": DELIVERY_PENDING,
                "subjectId": subject_id,
                "gsi2pk": f"{GSI2_PK_PREFIX}{subject_id}",
                "gsi2sk": f"{ORDER_ID_PREFIX}{order_id}#{now}",
            }
            # RIS OrderV1 carries Agent Order V1 in orderDescription alongside
            # its customer/items/currency envelope. Preserve those validated
            # OrderV1 fields while retaining the parsed canonical agent body.
            if "customer" in input_data:
                stored_items = [
                    {**line, "lineTotal": line["quantity"] * line["unitPrice"]}
                    for line in input_data["items"]
                ]
                item.update({
                    "customer": input_data["customer"],
                    "items": stored_items,
                    "currency": input_data["currency"],
                    "totalAmount": sum(line["lineTotal"] for line in stored_items),
                    "orderDescription": input_data["orderDescription"],
                })
            if identity_fields:
                item.update(identity_fields)
            self._table.put_item(Item=item)
            return to_public_order(item)

        items = [
            {**item, "lineTotal": item["quantity"] * item["unitPrice"]}
            for item in input_data["items"]
        ]
        total_amount = sum(item["lineTotal"] for item in items)

        item: Dict[str, Any] = {
            "pk": f"{ORDER_ID_PREFIX}{order_id}",
            "sk": ORDER_SK,
            "orderId": order_id,
            "status": "PENDING",
            # MO-RC4-P02E: fachlicher Verarbeitungstyp (Default "generic").
            "orderType": input_data["orderType"],
            "customer": input_data["customer"],
            "items": items,
            "currency": input_data["currency"],
            "totalAmount": total_amount,
            "createdAt": now,
            "updatedAt": now,
            "version": 1,
            "gsi1pk": GSI1_PK,
            "gsi1sk": now,
            # Zustellung ist von der fachlichen Verarbeitung getrennt.
            "deliveryState": DELIVERY_PENDING,
        }
        if "orderDescription" in input_data:
            item["orderDescription"] = input_data["orderDescription"]

        # Ownership ist ab MO-RC4-P02 garantiert (siehe oben) und wird dauerhaft
        # gespeichert; GSI2 macht die Bestellung fuer Privacy-Lookups auffindbar.
        item["subjectId"] = subject_id
        item["gsi2pk"] = f"{GSI2_PK_PREFIX}{subject_id}"
        item["gsi2sk"] = f"{ORDER_ID_PREFIX}{order_id}#{now}"
        # P02A: Consumer-/Owner-/Actor-Trennung (nur bei aufgeloester Identitaet).
        # subjectId und GSI2 bleiben unveraendert -> Privacy-Abfragen bleiben gueltig.
        if identity_fields:
            item.update(identity_fields)

        self._table.put_item(Item=item)

        return to_public_order(item)

    def mark_delivery_state(self, order_id: str, state: str) -> None:
        """Setzt den Zustellzustand nach einem Sendeversuch (MO-RC4-P02F).

        Bewusst OHNE Bedingung: Der Aufrufer besitzt in diesem Moment keinen
        Lease-Anspruch (POST-Pfad). Der Recovery-Pfad nutzt eigene Claims.
        Ein Fehler hier darf die API-Antwort nicht veraendern (Aufrufer faengt).
        """
        if state not in DELIVERY_STATES:
            raise validation_error(f"Invalid delivery state '{state}'")
        self._table.update_item(
            Key={"pk": f"{ORDER_ID_PREFIX}{order_id}", "sk": ORDER_SK},
            UpdateExpression=(
                "SET deliveryState = :state, lastDeliveryAt = :now, "
                "deliveryAttempts = if_not_exists(deliveryAttempts, :zero) + :one"
            ),
            ExpressionAttributeValues={":state": state, ":now": now_iso(), ":zero": 0, ":one": 1},
        )

    def _get_raw_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Vollstaendiges Order-Item (ConsistentRead), ohne Autorisierung."""
        key = {"pk": f"{ORDER_ID_PREFIX}{order_id}", "sk": ORDER_SK}
        try:
            result = self._table.get_item(Key=key, ConsistentRead=True)
        except TypeError as exc:
            # Lightweight in-memory contract tables may implement only the
            # DynamoDB-compatible required Key argument. Real DynamoDB always
            # accepts ConsistentRead; fall back only for that signature mismatch.
            if "ConsistentRead" not in str(exc):
                raise
            result = self._table.get_item(Key=key)
        return result.get("Item")

    def prepare_dispatch(self, order_id: str, identity: OrderIdentity) -> Dict[str, Any]:
        """Return the single server-bound work identity for an owned agent order."""
        item = self._get_raw_order(order_id)
        if item is None or not authorize_order_access(item, identity):
            raise order_not_found(order_id)
        if item.get("orderType") != ORDER_TYPE_AGENT:
            raise DispatchRejected("not_agent_order", "Order is not an agent execution order")
        if item.get("status") == "CANCELLED":
            raise DispatchRejected("order_cancelled", "Cancelled orders are not dispatched")
        if not item.get("agentOrderFingerprint"):
            raise DispatchRejected("fingerprint_missing", "Order has no execution fingerprint")
        if item.get("agentOrderFingerprint") != agent_order_fingerprint(item.get("agentOrder", {})):
            raise DispatchRejected("fingerprint_mismatch", "Stored agent order changed")
        existing_work_id = item.get("expectedWorkId")
        if existing_work_id:
            return {"orderId": order_id, "workId": existing_work_id, "reused": True,
                    "dispatchStatus": (item.get("dispatch") or {}).get("status")}
        work_id = new_work_id()
        now = now_iso()
        try:
            self._table.update_item(
                Key={"pk": f"{ORDER_ID_PREFIX}{order_id}", "sk": ORDER_SK},
                UpdateExpression="SET expectedWorkId = :w, #d = :d, updatedAt = :u",
                ConditionExpression="attribute_exists(pk) AND attribute_not_exists(expectedWorkId)",
                ExpressionAttributeNames={"#d": "dispatch"},
                ExpressionAttributeValues={":w": work_id, ":d": {"status": "PENDING", "boundAt": now}, ":u": now},
            )
        except Exception as err:
            if is_conditional_check_failed(err):
                refreshed = self._get_raw_order(order_id) or {}
                bound = refreshed.get("expectedWorkId")
                if bound:
                    return {"orderId": order_id, "workId": bound, "reused": True,
                            "dispatchStatus": (refreshed.get("dispatch") or {}).get("status")}
                raise DispatchRejected("dispatch_bind_failed", "Work id could not be bound") from err
            raise
        return {"orderId": order_id, "workId": work_id, "reused": False,
                "dispatchStatus": "PENDING"}

    def dispatch_envelope(self, order_id: str, work_id: str) -> Dict[str, Any]:
        item = self._get_raw_order(order_id)
        if item is None:
            raise order_not_found(order_id)
        if item.get("expectedWorkId") != work_id:
            raise DispatchRejected("work_mismatch", "Work id is not bound to this order")
        return build_dispatch_envelope(item, work_id)

    def mark_dispatch_sent(self, order_id: str, work_id: str, message_id: str) -> Dict[str, Any]:
        item = self._get_raw_order(order_id)
        if item is None:
            raise order_not_found(order_id)
        if item.get("expectedWorkId") != work_id:
            raise DispatchRejected("work_mismatch", "Work id is not bound to this order")
        current = item.get("dispatch") or {}
        if current.get("status") == "SENT":
            if current.get("messageId") == message_id:
                return dict(current)
            raise DispatchRejected("dispatch_conflict", "Order was already dispatched")
        record = {"status": "SENT", "messageId": message_id, "sentAt": now_iso()}
        self._table.update_item(
            Key={"pk": f"{ORDER_ID_PREFIX}{order_id}", "sk": ORDER_SK},
            UpdateExpression="SET #d = :d, updatedAt = :u",
            ConditionExpression="attribute_exists(pk) AND expectedWorkId = :w",
            ExpressionAttributeNames={"#d": "dispatch"},
            ExpressionAttributeValues={":d": record, ":u": now_iso(), ":w": work_id},
        )
        return record

    def apply_result(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a signed, schema-validated result only to its bound order."""
        order_id = envelope["orderId"]
        item = self._get_raw_order(order_id)
        if item is None:
            raise order_not_found(order_id)
        if item.get("orderType") != ORDER_TYPE_AGENT:
            raise ResultRejected("not_agent_order", "Order is not an agent execution order")
        if item.get("status") == "CANCELLED":
            raise ResultRejected("order_cancelled", "Cancelled orders cannot accept a result")
        expected_correlation = (item.get("agentOrder", {}).get("metadata", {})
                                .get("requestId"))
        if not expected_correlation:
            raise ResultRejected("missing_correlation", "Order has no correlation reference")
        if expected_correlation != envelope["correlationId"]:
            raise ResultRejected("correlation_mismatch", "Result does not belong to this order")
        execution = envelope["execution"]
        if item.get("expectedWorkId") != execution["workId"]:
            raise ResultRejected("work_mismatch", "Result work id is not bound to this order")
        attempt = execution["attempt"]
        existing = item.get("processing")
        if isinstance(existing, dict) and existing.get("status") in ("COMPLETED", "FAILED"):
            if existing.get("idempotencyKey") == envelope["idempotencyKey"]:
                if existing.get("executionId") and execution.get("executionId") != existing.get("executionId"):
                    raise ResultRejected("execution_mismatch", "Execution id differs on duplicate result")
                return dict(existing)
            raise ResultRejected("already_finalised", "Order already has a terminal result")
        if isinstance(existing, dict) and int(existing.get("attempt") or 0) > attempt:
            raise ResultRejected("stale_attempt", "A newer result attempt is already stored")
        from processing_result import validate_processing_result
        succeeded = envelope["messageType"] == ORDER_RESULT
        payload = validate_processing_result(envelope["payload"] if succeeded else None)
        error = None if succeeded else envelope["payload"].get("error", {"message": "Agent execution failed"})
        now = now_iso()
        record: Dict[str, Any] = {
            "schemaVersion": "1.0", "status": "COMPLETED" if succeeded else "FAILED",
            "attempt": attempt, "workId": execution["workId"],
            "idempotencyKey": envelope["idempotencyKey"],
            "messageId": envelope["messageId"], "completedAt": now,
        }
        if execution.get("executionId"):
            record["executionId"] = execution["executionId"]
        if succeeded:
            record["result"] = payload
        elif isinstance(error, dict):
            record["error"] = error
        else:
            record["error"] = {"message": "Agent execution failed"}
        values = {":p": record, ":u": now, ":one": 1, ":w": execution["workId"]}
        if error is not None:
            values[":error"] = error
        try:
            self._table.update_item(
                Key={"pk": f"{ORDER_ID_PREFIX}{order_id}", "sk": ORDER_SK},
                UpdateExpression="SET #p = :p, updatedAt = :u, #v = #v + :one",
                ConditionExpression="attribute_exists(pk) AND attribute_not_exists(#p) AND expectedWorkId = :w",
                ExpressionAttributeNames={"#p": "processing", "#v": "version"},
                ExpressionAttributeValues=values,
            )
        except Exception as err:
            if is_conditional_check_failed(err):
                refreshed = self._get_raw_order(order_id) or {}
                current = refreshed.get("processing") or {}
                if current.get("idempotencyKey") == envelope["idempotencyKey"]:
                    return dict(current)
                raise ResultRejected("concurrent_result", "A conflicting result won the write") from err
            raise
        return record

    def get_order(self, order_id: str, identity: OrderIdentity) -> Dict[str, Any]:
        """Liest eine Order nur bei passender Owner- UND Consumer-Identitaet.

        Fremde und Legacy-Orders ohne vollstaendige Identitaet liefern 404
        (keine Existenzoffenlegung).
        """
        item = self._get_raw_order(order_id)
        if item is None or not authorize_order_access(item, identity):
            raise order_not_found(order_id)
        public = to_public_order(item)
        if item.get("orderType") == ORDER_TYPE_AGENT and isinstance(item.get("agentOrder"), dict):
            public["agentOrder"] = to_public_agent_order(item["agentOrder"])
        if isinstance(item.get("processing"), dict):
            public["processing"] = to_public_processing(item["processing"])
        return public

    def list_orders(
        self,
        limit: int,
        next_token: Optional[str] = None,
        *,
        identity: OrderIdentity,
    ) -> Dict[str, Any]:
        """Listet ausschliesslich Orders des verifizierten Owners+Consumers.

        GSI2 partitioniert nach `SUBJECT#<subjectId>`; da der Index `consumerId`
        nicht projiziert, wird jedes Item vollstaendig geladen und gefiltert
        (P02G-A-Muster). Der Cursor ist ein GSI2-`LastEvaluatedKey`.
        """
        last_key = decode_next_token(next_token) if next_token else None
        collected: List[Dict[str, Any]] = []
        seen = set()
        pages = 0

        try:
            while len(collected) < limit and pages < MAX_LIST_PAGES:
                pages += 1
                query_kwargs: Dict[str, Any] = {
                    "IndexName": GSI2_NAME,
                    "KeyConditionExpression": "gsi2pk = :pk",
                    "ExpressionAttributeValues": {
                        ":pk": f"{GSI2_PK_PREFIX}{identity.owner_id}"
                    },
                    # Nur projizierte Attribute anfragen (P02G-A-Befund).
                    "ProjectionExpression": "orderId",
                    "ScanIndexForward": False,
                    "Limit": limit,
                }
                if last_key:
                    query_kwargs["ExclusiveStartKey"] = last_key
                result = self._table.query(**query_kwargs)

                for entry in result.get("Items", []):
                    order_id = entry.get("orderId")
                    if not order_id or order_id in seen:
                        continue
                    seen.add(order_id)
                    item = self._load_order_item(order_id)
                    if item is None or not authorize_order_access(item, identity):
                        continue
                    collected.append(item)
                    if len(collected) >= limit:
                        break

                last_key = result.get("LastEvaluatedKey")
                if not last_key:
                    break
        except Exception as err:
            if is_validation_exception(err):
                # z. B. alter GSI1-Cursor, der zu GSI2 nicht passt
                raise validation_error(
                    "Invalid pagination token or query",
                    {"path": "nextToken"},
                ) from err
            raise

        collected.sort(key=lambda entry: entry.get("createdAt", ""), reverse=True)
        orders = [to_list_item(item) for item in collected]

        response: Dict[str, Any] = {"orders": orders, "count": len(orders)}
        encoded = encode_next_token(last_key)
        if encoded:
            response["nextToken"] = encoded
        return response

    def update_order_status(
        self, order_id: str, status: str, *, identity: OrderIdentity
    ) -> Dict[str, Any]:
        """Aendert den Status nur bei passender Owner- UND Consumer-Identitaet.

        Die Autorisierung ist Teil DERSELBEN Conditional-Expression wie Status
        und Version (kein TOCTOU, kein ungeschuetzter Fallback-Write).
        """
        item = self._get_raw_order(order_id)
        if item is None or not authorize_order_access(item, identity):
            raise order_not_found(order_id)

        current_status = item.get("status")
        if not can_transition(current_status, status):
            raise invalid_transition(current_status, status)

        try:
            result = self._table.update_item(
                Key={"pk": f"{ORDER_ID_PREFIX}{order_id}", "sk": ORDER_SK},
                UpdateExpression=(
                    "SET #status = :newStatus, updatedAt = :now, "
                    "#version = if_not_exists(#version, :zero) + :one"
                ),
                ConditionExpression=(
                    "attribute_exists(pk) AND #status = :currentStatus "
                    "AND #subjectId = :owner AND #consumerId = :consumer"
                ),
                ExpressionAttributeNames={
                    "#status": "status",
                    "#version": "version",
                    "#subjectId": "subjectId",
                    "#consumerId": "consumerId",
                },
                ExpressionAttributeValues={
                    ":newStatus": status,
                    ":currentStatus": current_status,
                    ":owner": identity.owner_id,
                    ":consumer": identity.consumer_id,
                    ":now": now_iso(),
                    ":zero": 0,
                    ":one": 1,
                },
                ReturnValues="ALL_NEW",
            )
            return to_public_order(result["Attributes"])
        except Exception as err:
            if is_conditional_check_failed(err):
                fresh = self._get_raw_order(order_id)
                # Kein Fallback-Write: fremd/verschwunden -> 404, sonst 409.
                if fresh is None or not authorize_order_access(fresh, identity):
                    raise order_not_found(order_id) from err
                raise conflicted_update() from err
            raise

    def _load_order_item(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Laedt das vollstaendige Order-Item (ConsistentRead).

        GSI2 projiziert nur einen Teil der Attribute (kein `consumerId`, keine
        Verarbeitungsfelder). Eine Query mit nicht projizierten Feldern wuerde
        in DynamoDB fehlschlagen; deshalb wird nach der Query je Order geladen.
        """
        result = self._table.get_item(
            Key={"pk": f"{ORDER_ID_PREFIX}{order_id}", "sk": ORDER_SK},
            ConsistentRead=True,
        )
        return result.get("Item")

    def inspect_subject(self, subject_id: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._require_privacy_auth(context, "privacy_inspect")

        if not subject_id or not isinstance(subject_id, str):
            raise validation_error("Invalid subjectId")

        # Query GSI2 for orders linked to subject (vollstaendig paginiert:
        # MO-RC4-P02 — ein Benutzer kann mehr Bestellungen haben als eine
        # DynamoDB-Seite (1 MB) zurueckgibt).
        scope = privacy_scope_consumer(context)
        items = []
        last_evaluated_key = None
        try:
            while True:
                query_kwargs: Dict[str, Any] = {
                    "IndexName": GSI2_NAME,
                    "KeyConditionExpression": "gsi2pk = :pk",
                    "ExpressionAttributeValues": {":pk": f"{GSI2_PK_PREFIX}{subject_id}"},
                    # Nur projizierte Attribute anfragen (GSI2 kennt die
                    # Verarbeitungsfelder nicht) und je Order vollstaendig laden.
                    "ProjectionExpression": "orderId",
                }
                if last_evaluated_key:
                    query_kwargs["ExclusiveStartKey"] = last_evaluated_key
                result = self._table.query(**query_kwargs)
                for entry in result.get("Items", []):
                    order_id = entry.get("orderId")
                    if not order_id:
                        continue
                    item = self._load_order_item(order_id)
                    if item is None:
                        continue
                    if not item_in_privacy_scope(item, scope):
                        continue
                    items.append(item)
                last_evaluated_key = result.get("LastEvaluatedKey")
                if not last_evaluated_key:
                    break
        except Exception:
            # Technical failure must not be reported as successful empty result
            return {
                "subjectId": subject_id,
                "status": "BLOCKED",
                "affectedRecords": 0,
                "orderReferences": [],
                "dataCategories": [],
                "limitations": ["GSI2 query failed"],
            }
        order_refs = []
        for item in items:
            oid = item.get("orderId")
            if oid:
                order_refs.append(oid)

        data_categories = []
        if any("orderDescription" in entry for entry in items):
            data_categories.append("orderDescription")
        if items:
            # Determine which personal data fields exist in first item
            cust = items[0].get("customer", {})
            if isinstance(cust, dict):
                if "name" in cust:
                    data_categories.append("customer.name")
                if "email" in cust:
                    data_categories.append("customer.email")

        # MO-RC4-P02G-A: datensparsame Kennzeichnung, KEINE Ergebnisinhalte.
        summary = processing_summary(items)
        if summary["hasProcessingResult"]:
            data_categories.append("processing.result")
        if summary["hasProcessingError"]:
            data_categories.append("processing.error")

        return {
            "subjectId": subject_id,
            "status": "COMPLETED",
            "affectedRecords": len(order_refs),
            "orderReferences": order_refs,
            "dataCategories": data_categories,
            "hasProcessingResult": summary["hasProcessingResult"],
            "hasProcessingError": summary["hasProcessingError"],
            "processingStates": summary["processingStates"],
            "limitations": [],
        }

    def export_subject(self, subject_id: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._require_privacy_auth(context, "privacy_export")

        if not subject_id or not isinstance(subject_id, str):
            raise validation_error("Invalid subjectId")

        operation_id = str(uuid.uuid4())
        scope = privacy_scope_consumer(context)
        orders = []
        last_evaluated_key = None
        limitations = []
        # Pagination loop
        try:
            while True:
                query_kwargs = {
                    "IndexName": GSI2_NAME,
                    "KeyConditionExpression": "gsi2pk = :pk",
                    "ExpressionAttributeValues": {":pk": f"{GSI2_PK_PREFIX}{subject_id}"},
                    # Nur projizierte Attribute anfragen; Details je Order laden.
                    "ProjectionExpression": "orderId",
                }
                if last_evaluated_key:
                    query_kwargs["ExclusiveStartKey"] = last_evaluated_key
                result = self._table.query(**query_kwargs)
                for entry in result.get("Items", []):
                    order_id = entry.get("orderId")
                    if not order_id:
                        continue
                    item = self._load_order_item(order_id)
                    if item is None:
                        continue
                    if not item_in_privacy_scope(item, scope):
                        continue
                    # Build minimal export view, exclude internal fields
                    export_item = {
                        "orderId": item.get("orderId"),
                        "status": item.get("status"),
                        "createdAt": item.get("createdAt"),
                        "customer": {
                            "name": item.get("customer", {}).get("name"),
                            "email": item.get("customer", {}).get("email"),
                        },
                    }
                    # Optional fields
                    if "totalAmount" in item:
                        export_item["totalAmount"] = item["totalAmount"]
                    if "currency" in item:
                        export_item["currency"] = item["currency"]
                    if "orderDescription" in item:
                        export_item["orderDescription"] = item["orderDescription"]
                    # MO-RC4-P02G-A: Ergebnis-/Verarbeitungsfelder vollstaendig
                    # in die Auskunft aufnehmen (nur vorhandene Felder).
                    for field in (
                        FIELD_PROCESSING_STATE,
                        FIELD_PROCESSING_ATTEMPT_ID,
                        FIELD_RESULT,
                        "completedAt",
                        FIELD_PROCESSING_ERROR,
                    ):
                        if field in item:
                            export_item[field] = item[field]
                    if isinstance(item.get("processing"), dict):
                        export_item["processing"] = to_public_processing(item["processing"])
                    if item.get("orderType") == ORDER_TYPE_AGENT:
                        export_item["orderType"] = ORDER_TYPE_AGENT
                        export_item["agentOrder"] = to_public_agent_order(item.get("agentOrder"))
                    orders.append(export_item)
                last_evaluated_key = result.get("LastEvaluatedKey")
                if not last_evaluated_key:
                    break
        except Exception as err:
            # Technical failure must be explicit, do not return partial data as complete
            return {
                "schemaVersion": "1.0",
                "operationId": operation_id,
                "subjectId": subject_id,
                "status": "BLOCKED",
                "exportedAt": now_iso(),
                "recordCount": 0,
                "orders": [],
                "limitations": ["GSI2 query failed"],
            }

        return {
            "schemaVersion": "1.0",
            "operationId": operation_id,
            "subjectId": subject_id,
            "status": "COMPLETED" if not limitations else "PARTIALLY_COMPLETED",
            "exportedAt": now_iso(),
            "recordCount": len(orders),
            "orders": orders,
            "limitations": limitations,
        }

    def erase_subject(self, subject_id: str, context: Optional[Dict[str, Any]] = None, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._require_privacy_auth(context, "privacy_erase")

        if not subject_id or not isinstance(subject_id, str):
            raise validation_error("Invalid subjectId")

        opts = options or {}
        mode = opts.get("mode", "PREVIEW").upper()
        policy = opts.get("policy")
        if policy:
            policy = policy.upper()
        else:
            policy = None

        if mode not in ("PREVIEW", "EXECUTE"):
            raise validation_error("Invalid mode")
        if policy and policy not in ("ERASE", "ANONYMIZE", "RETAIN"):
            raise validation_error("Invalid policy")

        operation_id = str(uuid.uuid4())
        affected = []
        last_evaluated_key = None

        # Collect items via GSI2
        try:
            while True:
                query_kwargs = {
                    "IndexName": GSI2_NAME,
                    "KeyConditionExpression": "gsi2pk = :pk",
                    "ExpressionAttributeValues": {":pk": f"{GSI2_PK_PREFIX}{subject_id}"},
                    # consumerId is not projected by GSI2. Only the orderId is
                    # read from the index; the complete item (including
                    # consumerId/version) is loaded consistently below before
                    # the optional consumer-scope filter is applied.
                    "ProjectionExpression": "orderId",
                }
                if last_evaluated_key:
                    query_kwargs["ExclusiveStartKey"] = last_evaluated_key
                result = self._table.query(**query_kwargs)
                items = result.get("Items", [])
                for entry in items:
                    order_id = entry.get("orderId")
                    if not order_id:
                        continue
                    item = self._load_order_item(order_id)
                    if item is None:
                        continue
                    affected.append({
                        "pk": item.get("pk"),
                        "sk": item.get("sk"),
                        "orderId": item.get("orderId"),
                        "subjectId": item.get("subjectId"),
                        "version": item.get("version"),
                        # P02B: fuer den optionalen Consumer-Scope-Filter
                        "consumerId": item.get("consumerId"),
                    })
                last_evaluated_key = result.get("LastEvaluatedKey")
                if not last_evaluated_key:
                    break
        except Exception:
            return {
                "operationId": operation_id,
                "subjectId": subject_id,
                "status": "BLOCKED",
                "affectedRecords": 0,
                "deletedRecords": 0,
                "anonymizedRecords": 0,
                "retainedRecords": 0,
                "failedRecords": 0,
                "limitations": ["GSI2 not available"],
                "completedAt": now_iso(),
            }

        scope = privacy_scope_consumer(context)
        if scope is not None:
            in_scope = [entry for entry in affected if item_in_privacy_scope(entry, scope)]
            excluded = len(affected) - len(in_scope)
            affected = in_scope
        else:
            excluded = 0
        scope_limitations = (
            [f"{excluded} record(s) outside consumer scope were not touched"]
            if excluded
            else []
        )

        if mode == "PREVIEW":
            planned_deletes = 0
            planned_retentions = 0
            if policy == "ERASE":
                planned_deletes = len(affected)
            elif policy == "ANONYMIZE":
                planned_deletes = 0  # anonymize counts separately
            elif policy == "RETAIN":
                planned_retentions = len(affected)
            return {
                "operationId": operation_id,
                "subjectId": subject_id,
                "status": "PREVIEW",
                "affectedRecords": len(affected),
                "plannedDeletes": planned_deletes if policy == "ERASE" else 0,
                "plannedAnonymizations": len(affected) if policy == "ANONYMIZE" else 0,
                "plannedRetentions": planned_retentions,
                "limitations": list(scope_limitations),
                "completedAt": now_iso(),
            }

        # EXECUTE mode - policy must be explicitly provided
        if not policy:
            return {
                "operationId": operation_id,
                "subjectId": subject_id,
                "status": "BLOCKED",
                "affectedRecords": len(affected),
                "deletedRecords": 0,
                "anonymizedRecords": 0,
                "retainedRecords": 0,
                "skippedRecords": 0,
                "failedRecords": 0,
                "limitations": ["Missing explicit retention policy"],
                "completedAt": now_iso(),
            }
        # EXECUTE mode
        deleted = 0
        anonymized = 0
        retained = 0
        failed = 0
        skipped = 0
        for item in affected:
            pk = item.get("pk")
            sk = item.get("sk")
            if not pk or not sk:
                failed += 1
                continue
            try:
                if policy == "RETAIN":
                    retained += 1
                    continue
                if policy == "ERASE":
                    version = item.get("version")
                    cond_values = {":sid": subject_id}
                    cond_expr = "subjectId = :sid"
                    if version is not None:
                        cond_values[":ver"] = version
                        cond_expr += " AND version = :ver"
                    self._table.delete_item(
                        Key={"pk": pk, "sk": sk},
                        ConditionExpression=cond_expr,
                        ExpressionAttributeValues=cond_values,
                    )
                    deleted += 1
                elif policy == "ANONYMIZE":
                    version = item.get("version")
                    cond_values = {":sid": subject_id}
                    cond_expr = "subjectId = :sid"
                    if version is not None:
                        cond_values[":ver"] = version
                        cond_expr += " AND version = :ver"
                    self._table.update_item(
                        Key={"pk": pk, "sk": sk},
                        UpdateExpression=(
                            "SET #c.#n = :anon, #c.#e = :anon_email "
                            "REMOVE subjectId, consumerId, ownerType, ownerId, actorType, "
                            "actorId, identityVersion, identityVerification, gsi2pk, gsi2sk, "
                            "#result, #perr, #patt, gsi3pk, gsi3sk, #desc, #processing, "
                            "#agent, #fingerprint, #work, #dispatch"
                        ),
                        ConditionExpression=cond_expr,
                        ExpressionAttributeNames={
                            "#c": "customer", "#n": "name", "#e": "email",
                            "#desc": "orderDescription",
                            "#processing": "processing",
                            "#agent": "agentOrder",
                            "#fingerprint": "agentOrderFingerprint",
                            "#work": "expectedWorkId",
                            "#dispatch": "dispatch",
                            # MO-RC4-P02G-A: Ergebnisse werden NICHT selektiv
                            # bereinigt, sondern vollstaendig entfernt.
                            "#result": "result",
                            "#perr": "processingError",
                            "#patt": "processingAttemptId",
                        },
                        ExpressionAttributeValues={":anon": "ANONYMIZED", ":anon_email": "anonymized@example.com", **cond_values},
                    )
                    anonymized += 1
            except Exception as err:
                # MO-RC4-P02: Idempotenz. Wurde der Datensatz zwischen Query und
                # Schreiboperation bereits geloescht oder parallel geaendert,
                # ist das KEIN Fehler — es wurde nichts Fremdes veraendert.
                # Der Aufruf bleibt gefahrlos wiederholbar.
                if is_conditional_check_failed(err):
                    skipped += 1
                else:
                    failed += 1

        status = "COMPLETED"
        if failed > 0 or retained > 0:
            status = "PARTIALLY_COMPLETED"

        return {
            "schemaVersion": "1.0",
            "operationId": operation_id,
            "subjectId": subject_id,
            "status": status,
            "affectedRecords": len(affected),
            "deletedRecords": deleted,
            "anonymizedRecords": anonymized,
            "retainedRecords": retained,
            "skippedRecords": skipped,
            "failedRecords": failed,
            "limitations": list(scope_limitations),
            "completedAt": now_iso(),
        }


def create_order_service(
    table_name: str,
    client: Any = None,
    secret_provider: Optional[SecretProvider] = None,
) -> OrderService:
    return OrderService(table_name, client, secret_provider=secret_provider)
