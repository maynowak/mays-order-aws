# Glossary — May's Orders

> **Quelle:** `presentation/friday-review-prep.md` (Abschnitt: DIE 10 WICHTIGSTEN BEGRIFFE)
> **Zweck:** Zentrale Begriffsdefinitionen für Prüfung und Referenz
> **Navigation:** Questions → `presentation/friday-review-prep.md` | Answers → `docs/learning/exam-answers.md` | Traceability → `docs/learning/requirements-traceability.md` | Future Extensions → `docs/roadmap/future-extensions.md`

---

## Die 10 wichtigsten Begriffe

| # | Begriff | Definition | AWS-Konzept | May's Orders Bezug |
|---|---------|------------|-------------|---------------------|
| 1 | **Serverless** | Keine Server-Verwaltung, Pay-per-use, auto-scaling (Lambda, API GW, DynamoDB). | Serverless Computing | Kernarchitektur (ADR-001) |
| 2 | **API Gateway** | Verwalteter HTTP-Eingang, JWT-Validierung, HTTP API V2. | API Gateway V2 (HTTP API) | `terraform/main.tf:197` |
| 3 | **Lambda** | Serverless Compute, Python 3.14, Business-Logik, stateless. | AWS Lambda (Python 3.14) | `lambda/src/index.py` |
| 4 | **DynamoDB** | Managed NoSQL, Single-Table, On-Demand, GSI1. | DynamoDB (On-Demand) | `terraform/main.tf:22`, `database/dynamodb-design.md` |
| 5 | **GSI** | Global Secondary Index für effizientes Listing (Query statt Scan). | DynamoDB Global Secondary Index | `database/access-patterns.md` AP3 |
| 6 | **JWT** | JSON Web Token, signiert, Claims, von API-GW-Authorizer geprüft. | JWT (JSON Web Token) | `security/authentication-decision.md` |
| 7 | **IAM** | Service-Berechtigungen (Lambda→DynamoDB), Least Privilege. | IAM Roles & Policies | `security/iam-design.md`, `terraform/main.tf:81-118` |
| 8 | **State Transition** | Erlaubte/verbotene Statusübergänge in einer Transitionstabelle. | State Machine | `lambda/src/state_machine.py`, `order-lifecycle/transition-rules.md` |
| 9 | **Conditional Write** | Atomarer Schutz gegen konkurrierende Updates (`status = :current`). | DynamoDB Conditional Write | `lambda/src/order_service.py`, `reliability/consistency-and-failure-handling.md` |
| 10 | **Infrastructure as Code (IaC)** | AWS-Infrastruktur als Terraform-Code, reproduzierbar. | Terraform / IaC | `terraform/`, `docs/features/F011-terraform-infrastructure.md` |

---

## Erweiterte Begriffsliste

| Begriff | Definition | AWS-Service | Referenz |
|---------|------------|-------------|----------|
| **API Gateway V2 (HTTP API)** | Verwalteter HTTP-Einstiegspunkt, JWT-Validierung, günstiger als REST API | API Gateway V2 | `terraform/main.tf:197`, ADR-004 |
| **Lambda Function** | Serverless Compute, Python 3.14, stateless, Pay-per-use | AWS Lambda | `terraform/main.tf:125`, `lambda/src/index.py` |
| **DynamoDB On-Demand** | Managed NoSQL, automatische Skalierung, Pay-per-Request | DynamoDB | `terraform/main.tf:22`, ADR-007 |
| **Single-Table Design** | Ein-Tabelle-Design für alle Entitäten (PK/SK + GSI) | DynamoDB | `database/dynamodb-design.md` |
| **GSI1 (Global Secondary Index)** | `gsi1pk=LIST`, `gsi1sk=createdAt` → Listing aller Orders absteigend | DynamoDB GSI | `database/access-patterns.md` AP3 |
| **Conditional Write** | Atomare Updates mit `ConditionExpression` (`status = :current`) | DynamoDB | `lambda/src/order_service.py` |
| **ConditionalCheckFailedException** | Exception bei fehlgeschlagenem Conditional Write → 409 CONFLICTED_UPDATE | DynamoDB | `lambda/src/order_service.py` |
| **Optimistic Locking (version)** | `version`-Feld wird bei AP4 inkrementiert, zusätzliche Sicherheit | DynamoDB | `database/dynamodb-design.md` |
| **Cognito User Pool** | Verwalteter Benutzer-Store, JWT-Ausstellung, Gruppe `staff` | Amazon Cognito | `security/authentication-decision.md` |
| **Cognito App Client** | Public Client, `USER_PASSWORD_AUTH` + `REFRESH_TOKEN_AUTH`, kein Secret | Cognito | `terraform/main.tf` (Cognito) |
| **JWT Authorizer** | API-GW-Authorizer prüft JWT (Signatur, Ablauf, Issuer, Audience) | API Gateway | `terraform/main.tf` (Authorizer) |
| **IAM Role / Trust Policy** | `lambda.amazonaws.com` darf Rolle annehmen | IAM | `terraform/main.tf:81-118` |
| **Inline Policy** | Least Privilege: `PutItem`, `GetItem`, `UpdateItem`, `Query`, `logs:*` | IAM | `security/iam-design.md` |
| **Lambda Permission** | `apigateway.amazonaws.com` darf Lambda aufrufen, `source_arn` eng | Lambda | `terraform/main.tf:273` |
| **CloudWatch Log Group** | `/aws/lambda/mays-orders-handler`, Retention 7 Tage | CloudWatch Logs | `terraform/monitoring.tf` |
| **CloudWatch Metrics** | Echte AWS-Metriken: API GW (Count, 4XX, 5XX), Lambda (Invocations, Errors, Duration, Throttles, ConcurrentExecutions), DynamoDB (ThrottledRequests, ConditionalCheckFailedRequests) | CloudWatch | `terraform/monitoring.tf` |
| **CloudWatch Alarms** | 6 Alarme: api-5xx, api-4xx, lambda-errors, lambda-duration, lambda-throttles, dynamodb-throttled | CloudWatch | `terraform/monitoring.tf` |
| **CloudWatch Dashboard** | `mays-orders-overview`: SYSTEM HEALTH, ORDER OPERATIONS, ERROR ANALYSIS | CloudWatch | `terraform/monitoring.tf` |
| **Terraform State** | Quelle der Wahrheit, speichert Ressourcen-Adressen | Terraform | `terraform/README.md` |
| **IaC (Infrastructure as Code)** | Infrastruktur als Code, versionierbar, reviewbar, reproduzierbar | Terraform | `terraform/README.md` |
| **ADR (Architecture Decision Record)** | Dokumentierte Architekturentscheidungen (ADR-001 bis ADR-007) | Architektur | `architecture/architecture-decisions.md` |
| **State Machine** | Zustandsmodell für Order Lifecycle (Transitionstabelle) | Applikation | `lambda/src/state_machine.py` |
| **Conditional Write** | Atomare DB-Updates mit `ConditionExpression` (`status = :current`) | DynamoDB | `order_service.py`, `reliability/consistency-and-failure-handling.md` |
| **Optimistic Locking (version)** | `version`-Feld inkrementiert bei AP4, Reserve für Concurrency | DynamoDB | `database/dynamodb-design.md` |
| **Hot Partition (GSI1)** | Partition `LIST` konstant → theoretisches Skalierungslimit | DynamoDB | `database/dynamodb-design.md` §6 |
| **IaC** | Infrastructure as Code — Infrastruktur als Code, reproduzierbar, versionierbar | Terraform | `terraform/README.md` |
| **ADR** | Architecture Decision Record — dokumentierte Architekturentscheidungen | Architektur | `architecture/architecture-decisions.md` |
| **Well-Architected Framework** | AWS Framework: Operational Excellence, Security, Reliability, Performance Efficiency, Cost Optimization | AWS | `docs/reports/four-week-plan.md` |

---

## Status-Legende

| Status | Bedeutung |
|--------|-----------|
| **IMPLEMENTED** | Code/IaC vorhanden, lokal getestet/validiert |
| **VALIDATED** | fmt/validate/plan erfolgreich |
| **DOCUMENTED** | In Dokumentation erfasst (ADR, Design-Docs) |
| **NOT VERIFIED / NOT RUN** | Nicht in AWS live getestet (kein apply) |
| **PLANNED** | Geplant für spätere Phase (z. B. W4) |

---

*Stand: 2026-08-20 — entspricht Repo-Stand (main, HEAD `ec831d9`).*