# MO-RIS-MODULE-BASELINE-RECOVERY-07 — CROSS-REPOSITORY MODULE RECOVERY & INTEGRATION

**Status: BLOCKED — MODULE / IAM / TERRAFORM CONTRACT**

- Mays-Orders main: `8830da2` (unchanged)
- RIS main: `97a60df` (unchanged)
- No main merge, Terraform plan/apply, AWS mutation, deployment or live data change.
- Cross-repository integration is partially green: A/B builder fixes and D portability are ready; full agent-transport consolidation and SQS/IAM decisions remain blocked.

## 1. Branches and commits

| Agent | Repository | Branch | Commit | State |
| --- | --- | --- | --- | --- |
| A | Mays-Orders | `fix/mo-module-builder-preset-07a` | `386d741` | pushed, based on `016cdfd` |
| B | Mays-Orders | `fix/mo-orders-service-terraform-07b` | `570bbe7` | pushed, based on `main` |
| C | Mays-Orders | `integration/mo-ris-module-contract-07c` | `b161b18` | pushed, based on `main` + B + transferable A |
| D | RIS | `fix/ris-module-builder-portability-07d` | `cce4cf5` | pushed, based on `d76fb99` |

`1dbb0cb` is an **ancestor of current main** `8830da2` (0/265 divergence). The real
divergence is `main` vs `016cdfd` (21 commits unique to `016cdfd`; none in main).

## 2. Agent A — module-builder presets

Commit `386d741`, 4 files, +111/−4, only `module_builder/`.

Root cause:

- `catalog.VARIABLE_MODULES` had no bindings for `enable_agent_transport`,
  `ris_result_producer_role_arns`, or `lambda_execution_boundary`, so full
  custom selection emitted `var.*` references without declarations.
- `spec.COMPLETE_MODULES` referenced `./modules/agent_transport` but did not
  copy that directory, so the complete preset was not init-able.

Fix:

- Added the three variable bindings and the `agent_transport` module to the
  complete preset.
- Strengthened preset/custom parity to compare module directories and
  `[a-z0-9_]+` variable names.
- Added a self-contained-wiring invariant test.
- No security defaults were changed.

Verification:

- Module-builder suite: **94 PASS**.
- Generated complete and full custom modules: `fmt -check`, `init
  -backend=false`, `validate` **PASS**.
- Preset vs full custom tree differs only in project/manifest/README/blank
  lines; contracts match.

Adjacent findings, not fixed:

- `LAMBDA_ZIP_MODULES` does not include `agent_transport`; a selection that
  includes `agent_transport` without `lambda` can generate a module whose
  lambda artifact is absent. Plan/apply would fail.
- The builder test run rewrites the tracked `lambda/dist/lambda.zip`; A
  restored it before commit. This should be fixed separately (build to temp).

## 3. Agent B — orders-service preset

Commit `570bbe7`, based on main.

Root cause:

- `build_module()` filtered variables/modules through static contract lists
  without checking the actual root wiring. Post-contract root changes
  (`deployment_version`, SQS knobs, privacy module/variables) were omitted.
- The reported `deployment_version`/`sqs_max_receive_count` errors were only
  two of the missing references; `privacy_secret` and additional `sqs_*`
  variables were also missing.

Fix:

- Added the five root variables to `ORDERS_SERVICE_VARIABLES`.
- Added an explicit privacy exclusion allowlist and a fail-closed
  `_strip_out_of_contract_wiring()`.
- Added a pre-write contract audit that requires the generated `var.*`
  reference set to match exactly.
- No generated files were hand-patched; presets and security defaults remain.

Verification:

- `build --preset orders-service --validate`: **PASS**.
- `build --preset complete --validate`: **PASS**.
- Module-builder: **134 PASS** (+5 regressions); Lambda **456 PASS**;
  Installer **81 PASS**; Seed **28 PASS**; Policy **30 PASS / 1 skip**.

## 4. Agent C — module / IAM consolidation

Limited integration branch `b161b18` = main + B `570bbe7` + transferable A
`386d741`.

- B cherry-pick: clean.
- A cherry-pick: one `catalog.py` conflict; only A's transferable content was
  kept. `agent_transport` contract entries and its test were deferred because
  main has no agent-transport module.
- Tests: module-builder **136 PASS**, Lambda **456 PASS**, Installer **81
  PASS**; root fmt/validate PASS.
- Generated presets: complete **PASS**, full custom **PASS**, orders-service
  **PASS** (previously failing).

### Full consolidation blockers

1. **Agent-transport contract missing on main.** `agent_transport` module,
   `enable_agent_transport`, `ris_result_producer_role_arns`, and lambda
   `cognito_issuer`/`cognito_client_id` are absent.
   - RIS injection appends three outputs, then Terraform fails with
     `Reference to undeclared module module.agent_transport[0]` (3×).
   - RIS `apply_ris_order_dispatch_env_patch` raises because main uses
     `variables = merge(...)`, not the expected `variables = {` block.
   - That patch is also non-atomic: it writes some changes before failing.
2. **SQS policy decision.** Main keeps F-03 (no `aws_sqs_queue_policy.orders`).
   `016cdfd` has account-root policy. Live `ris-dev-mays-orders-orders-queue`
   has a wildcard-principal policy. A plan from main would DELETE the policy;
   a plan from 016cdfd would UPDATE it. This requires a separate Security/
   Release decision.
3. **Ownership index `gsi3` conflict.** Main has `gsi3` for processing claims
   (KEYS_ONLY, no PII); `016cdfd` has `gsi3` for ownership (INCLUDE
   `customer`/`totalAmount`). A merge needs `gsi4` plus a PII decision.
4. **`apply_result` write path.** Main deliberately has no write function and
   uses `RESULT_WRITE_GUARD`; `016cdfd` writes with a version guard but no
   `RESULT_WRITE_GUARD`. Needs Privacy/Security approval.
5. **Two HMAC envelope contracts.** Main allows only
   `privacy.internal.v1`; `016cdfd` adds `ORDER_RESULT`/`ORDER_FAILED` with a
   separate envelope. Needs one allowlist decision.
6. **Live provenance orphan.** RIS state contains an `agent_dispatch` IAM
   policy and wildcard queue policy that no Mays-Orders commit models. RIS
   moves the former at root; the latter is the SQS decision.
7. **Empty-principal hazard.** `agent_transport` with
   `ris_result_producer_role_arns = []` can render an empty AWS principal;
   variable validation should fail closed at plan.

## 5. Agent D — RIS builder portability

Commit `cce4cf5`.

- Replaced Windows `where` and hardcoded Git path with `shutil.which()` plus
  explicit `TERRAFORM_EXE`/`GIT_EXE` overrides and Windows fallbacks.
- Missing tools fail closed with actionable messages.
- Removed an unreachable fragment in `build_module()` that could cause a
  NameError.
- CLI parameters, pin files, generated contract and transport injection
  unchanged.
- New portability tests: 16; focused total 75 PASS; wrapper 43 PASS / 6
  pre-existing stale-fixture failures.
- Real build in `/tmp` with pin `016cdfd`: orders-service generated,
  transport injection, fmt/init/validate PASS; installed module revalidated.
- RIS full suite after D: **3417 PASS / 129 skipped / 10 failures**
  (6 wrapper stale fixtures + 3 composite + missing `lambda.zip`), no new
  failure versus the documented baseline.
- Root `terraform fmt`: PASS; root validate still fails only on the
  incomplete `mays_orders` module.

## 6. Original Mays-Orders tests

Additional suites run for the module itself:

| Suite | `1dbb0cb` | `016cdfd` | main `8830da2` |
| --- | ---: | ---: | ---: |
| Lambda | 76 PASS | 225 PASS | 456 PASS |
| Installer | 129 PASS | 129 PASS | — |
| Module builder | 90 PASS | 91 / 1 FAIL | 129 PASS |
| `scripts/tests` | 28 PASS | 28 PASS | 28 PASS |
| `cognito_backup/tests` | 2 PASS | 2 PASS | 2 PASS |
| Terraform fmt | FAIL (`main.tf`) | PASS | — |
| Terraform validate | PASS | PASS | — |
| `orders-service` build + validate | PASS | PASS | **FAIL** (before B) |
| RIS transport injection + validate | FAIL (no agent_transport) | PASS | not applicable |

The original `016cdfd` failure was:
`test_full_custom_selection_equivalent_to_complete` — missing
`enable_agent_transport`, `ris_result_producer_role_arns`,
`lambda_execution_boundary`. Agent A fixes this on the 016cdfd branch; Agent C
keeps only the transferable parity/self-containment parts on main.

## 7. RIS usage contract

RIS consumes the generated module in `terraform/main.tf` with:

- `project_name`
- `enable_agent_transport`
- `ris_result_producer_role_arns`
- `order_dispatch_queue_url`

The current main-based integration branch lacks the first two variables and
the `agent_transport` module. The RIS root therefore cannot yet consume the
new module. This is why the cross-repository gate is blocked even though A/B/D
are individually green.

## 8. Final gate

| Gate | Status |
| --- | --- |
| A — Module builder presets | PASS on `386d741`; transferable parts integrated in `b161b18` |
| B — Orders-service preset | PASS on `570bbe7`; integrated in `b161b18` |
| C — Module/IAM consolidation | **BLOCKED** — agent transport + SQS + gsi/apply/HMAC decisions |
| D — RIS builder portability | PASS on `cce4cf5` |
| Orders original tests | PASS for A/B/C scope; full agent-transport merge not attempted |
| RIS integration | **BLOCKED** — generated main module lacks agent transport; root validate impossible |
| Main merge / plan / apply / deploy | none |

**BLOCKED — MODULE / IAM / TERRAFORM CONTRACT**

## 9. Recommended next step

1. Run a separate, explicitly authorized **agent-transport consolidation** on
   a new Mays-Orders branch based on main; add the module, variables, lambda
   cognito wiring and result-consumer code, resolving `gsi3/gsi4`,
   `apply_result` and HMAC decisions with Privacy/Security.
2. Decide the SQS F-03 policy separately: delete the legacy wildcard policy
   via approved remediation, or adopt a scoped account-root policy. Do not
   let a pin update choose this implicitly.
3. Adapt the RIS builder patch to the consolidated lambda wiring (or declare
   `order_dispatch_queue_url` natively in the module) and make the patch
   atomic.
4. Rebuild `terraform/modules/mays_orders` from the new pin, run RIS root
   validate with the real module wiring, and only then prepare a pin change /
   plan on the integration branch.
5. No Terraform plan against live state, no AWS apply, no deployment and no
   main merge before those gates.

## 10. Audit

- `docs/AI_AUDITLOG.md` updated in both repositories.
- No real allowlist, secret or credential is present in this report.
