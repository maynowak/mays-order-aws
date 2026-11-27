# MO-RC4-RIS-COMPATIBILITY-FIX-01 — Progress

Status: **IN PROGRESS**

## Baseline and reconciliation (Step 0)

- Mays repository: `https://github.com/maynowak/mays-order-aws.git`.
- Current `origin/main`: `8830da290e2960c1f319fb0a2b4a6724d00cbafd`.
- RC4 annotated tag object: `79628819717e4609d828581dff53055f2b32f8ec`;
  peeled commit: `5bc154e079b4d7ee9eedbbf5b45b1ecca5c35420`.
- New work branch: `feature/mo-rc4-ris-compatibility-fix-01`, created from
  current `origin/main`; no tag mutation.
- RIS evidence source: branch `feature/ris-analysis-integration-07`, exact HEAD
  `9e1cff4f392410de887ddef10e86edc9008d2bdb`, report run `45966656833`.
- Separate worktree used because the pre-existing canonical Mays worktree had
  unrelated changes in `ci/pipeline/.terraform.lock.hcl` and `docs/AI_AUDITLOG.md`.
  Those changes remain untouched.

### Existing fixes found (reuse; do not duplicate)

| Issue | Verified implementation | State on main at baseline |
|---|---|---|
| Strict `orderDescription` create/persist/read/privacy contract | `80a84ca`; `lambda/src/validation.py`, `order_service.py`, `order_types.py`; 16 tests in `lambda/tests/test_order_description.py` | Present and verified: focused suite 16/16 PASS |
| Dispatch/result producer-consumer and transport infrastructure | Existing feature line through `db4f9e7`; modules include `dispatch.py`, `result_envelope.py`, `result_handler.py`, `result_consumer.py`, `agent_order.py` | Not yet integrated in main |
| `orders-service` Terraform generation/manifest | `570bbe7` (full source SHA and valid variable/module selection contract) | Not yet integrated in main |
| Transport module selection in preset/custom builds | `386d741` | Not yet integrated in main |
| Optional permission boundary for result consumer | `ceebc374e35132ee45613b9637909a5b9e77992a` | Not yet integrated in main |
| Result envelope message identity and batch failure signaling | `b83f130` | Included in later source feature line; retain and re-test |

The source candidate must combine these verified changes against current
`origin/main`, preserve all 440 RC4 Lambda originals and other current tests,
and resolve any conflicts without regressing current-main security/privacy,
installer, or lifecycle behavior. The `db4f9e7` test count is not used to delete
or replace main's original tests.

## Progress

- Step 0 complete: origin refs fetched, main advanced from local `1eaa14e` to
  `8830da2`, RC4 tag verified, later fix branches inspected, candidate base
  selected. No source edits yet.
- `lambda/tests/test_order_description.py`: 16 tests PASS on baseline main
  using Python 3.15.0. This confirms that issue is already fixed on main.
- Steps 1–8 pending: candidate source integration, original/builder/installer
  and generated Terraform tests, RIS XRepo QA, provenance, handoff, and reports.
- Safety: no AWS access or mutations, LIVE remains locked, no Terraform plan,
  no pin/install, no redrive/order/workitem/data repair; RIS repository untouched.

Next: commit/push Step 0 reconciliation evidence, then integrate the already
verified source/builder fixes onto this branch and run their existing tests.
