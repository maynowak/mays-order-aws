# Requirements Traceability Matrix — May's Orders

> **Quelle:** `presentation/friday-review-prep.md` (Abschnitt 6)
> **Zweck:** Requirements Traceability Matrix — 17 Business Requirements aus Ausgangsdokument
> **Navigation:** Questions → `presentation/friday-review-prep.md` | Answers → `docs/learning/exam-answers.md` | Glossary → `docs/learning/glossary.md`

---

## 17 Projektanforderungen — Lernmatrix

| # | Original Requirement (Ausgangsdokument §2) | Umsetzung | Nachweis | Status |
|---|--------------------------------------------|-----------|----------|--------|
| 1 | Allow an order to be created. | `POST /orders` → PutItem, Status PENDING | `order_service.py`, Test T-01 | IMPLEMENTED |
| 2 | Assign a unique order identifier. | `ord_` + 24 Hex (`secrets.token_hex`) | `order_service.py generate_order_id` | IMPLEMENTED |
| 3 | Store order information persistently. | DynamoDB Tabelle `mays-orders` | `terraform/main.tf:22` | IMPLEMENTED (IaC) / NOT VERIFIED |
| 4 | Allow authorized users to retrieve an order. | `GET /orders/{orderId}` (JWT) | `index.py`, Route in Terraform | IMPLEMENTED (IaC) / NOT VERIFIED |
| 5 | Allow authorized users to retrieve multiple orders. | `GET /orders` (GSI1-Query, paginiert) | `order_service.py list_orders` | IMPLEMENTED |
| 6 | Allow order status to be updated. | `PATCH /orders/{orderId}/status` | `update_order_status` | IMPLEMENTED |
| 7 | Prevent invalid order-state transitions. | State Machine + Conditional Write | `state_machine.py`, `order_service.py` | IMPLEMENTED |
| 8 | Allow appropriate orders to be cancelled. | PENDING/CONFIRMED → CANCELLED | `state_machine.py` | IMPLEMENTED |
| 9 | Validate incoming requests. | `validation.py` (strikt, unbekannte Felder abgelehnt) | Tests (19 in test_validation.py) | IMPLEMENTED |
| 10 | Handle errors gracefully. | `errors.py` (400/404/409/500, strukturiert) | `index.py fail()`, `api/endpoints.md` §3 | IMPLEMENTED |
| 11 | Automatically scale as request volume increases. | Serverless auto-scaling | ADR-001, DynamoDB On-Demand | DOCUMENTED / PLANNED (W4) |
| 12 | Avoid continuously running application servers. | Kein EC2; Lambda Pay-per-use | ADR-001, `cost/cost-analysis.md` | DOCUMENTED |
| 13 | Protect order data from unauthorized access. | Cognito JWT + IAM Least Privilege + kein direkter DB-Zugriff | `security/*` | IMPLEMENTED (IaC) / NOT VERIFIED |
| 14 | Provide logging and monitoring. | CloudWatch Logs, Metriken, 6 Alarme, Dashboard | `terraform/monitoring.tf`, T011-11 | VALIDATED (plan) / LIVE NOT RUN |
| 15 | Keep the architecture simple and cost-conscious. | HTTP API, On-Demand, keine Extra-Services | ADR-004/006, `cost/cost-analysis.md` | DOCUMENTED |
| 16 | Support infrastructure management through Terraform. | `terraform/` (main, variables, outputs, monitoring, README) | fmt/validate/plan PASS | IMPLEMENTED / VALIDATED |
| 17 | Be suitable for implementation as a small AWS project. | Fokus auf Core, kein Service-Bloat | ADR-006, README | DOCUMENTED |

---

## Legende

| Status | Bedeutung |
|--------|-----------|
| **IMPLEMENTED** | Code/IaC vorhanden, lokal getestet/validiert |
| **VALIDATED** | fmt/validate/plan erfolgreich |
| **DOCUMENTED** | In Dokumentation erfasst (ADR, Design-Docs) |
| **NOT VERIFIED / NOT RUN** | Nicht in AWS live getestet (kein apply) |
| **PLANNED** | Geplant für spätere Phase (z. B. W4) |

---

## Referenzen

| Bereich | Verweis |
|---------|---------|
| Business Requirements | `requirements/business-requirements.md` |
| Technical Requirements | `requirements/technical-requirements.md` |
| State Machine | `order-lifecycle/state-machine.md` |
| Transition Rules | `order-lifecycle/transition-rules.md` |
| DynamoDB Design | `database/dynamodb-design.md` |
| Access Patterns | `database/access-patterns.md` |
| IAM Design | `security/iam-design.md` |
| Auth Decision | `security/authentication-decision.md` |
| Architecture Decisions | `architecture/architecture-decisions.md` |
| Monitoring Design | `monitoring/monitoring-design.md` |
| Cost Analysis | `cost/cost-analysis.md` |
| Terraform Code | `terraform/` |
| Lambda Code | `lambda/src/` |

---

*Stand: 2026-08-20 — entspricht Repo-Stand (main, HEAD `ec831d9`).*