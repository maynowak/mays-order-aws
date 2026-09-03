# Terraform Cost/Resource Policy Gate — Initial Implementation

**Project:** May's Orders  
**Date:** 2026-09-03  
**Status:** Implemented; live Terraform plan execution still required.

## Purpose

The gate validates a Terraform JSON plan before `terraform apply`. It enforces concrete project/resource governance limits without attempting to replace AWS IAM authorization or calculate an exact AWS bill.

## Files

- `terraform/policy/resource-policy.json` — declarative policy limits.
- `terraform/policy/validate-plan.py` — plan validator; exit code `0` = PASS, `1` = FAIL, `2` = gate/configuration error.

## Current rules

- AWS region: `eu-central-*`.
- Developer environment: `Development`; `Production` is rejected.
- Required tags on resources exposing Terraform `tags`: `Project`, `Maker`, `Environment`.
- `Project` must equal `mays-orders` for the current project policy.
- EC2: `t3.micro`, `t3.small`, `t2.micro`, `t2.small`; maximum 4 instances; EBS maximum 20 GiB policy value retained for future EC2 checks.
- Lambda runtime: `python3.14`; timeout maximum 10 seconds; Lambda log retention maximum 7 days.
- DynamoDB: `PAY_PER_REQUEST` only.
- S3: project namespace plus public-access block and server-side encryption checks.
- CloudTrail: multi-region, global service events, and log-file validation required.
- Unknown AWS resource types are rejected by the allow-list.
- Budget alarm remains monitoring; this gate is not an exact billing calculator.

## Important current-project finding

The current Terraform provider already supplies `Project` and `Maker` through `default_tags`, while `Environment` is not currently a root default tag. Therefore, the first real Terraform plan may fail the gate for missing `Environment` on taggable resources. This is intentional: the gate exposes the governance gap instead of silently inventing a value.

## Execution

```bash
terraform plan -out=tfplan
terraform show -json tfplan > tfplan.json
python3 policy/validate-plan.py tfplan.json
```

Only a `PASS` result should permit the governed apply workflow. An AWS `AccessDenied` during apply remains a separate target-environment capability/authorization finding.

## Next governance step

Run the gate against the actual current Terraform plan. Review every finding, especially required `Environment` tags and any resource type/attribute that the real plan exposes. Do not weaken the gate merely to make the current plan pass; resolve genuine project configuration gaps or document an explicit governance exception.
