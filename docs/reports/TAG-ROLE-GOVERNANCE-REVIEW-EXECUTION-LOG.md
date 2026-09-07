# TAG + ROLE GOVERNANCE REVIEW — Execution Log

> **Task:** Focused governance review of the tagging model and IAM identity/role model,
> BEFORE continuing with T019. ANALYSIS FIRST.
> **Mode:** READ-ONLY ANALYSIS — **no `terraform apply`/`destroy`, no commit/push.**
> **Date:** 2026-09-03

---

## 1. Start state (verified)

- Branch: `main`
- HEAD: `4c4c4c27d0847b9169654ea0db35ad805e942da1` (policy-gate commit)
- Terraform CLI v1.15.8; AWS provider `~> 6.0` (lock 6.60.0).
- Pre-existing worktree state preserved: ` D docsMaysOrdersAws.zip` (unexplained deletion),
  plus the long-standing modified/untracked set (T011–T018 docs, cloudtrail module, etc.).

## 2. Files / resources inspected (verified)

- `terraform/main.tf` (provider `default_tags`, module calls), `terraform/variables.tf`
- `terraform/modules/{dynamodb,iam,lambda,cognito,api,monitoring,cloudtrail}/main.tf` (+ variables/outputs)
- `terraform/policy/resource-policy.json`, `terraform/policy/validate-plan.py`
- `docs/TERRAFORM_POLICY_GATE.md`, `docs/reports/TERRAFORM-COST-RESOURCE-POLICY-GATE.md`
- `architecture/installation-concept.md` (§3.5), `terraform/README.md` (§9.9) — prior T018 output

## 3. Verified current tagging behavior

### Provider default tags (`terraform/main.tf:29-38`)
```hcl
default_tags {
  tags = merge({ "Project" = var.project_name, "Maker" = local.maker }, var.tags)
}
```
- `local.maker = "mays-orders"` (immutable). So `Project` + `Maker` (+ anything in `var.tags`)
  are applied to **every** tag-capable resource via the provider.

### Resource-level tags (per module)
- `dynamodb`, `iam`, `cognito`, `api`, `cloudtrail`, `lambda` (function + log group) all set
  `tags = merge({ "Project" = var.project_name }, var.tags)`.
- **`monitoring` module sets NO resource-level tags** on the dashboard or the 6 alarms (verified:
  no `tags =` line in `modules/monitoring/main.tf`). It relies solely on provider `default_tags`.
- Consistent but **redundant**: the per-module `Project = var.project_name` duplicates the
  provider `default_tags` `Project` value (same value → no conflict, but redundant).

### Current tags actually present (per resource group)

| Resource group | Explicit `tags` | `tags_all` (default_tags + explicit) |
|---|---|---|
| dynamodb, iam, cognito, api, cloudtrail, lambda | `Project` (+ `var.tags`) | `Project` + `Maker` (+ `var.tags`) |
| monitoring dashboard + 6 alarms | *(none)* | `Project` + `Maker` (+ `var.tags`) |

- `Environment` is **not defined anywhere** in Terraform.
- `Role` / `Actor` / `ApprovalPolicy` / `AIManaged` are **not defined anywhere** in Terraform.

## 4. Verified Policy Gate relationship (critical finding)

`resource-policy.json` `required_tags = ["Project", "Maker", "Environment"]`.

`validate-plan.py` reads **`resource["tags"]`** (the *explicit* tags, `get_tags` → `resource.get("tags")`),
**not** `tags_all`. Consequences:

- Provider `default_tags` values (`Project`, `Maker`) land in `tags_all`, **not** in `tags`
  → the gate does **not** see `Maker` (it is supplied only via `default_tags`).
- `Project` is seen by the gate only because each module *also* sets it explicitly — except the
  `monitoring` module, which sets nothing → the gate reports `Project` missing on alarms.
- `Environment` is required but absent → gate FAILs on every resource.

**Executed gate result (verified, exit 1):** `terraform plan -out` → `show -json` →
`validate-plan.py` produced `RESULT: FAIL` with, among others:
- `missing required tag(s): Maker, Environment` on nearly all resources;
- `missing required tag(s): Project, Maker, Environment` on `module.monitoring.aws_cloudwatch_metric_alarm.*`;
- `module.api.aws_apigatewayv2_stage.default: API Gateway name '$default' is outside the project
  namespace 'mays-orders-*'.` (stage `$default` is a fixed technical name — a gate false
  positive, not a real governance violation).

This confirms the known gap from commit `4c4c4c2`: the gate intentionally FAILs until
`Environment` is supplied cleanly or a governance exception is defined.

## 5. Verified IAM role structure

Terraform (in-repo) IAM resources — **only one role**:

| Resource | Terraform address | Actual AWS name |
|---|---|---|
| Runtime execution role | `module.iam.aws_iam_role.handler` | `mays-orders-handler-role` |
| Inline runtime policy | `module.iam.aws_iam_role_policy.handler` | `mays-orders-handler-policy` |
| Trust | `data.aws_iam_policy_document.handler_trust` | `lambda.amazonaws.com` (AssumeRole) |

- Inline policy scope (verified): `dynamodb:PutItem/GetItem/UpdateItem/Query` on table+GSI1,
  `logs:CreateLogGroup/CreateLogStream/PutLogEvents`. No `Scan/Delete/Batch`, no `iam:*`, no
  `s3:*`, **no `iam:PassRole`**, no `AdministratorAccess`.
- API→Lambda permission is a separate `aws_lambda_permission` (resource-based), not an IAM role.

The **governance identity names** in the task brief are **NOT Terraform resources** anywhere
in the repo (grep found no `.tf`/`.json` definitions):
- `MaysOrders-Terraform-Developer` (+ `-Policy`, `-Boundary`)
- `MaysOrders-Lambda-Execution`
- any AI-specific role

They exist only as **concepts** referenced in `docs/TERRAFORM_POLICY_GATE.md` and my own
T018 docs. The only name actually materialized in IaC is `mays-orders-handler-role`.

### Naming inconsistency (verified)
- Terraform runtime role: `mays-orders-handler-role` (lowercase-hyphen, "handler").
- Governance concept: `MaysOrders-Lambda-Execution` (PascalCase, "lambda-execution").
- Policy Gate `project` namespace is `mays-orders` and the IAM check requires prefix
  `mays-orders-` (case-sensitive). The Terraform name satisfies it; the PascalCase governance
  name **would not** (case mismatch).

## 6. TAG / ROLE GOVERNANCE MATRIX (tag × resource)

Legend: E = explicit resource tag; D = via provider default_tags; — = absent.

| Resource / Module | Project | Maker | Environment | Role/Actor/ApprovalPolicy/AIManaged | Notes |
|---|---|---|---|---|---|
| dynamodb table | E+D | D | — | — | redundant `Project` (E duplicates D) |
| iam role + policy | E+D | D | — | — | role is the "Runtime" identity |
| lambda function + log group | E+D | D | — | — | runtime resources |
| cognito pool/client/group | E+D | D | — | — | — |
| api (api/stage/authorizer/integration/routes/permission) | E+D | D | — | — | `aws_lambda_permission` has no tags (not tag-capable) |
| cloudtrail trail + s3 bucket (+ access/SSE/policy) | E+D | D | — | — | some S3 sub-resources not tag-capable |
| monitoring dashboard + 6 alarms | D | D | — | — | **no explicit tags** → gate reports `Project` missing |
| terraform_data seed | — | — | — | — | not tag-capable (no tags attribute) |

## 7. IDENTITY / ROLE GOVERNANCE MATRIX

| Identity / Role | In repo? | Purpose | Policy | Boundary | Role tag | Actor tag | AIManaged | ApprovalPolicy | Recommendation |
|---|---|---|---|---|---|---|---|---|---|
| Human Developer (Terraform) | concept only | deploys infra | external (not in IaC) | `MaysOrders-Terraform-Developer-Boundary` (external) | `Developer` | `HumanDeveloper` | `false` | `HumanApprovalRequired` | KEEP external; do not encode in IaC |
| AI Developer | **not present** | future agent deployment | none | none | `Developer` | `AIDeveloper` | `true` | `HumanApprovalRequired` | DEFER — no AI-specific role justified today |
| Lambda Runtime | `module.iam` | app runtime exec | inline `mays-orders-handler-policy` | none | `Runtime` | *(n/a)* | *(n/a)* | *(n/a)* | KEEP; rename is NOT justified now |
| API→Lambda invoke | `module.api` | resource-based permission | `aws_lambda_permission` | none | *(n/a)* | *(n/a)* | *(n/a)* | *(n/a)* | KEEP |

## 8. Seven-tag classification (task item 6)

| Tag | Classification | Rationale (actual project) |
|---|---|---|
| `Project` | **A — project-wide/default** | resource naming + ownership grouping; already via `default_tags` (+ redundant explicit copies). |
| `Maker` | **A — project-wide/default** | immutable provenance; already via `default_tags` only. |
| `Environment` | **A — project-wide/default** | every resource in the same env; required by gate but absent → real gap. |
| `Role` | **C — IAM/governance only** | `Developer` vs `Runtime` is meaningful only on IAM identities, NOT on app resources (a DynamoDB table's "role" is its resource type). |
| `Actor` | **C — IAM/governance only** | `HumanDeveloper` vs `AIDeveloper` describes the acting identity, not runtime resources. |
| `ApprovalPolicy` | **D — documentation/governance only** | describes the deployment approval *process*, not the resource itself; better outside resource tags. |
| `AIManaged` | **D — documentation only (needs definition)** | ambiguous: ownership vs code-generation vs deployment provenance is undefined → must be clarified by a human before tagging. |

## 9. Problems / ambiguities found

1. **`Environment` is mandatory in the gate but supplied nowhere** — the single concrete
   governance gap; every real plan FAILs (verified).
2. **Gate reads `tags`, not `tags_all`** — so `Maker` (default_tags only) is invisible to the
   gate; the gate would still report `Maker` missing even after Environment is fixed, unless the
   gate is changed to read `tags_all` or `Maker` is also set explicitly.
3. **`monitoring` module sets no explicit tags** — gate reports `Project` missing on alarms
   (integration inconsistency with every other module).
4. **API Gateway `$default` stage** trips the namespace rule (`$default` is a fixed technical
   name) — gate false positive.
5. **Naming mismatch** between Terraform runtime role (`mays-orders-handler-role`) and the
   governance concept name (`MaysOrders-Lambda-Execution`).
6. **`AIManaged` / `Actor` / `ApprovalPolicy` semantics undefined** — cannot be safely tagged
   without a human decision on what each means (ownership vs code vs deployment vs approval).
7. **No AI Developer identity exists** and the current architecture does not justify one —
   creating `MaysOrders-Terraform-AI-Developer` would add a role with no consumer.

## 10. Recommended target model

- **Keep as default (`default_tags`)**: `Project`, `Maker` (+ add `Environment` here to close the
  gap).
- **Candidate for resource-specific/announced only**: none strictly required today.
- **IAM/governance-only (defer implementation)**: `Role`, `Actor` on IAM identity resources only.
- **Documentation/governance only (do NOT tag resources)**: `ApprovalPolicy`, `AIManaged`.

## 11. What should NOT be changed

- Do **not** promote `Role`/`Actor`/`ApprovalPolicy`/`AIManaged` to mandatory tags.
- Do **not** create `MaysOrders-Terraform-AI-Developer`.
- Do **not** weaken the gate (do not delete `Environment` from `required_tags`), and do **not**
  rename the runtime role (state/migration + no benefit).
- Do **not** merge `Actor` and `AIManaged` into one tag (ambiguous).
- Do **not** modify Terraform infrastructure in this review.

## 12. KEEP / CHANGE / DEFER

**KEEP AS-IS**
- `Project`/`Maker` via `default_tags`; runtime IAM role + inline policy; Permissions Boundary
  as external optional control; gate `required_tags = [Project, Maker, Environment]`.

**CHANGE / IMPLEMENT (requires human review decision)**
- Add `Environment` (value `Development`) — smallest clean fix is a new root variable
  `environment` (default `"Development"`) merged into `default_tags`; alternatively document a
  deliberate governance exception. This closes the real gate FAIL.
- Decide whether `validate-plan.py` should read `tags_all` (to honor `default_tags`) — otherwise
  `Maker` remains invisible to the gate.

**DEFER / FUTURE GOVERNANCE**
- `Role`, `Actor`, `ApprovalPolicy`, `AIManaged` tagging (adopt only after a human defines their
  semantics and only `Role`/`Actor` on IAM identities).
- AI Developer identity/role + its Permissions Boundary.
- IAM Capability Preflight (explicitly out of scope here).

## 13. Should implementation proceed now or require human review?

**Require human review before any change.** The `Environment` gap and the `tags`-vs-`tags_all`
behavior are governance decisions (gate + tagging semantics), not ordinary fixes. The
`AIManaged`/`Actor`/`ApprovalPolicy` semantics are undefined and must be defined by the human.
No Terraform code was changed in this review.

## 14. Tests / checks performed (read-only)

- `terraform fmt -check -recursive` — PASS (no `.tf` changed).
- `terraform validate` — PASS.
- `terraform plan` — 30 to add, 0 to change, 0 to destroy (unchanged).
- `terraform plan -out -json` + `python3 policy/validate-plan.py` — **FAIL** (documented in §4).

## 15. Final state / files changed

- **Files changed: NONE** (analysis only). Only this execution log created.
- AWS changes: NONE. Git changes: NONE (no commit/push/apply/destroy).
- `docsMaysOrdersAws.zip` deletion and all unrelated work untouched.

## 16. Resume point

Governance review complete. Next step (requires human decision):
1. Decide `Environment` mechanism (add `environment` variable in `default_tags` vs governance
   exception) + whether the gate should read `tags_all`.
2. After that: **T019 — OPTIONAL FEATURES**.

---

**FILES CHANGED: NONE** (only this log)
**AWS CHANGES: NONE** · **GIT CHANGES: NONE**
**PRE-EXISTING DISCREPANCY:** `docsMaysOrdersAws.zip` deleted (unexplained, untouched)

---

# UPDATE — DECISION B (IMPLEMENTED): Policy Gate evaluates effective `tags_all`

> Human decision B already approved: the gate SHALL evaluate effective Terraform tags via
> `tags_all`, not only explicit resource `tags`. Executed 2026-09-03.

## 1. Files changed

- MOD `terraform/policy/validate-plan.py` (the only code change)
- MOD this execution log (`docs/reports/TAG-ROLE-GOVERNANCE-REVIEW-EXECUTION-LOG.md`)

## 2. Exact `tags` → `tags_all` implementation

Two minimal edits in `validate-plan.py`:

1. `get_tags()` now returns the **effective tag map**:
   ```python
   def get_tags(resource):
       # Decision B: evaluate EFFECTIVE tags (explicit + provider default_tags).
       tags = resource.get("tags_all")
       return tags if isinstance(tags, dict) else {}
   ```
   (previously: `resource.get("tags")`).

2. The tag-check guard now keys on the effective map:
   ```python
   if "tags_all" in resource:
   ```
   (previously: `if "tags" in resource:`).

No fallback to the old `tags` logic was added: the real plan JSON verifies that `tags_all` is
present on every tag-capable resource (the same 10 types expose both `tags` and `tags_all`);
non-tag-capable resources (inline IAM policy, S3 sub-resources, `aws_lambda_permission`, routes,
authorizer, integration, `terraform_data`) expose neither and are correctly skipped.

## 3. Verified plan-JSON representation (proof, not assumption)

From `terraform show -json` `resource_changes[].change.after`:

- `aws_dynamodb_table.orders`: `tags = {"Project":"mays-orders"}`, `tags_all = {"Maker":"mays-orders","Project":"mays-orders"}`
- `aws_cloudwatch_metric_alarm.api_4xx[0]` (monitoring module, no explicit tags): `tags = null`, `tags_all = {"Maker":"mays-orders","Project":"mays-orders"}`

This proves `Maker` (provider `default_tags` only) and `Project` are present in `tags_all` and
were previously invisible to the gate.

## 4. Policy Gate before / after (real plan, `validate-plan.py` on `tfplan.json`)

**BEFORE (tags):** `RESULT: FAIL` — flagged `missing required tag(s): Maker, Environment` on
nearly every resource, `Project, Maker, Environment` on monitoring alarms, plus the `$default`
stage namespace hit (12 unique resources, many duplicate errors).

**AFTER (tags_all):** `RESULT: FAIL` (still) — but ONLY because of:
- `missing required tag(s): Environment` on every tag-capable resource, and
- `module.api.aws_apigatewayv2_stage.default: API Gateway name '$default' is outside the project
  namespace 'mays-orders-*'.`

`Project` and `Maker` are no longer reported as missing anywhere (including the monitoring
alarms). The remaining failures are the *expected*, still-unresolved items by design.

## 5. Environment status — still unresolved (by design)

`Environment` is still required by `resource-policy.json` (`required_tags` includes
`Environment`) but is not supplied by any Terraform config. Not implemented here (per scope).
This is **Decision A** (the next item), not part of Decision B.

## 6. API Gateway `$default` status

Unchanged: the HTTP API `$default` stage name is a fixed technical name and still trips the
namespace rule (`mays-orders-*`). This is a separate gate behavior, not touched by Decision B;
documented as a false positive for later review.

## 7. Terraform validation / plan (read-only, re-run after change)

- `terraform validate` — PASS ("The configuration is valid.")
- `terraform plan` — **30 to add, 0 to change, 0 to destroy** (unchanged; `.py` is not `.tf`).
- `terraform show -json` — used to produce the plan JSON for the gate (see §3).

No `terraform apply`, no `terraform destroy`.

## 8. Git status / HEAD

- Branch: `main`; HEAD: `4c4c4c2`.
- New change: `M terraform/policy/validate-plan.py` (Decision B).
- Unchanged/preserved: all pre-existing modified/untracked entries, ` D docsMaysOrdersAws.zip`.

## 9. Resume point

Decision B implemented and verified. Next = **Decision A — Environment strategy** (supply
`Environment` via a root variable in `default_tags`, or define a governance exception).

---

# UPDATE — DECISION A (IMPLEMENTED): `Environment = Development` via default_tags

> Human decision confirmed: add `Environment = Development` to the provider `default_tags`
> (consistent with `Project`/`Maker`), NOT a governance exception. Executed 2026-09-03.

## 1. Files changed

- MOD `terraform/main.tf`
- MOD this execution log

## 2. Exact implementation

In `terraform/main.tf`:

1. New local constant next to `maker`:
   ```hcl
   locals {
     maker       = "mays-orders"
     environment = "Development"
   }
   ```
2. Added to provider `default_tags`:
   ```hcl
   {
     "Project"     = var.project_name
     "Maker"       = local.maker
     "Environment" = local.environment
   }
   ```
   (still `merge(..., var.tags)`, so an explicit `var.tags` override remains possible.)

## 3. Verified effective tags (proof)

From `terraform show -json` after the change:
- `aws_dynamodb_table.orders` `tags_all` = `{"Environment":"Development","Maker":"mays-orders","Project":"mays-orders"}`
- `aws_cloudwatch_metric_alarm` `tags_all` = `{"Environment":"Development","Maker":"mays-orders","Project":"mays-orders"}`

So `Environment` now propagates globally via `default_tags`, exactly like `Project`/`Maker`.

## 4. Policy Gate after Decision A + B

`validate-plan.py` on the real plan now yields a single remaining finding:

```
RESULT: FAIL
  - module.api.aws_apigatewayv2_stage.default: API Gateway name '$default' is outside the project namespace 'mays-orders-*'.
```

All tag requirements (`Project`, `Maker`, `Environment`) now pass everywhere. The only remaining
item is the **`$default` stage namespace false positive** — a fixed technical stage name, not a
real governance violation, and **not part of Decision A or B** (separate follow-up).

## 5. Terraform validation / plan

- `terraform fmt -check -recursive` — PASS
- `terraform validate` — PASS
- `terraform plan` — **30 to add, 0 to change, 0 to destroy** (tag-only change → no resource count change)

No `terraform apply`, no `terraform destroy`.

## 6. Git status / HEAD

- Branch: `main`; HEAD: `4c4c4c2`
- New changes this step: `M terraform/main.tf` (Decision A); previously `M terraform/policy/validate-plan.py` (Decision B).
- All pre-existing entries + ` D docsMaysOrdersAws.zip` preserved.

## 7. Resume point

Decision A + B complete. Next remaining governance item (separate, optional):
**`$default` stage namespace rule** in `validate-plan.py` (allow the fixed `$default` stage name
or skip namespace check for API-Gateway stages) — otherwise the gate stays FAIL on that
false positive while the tag model is now fully consistent.