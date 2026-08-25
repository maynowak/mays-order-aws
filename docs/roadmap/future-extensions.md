# Future Extensions / Roadmap — May's Orders

> **Quelle:** `presentation/friday-review-prep.md` (Abschnitt 7)
> **Zweck:** Roadmap / Future Extensions — NICHT aktueller Prüfungsstand
> **Navigation:** Questions → `presentation/friday-review-prep.md` | Answers → `docs/learning/exam-answers.md` | Traceability → `docs/learning/requirements-traceability.md` | Glossary → `docs/learning/glossary.md`

---

## Future Extensions / Portfolio

> **FUTURE EXTENSION — NICHT AKTUELLER PRÜFUNGSSTAND.** Nur als Ausblick, klar getrennt.

---

## Geplante Erweiterungen

### 1. Shopping-Seite / Web-Client
- **Status:** Planned
- **Beschreibung:** Frontend für Endkunden (aktuell: nur Backend-API)
- **Abhängigkeit:** Authentication (Cognito Hosted UI oder Custom UI)
- **Referenz:** `architecture/architecture-decisions.md` (ADR-006)

---

### 2. SQS Fulfillment
- **Status:** Planned (bewusst ausgeschlossen in ADR-006)
- **Beschreibung:** Asynchrone Auftragsverarbeitung via SQS Queue + Worker
- **Begründung:** In ADR-006 bewusst ausgeschlossen (Scope-Reduktion)
- **Referenz:** `architecture/architecture-decisions.md` (ADR-006)

---

### 3. Worker / Langläufer
- **Status:** Planned
- **Beschreibung:** Langlaufende Prozesse (z. B. Versand-Integration, Reporting)
- **Option:** Step Functions als Migration (ADR-005)
- **Referenz:** `architecture/architecture-decisions.md` (ADR-005)

---

### 4. ECS / Fargate
- **Status:** Planned (conditional)
- **Beschreibung:** Nur falls spezialisierte Container-Last entsteht (aktuell Overkill)
- **Bedingung:** Falls spezialisierte Worker benötigt werden (z. B. ML, Reporting)
- **Referenz:** `architecture/architecture-decisions.md` (ADR-005)

---

### 5. SNS (Alarm-Benachrichtigung)
- **Status:** Planned
- **Beschreibung:** SNS-Topic für Alarm-Benachrichtigungen (E-Mail, SMS, Slack)
- **Status in T011-11:** Bewusst ohne SNS-Topic (kostenbewusst)
- **Referenz:** `terraform/monitoring.tf`, `monitoring/monitoring-design.md`

---

### 6. Customer Notifications
- **Status:** Planned
- **Beschreibung:** E-Mail/SMS bei Statuswechsel (Bestellbestätigung, Versand, Lieferung)
- **Technologie:** SES + Lambda + EventBridge / SNS

---

### 3. Inventory Management
- **Status:** Planned
- **Beschreibung:** Produktbestände, Abgleich mit Order-Items, Lagerbestands-Prüfung bei Create
- **Erweiterung:** Separate Inventory-Tabelle oder Integration in Orders

---

### 4. Reorder Flow
- **Status:** Planned
- **Beschreibung:** Wiederkauf-Flow (One-Click Reorder), Bestellhistorie nutzen

---

### 4. Business Metrics
- **Status:** GAP / PLANNED
- **Beschreibung:** Orders Created / by Status / Success Rate
- **Status in T011-11:** Business-Metriken bewusst NICHT als Custom Metrics implementiert
- **Datenquelle später:** DynamoDB/Order-Daten via Lambda oder DynamoDB (`createdAt`, `updatedAt`, `status`, `totalAmount`)
- **Erste Auswertung:** Query auf GSI1 (`gsi1pk=LIST`, `gsi1sk=createdAt`) oder Lambda-Metric-Logger
- **Referenz:** `monitoring/monitoring-design.md` §9, `docs/reports/T011-11-CLOUDWATCH-MONITORING.md`

---

### 4. Späte Stornierung / Retoure
- **Status:** Planned (aus Scope genommen)
- **Beschreibung:** Separater Rückabwicklungs-Prozess (Retouren, Refunds)
- **Status:** Aus aktuellem Scope genommen

---

## Migration Pfade (ADR-005)

| Auslöser | Migration | Technologie |
|----------|-----------|-------------|
| Langlaufende Prozesse (>15 min) | Step Functions | AWS Step Functions |
| Container-Last | ECS/Fargate | AWS ECS/Fargate |
| Hot Partition (GSI1) | GSI Sharding | DynamoDB |
| Hohe Concurrency | Reserved Concurrency | Lambda |

---

## Priorisierung

| Priorität | Extension | Begründung |
|-----------|-----------|------------|
| Hoch | Business Metrics | Monitoring-Lücke (T011-11 GAP) |
| Hoch | SNS Notifications | Operations-Reife |
| Mittel | SQS Fulfillment | Skalierbarkeit Order Processing |
| Niedrig | Web Client | Frontend separat (separates Repo) |
| Niedrig | ECS/Fargate | Nur bei Bedarf (Worker) |

---

## Referenzen

| Dokument | Pfad |
|----------|------|
| Architecture Decisions | `architecture/architecture-decisions.md` |
| Monitoring Design | `monitoring/monitoring-design.md` |
| Cost Analysis | `cost/cost-analysis.md` |
| Reliability Design | `reliability/consistency-and-failure-handling.md` |
| T011-11 Report | `docs/reports/T011-11-CLOUDWATCH-MONITORING.md` |
| ADR-005 (Migration) | `architecture/architecture-decisions.md` (ADR-005) |
| ADR-006 (Scope) | `architecture/architecture-decisions.md` (ADR-006) |

---

## Wichtige Hinweise

> **Diese Extensions sind NICHT Teil des aktuellen Prüfungsstands (T011-12).**
> Sie dienen als Portfolio-Ausblick und Roadmap-Dokumentation.
> Keine dieser Extensions ist implementiert oder validiert.

> **T011-12 Scope:** Core Backend (Lambda, API GW, DynamoDB, Cognito, IAM, CloudWatch, Terraform).
> Alles darüber hinaus ist Future Work.

---

*Stand: 2026-08-20 — entspricht Repo-Stand (main, HEAD `ec831d9`).*