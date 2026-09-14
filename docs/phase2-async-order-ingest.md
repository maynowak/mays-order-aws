# Phase 2 — Async Order Ingest + SQS Worker Lifecycle

**Status:** IMPLEMENTED (not yet deployed)

## IMPLEMENTATION SUMMARY

### Files Changed

| File | Changes |
|------|---------|
| `lambda/src/index.py` | Added SQS client, message sending, environment variable |
| `lambda/src/sqs_handler.py` | Implemented full worker processing logic |
| `terraform/modules/iam/variables.tf` | Added `sqs_queue_arn` variable |
| `terraform/modules/iam/main.tf` | Added `sqs:SendMessage` permission |
| `terraform/modules/lambda/variables.tf` | Added `queue_url` variable |
| `terraform/modules/lambda/main.tf` | Added `SQS_QUEUE_URL` to environment |
| `terraform/main.tf` | Added `queue_url` and `sqs_queue_arn` to module calls |

---

## CURRENT ASYNC FLOW

```
Client
  ↓
Cognito/JWT
  ↓
API Gateway
  ↓
Lambda Handler (mays-orders-handler)
  ├─→ DynamoDB (PutItem, status=PENDING)
  └─→ SQS (send_message, trigger CONFIRMED)
       ↓
SQS Worker (mays-orders-sqs-worker)
  ↓
DynamoDB UpdateItem (PENDING→CONFIRMED)
```

**Critical:** The API Gateway still points to Lambda directly - no changes to API Gateway integration for Phase 2.

---

## SQS MESSAGE MODEL

### Producer Message Format

```json
{
  "orderId": "ord_<12-char-hex>",
  "status": "CONFIRMED",
  "metadata": {"reason": "order_created"}
}
```

**Message Attributes:**
- `orderId` (String): Order identifier for tracing

---

## WORKER IMPLEMENTATION

### SQS Handler Logic (`sqs_handler.py`)

1. **Receive SQS event** - Each record has `body` with JSON message
2. **Extract fields** - `orderId`, `status`, `payload`
3. **Validate** - Check message structure
4. **Check DynamoDB** - Get current order item
5. **Validate transition** - Use existing state machine (`state_machine.can_transition`)
6. **Update status** - Atomic DynamoDB UpdateItem
7. **Log result** - Return processed count

### Worker State Machine

Uses existing `state_machine.py` transitions:

| From | To | Valid |
|------|-----|-------|
| PENDING | CONFIRMED | ✓ |
| PENDING | CANCELLED | ✓ |
| CONFIRMED | PROCESSING | ✓ |
| CONFIRMED | CANCELLED | ✓ |
| PROCESSING | SHIPPED | ✓ |
| SHIPPED | DELIVERED | ✓ |

---

## IAM PERMISSION CHANGES

### Producer (handler) - Added:

```json
{
  "Sid": "SQS",
  "Effect": "Allow",
  "Action": ["sqs:SendMessage"],
  "Resource": [module.sqs.queue_arn]
}
```

### Worker - Already had:
- `sqs:ReceiveMessage`
- `sqs:DeleteMessage`
- `sqs:GetQueueAttributes`
- `dynamodb:GetItem`

---

## ENVIRONMENT VARIABLES

### Handler Lambda:
- `ORDERS_TABLE` - DynamoDB table name (existing)
- `SQS_QUEUE_URL` - SQS queue URL for sending messages (NEW)

### Worker Lambda:
- `ORDERS_TABLE` - DynamoDB table name (existing)

---

## TARGET Status Semantics

Following existing state machine exactly:

- **PENDING** - Order just created, awaiting confirmation
- **CONFIRMED** - Worker has taken responsibility
- **PROCESSING** - Order being processed
- **SHIPPED** - Order shipped
- **DELIVERED** - Order delivered (terminal)
- **CANCELLED** - Order cancelled (terminal)

**Note:** Do NOT use ORDERED or COMPLETED per requirements.

---

## STATUS QUERY FLOW (DEFERRED to Phase 3)

The `GET /orders/{orderId}` endpoint remains unchanged:

```
Client
  ↓
GET /orders/{orderId}
  ↓
API Gateway → Lambda → DynamoDB
  ↓
Return current status
```

No queue-based status lookup implemented yet.

---

## IMPLEMENTATION NOTES

### Idempotency / Duplicate Handling

**NOT IMPLEMENTED** - Current state:
- Producer uses existing `secrets.token_hex(12)` for order IDs
- No client-provided idempotency key
- No deduplication mechanism
- **Risk:** Duplicate requests could create duplicate orders + SQS messages

**Phase 3 requires:** Implement idempotency check before DynamoDB write

### Retry / DLQ Behavior

**Current SQS config:**
- Visibility timeout: 30 seconds
- Message retention: 120 seconds
- No DLQ configured
- Default Lambda retry: 2 retries

**Recommendation:** Configure DLQ in Phase 3 for failed messages.

### Worker Acknowledgement

- Returns `{"processed": N, "total": N}` on success
- On failure, Lambda retries per Event Source Mapping settings
- No explicit message deletion (handled by Lambda runtime on success)

---

## DEPLOYMENT STATUS

### What's Ready:
- ✓ Producer code sends to SQS
- ✓ Worker code processes orders
- ✓ Terraform modules have queue_url and permissions

### What's MISSING:
- ✗ Cannot run `terraform apply` - would duplicate API Gateway, Cognito, etc.
- ✗ Lambda ZIP file not rebuilt
- ✗ No targeted deployment tested

### Deployment Actions Required:
1. Build new Lambda ZIP: `python3 lambda/build_zip.py`
2. Import producer IAM policy with SQS permissions:
   ```bash
   terraform import module.iam.data.aws_iam_policy_document.handler_trust <...>
   ```
   Or use targeted apply for producer module only

---

## OPEN ISSUES / QUESTIONS

1. **API Gateway Integration:** Does not route to SQS - will need Lambda-proxy or direct SQS integration
2. **Idempotency:** Not implemented - need Phase 3
3. **DLQ:** Not configured - need Phase 3
4. **Error handling:** Worker raises exceptions on failure - good for retries

---

## TESTING

### Unit Tests (existing in tests/)

```bash
cd /home/dci-student/projects/Mays-Orders-AWS
PYTHONPATH=lambda/src python3 -m unittest discover -s tests -v
```

### Integration Test Steps:

1. Build and deploy producer Lambda (targeted)
2. POST /orders with valid order
3. Verify:
   - Order created in DynamoDB (status=PENDING)
   - Message sent to SQS
   - Worker picks up message
   - Order status updated (PENDING→CONFIRMED)
   - No duplicate processing on retry

---

## FILES REFERENCED

### Inspected:
- `lambda/src/index.py` - Producer handler
- `lambda/src/order_service.py` - Order service
- `lambda/src/order_types.py` - Type definitions
- `lambda/src/validation.py` - Input validation
- `lambda/src/state_machine.py` - State transitions
- `lambda/src/sqs_handler.py` - SQS worker
- `terraform/modules/sqs/main.tf` - SQS module
- `terraform/modules/sqs-worker/main.tf` - Worker module
- `terraform/modules/iam/main.tf` - IAM policy
- `terraform/modules/lambda/main.tf` - Lambda module

### Created:
- `docs/phase1-order-message-status-model.md` - Phase 1 analysis
- `docs/phase2-async-order-ingest.md` - THIS FILE

---

## RECOMMENDATION

Complete Phase 2 by:

1. **BUILD:** Recompile Lambda ZIP with new code
2. **DEPLOY:** Use targeted terraform changes only
3. **TEST:** End-to-end order flow verification
4. **Phase 3:** Implement idempotency and DLQ

**Do NOT** run full `terraform apply` - will create duplicate resources.
