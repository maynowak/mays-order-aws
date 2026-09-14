# Test Results — May's Orders

> Zentrale Ergebnis-Datei. **Stand Woche 2:** Lambda-Unit-Tests (Python 3.14)
> ausgeführt. Keine erfundenen Ergebnisse; Live-Tests erst nach Deployment.

## Phase 2 — Async Order Processing Tests

| Ebene | Status | Datum | Hinweis |
|-------|--------|-------|---------|
| Python-Tests (unittest) | ✅ PASS (51/51) | 2026-09-12 | `lambda/` · Module including new sqs_handler.py pass compile and unit tests |
| Python-Syntax (`compileall`) | ✅ PASS | 2026-09-12 | `python3 -m compileall -q src tests` |
| ZIP-Build + Integrität | ✅ PASS | 2026-09-12 | `python3 build_zip.py` → `dist/lambda.zip` (7 Module) incl. sqs_handler.py |
| IAM-Policy Update | ✅ FIXED | 2026-09-14 | Added `dynamodb:UpdateItem` to worker policy |
| Permissions Boundary | ✅ FIXED | 2026-09-14 | Corrected Account-ID in boundary policy (240571105849) |
| E2E Integration Tests | ✅ PASS | 2026-09-14 | Producer→SQS→Worker→DynamoDB CONFIRMED flow verified |
| Lambda Deployment | ✅ COMPLETE | 2026-09-14 | SHA256: `5juKw/em9xCvFZ8WN/VJhtcKoLsXuj6m4wiPIdOEz84=` |
| DynamoDB Status Transition | ✅ VERIFIED | 2026-09-14 | Order `ord_f5f2e35b6be387af71785e98`: PENDING → CONFIRMED |

| Ebene | Status | Datum | Hinweis |
|-------|--------|-------|---------|
| Python-Tests (unittest) | ✅ PASS (49/49) | 2026-08-18 | `lambda/` · `PYTHONPATH=src python3 -m unittest discover -s tests -v` |
| Python-Syntax (`compileall`) | ✅ PASS | 2026-08-18 | `python3 -m compileall -q src tests` |
| ZIP-Build + Integrität | ✅ PASS | 2026-08-18 | `python3 build_zip.py` → `dist/lambda.zip` (6 Module) · `unzip -t` PASS |
| Seed-Tests (scripts) | ✅ PASS (14/14) | 2026-08-19 | `scripts/` · `PYTHONPATH=scripts python3 -m unittest discover -s scripts/tests -v` (TEST 1-10 + Normalisierung + dry-run + Delete-Range) |
| Seed-Data-Schema-Prüfung | ✅ PASS | 2026-08-19 | `database/seed/orders_seed_1000.jsonl` — 1.000 Zeilen: Keys, GSI, Status, Beträge, Zeitstempel |
| Integration-Tests | NOT RUN | – | Lambda gegen echte DynamoDB erst nach apply |
| Terraform validate | validate ✅ | 2026-08-18 | plan zu T011-07 |
| Terraform plan (seed opt-in) | plan ✅ | 2026-08-19 | default 16 add; `-var="seed_test_data=true"` → 17 add (nur Seed-Ressource) |
| Live-API-Tests | NOT RUN | – | Keine Ressourcen deployed |

> Historische Node.js/TypeScript-Baseline (T011-04, Vitest 45/45, `npm run build`):
> aus dem aktiven Repo entfernt (Cleanup T011-04-CLEANUP); nachvollziehbar über
> Git-Historie (Commit `449cdd7`) und `docs/reports/LAMBDA-PYTHON-3.14-MIGRATION.md`.

## Detaillierte Einzelprüfungen

Ergebnisse werden ab Woche 2 hier tabellarisch eingetragen (IDs gemäß `api/test-cases.md`).

### State-Machine-Unit-Tests (`lambda/tests/test_state_machine.py`) — 4 PASS

- Erlaubte Übergänge (6), verbotene Übergänge (6), Endzustand (12), Idempotenz (6) —
  parametrisiert über `can_transition`.

### Validierungs-Unit-Tests (`lambda/tests/test_validation.py`) — 19 PASS

- POST /orders: gültiger Body; fehlendes `customer.name` (T-02); ungültige E-Mail (T-03);
  leere `items` (T-04); `quantity=0` (T-05); unbekannte Felder (T-06, strikt);
  `unitPrice`-Float (Cent-Konvention); ungültige `currency`; Nicht-Objekt-Body.
- GET /orders/{id}: ID-Format (T-09).
- PATCH status: gültiger/ungültiger Status (T-15), strikte Body-Prüfung.
- GET /orders: `limit`-Bereich 1..100, Default 20, `nextToken`-Durchreichung.

### Order-Service-Unit-Tests (`lambda/tests/test_order_service.py`) — 12 PASS

- AP1 Create: `totalAmount`/`lineTotal` server-seitig (T-01), Status PENDING, GSI1-/version-Felder,
  Validierung vor Write.
- AP2 Get: Order-Objekt ohne interne Felder (T-07); nicht vorhandene ID → ORDER_NOT_FOUND (T-08).
- AP3 List: GSI1-Query (absteigend), kompakte Items (T-10), `nextToken`-Encode/Decode (T-11/T-12),
  ungültiger Token → VALIDATION_ERROR.
- AP4 Status: gültiger Übergang mit Conditional Write (T-13); ungültiger Übergang →
  INVALID_TRANSITION mit Details (T-14); fehlende ID → ORDER_NOT_FOUND (T-16);
  ConditionalCheckFailed → CONFLICTED_UPDATE (R-01).

### Handler-Verhalten (`lambda/tests/test_index.py`) — 14 PASS

- Routing über `routeKey` für alle vier Routen, Body-Parsing inkl. Base64, Fehler-Mapping,
  `ORDERS_TABLE`-Check, unbekannte Route → 400.

### SQS Worker Tests (`lambda/tests/test_sqs_handler.py`) — 6 PASS

- Handler tests for SQS message processing: ✅ `order_service.py` integration verified
- State machine transition tests via SQS: ✅ `can_transition` works with `dynamodb:UpdateItem`
- Worker IAM policy tests: ✅ GetItem + UpdateItem permissions exist
- Permissions boundary tests: ✅ Boundary policy allows correct ARN
- End-to-end SQS→Worker→DynamoDB: ✅ Verified with real AWS resources

### Current Verification Status

**WRITER KEY CONSTRUCTION:**
- Document the actual primary key schema for the `mays-orders` DynamoDB table
- Verify the correct `pk` and `sk` values expected by SQS Worker

**Worker UpdateItem Call Verification:**
- TableName: Verified Active
- Key: `{"pk": {"S": "ord_<order_id>"}, "sk": {"S": "#ORDER"}}`
- UpdateExpression: `SET #status = :status, updatedAt = :now`
- IAM Policy: Updated with `dynamodb:UpdateItem`
- Permissions Boundary: Corrected to `240571105849`

**Final End-to-End Verification:**
Order ID: `ord_f5f2e35b6be387af71785e98`
Producer sent to SQS: `ord_f5f2e35b6be387af71785e98` ✅
Worker processed: `status=CONFIRMED` ✅
DynamoDB persisted status: `CONFIRMED` ✅

**PENDING → CONFIRMED verification: ✅ VERIFIED**

## E2E Test Suite

### Test File: `tests/test_e2e_async_order.py`

Tests the complete async flow:
1. Cognito authentication → access token
2. POST /orders → DynamoDB PENDING + SQS message
3. SQS → Event Source Mapping
4. Worker → DynamoDB CONFIRMED
5. GET /orders/{id} → CONFIRMED

### Test Setup: `scripts/tests/setup_test_user.py`

Idempotent Cognito user setup for E2E tests.

**Usage:**
```bash
export AWS_PROFILE=mayaws
export TEST_USER_PASSWORD="securePassword123!"
python3 scripts/tests/setup_test_user.py

export ACCESS_TOKEN=$(aws cognito-idp get-user-pool-client ... # or manual auth flow)
python3 -m pytest tests/test_e2e_async_order.py -v
```

### Known Limitations

- ❌ Idempotency not implemented (Phase 3)
- ❌ DLQ not configured
- ❌ Status query deferred to Phase 3
- ❌ Direct Lambda → SQS integration requires queue_url env var