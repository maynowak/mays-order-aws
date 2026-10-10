from __future__ import annotations

import base64
import json
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from errors import conflicted_update, invalid_transition, order_not_found, validation_error
from state_machine import can_transition
from order_types import GSI1_PK, GSI2_NAME, GSI2_PK_PREFIX, ORDER_ID_PREFIX, ORDER_SK, TABLE_INDEX_NAME
from validation import validate_create_order

# version = Optimistic-Locking-Feld (intern); isTestData = reiner Seed-Marker,
# darf in API-Antworten niemals auftauchen (nur Demo-Seed setzt es).
INTERNAL_FIELDS = {"pk", "sk", "gsi1pk", "gsi1sk", "gsi2pk", "gsi2sk", "version", "isTestData", "subjectId"}

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


def to_list_item(item: Dict[str, Any]) -> Dict[str, Any]:
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
    raw = json.dumps(last_evaluated_key, separators=(",", ":"))
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

    def create_order(self, raw_body: Any, subject_id: Optional[str] = None) -> Dict[str, Any]:
        input_data = validate_create_order(raw_body)
        now = now_iso()
        order_id = generate_order_id()

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
        }

        if subject_id:
            item["subjectId"] = subject_id
            from order_types import GSI2_PK_PREFIX, GSI2_NAME
            # GSI2 not required for public API, but prepared for privacy capability
            item["gsi2pk"] = f"{GSI2_PK_PREFIX}{subject_id}"
            item["gsi2sk"] = f"{ORDER_ID_PREFIX}{order_id}#{now}"

        self._table.put_item(Item=item)

        return to_public_order(item)

    def get_order(self, order_id: str) -> Dict[str, Any]:
        result = self._table.get_item(
            Key={"pk": f"{ORDER_ID_PREFIX}{order_id}", "sk": ORDER_SK}
        )
        item = result.get("Item")
        if item is None:
            raise order_not_found(order_id)
        return to_public_order(item)

    def list_orders(self, limit: int, next_token: Optional[str] = None) -> Dict[str, Any]:
        query_kwargs: Dict[str, Any] = {
            "IndexName": TABLE_INDEX_NAME,
            "KeyConditionExpression": "gsi1pk = :pk",
            "ExpressionAttributeValues": {":pk": GSI1_PK},
            "ScanIndexForward": False,
            "Limit": limit,
        }
        if next_token:
            query_kwargs["ExclusiveStartKey"] = decode_next_token(next_token)

        try:
            result = self._table.query(**query_kwargs)
        except Exception as err:
            if is_validation_exception(err):
                raise validation_error(
                    "Invalid pagination token or query",
                    {"path": "nextToken"},
                ) from err
            raise

        orders = [to_list_item(item) for item in result.get("Items", [])]

        response: Dict[str, Any] = {"orders": orders, "count": len(orders)}
        encoded = encode_next_token(result.get("LastEvaluatedKey"))
        if encoded:
            response["nextToken"] = encoded
        return response

    def update_order_status(self, order_id: str, status: str) -> Dict[str, Any]:
        current = self.get_order(order_id)

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
                ProjectionExpression="orderId,status,createdAt,updatedAt,customer",
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
                    "ProjectionExpression": "orderId,status,createdAt,updatedAt,customer,totalAmount,currency",
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
                    "ProjectionExpression": "orderId,pk,sk,subjectId,createdAt",
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
                    self._table.delete_item(
                        Key={"pk": pk, "sk": sk},
                        ConditionExpression="subjectId = :sid",
                        ExpressionAttributeValues={":sid": subject_id},
                    )
                    deleted += 1
                elif policy == "ANONYMIZE":
                    self._table.update_item(
                        Key={"pk": pk, "sk": sk},
                        UpdateExpression="SET #c.#n = :anon, #c.#e = :anon_email REMOVE subjectId, gsi2pk, gsi2sk",
                        ConditionExpression="subjectId = :sid",
                        ExpressionAttributeNames={"#c": "customer", "#n": "name", "#e": "email"},
                        ExpressionAttributeValues={":anon": "ANONYMIZED", ":anon_email": "anonymized@example.com", ":sid": subject_id},
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
