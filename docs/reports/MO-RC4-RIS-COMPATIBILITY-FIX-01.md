# MO-RC4-RIS-COMPATIBILITY-FIX-01

Status: **IN PROGRESS — Step 0 reconciled; candidate implementation and QA pending.**

## Scope and boundaries

This work targets a new Mays-Orders upgrade candidate for the RIS reference
contract. It does not modify RIS, update the RIS module pin, install a module,
publish a release, mutate the existing RC4 tag, access AWS, run LIVE, create a
Terraform plan, or merge to main. The candidate is based on the exact current
Mays `origin/main` and is developed on
`feature/mo-rc4-ris-compatibility-fix-01`.

## Step 0 — release and branch reconciliation

| Reference | Exact identity | Finding |
|---|---|---|
| Mays `origin/main` at reconciliation | `8830da290e2960c1f319fb0a2b4a6724d00cbafd` | Chosen candidate base; fetched before branch creation |
| RC4 tag object | `79628819717e4609d828581dff53055f2b32f8ec` | Annotated tag verified; not changed |
| RC4 peeled commit | `5bc154e079b4d7ee9eedbbf5b45b1ecca5c35420` | Exact faulty release baseline |
| RIS reference | `9e1cff4f392410de887ddef10e86edc9008d2bdb` | Read-only; RIS 19F4 run `45966656833` |

The local canonical Mays worktree was on stale local `main` `1eaa14e`, behind
`origin/main`, and had unrelated modifications to
`ci/pipeline/.terraform.lock.hcl` and `docs/AI_AUDITLOG.md`. It was not switched,
reset, stashed, or edited. A separate clean worktree was created from the
current remote main as the new feature branch.

### Reconciliation of known defects

1. **`orderDescription`: already fixed on main.** Main contains commit `80a84ca`
   and `docs/features/F012-order-description.md`. It accepts the field through
   a strict allowlist, trims/validates up to 1,024 characters, persists and
   returns it in the create/detail contract, and preserves privacy behavior.
   Unknown fields remain rejected. Baseline `lambda/tests/test_order_description.py`
   passed all 16 tests on 2026-11-27. This work will reuse and regression-test
   the implementation; no duplicate fix is planned.
2. **Transport and consumer:** the verified feature line ending at
   `db4f9e79980443de1cd3d5b688a33c0cf0eb771f` contains the required dispatch,
   envelope, result-handler/consumer, agent-order, and Terraform transport
   components. These are absent from the exact RC4 commit. They will be
   integrated as Mays-owned source, preserving strict HMAC, idempotency, and
   owner/tenant boundaries.
3. **Generated Terraform:** verified fix `570bbe7ba14e0e5379aed9c086138b5cd272b1da`
   repairs the `orders-service` selection and stale privacy module references;
   its builder uses the full `git rev-parse HEAD` source SHA. The separate
   verified `386d74169aa567a1e7c2f0aef4c602695d6e755d` adds the agent transport
   contract to preset/custom selection. `ceebc374e35132ee45613b9637909a5b9e77992a`
   corrects the optional result-consumer permission boundary. These are not on
   current main and require integration plus fresh verification together.
4. **Original test preservation:** current main is the compatibility-fix base.
   No test will be removed, skipped, or weakened to match the older integrated
   source's smaller Lambda test inventory. Baseline RC4 Lambda count was 440;
   candidate totals may increase.

## Step 0 test

- `lambda/tests/test_order_description.py`: **16 passed** on baseline main.
- Other test groups: not run yet.
- Terraform: not initialized or validated yet.

## Checkpoints

- Step 0 report/progress checkpoint: commit and push pending.
- Steps 1–8: not started. This report will record exact commit SHAs, source
  provenance, actual test results, immutable candidate identity proposal, and
  final gates only after those checks execute.
