# Phase 1 — Order / Message / Status Model

**Purpose:** Define the concrete Order model, SQS message model, idempotency/hash model, and Order status lifecycle based on the EXISTING project implementation.

---

## CURRENT ORDER MODEL

**Source Files:**
- `lambda/src/order_types.py`
- `lambda/src/order_service.py`
- `lambda/src/validation.py`

### Order Identification

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| `orderId` | string | Primary identifier | Format: `ord_<12-char-hex>` |
| `pk` | string | Partition key | Format: `{ORDER_ID_PREFIX}{order_id}` |
| `sk` | string | Sort key | Value: `#ORDER` |

**Order ID Generation:**
- Location: `order_service.py:38-39`
- Method: `secrets.token_hex(12)` prefixed with `ord_`
- Generated at: `create_order()` time

### Order Fields (Public API)

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `orderId` | string | Yes | `ord_[A-Za-z0-9]+` |
| `status` | string | Yes | See [Current Status Model](#current-status-model) |
| `customer.name` | string | Yes | Non-empty string |
| `customer.email` | string | Yes | Valid email regex |
| `items[].sku` | string | Yes | Non-empty string |
| `items[].quantity` | integer | Yes | >= 1 |
| `items[].unitPrice` | integer | Yes | >= 1 |
| `currency` | string | Yes | 3-letter ISO-4217 (uppercase) |
| `totalAmount` | integer | Yes | Calculated server-side |
| `createdAt` | string | Yes | ISO-8601, server-generated |
| `updatedAt` | string | Yes | ISO-8601, server-generated |

### DynamoDB Internal Fields

| Field | Type | Notes |
|-------|------|-------|
| `gsi1pk` | string | Value: `LIST` (global secondary index partition key) |
| `gsi1sk` | string | Value: ISO timestamp (GSI sort key) |
| `version` | integer | Optimistic locking field |
| `isTestData` | boolean | NOT part of production model |

---

## CURRENT STATUS MODEL

**Source File:** `order_types.py:5-12`, `state_machine.py:5-12`

### Status Values

| Status | Meaning | Transitions To |
|--------|---------|----------------|
| `PENDING` | Order just created, awaiting processing | `CONFIRMED`, `CANCELLED` |
| `CONFIRMED` | Order confirmed, ready for processing | `PROCESSING`, `CANCELLED` |
| `PROCESSING` | Order is being processed | `SHIPPED` |
| `SHIPPED` | Order shipped to customer | `DELIVERED` |
| `DELIVERED` | Order delivered to customer | (terminal) |
| `CANCELLED` | Order cancelled | (terminal) |

### State Machine Transitions

```python
TRANSITIONS = {
    "PENDING": ["CONFIRMED", "CANCELLED"],
    "CONFIRMED": ["PROCESSING", "CANCELLED"],
    "PROCESSING": ["SHIPPED"],
    "SHIPPED": ["DELIVERED"],
    "DELIVERED": [],
    "CANCELLED": [],
}
```

### Status Setting

| Operation | Location | Notes |
|-----------|----------|-------|
| Initial status | `order_service.py:115` | Set to `"PENDING"` on create |
| Status update | `order_service.py:169-193` | Uses state machine validation |

---

## CURRENT SQS MESSAGE MODEL

**Source File:** `lambda/src/sqs_handler.py`

### Current SQS Handler

The SQS worker handler is **MINIMAL** and **INCOMPLETE**:

```python
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    records = event.get("Records", [])
    
    for record in records:
        body = record.get("body")
        if body:
            message = json.loads(body)
            order_id = message.get("orderId")
            status = message.get("status")
            print(f"Worker processing: order_id={order_id}, status={status}")

    return {"statusCode": 200, "body": json.dumps({"processed": len(records)})}
```

### Message Schema (LIMITED)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `orderId` | string | Yes | Order identifier |
| `status` | string | Yes | Target status |

**Critical Observations:**
- No actual processing logic implemented
- No DynamoDB updates
- Message body format is JSON (body), not attributes
- No idempotency handling
- No error handling or DLQ preparation

---

## CURRENT WORKER RESPONSIBILITY

**Accounted for:** The worker Lambda `mays-orders-sqs-worker` exists but:

1. **Current Implementation:** Only logs messages, does NO actual work
2. **No DynamoDB interaction**
3. **No business logic execution**
4. **No status transitions**

---

## CURRENT HANDLER/PRODUCER RESPONSIBILITY

**Source File:** `lambda/src/index.py`

### Current API Role

The Lambda currently acts as:

| Route | Function | Database Operation |
|-------|----------|-------------------|
| `POST /orders` | `create_order()` | DynamoDB PutItem |
| `PATCH /orders/{orderId}/status` | `update_order_status()` | DynamoDB UpdateItem |
| `GET /orders` | `list_orders()` | DynamoDB Query (GSI1) |
| `GET /orders/{orderId}` | `get_order()` | DynamoDB GetItem |

### Current SQS Role

**NONE** - The handler does NOT send to SQS.

### Current Flow (VERIFIED)

```
Client → API Gateway → Lambda Handler → DynamoDB
```

**NO SQS INVOLVED in current implementation.**

---

## EXISTING IDEMPOTENCY / DUPLICATE HANDLING

### Current Behavior

| Scenario | Current Handling |
|----------|------------------|
| Duplicate order requests | Would create duplicate orders |
| Duplicate SQS messages | Would re-process each message |
| Idempotency key | NOT IMPLEMENTED |

### DynamoDB Constraints

- No `conditionExpression` in `create_order()` to prevent duplicates
- Uses optimistic locking (`version` field) on updates only

---

## TARGET STATUS MODEL

### Proposed Lifecycle

```
ORDERED
   ↓
CONFIRMED
   ↓
PROCESSING
   ↓
COMPLETED
```

### Comparison: Proposed vs Existing

| Status | Proposed | Existing | Notes |
|--------|----------|----------|-------|
| `ORDERED` | ✓ Added | ✗ Missing | New between PENDING and CONFIRMED |
| `CONFIRMED` | ✓ Same | ✓ Exists | Same |
| `PROCESSING` | ✓ Same | ✓ Exists | Same |
| `COMPLETED` | ✓ Renamed | ✗ `DELIVERED` | Different final state |
| `DELIVERED` | ✗ Removed | ✓ Exists | Conflict (existing has DELIVERED) |
| `SHIPPED` | ✗ Removed | ✓ Exists | Conflict |
| `CANCELLED` | ✗ Removed | ✓ Exists | Conflict |

### Status Model Decision Required

**Conflict:** The existing model has `DELIVERED`, `SHIPPED`, and `CANCELLED` which are NOT in the proposed model.

**Recommendation:** The proposed lifecycle replaces `PROCESSING → COMPLETED` instead of `PROCESSING → SHIPPED → DELIVERED`. This is a **design decision**.

---

## PROPOSED REQUEST FLOW (Target Architecture)

```
Client
  ↓
Cognito / JWT
  ↓
API Gateway
  ↓
SQS (Order Request Queue)
  ↓
Lambda Event Source Mapping
  ↓
SQS Worker Lambda
  ↓
DynamoDB
```

### Key Components

| Component | Status | Notes |
|-----------|--------|-------|
| SQS Queue | ✅ EXISTS | `mays-orders-orders-queue` |
| Worker Lambda | ✅ EXISTS | `mays-orders-sqs-worker` |
| Event Source Mapping | ✅ EXISTS | Enabled |
| Producer Lambda | ❌ NOT SENT TO SQS | Currently writes directly to DynamoDB |
| Status Transitions | ⚠️ PARTIAL | Exists but different from proposed |

---

## PROPOSED STATUS QUERY FLOW

```
Client
  ↓
GET /orders/{orderId}
  ↓
API Gateway
  ↓
Lambda
  ↓
DynamoDB GetItem
  ↓
Return status
```

**Note:** Status query remains separate from processing. No queue/DB hybrid lookup required in current design.

---

## OPEN DESIGN DECISIONS

### 1. Status Model Alignment
The existing statuses differ from the proposed model. Decision required:
- Keep existing statuses (`DELIVERED`, `SHIPPED`, `CANCELLED`)
- Or adopt proposed (`ORDERED`, `COMPLETED`)

### 2. Idempotency Implementation
Not currently implemented. Decision required:
- Client-provided idempotency key
- Hash-based deduplication
- DynamoDB conditional write

### 3. Producer vs Distributor Architecture
Current: Lambda handles all operations

Proposed: Dedicated producer for SQS dispatch OR Lambda sends to SQS

### 4. Worker Business Logic
Current worker is minimal stub. Need to implement:
- Order processing logic
- Status transitions
- Error handling

### 5. Order State Visualization
The `/order-lifecycle/` folder exists with:
- `state-machine.md`
- `transition-rules.md`

Need to verify these match or update to reflect actual implementation.

---

## PHASE 2 IMPLEMENTATION REQUIREMENTS

### 1. Producer → SQS Integration

**Files to modify:**
- `lambda/src/index.py` - Add SQS send after DynamoDB PutItem
- `terraform/modules/lambda/main.tf` - Add `SQS_QUEUE_URL` environment variable
- `terraform/modules/iam/main.tf` - Add `sqs:SendMessage` permission

**Changes needed:**
```python
# After order creation
sqs = boto3.client('sqs')
sqs.send_message(
    QueueUrl=os.environ['SQS_QUEUE_URL'],
    MessageBody=json.dumps({
        'orderId': order['orderId'],
        'status': 'PENDING'
    })
)
```

### 2. Worker Enhancement

**Current**: Stub that only logs

**Required**: Implement actual processing logic

### 3. Idempotency / Deduplication

**Required**: Add to producer or worker

### 4. Testing

**Existing:** Tests in `tests/` directory

**Need to verify:**
- SQS message format matches worker expectations
- End-to-end flow works

---

## VERIFIED FINDINGS SUMMARY

| Component | Current State | Verification Method |
|-----------|--------------|---------------------|
| Order Model | Defined in `order_types.py` | Code inspection |
| Status Model | 6 statuses, state machine | Code inspection |
| SQS Queue | Exists | AWS CLI |
| Worker Lambda | Exists, minimal code | Code inspection |
| Producer Lambda | Exists, NO SQS integration | Code + AWS CLI |
| Event Source Mapping | ENABLED | AWS CLI |
| API Gateway → SQS | NOT INTEGRATED | API Gateway inspection |

---

## FILES INSPECTED

1. `lambda/src/index.py` - API handler
2. `lambda/src/order_service.py` - Order service with DynamoDB operations
3. `lambda/src/order_types.py` - Order types and statuses
4. `lambda/src/validation.py` - Input validation
5. `lambda/src/state_machine.py` - Status transitions
6. `lambda/src/sqs_handler.py` - Minimal SQS worker
7. `terraform/modules/sqs/main.tf` - SQS module
8. `terraform/modules/sqs-worker/main.tf` - Worker module
9. `terraform/modules/lambda/main.tf` - Handler module
10. `architecture/request-flow.md` - Request flow docs
11. `architecture/architecture-diagram.svg` - Architecture diagram
12. `order-lifecycle/state-machine.md` - State machine docs

---

## AWS CHECKS PERFORMED

1. ✅ API Gateway routes and integrations
2. ✅ SQS queue existence
3. ✅ Worker Lambda existence
4. ✅ Event Source Mapping status
5. ✅ Producer Lambda environment variables
6. ✅ IAM policies