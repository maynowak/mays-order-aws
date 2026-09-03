# May's Orders — Terraform Cost/Resource Policy Gate

**Status:** Implemented — first validation version  
**Purpose:** Pre-apply governance check for Terraform plans  
**Audience:** Human Developers, AI Coding Agents, Reviewers and Security/Governance owners

## 1. Why this gate exists

The Policy Gate is a project-level safety layer between `terraform plan` and `terraform apply`.
It does **not** replace AWS IAM, Permissions Boundaries, AWS Budgets, or human approval.
It answers a narrower question:

> Does the Terraform plan stay within the resource, size, region, tagging and low-cost rules defined for May's Orders development?

The target AWS account may still reject a required operation during `apply` with `AccessDenied`.
That is intentional: AWS authorization is the final target-system capability check.

## 2. Governance layers

```text
Human / AI identity
        |
        v
IAM Identity Policy + Permissions Boundary
        |
        v
terraform validate
        |
        v
terraform plan
        |
        v
Terraform Cost/Resource Policy Gate  <-- this document
        |
        +---- FAIL -> stop; review/change plan
        |
        +---- PASS -> eligible for the next approval step
                              |
                              v
                         terraform apply
                              |
                              v
                     AWS target-system checks
                     (including AccessDenied)
```

The gate therefore must not be used as a substitute for IAM least privilege or for the account's governance controls.

## 3. Current policy

The executable policy is stored in:

`terraform/policy/resource-policy.json`

The validator is:

`terraform/policy/validate-plan.py`

Current rules are:

| Area | Development rule |
|---|---|
| Region | `eu-central-*` |
| Environment | `Development` for Developer plans; Production is not allowed |
| Required tags | `Project`, `Maker`, `Environment` on resources exposing Terraform `tags` |
| EC2 instance types | `t3.micro`, `t3.small`, `t2.micro`, `t2.small` |
| EC2 count | maximum 4 planned instances |
| EBS | maximum 20 GiB where the implemented EC2 checks expose the relevant value |
| Lambda runtime | `python3.14` |
| Lambda timeout | maximum 10 seconds |
| CloudWatch log retention | maximum 7 days |
| DynamoDB | `PAY_PER_REQUEST` only |
| S3 | project namespace, public-access block, server-side encryption |
| CloudTrail | multi-region, global service events, log-file validation |
| IAM roles | project namespace (`mays-orders-*`) |
| API Gateway | project namespace (`mays-orders-*`) |
| Cognito user pool | project namespace (`mays-orders-*`) |

### Cost model

This is deliberately a **low-cost / Free-Tier-oriented** gate. It enforces concrete resource limits rather than pretending to calculate an exact AWS bill.

The existing AWS Budget alarm remains **monitoring only**. It is not a hard deployment circuit breaker.

## 4. Required tags

The current project-level minimum is:

- `Project`
- `Maker`
- `Environment`

The broader governance model may additionally use responsibility/provenance tags such as:

- `Role`
- `Actor`
- `AIManaged`
- `ApprovalPolicy`

Those additional tags are not currently mandatory for every resource in this first gate version.

The existing Terraform provider already supplies project-wide default tags for `Project` and `Maker`. `Environment` must be explicitly supplied by the Terraform configuration for the gate to pass on resources that expose `tags`.

## 5. IAM is intentionally not pre-declared as an installation allow-list

May's Orders may need IAM resources as part of its installation.
The Policy Gate therefore does **not** attempt to predict every IAM permission the target AWS account must allow.

Instead:

1. Terraform declares the IAM resources required by the project.
2. The Policy Gate checks project-level governance constraints.
3. `terraform apply` tests whether the target AWS identity/account actually permits the requested operations.
4. An AWS `AccessDenied` is evidence of a target-system restriction, not automatically a Policy Gate defect.

This distinction is intentional and supports installation-capability discovery.

## 6. Region extension

The current allowed region pattern is defined in `terraform/policy/resource-policy.json` under:

`region.allowed_patterns`

The Human Developer Permissions Boundary has a separate region rule under `RestrictRequestedRegion`.
If a second development/test region is approved later, **both locations must be updated** and then tested.

Do not add a region merely because a service is available there; it requires an explicit governance decision.

## 7. How to run the gate

From the `terraform/` directory:

```bash
terraform validate
terraform plan -out=tfplan
terraform show -json tfplan > tfplan.json
python3 policy/validate-plan.py tfplan.json
```

Expected result:

```text
RESULT: PASS
```

or:

```text
RESULT: FAIL
```

Exit codes:

- `0` = PASS
- `1` = policy violation / FAIL
- `2` = usage, policy or plan input error

A `FAIL` must not be bypassed merely to make deployment succeed. Investigate whether the finding is a real governance violation, a project configuration problem, or an intentionally approved policy change.

## 8. AI agent rules

AI coding agents must:

1. Read this document and `terraform/policy/resource-policy.json` before changing Terraform infrastructure.
2. Never weaken or delete a Policy Gate rule solely to make a plan pass.
3. Report every Policy Gate failure explicitly.
4. Keep IAM installation requirements separate from governance assumptions.
5. Run `terraform validate` and `terraform plan` before proposing `apply`.
6. Never run `terraform apply` or `terraform destroy` without the required human authorization.
7. Update the current project report / execution log under `docs/reports/` during significant work so the state survives an IDE/agent crash.

## 9. Human Developer rules

The Human Developer may use the gate to validate a proposed infrastructure change, but the gate does not grant AWS permissions.

A passing gate means:

> The Terraform plan is compatible with the currently encoded May's Orders project governance rules.

It does **not** mean:

> AWS will necessarily allow the deployment.

AWS authorization, account restrictions, quotas and service-specific constraints are still checked during the actual deployment workflow.

## 10. Review and change control

Changes to `resource-policy.json` are governance changes, not ordinary formatting changes.
They should be reviewed and documented with:

- reason for the change,
- affected resource/rule,
- security/cost impact,
- test result,
- reviewer/approval where required.

The first version intentionally keeps the policy small and explicit. New restrictions should be added when a concrete project requirement or observed risk justifies them, not speculatively.

## 11. Known current limitations

This first version does not claim to enforce every AWS cost or security property.
In particular:

- exact AWS cost calculation is outside the gate;
- AWS Budgets remains separate monitoring;
- maximum EC2 count is checked from the Terraform plan, not as a universal AWS account quota;
- EBS size enforcement depends on the attributes exposed by the relevant planned resources;
- IAM authorization is finally determined by AWS during the operation;
- Production protection in IAM and the Policy Gate are separate layers and both should remain in place;
- the current gate only checks resources represented by its explicit rules.

These limitations are intentional and should be visible to AI agents and reviewers.
