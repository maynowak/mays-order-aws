import json
import os
import boto3
from typing import Any, Dict

from order_types import ORDER_ID_PREFIX, ORDER_SK, TABLE_INDEX_NAME
from order_service import generate_order_id, now_iso

_dynamodb_client = None
_sqs_client = None

def _get_dynamodb_client():
    global _dynamodb_client
    if _dynamodb_client is None:
        import boto3
        _dynamodb_client = boto3.client('dynamodb', region_name=os.environ.get('AWS_REGION', 'eu-central-1'))
    return _dynamodb_client

def _get_sqs_client():
    global _sqs_client
    if _sqs_client is None:
        import boto3
        _sqs_client = boto3.client('sqs', region_name=os.environ.get('AWS_REGION', 'eu-central-1'))
    return _sqs_client

def _get_table_name():
    return os.environ.get('ORDERS_TABLE')

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    records = event.get("Records", [])
    processed = 0
    
    for record in records:
        body = record.get("body")
        if body:
            try:
                message = json.loads(body)
                order_id = message.get("orderId")
                status = message.get("status")
                payload = message.get("payload", {})
                
                print(f"Worker processing: order_id={order_id}, status={status}")
                
                if order_id and status:
                    success = _process_order(order_id, status, payload)
                    if success:
                        processed += 1
                else:
                    print(f"Invalid message format: missing orderId or status")
            except json.JSONDecodeError as e:
                print(f"Failed to parse message: {e}")
            except Exception as e:
                print(f"Error processing message: {e}")
                raise
    
    return {"statusCode": 200, "body": json.dumps({"processed": processed, "total": len(records)})}

def _process_order(order_id: str, status: str, payload: Dict[str, Any]) -> bool:
    table_name = _get_table_name()
    if not table_name:
        raise ValueError("ORDERS_TABLE environment variable not set")
    
    dynamodb = _get_dynamodb_client()
    
    pk = f"{ORDER_ID_PREFIX}{order_id}"
    
    current_item = dynamodb.get_item(
        TableName=table_name,
        Key={"pk": {"S": pk}, "sk": {"S": ORDER_SK}}
    )
    
    if "Item" not in current_item:
        print(f"Order not found for processing: {order_id}")
        return False
    
    from state_machine import can_transition
    current_status = current_item["Item"].get("status", {}).get("S", "PENDING")
    
    if not can_transition(current_status, status):
        print(f"Invalid transition: {current_status} -> {status}")
        return False
    
    now = now_iso()
    dynamodb.update_item(
        TableName=table_name,
        Key={"pk": {"S": pk}, "sk": {"S": ORDER_SK}},
        UpdateExpression="SET #status = :status, updatedAt = :now",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": {"S": status},
            ":now": {"S": now}
        }
    )
    
    print(f"Order {order_id} transitioned {current_status} -> {status}")
    return True