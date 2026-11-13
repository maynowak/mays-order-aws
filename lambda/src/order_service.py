from __future__ import annotations

import base64
import json
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from errors import conflicted_update, invalid_transition, json_default, order_not_found, service_unavailable, validation_error
from state_machine import can_transition
from order_types import GSI1_PK, GSI2_NAME, GSI2_PK_PREFIX, ORDER_ID_PREFIX, ORDER_SK, TABLE_INDEX_NAME
from validation import validate_create_order
from agent_order import ORDER_TYPE_AGENT, fingerprint as agent_order_fingerprint
from identity import OwnerIdentity
from result_envelope import ORDER_RESULT, ResultRejected

#: Dedicated ownership index. Deliberately separate from gsi1 (global list) and
#: gsi2 (privacy subject): ownership and privacy are different concerns.
OWNER_INDEX_NAME = "gsi3"
OWNER_INDEX_HASH_KEY = "gsi3pk"
OWNER_INDEX_RANGE_KEY = "gsi3sk"

# version = Optimistic-Locking-Feld (intern); isTestData = reiner Seed-Marker,
# darf in API-Antworten niemals auftauchen (nur Demo-Seed setzt es).
# agentOrder/agentOrderFingerprint sind fachlicher Bestandteil der Order, werden
# aber NICHT über öffentliche Read-/List-Antworten ausgegeben (A04.5: die
# Zielbasis hat noch keine verlässliche Eigentümerprüfung).
INTERNAL_FIELDS = {"pk", "sk", "gsi1pk", "gsi1sk", "gsi2pk", "gsi2sk", "version", "isTestData", "subjectId", "agentOrder", "agentOrderFingerprint",
                   # Ownership internals (MO-AGENT-ORDER-OWNERSHIP-02): identity
                   # bindings and index keys must never reach a client.
                   "ownerIssuer", "ownerSubject", "ownerKey", "ownerClientId",
                   "actorType", "actorId", "gsi3pk", "gsi3sk"}

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


#: Fields of ``agentOrder`` that may be shown to the verified owner.
#: Everything else stays internal by omission, not by blacklist: a new field in
#: the stored body is simply not projected until it is explicitly released here.
PUBLIC_AGENT_ORDER_METADATA = ("source", "requestId")


def to_public_agent_order(agent_order: Any) -> Dict[str, Any]:
    """Owner-facing projection of one agent order.

    Released: target, fachliche input, the two non-identifying metadata
    references, and the result contract.

    Withheld: ``processing`` (technical execution state), ``metadata``
    identity references (``partnerApplicationRef``, ``apiProfileRef``) and
    ``idempotencyKey``. Reading an order does not grant access to identity or
    processing internals.
    """
    if not isinstance(agent_order, dict):
        return {}

    # Only a body that still satisfies the V1 contract is projected. A tampered
    # or drifted stored body is withheld entirely instead of being forwarded
    # unvalidated (no unknown fields, no credential-shaped content).
    from agent_order import AgentOrderValidationError, validate_agent_order

    try:
        agent_order = validate_agent_order(agent_order)
    except AgentOrderValidationError:
        return {}

    target = agent_order.get("target") if isinstance(
        agent_order.get("target"), dict) else {}
    raw_input = agent_order.get("input") if isinstance(
        agent_order.get("input"), dict) else {}
    metadata = agent_order.get("metadata") if isinstance(
        agent_order.get("metadata"), dict) else {}
    contract = agent_order.get("resultContract") if isinstance(
        agent_order.get("resultContract"), dict) else {}

    projected = {
        "schemaVersion": agent_order.get("schemaVersion"),
        "target": {
            "agentId": target.get("agentId"),
            "capability": target.get("capability"),
            "agentVersion": target.get("agentVersion"),
        },
        "input": {
            "schemaVersion": raw_input.get("schemaVersion"),
            "data": raw_input.get("data") if isinstance(
                raw_input.get("data"), dict) else {},
        },
        "metadata": {
            key: metadata[key] for key in PUBLIC_AGENT_ORDER_METADATA
            if metadata.get(key) is not None
        },
        "resultContract": {
            "schemaVersion": contract.get("schemaVersion"),
            "format": contract.get("format"),
            "expectedCapability": contract.get("expectedCapability"),
            "delivery": contract.get("delivery"),
        },
    }
    return projected


def to_public_processing(processing: Any) -> Dict[str, Any]:
    """Owner-facing view of the technical result.

    Released: status, attempt, completion time, the fachliche result or a
    sanitised error message. Withheld: work/message ids and the idempotency key
    (internal correlation tokens).
    """
    if not isinstance(processing, dict):
        return {}
    projected: Dict[str, Any] = {}
    for key in ("status", "attempt", "completedAt"):
        if processing.get(key) is not None:
            projected[key] = processing[key]
    if isinstance(processing.get("result"), dict):
        projected["result"] = processing["result"]
    error = processing.get("error")
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        projected["error"] = {"message": error["message"][:500]}
    return projected


def to_list_item(item: Dict[str, Any]) -> Dict[str, Any]:
    if item.get("orderType") == ORDER_TYPE_AGENT:
        # Agent orders carry no retail fields; the list projection stays
        # minimal and never exposes the agentOrder component.
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


class OrderService:
    def __init__(self, table_name: str, client: Any = None) -> None:
        self._table_name = table_name
        self._table = client if client is not None else _get_dynamodb_resource().Table(table_name)

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
        # Internal trust boundary: secret must be configured and token must match
        internal_secret = os.environ.get("PRIVACY_INTERNAL_SECRET")
        if not internal_secret:
            raise validation_error("Internal secret not configured")
        token = context.get("internal_token")
        if not token:
            raise validation_error("Internal token missing")
        # Use constant-time compare
        import secrets
        if not secrets.compare_digest(str(token), str(internal_secret)):
            raise validation_error("Internal trust boundary violation")

    def create_order(self, raw_body: Any, identity: OwnerIdentity) -> Dict[str, Any]:
        if not isinstance(identity, OwnerIdentity):
            raise validation_error("Verified identity is required")
        input_data = validate_create_order(raw_body)
        now = now_iso()
        order_id = generate_order_id()

        if input_data.get("orderType") == ORDER_TYPE_AGENT:
            return self._create_agent_order(input_data, order_id, now, identity)

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
            "customer": input_data["customer"],
            "items": items,
            "currency": input_data["currency"],
            "totalAmount": total_amount,
            "createdAt": now,
            "updatedAt": now,
            "version": 1,
            "gsi1pk": GSI1_PK,
            "gsi1sk": now,
            **identity.item_fields(),
            "gsi3pk": identity.owner_key,
            "gsi3sk": f"{now}#{order_id}",
        }

        self._table.put_item(Item=item)

        return to_public_order(item)

    def _create_agent_order(self, input_data: Dict[str, Any], order_id: str,
                            now: str, identity: OwnerIdentity) -> Dict[str, Any]:
        """Persist an agent order: no retail fields, no invented line items.

        The validated ``agentOrder`` is stored as its own component. It is never
        placed inside ``customer``/``items``/``currency`` and never returned by
        the public projection (see ``INTERNAL_FIELDS``).
        """
        agent_order = input_data["agentOrder"]
        item: Dict[str, Any] = {
            "pk": f"{ORDER_ID_PREFIX}{order_id}",
            "sk": ORDER_SK,
            "orderId": order_id,
            "orderType": ORDER_TYPE_AGENT,
            "status": "PENDING",
            "agentOrder": agent_order,
            # Immutability marker: proves the accepted execution parameters did
            # not change silently on a later write/retry.
            "agentOrderFingerprint": agent_order_fingerprint(agent_order),
            "createdAt": now,
            "updatedAt": now,
            "version": 1,
            "gsi1pk": GSI1_PK,
            "gsi1sk": now,
            **identity.item_fields(),
            "gsi3pk": identity.owner_key,
            "gsi3sk": f"{now}#{order_id}",
        }

        self._table.put_item(Item=item)
        return to_public_order(item)

    def _get_raw_item(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Stored item as-is (ownership and result matching need internals)."""
        result = self._table.get_item(
            Key={"pk": f"{ORDER_ID_PREFIX}{order_id}", "sk": ORDER_SK}
        )
        return result.get("Item")

    def apply_result(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        """Store one RIS result on the matching agent order (idempotent).

        The stored order is the authoritative source: the order id, the
        correlation reference and (when dispatch recorded one) the work id must
        all match. The fachliche order status is never reinterpreted; the result
        lives in its own ``processing`` field.
        """
        order_id = envelope["orderId"]
        item = self._get_raw_item(order_id)
        if item is None:
            raise order_not_found(order_id)
        if item.get("orderType") != ORDER_TYPE_AGENT:
            raise ResultRejected("not_agent_order",
                                 "Order is not an agent execution order")
        if item.get("status") == "CANCELLED":
            raise ResultRejected("order_cancelled",
                                 "Order was cancelled; result is not accepted")

        agent_order = item.get("agentOrder") or {}
        expected_correlation = (agent_order.get("metadata") or {}).get(
            "requestId")
        if not expected_correlation:
            raise ResultRejected(
                "missing_correlation",
                "Order carries no correlation reference")
        if expected_correlation != envelope["correlationId"]:
            raise ResultRejected("correlation_mismatch",
                                 "Result does not belong to this order")

        execution = envelope["execution"]
        expected_work = item.get("expectedWorkId")
        if expected_work and expected_work != execution["workId"]:
            raise ResultRejected("work_mismatch",
                                 "Result does not belong to this execution")

        existing = item.get("processing")
        if isinstance(existing, dict):
            if existing.get("status") in ("COMPLETED", "FAILED"):
                if existing.get("idempotencyKey") == envelope["idempotencyKey"]:
                    stored_execution = existing.get("executionId")
                    incoming_execution = execution.get("executionId")
                    if (stored_execution and incoming_execution
                            and stored_execution != incoming_execution):
                        raise ResultRejected(
                            "execution_mismatch",
                            "Result execution does not match the stored one")
                    return dict(existing)  # duplicate delivery: no-op
                raise ResultRejected(
                    "already_finalised",
                    "Order already carries a terminal result")
            if int(existing.get("attempt") or 0) > int(execution["attempt"]):
                raise ResultRejected("stale_attempt",
                                     "A newer attempt was already recorded")

        record: Dict[str, Any] = {
            "schemaVersion": "1.0",
            "status": ("COMPLETED" if envelope["messageType"] == ORDER_RESULT
                       else "FAILED"),
            "attempt": execution["attempt"],
            "workId": execution["workId"],
            "idempotencyKey": envelope["idempotencyKey"],
            "messageId": envelope["messageId"],
            "completedAt": now_iso(),
        }
        if execution.get("executionId"):
            record["executionId"] = execution["executionId"]
        if envelope["messageType"] == ORDER_RESULT:
            record["result"] = envelope["payload"]
        else:
            error = envelope["payload"].get("error")
            record["error"] = error if isinstance(error, dict) else {
                "message": "Agent execution failed"}

        try:
            self._table.update_item(
                Key={"pk": f"{ORDER_ID_PREFIX}{order_id}", "sk": ORDER_SK},
                UpdateExpression=(
                    "SET #p = :p, updatedAt = :u, #v = #v + :one"),
                ConditionExpression="attribute_exists(pk) AND "
                                    "attribute_not_exists(#p)",
                ExpressionAttributeNames={"#p": "processing", "#v": "version"},
                ExpressionAttributeValues={
                    ":p": record, ":u": now_iso(), ":one": 1},
                ReturnValues="ALL_NEW",
            )
        except Exception as err:
            if is_conditional_check_failed(err):
                refreshed = self._get_raw_item(order_id) or {}
                current = refreshed.get("processing") or {}
                if current.get("idempotencyKey") == envelope["idempotencyKey"]:
                    return dict(current)
                raise ResultRejected(
                    "concurrent_result",
                    "A result was stored concurrently") from err
            raise
        return record

    def get_order(self, order_id: str,
                  identity: OwnerIdentity) -> Dict[str, Any]:
        """Return the order only to its verified owner.

        A missing order and an order owned by someone else are indistinguishable
        (both ``404``), and an order without an owner binding (legacy) is never
        returned to a normal caller.
        """
        if not isinstance(identity, OwnerIdentity):
            raise order_not_found(order_id)
        result = self._table.get_item(
            Key={"pk": f"{ORDER_ID_PREFIX}{order_id}", "sk": ORDER_SK}
        )
        item = result.get("Item")
        if item is None:
            raise order_not_found(order_id)
        if not identity.can_read(item):
            raise order_not_found(order_id)

        public = to_public_order(item)
        # Owner-only detail projection: the fachliche agentOrder is released
        # here and only here, after the ownership check. Lists, create and
        # patch responses keep it internal.
        if item.get("orderType") == ORDER_TYPE_AGENT and item.get("agentOrder"):
            public["agentOrder"] = to_public_agent_order(item["agentOrder"])
        if isinstance(item.get("processing"), dict):
            public["processing"] = to_public_processing(item["processing"])
        return public

    def list_orders(self, identity: OwnerIdentity, limit: int,
                    next_token: Optional[str] = None) -> Dict[str, Any]:
        """List only the caller's own orders.

        There is deliberately **no** fallback to the global list: if the
        ownership index is unavailable, the request fails closed with ``503``
        instead of exposing every order in the system.
        """
        if not isinstance(identity, OwnerIdentity):
            raise service_unavailable("Ownership index is not available")

        query_kwargs: Dict[str, Any] = {
            "IndexName": OWNER_INDEX_NAME,
            "KeyConditionExpression": f"{OWNER_INDEX_HASH_KEY} = :owner",
            "ExpressionAttributeValues": {":owner": identity.owner_key},
            "ScanIndexForward": False,
            "Limit": limit,
        }
        if next_token:
            query_kwargs["ExclusiveStartKey"] = decode_next_token(next_token)

        try:
            result = self._table.query(**query_kwargs)
        except Exception as err:
            if is_validation_exception(err):
                # Missing index or unusable key: never fall back to the global
                # list, because that would expose foreign orders.
                raise service_unavailable(
                    "Ownership index is not available") from err
            raise

        orders = [to_list_item(item) for item in result.get("Items", [])]

        response: Dict[str, Any] = {"orders": orders, "count": len(orders)}
        encoded = encode_next_token(result.get("LastEvaluatedKey"))
        if encoded:
            response["nextToken"] = encoded
        return response

    def update_order_status(self, order_id: str, status: str,
                            identity: OwnerIdentity) -> Dict[str, Any]:
        current = self.get_order(order_id, identity)

        if not can_transition(current["status"], status):
            raise invalid_transition(current["status"], status)

        try:
            result = self._table.update_item(
                Key={"pk": f"{ORDER_ID_PREFIX}{order_id}", "sk": ORDER_SK},
                UpdateExpression="SET #status = :newStatus, updatedAt = :now, #version = #version + :one",
                ConditionExpression="attribute_exists(pk) AND #status = :currentStatus",
                ExpressionAttributeNames={"#status": "status", "#version": "version"},
                ExpressionAttributeValues={
                    ":newStatus": status,
                    ":currentStatus": current["status"],
                    ":now": now_iso(),
                    ":one": 1,
                },
                ReturnValues="ALL_NEW",
            )
            return to_public_order(result["Attributes"])
        except Exception as err:
            if is_conditional_check_failed(err):
                raise conflicted_update() from err
            raise

    def inspect_subject(self, subject_id: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._require_privacy_auth(context, "privacy_inspect")

        if not subject_id or not isinstance(subject_id, str):
            raise validation_error("Invalid subjectId")

        # Query GSI2 for orders linked to subject
        try:
            result = self._table.query(
                IndexName=GSI2_NAME,
                KeyConditionExpression="gsi2pk = :pk",
                ExpressionAttributeValues={":pk": f"{GSI2_PK_PREFIX}{subject_id}"},
                ProjectionExpression="orderId,#status,createdAt,updatedAt,customer",
                ExpressionAttributeNames={"#status": "status"},
            )
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

        items = result.get("Items", [])
        order_refs = []
        for item in items:
            oid = item.get("orderId")
            if oid:
                order_refs.append(oid)

        data_categories = []
        if items:
            # Determine which personal data fields exist in first item
            cust = items[0].get("customer", {})
            if isinstance(cust, dict):
                if "name" in cust:
                    data_categories.append("customer.name")
                if "email" in cust:
                    data_categories.append("customer.email")

        return {
            "subjectId": subject_id,
            "status": "COMPLETED",
            "affectedRecords": len(order_refs),
            "orderReferences": order_refs,
            "dataCategories": data_categories,
            "limitations": [],
        }

    def export_subject(self, subject_id: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._require_privacy_auth(context, "privacy_export")

        if not subject_id or not isinstance(subject_id, str):
            raise validation_error("Invalid subjectId")

        operation_id = str(uuid.uuid4())
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
                    "ProjectionExpression": "orderId,#status,createdAt,updatedAt,customer,totalAmount,currency",
                    "ExpressionAttributeNames": {"#status": "status"},
                }
                if last_evaluated_key:
                    query_kwargs["ExclusiveStartKey"] = last_evaluated_key
                result = self._table.query(**query_kwargs)
                items = result.get("Items", [])
                for item in items:
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
                    "ProjectionExpression": "orderId,pk,sk,subjectId,version,createdAt",
                }
                if last_evaluated_key:
                    query_kwargs["ExclusiveStartKey"] = last_evaluated_key
                result = self._table.query(**query_kwargs)
                items = result.get("Items", [])
                for item in items:
                    affected.append({
                        "pk": item.get("pk"),
                        "sk": item.get("sk"),
                        "orderId": item.get("orderId"),
                        "subjectId": item.get("subjectId"),
                        "version": item.get("version"),
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
                "limitations": [],
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
                "failedRecords": 0,
                "limitations": ["Missing explicit retention policy"],
                "completedAt": now_iso(),
            }
        # EXECUTE mode
        deleted = 0
        anonymized = 0
        retained = 0
        failed = 0
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
                        UpdateExpression="SET #c.#n = :anon, #c.#e = :anon_email REMOVE subjectId, gsi2pk, gsi2sk",
                        ConditionExpression=cond_expr,
                        ExpressionAttributeNames={"#c": "customer", "#n": "name", "#e": "email"},
                        ExpressionAttributeValues={":anon": "ANONYMIZED", ":anon_email": "anonymized@example.com", **cond_values},
                    )
                    anonymized += 1
            except Exception:
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
            "failedRecords": failed,
            "limitations": [],
            "completedAt": now_iso(),
        }


def create_order_service(table_name: str, client: Any = None) -> OrderService:
    return OrderService(table_name, client)
