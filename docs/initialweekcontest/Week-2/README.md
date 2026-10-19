# Week 2 — Core Order Management API

> **Offizieller Fokus:** Core Implementation (Terraform, Lambda, API Gateway, DynamoDB, Cognito).
> **Status:** ✅ COMPLETE (kein `apply` — reine IaC + lokale Tests)
> **Go-to-Dokument:** `docs/reports/WEEK-02.md` · `docs/PROJECT_STATUS.md`

Diese Woche hat die Kern-Implementierung als Infrastructure-as-Code geliefert:
modularisierte Terraform-Infrastruktur (6 Child Modules) und den Python-Lambda-Handler
(`python3.14`). Kein Deployment wurde durchgeführt (menschliche Freigabe erforderlich).

## Deliverables

| # | Artefakt | Ort | Status |
|---|----------|-----|--------|
| 1 | Terraform-Infrastruktur (Root + 6 Module) | [`terraform/`](../terraform/) · [`terraform/main.tf`](../terraform/main.tf) | DONE |
| 2 | DynamoDB (Single-Table + GSI1) | [`terraform/modules/dynamodb/`](../terraform/modules/dynamodb/) | DONE |
| 3 | IAM (Lambda Execution Role, Least Privilege) | [`terraform/modules/iam/`](../terraform/modules/iam/) | DONE |
| 4 | Lambda Order Handler (Python 3.14) | [`lambda/src/`](../lambda/src/) · [`lambda/build_zip.py`](../lambda/build_zip.py) | DONE |
| 5 | Cognito (User Pool + Client + Gruppe) | [`terraform/modules/cognito/`](../terraform/modules/cognito/) | DONE |
| 6 | API Gateway HTTP API + Routes + JWT Authorizer | [`terraform/modules/api/`](../terraform/modules/api/) | DONE |
| 7 | CloudWatch Monitoring (Dashboard + Alarme) | [`terraform/modules/monitoring/`](../terraform/modules/monitoring/) | DONE |
| 8 | CloudTrail Audit Layer | [`terraform/modules/cloudtrail/`](../terraform/modules/cloudtrail/) | DONE |
| 9 | DynamoDB Seed-Skripte (opt-in) | [`scripts/seed_orders.py`](../scripts/seed_orders.py) · [`database/seed/`](../database/seed/) | DONE |
| 10 | Lambda-Unit-Tests (unittest) | [`lambda/tests/`](../lambda/tests/) | DONE |
| 11 | Feature-Doku F001–F011 | [`docs/features/`](../docs/features/) | DONE |

## Validierungsnachweis

Siehe `docs/BUILD.md` und `docs/reports/WEEK-02.md` §3 (compileall, unittest, ZIP-Build,
Terraform validate/plan — kein `apply`).

## Wöchentlicher Nachweis

- [Weekly Report Woche 2](../docs/reports/WEEK-02.md)

## Git Checkpoint

**Tag:** `week-2-checkpoint-20260912`  
**Commit:** `01aee73`  
**Date:** September 7, 2026  
**Milestone:** Week 2 — Core Order Management API (COMPLETE)

To explore this exact historical state:

```bash
git checkout week-2-checkpoint-20260912
```

At this checkpoint, the core infrastructure was implemented:
- Terraform modules for DynamoDB, IAM, Lambda, Cognito, API Gateway
- CloudWatch monitoring and CloudTrail audit layer
- Python 3.14 Lambda handler with unit tests
- Seed scripts for test data (opt-in)
- All configurations tested but no `terraform apply` executed