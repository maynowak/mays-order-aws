# MO-RIS-MODULE-VERSION-07 — CONSOLIDATED BUILD / INTEGRATION PROOF

**Status: BUILD / INTEGRATION PROVEN — PIN DECISION STILL OPEN**

- Consolidated branch: `integration/mo-ris-module-version-07`
- Proven code commit: **`386d741`**
- Base: `016cdfd` (Mays-Orders agent-transport line)
- RIS builder portability: `cce4cf5` (`fix/ris-module-builder-portability-07d`)
- No main merge, Terraform plan/apply, AWS mutation or deployment.

## 1. Consolidated version

The build/integration-proven Mays-Orders version is:

```
386d741  fix(module-builder): keep agent transport contract in preset and custom selection
         base: 016cdfd
```

It contains:

- the agent-transport/result-consumer line of `016cdfd`;
- Agent A's preset/custom contract fix;
- no generated files, no pin change, no SQS policy change.

The branch `integration/mo-ris-module-version-07` is this version plus this
evidence report.

## 2. What was proven

| Check | Result |
| --- | --- |
| Module-builder tests | **94 PASS** |
| Lambda unit tests | PASS (Agent A evidence) |
| Installer tests | **81 PASS** (Agent A evidence) |
| `complete` preset generated | fmt/init/validate **PASS** |
| Full custom selection generated | fmt/init/validate **PASS** |
| `orders-service` preset generated | fmt/init/validate **PASS** |
| RIS transport-output injection | **PASS** (3 outputs) |
| Generated module + RIS injection + `terraform validate` | **PASS** |
| RIS contract audit | 8 inputs / 23 outputs / no wildcard SQS document |

The generated `orders-service` module has:

- `enable_agent_transport`
- `ris_result_producer_role_arns`
- `lambda_execution_boundary`
- `agent_transport` Terraform module
- 23 outputs after RIS transport injection
- no `path.root`, no provider/terraform block in the module
- no wildcard SQS document

This is the version that can actually be built through the RIS module-builder
contract.

## 3. Why B is not merged into this version

Agent B's `570bbe7` fixes the **main** line, where the orders-service preset
was missing `deployment_version` and SQS variables. It is necessary there.

A direct A+B merge was tested on this branch and rejected:

- B's five contract variables are not used by the `016cdfd` root wiring;
- the builder's fail-closed exact-contract audit aborts with:
  `im Vertrag, aber nicht verwendet: deployment_version, sqs_*`;
- the trial branch was reset to `386d741`; no half-merged code was kept.

Therefore B remains a separate main-line fix (`570bbe7`), not part of the
016cdfd build-proven version.

## 4. Related proven branches

| Branch | Commit | Proof |
| --- | --- | --- |
| A `fix/mo-module-builder-preset-07a` | `386d741` | presets/custom, 94 tests |
| B `fix/mo-orders-service-terraform-07b` | `570bbe7` | main orders-service fix, 134 tests |
| C `integration/mo-ris-module-contract-07c` | `f85071d` (code `b161b18`) | main + B + transferable A; 136 tests; all presets validate; **no agent transport** |
| D RIS `fix/ris-module-builder-portability-07d` | `e237b45` (code `cce4cf5`) | Linux builder, 16 new tests, real 016cdfd build/validate |

## 5. What is still not proven / open

This consolidated version is **not a final RIS pin**:

1. It is based on `016cdfd`, not main; it does not contain main's later
   IAM-portability and SQS/F-03 changes.
2. Live `ris-dev-mays-orders-orders-queue` has a wildcard-principal policy.
   A plan from this line would change the queue policy; no policy decision has
   been made.
3. The RIS root still needs a full generated-module rebuild and root validate
   against the intended baseline.
4. Lambda/API contract merge from `016cdfd` into main (`agent_transport`,
   result consumer, gsi/apply_result/HMAC) remains a separate scoped decision.
5. No Terraform plan/apply or synthetic E2E.

## 6. Recommendation

Use **`386d741`** as the consolidated, build-proven Mays-Orders version for the
RIS line. Do **not** update the RIS pin or produce a plan until:

- the SQS/IAM policy decision is made;
- the main-line IAM fixes are reconciled or explicitly accepted;
- the RIS builder generates this module and the RIS root validates;
- Privacy/Legal and deployment approvals are recorded.

**BUILD / INTEGRATION PROVEN — PIN DECISION OPEN**
