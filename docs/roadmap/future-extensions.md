# Future Extensions / Roadmap — May's Orders

> **Quelle:** `presentation/friday-review-prep.md` (Abschnitt 7)
> **Zweck:** Roadmap / Future Extensions — NICHT aktueller Prüfungsstand
> **Navigation:** Questions → `presentation/friday-review-prep.md` | Answers → `docs/learning/exam-answers.md` | Traceability → `docs/learning/requirements-traceability.md` | Glossary → `docs/learning/glossary.md`

---

## Industry-Standard Evolution

> **Zweck:** Konsolidierter Ausblick, wie der aktuelle Serverless-Prototyp zu einer
> produktions-/industrieorientierten Architektur weitergebaut und -erkundet werden kann.
> **Abgrenzung:** IMPLEMENTED NOW / DOCUMENTED-DEFERRED / PRODUCTION TARGET werden strikt
> unterschieden — hier wird **keine** bereits erbrachte Leistung behauptet.

### 1. Aktueller Prototyp (IMPLEMENTED NOW — verified)

| Baustein | Stand |
|----------|-------|
| Region | `eu-central-1` (Default `var.aws_region`) |
| Architektur | Serverless: Cognito → API Gateway (HTTP) → Lambda → DynamoDB |
| Auth | Cognito User Pool + JWT-Autorisator (`staff`-Gruppe) |
| Lambda | Order Handler, `python3.14`, `index.handler`, Least-Privilege-Rolle |
| Daten | DynamoDB Single-Table + GSI1, On-Demand (`PAY_PER_REQUEST`) |
| Observability | CloudWatch: Logs, Dashboard, 6 Alarme, Retention 7 Tage |
| Audit | CloudTrail (multi-region, Management Events) → S3-Bucket (SSE-S3) |
| IaC | Terraform, modularisiert in 6 Child Modules + Policy Gate |
| Identität | AI Developer Profil-Konzept `maysOrdersAiDeveloper` (Empfehlung) |
| Kostenprofil | `LOWEST / PROTOTYPE` (Single Region, kein VPC, kein PITR/KMS) |

> Der Prototyp ist bewusst **nicht** produktionsreif. Er ist eine cost-conscious,
> valide Serverless-Demo ohne VPC, ohne Multi-Region und ohne erweiterten Security-/DR-Umfang.

### 2. Evolutionspfade nach Themenbereich

Die Spalten trennen: **JETZT** (implementiert) / **DEFERRED** (dokumentiert, bewusst zurückgestellt)
/ **ZIEL** (Produktions-/Industrie-Ansatz).

#### 2.1 Networking
- JETZT: keine Kunden-VPC; Lambda in AWS-managed Umgebung; AWS-interne TLS/SigV4-Sprünge.
- DEFERRED/ZIEL: VPC mit Public/Private-Subnetzen, Multi-AZ, CIDR, Lambda-VPC-Integration,
  NAT/VPC-Endpoints — nur wo gerechtfertigt. → `architecture/networking.md`.

#### 2.2 Security
- JETZT: Cognito-JWT, Least-Privilege-IAM, CloudTrail Baseline, at-rest-Verschlüsselung (AWS-managed/SSE-S3).
- DEFERRED/ZIEL: feinere App-Autorisierung (Cognito-Gruppen/Claims), Customer-managed KMS,
  WAF, GuardDuty/Security Hub, stärkere CloudTrail-Kontrollen (SSE-KMS, Data Events, Lifecycle),
  Secrets-Management. → `security/`, `docs/reports/future-extensions.md` §CloudTrail Hardening.

#### 2.3 Reliability / Disaster Recovery
- JETZT: AWS-managed Multi-AZ-Services; Infrastruktur reproduzierbar via Terraform.
- DEFERRED/ZIEL: DynamoDB PITR, Backups + dokumentierte Restore-Prozedur, Multi-Region nur bei
  Datenschicht-Replikation, dokumentierte RTO/RPO. → `architecture/architecture-and-security.md` §J.

#### 2.4 Infrastructure / DevOps
- JETZT: lokaler State; manuelles `terraform validate`/`plan`; Policy Gate; menschliche Freigabe.
- DEFERRED/ZIEL: Remote-State (S3 + DynamoDB-Locking), CI/CD, automatisierte Validierung +
  Policy-Checks, Environment-Trennung, kontrollierter Deployment-Workflow. → `installation-concept.md` §7/§12.

#### 2.5 Observability
- JETZT: CloudWatch Logs/Metriken/Dashboard/6 Alarme.
- DEFERRED/ZIEL: zentralisierte Observability, Alerting/Incident-Response (SNS/EventBridge),
  Tracing/X-Ray wo gerechtfertigt. → `monitoring/monitoring-design.md`.

#### 2.6 Scalability / Cost
- JETZT: DynamoDB On-Demand; Lambda Auto-Concurrency; API GW Auto.
- DEFERRED/ZIEL: Kapazitätsstrategie (GSI-Sharding, Reserved Concurrency), Workload-Benchmarking
  (100 → 100k Orders), Kosten-Monitoring, Budgets/Alerts, Right-Sizing, Multi-Region-Kostenfolgen.
  → `cost/cost-analysis.md`, `docs/roadmap/future-extensions.md` §Migration.

#### 2.7 Application Maturity
- JETZT: 4 Endpoints, State Machine (18 Fälle), Validation, Conditional Writes, Idempotenz-Semantik, Fehler→HTTP.
- DEFERRED/ZIEL: Teststrategie-Ausbau, API-Versioning, Operational Runbooks. → `api/`, `lambda/`, `tests/`.

### 3. Prototype-Trade-offs (bewusst, keine Versehen)

Folgende Punkte sind im Profil `LOWEST / PROTOTYPE` **absichtlich zurückgestellt** —
nicht versehentlich weggelassen:

| Deferred Feature | Zusatzkomplexität |
|------------------|-------------------|
| VPC / NAT / Endpoints | Kosten, Netzwerk-Konfiguration, Wartung, zusätzliche Failure-Modes |
| Multi-Region | Komplexität, Synchronisation, Kosten (nur bei Datenschicht-Replikation sinnvoll) |
| Customer-managed KMS | Key-Management + Kosten |
| PITR / Backups | Kosten, Restore-Prozeduren, Betriebsaufwand |
| Advanced Security (WAF/GuardDuty/Security Hub) | Kosten, Konfiguration, Alerting-Zyklus |
| Remote State + CI/CD | Zusätzliche Infrastruktur (S3/DynamoDB-Lock), Pipeline-Wartung |
| Advanced Observability | Kosten, Tracing-Instrumentierung |

> Diese Services kosten **nicht immer** Geld und sind **nicht immer** erforderlich — sie werden
> erst eingeführt, wenn ein konkretes Produktions-/Compliance-Erfordernis dies rechtfertigt
> (Cost-Profile-Wechsel `LOWEST → STANDARD → HIGH AVAILABILITY`).

### 4. Build → Explore → Production → Scale

```text
Phase 1 — Prototype    install → validate → plan → Policy Gate → menschliche Freigabe → deploy/test
Phase 2 — Harden       stärkere Autorisierung, DR (PITR/Backup), Security-Hardening, Remote State, CI/CD, Observability
Phase 3 — Production   Netzwerk-Architektur (falls gerechtfertigt), Multi-AZ/Resilience, Betriebskontrollen,
                       Monitoring/Alerting, Backup/Restore, Security-Kontrollen, Cost-Governance
Phase 4 — Scale        Workload-Benchmarking, Kapazitäts-Optimierung, Regional-/Datenschicht-Strategie, Service-Evolution
```

### 5. Professor-Facing Erklärung (Monday Demo)

> "The project is intentionally implemented as a cost-conscious serverless prototype. The
> repository documents the concrete path from this prototype to a production-oriented
> architecture, including networking, security, reliability/DR, observability, infrastructure
> governance, CI/CD and scalability."

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

## CloudTrail Production Hardening (Optional Install-Mode)

> **FUTURE EXTENSION — NICHT implementiert.** Klar getrennt vom implementierten
> CloudTrail-Prototyp-Baseline (`module.cloudtrail`). Kein fehlender Kern-Scope; der
> Baseline erfüllt bereits den Audit-Grundbedarf (WHO/WHAT/WHEN/WHERE). Siehe
> `security/cloudtrail-design.md` §9.

| # | Feature | Deferral-Reason | Abhängigkeit | Reihenfolge |
|---|---------|-----------------|--------------|-------------|
| 1 | SSE-KMS | Kosten + Keys-Management | `aws_kms_key` + Key-Policy | 1 |
| 2 | DynamoDB Data Events | Event-Volumen/Kosten | `event_selector` Data-Resource | 2 |
| 3 | S3 Lifecycle/Retention | Compliance-/betriebsgetrieben | `aws_s3_bucket_lifecycle_configuration` | 3 |
| 4 | Security-Eventing (SNS/EventBridge) | Trennung Audit vs. Alarmierung | CloudTrail → EventBridge → SNS | 4 |
| 5 | MFA Delete / Log-Protection | Operative Einschränkungen (Root) | Versioning + MFA | 5 |

- **Aktivierung:** optionaler Install-Modus über Terraform-Variablen (bewusst opt-in, nicht Default).
- **Begründung:** jeweils Kosten, operative Komplexität oder fehlende konkrete Compliance-Anforderung.

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