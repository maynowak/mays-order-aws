# MO-PRIVACY-PROVIDER-CONTRACT-REVIEW-01

**Status:** `MO PRIVACY PROVIDER CONTRACT RESPONSE READY` — STOP before implementation.  
**Review baseline:** `716a16590673cdb649df414c08fc0bf7814caac7` (`origin/main`).  
**Branch:** `feature/mo-privacy-provider-contract-01`.  
**Consumer source:** RIS `18f2128d6d60993b2cbe2296ac2a3f190617f289`, `DSGVO-02B-PROVIDER-INTEGRATION-REVIEW.md`.  
**Scope:** read-only contract review; this report and auditlog only. No tests run, runtime/provider code changed, AWS/Terraform action, deployment, Main merge or legal approval.

## Executive decision

| Consumer request | Recommendation | Summary |
|---|---|---|
| `CR-MO-PRIVACY-RIS-SUBJECT-DELEGATION-01` | **CHANGE REQUIRED** | Provider has the privacy operations and direct-Lambda invoke path, but does not support binding a separately authenticated RIS data subject to a created order. Internal order delegation is explicitly blocked. Consumer scoping exists only as an optional narrowing filter; absent scope is deployment-wide. Provider must define and test an additive trusted delegation contract before claiming RIS coverage. |
| `CR-MO-PRIVACY-ANONYMIZE-COVERAGE-02` | **CHANGE REQUIRED** | Current `ANONYMIZE` removes customer fields, privacy index, selected result/error/attempt fields, GSI3 keys and description, but leaves embedded `agentOrder` and identity/consumer fields. It does not satisfy an exhaustive residual-data contract. Provider owners must define the intended residual-field contract and add provider-owned tests; do not infer legal sufficiency. |

These recommendations do not change the existing standalone Cognito/JWT `/orders` contract. A new service contract must be separate, versioned, and additive; unauthenticated/client-body identity must remain rejected.

## 1. CR-MO-PRIVACY-RIS-SUBJECT-DELEGATION-01

### Existing provider offer — supported portions

- **Ordinary create is subject-bound:** `lambda/src/index.py` resolves verified API Gateway JWT claims and calls `create_order(..., subject_id=identity.owner_id, identity=identity)`. `lambda/src/order_service.py::create_order` writes `subjectId` and GSI2 (`gsi2pk`/`gsi2sk`) and keeps consumer/owner/actor fields separate. `lambda/src/validation.py` does not allow a public request body to choose identity. Public owner access checks both subject and consumer.
- **Privacy capabilities exist:** `OrderService.inspect_subject`, `export_subject`, and `erase_subject` use the GSI2 subject index and paginate. They are dispatched only through `index.py::_handle_internal` for `privacy/inspect`, `privacy/export`, and `privacy/erase`; there are no API Gateway privacy routes.
- **Internal authorization exists, with a constrained trust model:** `_require_privacy_auth` checks configured project, `authorized`, action-specific permission and constant-time comparison of `authContext.internal_token` with the configured provider secret. Direct invocation is protected by the caller's `lambda:InvokeFunction` IAM permission; the provider's handler does not itself derive an AWS caller principal from the invoke event. The invoker must protect both IAM grant and token and construct the context server-side. Current source also has a configurable secret-provider abstraction; deployment configuration is not proven by this source review.
- **Consumer isolation is available as a narrowing filter:** `identity.py::privacy_scope_consumer` reads optional `consumerId`/`consumer` from privacy context. With it, inspect/export/erase exclude other consumers and legacy items without a consumer ID; erase returns a limitation for excluded records. With no consumer scope, behavior remains deployment-wide. Thus isolation is supported when explicitly supplied, not enforced as a mandatory boundary for every internal call.
- **Preview and conditional mutation exist:** `erase_subject` defaults to `PREVIEW`; `EXECUTE` requires one of `ERASE`, `ANONYMIZE`, `RETAIN`. Writes condition on `subjectId` and, when available, `version`. Conditional conflicts are counted as `skippedRecords`.

### Unsupported delegation and reconciliation requirements

- `identity.py` explicitly lists `VERIFICATION_INTERNAL = "verified_internal_signed"` as not implemented; `VERIFIED_CONTEXTS` currently contains only `verified_jwt`. `resolve_internal_order_identity()` rejects that internal-signed context, rejects owner/actor separation without a signed proof, and enables only user owners. `docs/reports/MO-RC4-P02B-INTERNAL-IDENTITY-CONTRACT.md` says there is no internal order invoke route and delegation is blocked. Current `POST /orders` derives the subject from the provider-validated JWT; there is no trusted RIS `subjectRef` delegation input or internal create dispatch.
- Therefore RIS cannot use its service principal as though it were the data subject. Do not accept an arbitrary `subjectId`, `ownerId`, `consumerId`, or actor value from the public request body. `resolve_internal_order_identity` is a fail-closed helper, not an implemented RIS create API.
- Erase responses include a generated `operationId`, but no durable operation repository or status lookup is established by the reviewed handler/service contract. `PREVIEW` is non-mutating; `EXECUTE` is conditional/idempotent at item level, not a durable exactly-once operation. If a caller times out after some writes, a new invocation can see a reduced/empty GSI2 set and return a new response; the original operation outcome cannot be queried. The response code sets `PARTIALLY_COMPLETED` for failed/retained counts, but skipped conditional conflicts alone do not force that status. Transport success, zero matches, or a later retry therefore cannot prove the exact outcome of the prior attempt.

### Binding recommendation and minimal provider work order

**Recommendation: CHANGE REQUIRED before RIS delegated-subject coverage is supported.** Preserve the public JWT-only create path. Define one separate trusted provider-to-provider contract that binds `(provider consumer namespace, verified data subjectRef)` to an order only after validating an authenticated service context; keep actor distinct from owner. The provider must authorize the caller, enforce project/consumer scope, reject request-body spoofing, and persist the subject/GSI fields through all applicable create paths. Do not treat an IAM invoke permission alone as proof of a user's delegation; do not allow service or agent owner types by default.

For privacy invocations, retain the existing direct Lambda actions and action-specific authorization. Decide whether RIS is allowed deployment-wide scope or must always provide a bound `consumerId`; if consumer isolation is required, fail closed when scope is absent and bind it to the verified service contract, rather than trusting an arbitrary event field. Keep the secret out of public APIs/logs and use provider-supported secret configuration; the RIS caller still needs a separately scoped Lambda invoke grant and safe secret delivery.

Add durable idempotency/status reconciliation only if the provider/consumer contract requires an authoritative outcome after timeout. Minimum viable design must distinguish operation accepted/in progress/partial/completed, store/retrieve status by stable idempotency key, and reconcile per-item writes. Otherwise explicitly require caller status `UNKNOWN/RECONCILIATION_REQUIRED` on ambiguous timeout and prohibit automatic `EXECUTE` retry. No decision here selects a storage service or authorizes infrastructure.

**Minimal provider-owned files to assess:** `lambda/src/identity.py`, `lambda/src/index.py`, `lambda/src/order_service.py`, `lambda/src/validation.py`, `lambda/tests/test_identity.py`, `lambda/tests/test_index.py`, `lambda/tests/test_order_service.py`, `lambda/tests/test_ownership.py`, plus `api/endpoints.md`/internal contract documentation and relevant IAM/module input only if the approved design needs it. No file is changed in this review.

**Acceptance tests to prepare:**

1. Ordinary user POST still derives owner/subject only from verified JWT; body `subjectId`/`ownerId` spoof is rejected and existing API contract remains unchanged.
2. Trusted RIS service context binds the approved data subjectRef and correct consumer; invalid signature/audience/expiry, unknown service, wrong project, mismatched consumer, missing scope, or owner≠actor without proof fails closed.
3. Create→inspect/export/erase finds exactly the subject/consumer records; same subject in another consumer and legacy records are not exposed or mutated when scoped.
4. Internal privacy action tests require IAM-authorized invocation plus correct project, action permission and secret; unknown actions and incorrect/missing auth fail closed. Assert no public privacy route.
5. Preview performs no writes. Execute without explicit policy blocks. ERASE/ANONYMIZE/RETAIN counts reconcile with full item state; races, conditional skips, provider errors and partial writes produce explicit outcomes.
6. Inject timeout after zero, one and all item mutations; test stable-key retry/status reconciliation if implemented. Otherwise assert caller-facing unknown state and no claim that a fresh empty query proves the original execution completed.

## 2. CR-MO-PRIVACY-ANONYMIZE-COVERAGE-02

### Current behavior and residual fields

In current `lambda/src/order_service.py::erase_subject`, `ANONYMIZE` sets `customer.name` and `customer.email` to fixed values and removes `subjectId`, `gsi2pk`, `gsi2sk`, top-level `result`, `processingError`, `processingAttemptId`, `gsi3pk`, `gsi3sk`, and `orderDescription`, with a conditional subject/version update.

It **does not remove or inspect** the embedded `agentOrder` object. AgentOrder is user-provided at creation and may contain arbitrary request fields; the provider cannot assert it is free of personal data. The same update leaves `consumerId`, `ownerType`, `ownerId`, `actorType`, `actorId`, `identityVersion`, and `identityVerification` (and ordinary order/business fields such as order ID, items, amounts and timestamps). Some are identity/linkage fields; others may be needed for provider authorization, audit, accounting, or order integrity. The code does not classify their residual risk or prove the complete item anonymous.

Thus `ANONYMIZE` is a specific provider mutation profile, not a guarantee that every potentially identifying/custom field is removed or that a record is legally anonymous. RIS's requested embedded-AgentOrder coverage is **not currently supported**. Provider owners must decide field disposition and contract wording; legal sufficiency remains outside this review.

### Binding recommendation and minimal provider work order

**Recommendation: CHANGE REQUIRED** if provider contract is to claim AgentOrder-inclusive anonymization. Extend the provider-owned field inventory and define explicit post-ANONYMIZE residual semantics. Prefer a minimal, allowlisted update that removes the full `agentOrder` payload (or replaces it only with an approved non-identifying structural summary) and addresses remaining owner/consumer/actor identity fields consistently with authorization and retention requirements. If some fields must remain, return a documented limitation/retained category and do not label the operation complete for an exhaustive-erasure request. Preserve ordinary owner authorization behavior for still-active orders; if that cannot coexist, define an explicit terminal/tombstone state rather than silently retaining identifiers or breaking access control.

**Minimal provider-owned files to assess:** `lambda/src/order_service.py::erase_subject`, `lambda/src/order_service.py` export/inspect projections if category reporting changes, `lambda/tests/test_order_service.py` processing/anonymize coverage, `lambda/tests/test_ownership.py` if owner access semantics change, and provider data/privacy contract/report docs. No RIS workaround and no provider edit is made here.

**Acceptance tests to prepare:**

1. Seed synthetic nested AgentOrder values with identifying free text in supported fields; execute ANONYMIZE and assert the complete resulting item contains no original AgentOrder payload (or matches the explicitly approved residual summary).
2. Assert customer, description, result/error/attempt, subject/GSI2, GSI3 and every owner/consumer/actor/identity attribute against the approved residual-field matrix—not merely that `update_item` was called.
3. Verify anonymization removes the subject from inspect/export and cannot be reversed by result/dispatch/status updates; retries remain safe and version/subject conditions remain effective.
4. Verify provider consumer scope excludes foreign-consumer and legacy rows; any retained/excluded records or field-level limitations are surfaced in status/counts, never counted as erased.
5. Preserve public order projections and owner authorization for remaining active records, or test the approved terminal/tombstone behavior; no cross-consumer access regression.

## Evidence reused and limits

Provider source: `lambda/src/identity.py`, `lambda/src/index.py`, `lambda/src/order_service.py`, `lambda/src/secret_provider.py`, `lambda/src/validation.py`. Original tests: `lambda/tests/test_identity.py`, `test_index.py`, `test_order_service.py`, `test_ownership.py`. Reports: `MAYS-ORDERS-DSGVO-PRIVACY-CAPABILITY-01.md`, `...-CORE-01.md`, `...-ERASURE-01.md`, `...-EXPORT-01.md`, `...-INTEGRATION-01.md`, `MO-RC4-P02B-INTERNAL-IDENTITY-CONTRACT.md`, `MAYS-ORDERS-PRIVACY-SECRET-E2E-01.md`, `MAYS-ORDERS-PRIVACY-FINAL-E2E-ACCEPTANCE-01.md`, `MAYS-ORDERS-PRIVACY-FINAL-EVIDENCE-AND-DESTROY-01.md`, and `MO-ORDER-ERASURE-LEDGER-P3E-01.md`.

The identity report explicitly records signed internal delegation as not implemented and consumer scope as optional. The erasure-ledger report records operation outcomes as non-persistent, no automatic retry/resume, and restore-resurrection limitations. The historical secret E2E used an ephemeral secret that was removed; later historical acceptance refers to a test environment and does not prove the configuration of any current deployment. Reports and original test source were reviewed; **no test was run for this response**.

## Final status

`MO PRIVACY PROVIDER CONTRACT RESPONSE READY` — both requests receive a provider-owned recommendation and minimal acceptance plan. CR-01 has existing privacy calls but requires a trusted delegation/mandatory-scope contract before RIS service-subject linkage is supported. CR-02 requires provider field-contract work before claiming AgentOrder-inclusive anonymization. These are review findings, not implementation authorization, legal conclusions, deployment evidence, or approval to change the independent public provider contract.
