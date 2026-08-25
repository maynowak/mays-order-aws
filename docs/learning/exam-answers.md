# Exam Answers — May's Orders

> **Quelle:** `presentation/friday-review-prep.md` (Original-Fragenliste)
> **Zweck:** Detaillierte Antworten für Lernzwecke
> **Navigation:** Fragen → `presentation/friday-review-prep.md` | Traceability → `docs/learning/requirements-traceability.md` | Glossar → `docs/learning/glossary.md`

---

## Friday Review — Week 1

### Frage 1 — What problem is OrderFlow trying to solve?
**Was will der Dozent prüfen?** Ob ich das Fachproblem (nicht nur die Technik) verstanden habe.
**Kurze Antwort:** OrderFlow ist ein kleiner Online-Händler, dessen Bestellverwaltung nicht mehr mitwächst. Ziel: Order-Backend nach AWS verlagern, Orders per API anlegen/lesen/aktualisieren, Lebenszyklus korrekt abbilden, ohne Server zu administrieren.
**Vertiefung:** Es geht um einen vollständigen Order-Lebenszyklus mit Geschäftsregeln, nicht um bloßes CRUD.
**May's Orders:** fiktiver Händler „OrderFlow GmbH", Zielbild in README.
**Projektbeleg:** `requirements/business-requirements.md`, `README.md`
**Mögliche Nachfrage:** „Was wäre ohne AWS die Alternative?" → eigener Server/App, mehr Wartung.
**Achten auf:** Lösung begründen, nicht AWS um jeden Preis verkaufen.
**Status:** DOCUMENTED

---

### Frage 2 — What are the main functional requirements?
**Was will der Dozent prüfen?** Anforderungsanalyse („was", nicht „wie").
**Kurze Antwort:** Order anlegen, eindeutige Order-ID, persistente Speicherung, Order abrufen, mehrere Orders listen, Status aktualisieren, ungültige Transitions verhindern, Storno erlauben, Eingaben validieren, Fehler sauber behandeln.
**Vertiefung:** 17 Business Requirements im Ausgangsdokument → Lernmatrix in Abschnitt 7.
**Projektbeleg:** `requirements/business-requirements.md`
**Status:** DOCUMENTED

---

### Frage 3 — What are the non-functional requirements?
**Was will der Dozent prüfen?** Qualitätsziele: Skalierbarkeit, Verfügbarkeit, Sicherheit, Performance, Reliability, Kosten.
**Kurze Antwort:** automatisch skalierend ohne Server-Management, hohe Verfügbarkeit (managed Services), kein direkter DB-Zugriff für Clients, effiziente Zugriffe, kein Überschreiben bei konkurrierenden Updates, kostenbewusst, saubere Trennung API/Business/Data.
**Projektbeleg:** `requirements/technical-requirements.md`, `reliability/consistency-and-failure-handling.md`
**Status:** DOCUMENTED

---

### Frage 4 — What is the complete order lifecycle?
**Was will der Dozent prüfen?** Zustandsmodell.
**Kurze Antwort:** PENDING → CONFIRMED → PROCESSING → SHIPPED → DELIVERED; CANCELLED aus PENDING/CONFIRMED.
**Vertiefung:** Endzustände = DELIVERED/CANCELLED (keine weiteren Übergänge).
**Projektbeleg:** `order-lifecycle/state-machine.md`
**Status:** IMPLEMENTED (Code + Tests)

---

### Frage 5 — Which status transitions are allowed?
**Kurze Antwort:** PENDING→CONFIRMED, PENDING→CANCELLED, CONFIRMED→PROCESSING, CONFIRMED→CANCELLED, PROCESSING→SHIPPED, SHIPPED→DELIVERED.
**Projektbeleg:** `lambda/src/state_machine.py`
**Status:** IMPLEMENTED

---

### Frage 6 — Which status transitions must be rejected?
**Kurze Antwort:** alles nicht in der Tabelle: rückwärts, Stufen-Sprünge, aus Endzuständen, späte Stornos.
**Projektbeleg:** `order-lifecycle/transition-rules.md`, Tests (Fälle 7–14)
**Status:** IMPLEMENTED

---

### Frage 7 — What API endpoints are required?
**Kurze Antwort:** POST /orders, GET /orders/{orderId}, GET /orders, PATCH /orders/{orderId}/status.
**Projektbeleg:** `api/endpoints.md`, `terraform/main.tf` (Routen)
**Status:** IMPLEMENTED (IaC)

---

### Frage 8 — What information needs to be stored?
**Kurze Antwort:** Order-ID, Status, Kunde, Items, Währung, Betrag, createdAt/updatedAt, plus interne pk/sk/gsi1/version.
**Projektbeleg:** `database/dynamodb-design.md`, `lambda/src/order_types.py`
**Status:** IMPLEMENTED

---

### Frage 9 — Why is DynamoDB appropriate?
**Kurze Antwort:** persistente Speicherung + klare Access Patterns; O(1)-Punktzugriffe, automatische Skalierung, kein eigener DB-Server; Alternativen RDS nicht nötig (ADR-001).
**Projektbeleg:** `database/dynamodb-design.md`, ADR-002
**Status:** IMPLEMENTED (IaC) / NOT VERIFIED

---

### Frage 10 — What are the main DynamoDB access patterns?
**Kurze Antwort:** AP1 Create (PutItem), AP2 Get by ID (GetItem), AP3 List (Query GSI1), AP4 Status-Update (UpdateItem + Condition).
**Projektbeleg:** `database/access-patterns.md`, `lambda/src/order_service.py`
**Status:** IMPLEMENTED

---

### Frage 11 — Why avoid unnecessary Scan operations?
**Kurze Antwort:** Scan liest gesamte Tabelle → linear mit Datenmenge, teuer. Query nutzt Index, bleibt effizient. Kein Pattern braucht einen Scan.
**Projektbeleg:** `database/access-patterns.md` §3, IAM ohne `dynamodb:Scan`
**Status:** IMPLEMENTED

---

### Frage 12 — What alternatives were considered?
**Kurze Antwort:** Lambda vs EC2, DynamoDB vs RDS, API GW vs direkt, Step Functions vs Code, HTTP vs REST API, Cognito vs Lambda Authorizer vs IAM-Auth.
**Projektbeleg:** `architecture/architecture-decisions.md` (ADR-001…007)
**Status:** DOCUMENTED

---

### Frage 13 — Why was the proposed architecture selected?
**Kurze Antwort:** Serverless passt zu Zielvolumen: Pay-per-use, auto-scaling, kein Server-Betrieb, kostenbewusst; keine unnötigen Services (ADR-006).
**Projektbeleg:** ADR-001, `README.md`
**Status:** DOCUMENTED

---

### Fragen 14–22 — Demonstrate (Creating/Retrieving/Listing orders, updating status, invalid request, DynamoDB records, Lambda execution, API GW requests, CloudWatch logs)
**Wichtig:** LIVE-Demo ohne `terraform apply` NICHT möglich. Was ich zeigen kann: Unit-Tests, Terraform-Plan, Request-Flow-Diagramm, Code-Pfade, Seed-Daten.
**Kurze Antwort (Request-Flow):** Client sendet Request mit Bearer-JWT → API GW validiert Token → Lambda verarbeitet (validieren, State Machine, DynamoDB) → Antwort; Fehler als strukturierte HTTP-Antworten.
**Projektbeleg:** `architecture/request-flow.md`, `lambda/src/index.py`, `terraform/main.tf`, `docs/reports/T011-07-TERRAFORM-PLAN-REVIEW.md`
**Status:** IMPLEMENTED (Code/IaC) · LIVE NOT RUN

---

### Frage 23 — Explain: API Gateway
**Kurze Antwort:** verwalteter HTTP-Einstiegspunkt; JWT-Validierung am Gateway; Client erreicht nie direkt Lambda/DynamoDB. Wir nutzen HTTP API (V2), günstiger als REST (ADR-004).
**Projektbeleg:** `terraform/main.tf:197`, ADR-004
**Status:** IMPLEMENTED (IaC) / NOT VERIFIED

---

### Frage 24 — Explain: Lambda
**Kurze Antwort:** serverless Compute, führt Geschäftslogik aus, skaliert automatisch, Pay-per-use. Python 3.14, stateless (Zustand in DynamoDB).
**Projektbeleg:** `terraform/main.tf:125`, `lambda/src/index.py`
**Status:** IMPLEMENTED / NOT VERIFIED

---

### Frage 25 — Explain: DynamoDB
**Kurze Antwort:** verwalteter NoSQL-Datenspeicher; Single-Table; On-Demand; Punktzugriffe + GSI-Query.
**Projektbeleg:** `terraform/main.tf:22`, `database/dynamodb-design.md`
**Status:** IMPLEMENTED (IaC) / NOT VERIFIED

---

### Frage 26 — Explain: IAM
**Kurze Antwort:** Service-Berechtigungen (Lambda→DynamoDB), Least Privilege; NICHT für Benutzer-Login (das macht Cognito).
**Projektbeleg:** `security/iam-design.md`, `terraform/main.tf:81-118`
**Status:** IMPLEMENTED (IaC) / NOT VERIFIED

---

### Frage 27 — Explain: API request/response flow
**Kurze Antwort:** siehe Frage 14–22. End-to-End: Gateway (Auth) → Lambda (Logik) → DynamoDB → Antwort.
**Projektbeleg:** `architecture/request-flow.md`
**Status:** IMPLEMENTED / NOT VERIFIED

---

### Frage 28 — Explain: Database access pattern
**Kurze Antwort:** AP1…AP4 als Query/GetItem/UpdateItem; kein Scan; Pagination via LastEvaluatedKey.
**Projektbeleg:** `database/access-patterns.md`
**Status:** IMPLEMENTED

---

### Frage 29 — Why the client does not directly access DynamoDB
**Kurze Antwort:** Sicherheit (Least Privilege), kein Datenbank-Credential beim Client, Zugriff nur über Lambda-IAM-Rolle; API GW als einziger Eingang. Direkter Zugriff bräuchte IAM-Credentials/API-Keys beim Client → Security-Risiko, widerspricht Nicht-funktionaler Anforderung „Protect order data".
**Projektbeleg:** `security/iam-design.md`, `requirements/technical-requirements.md`
**Status:** DOCUMENTED / IMPLEMENTED (IaC)

---

### Frage 30 — Demonstrate: Valid order-state transition
**Kurze Antwort:** z. B. PENDING→CONFIRMED: Lambda prüft Tabelle, Conditional Write, 200.
**Projektbeleg:** `lambda/tests/test_order_service.py` (T-13), `transition-rules.md` (Fall 1)
**Status:** IMPLEMENTED (getestet) / LIVE NOT RUN

---

### Frage 31 — Demonstrate: Invalid order-state transition
**Kurze Antwort:** z. B. DELIVERED→PROCESSING: nicht in Tabelle → 409 INVALID_TRANSITION mit currentStatus+requestedStatus.
**Projektbeleg:** `transition-rules.md` (Fälle 7–14), `errors.py`
**Status:** IMPLEMENTED (getestet)

---

### Frage 32 — Demonstrate: Rejection of an invalid update
**Kurze Antwort:** Identisch zu Frage 31 (409); zusätzlich Conditional-Check-Fehler → 409 CONFLICTED_UPDATE.
**Projektbeleg:** `errors.py`, `order_service.py`
**Status:** IMPLEMENTED

---

### Frage 33 — Demonstrate: Retrieval of a non-existent order
**Kurze Antwort:** GetItem liefert kein Item → 404 ORDER_NOT_FOUND.
**Projektbeleg:** `order_service.py` (get_order), Test T-08
**Status:** IMPLEMENTED

---

### Frage 34 — Demonstrate: Invalid input handling
**Kurze Antwort:** Validierung → 400 VALIDATION_ERROR mit Feld-Pfad; strikte Ablehnung unbekannter Felder.
**Projektbeleg:** `lambda/src/validation.py`, Tests (19 in test_validation.py)
**Status:** IMPLEMENTED

---

### Frage 35 — Demonstrate: IAM permissions
**Kurze Antwort:** Lambda-Rolle mit Least Privilege (nur benötigte DynamoDB-Aktionen + Logs); Terraform Policy als Beleg. Live-Nachweis (401/403) erst nach apply.
**Projektbeleg:** `terraform/main.tf:81-118`, `security/iam-design.md`
**Status:** IMPLEMENTED (IaC) / LIVE NOT RUN

---

### Frage 36 — Demonstrate: CloudWatch logs
**Kurze Antwort:** Lambda-Log-Group mit 7-Tage-Retention per IaC; strukturierte Logs. Live-Logs erst nach apply.
**Projektbeleg:** `terraform/monitoring.tf` (log_group), `monitoring/monitoring-design.md`
**Status:** IMPLEMENTED (IaC) / LIVE NOT RUN

---

### Frage 37 — Demonstrate: Monitoring/alarms
**Kurze Antwort:** 6 Alarme + Dashboard als Terraform definiert (fmt/validate/plan PASS). Live-Zustand (OK/ALARM) erst nach apply messbar.
**Projektbeleg:** `terraform/monitoring.tf`, `docs/reports/T011-11-CLOUDWATCH-MONITORING.md`
**Status:** VALIDATED (plan PASS) · LIVE NOT RUN

---

### Frage 38 — Demonstrate: Concurrent/conflicting update considerations
**Kurze Antwort:** Zwei gleichzeitige Updates auf denselben Status → Conditional Write entscheidet; Verlierer → 409 CONFLICTED_UPDATE. Endzustand konsistent.
**Projektbeleg:** `transition-rules.md` §4, Test R-01 (test_order_service.py)
**Status:** IMPLEMENTED (getestet)

---

### Frage 39 — Why business rules belong in the application logic
**Kurze Antwort:** DB speichert nur Daten; Regeln sind fachliche Entscheidungen (erlaubte Übergänge), unit-testbar, versionierbar. Sonst wäre jeder DB-Write ein Risiko für inkonsistente Zustände.
**Projektbeleg:** `state_machine.py`, `transition-rules.md` §1, ADR-005
**Status:** IMPLEMENTED

---

### Frage 40 — How invalid state transitions are prevented
**Kurze Antwort:** (1) State-Machine-Check in Lambda, (2) Conditional Write (atomar) als zweite Linie.
**Projektbeleg:** `order_service.py` update_order_status
**Status:** IMPLEMENTED

---

### Frage 41 — How DynamoDB can help protect data consistency
**Kurze Antwort:** Conditional Writes (atomar pro Item), dadurch kein verlorenes/überschriebenes Update; `attribute_exists(pk)` verhindert Insert statt Update bei fehlender Order.
**Projektbeleg:** `reliability/consistency-and-failure-handling.md`, `order_service.py`
**Status:** IMPLEMENTED

---

### Frage 42 — Why the database should not be publicly accessible
**Kurze Antwort:** Direkter Zugriff = Datenklau/Manipulation ohne Kontrolle; Zugriff nur über Lambda (IAM-Rolle, Least Privilege); Clients sehen nie DB-Credentials.
**Projektbeleg:** `security/iam-design.md`, NFR Security
**Status:** DOCUMENTED / IMPLEMENTED (IaC)

---

### Frage 43 — How IAM controls service access
**Kurze Antwort:** Rollen+Policies definieren, welcher Service welche Aktion auf welche Ressource darf; hier Lambda→DynamoDB (eng), API GW→Lambda (Invoke-Permission, nur API GW).
**Projektbeleg:** `terraform/main.tf` (Rolle, Policy, Invoke-Permission)
**Status:** IMPLEMENTED (IaC) / NOT VERIFIED

---

### Frage 44 — How errors are detected
**Kurze Antwort:** Lambda try/except → strukturierte Fehlerantworten; unerwartete Fehler → 500 generisch; CloudWatch-Logs + Metriken (Errors, Duration, 5xx-Alarm) für Detektion.
**Projektbeleg:** `index.py` (fail), `errors.py`, `monitoring.tf` (Alarme)
**Status:** IMPLEMENTED / VALIDATED

---

### Frage 45 — How the system handles increasing traffic
**Kurze Antwort:** Serverless skaliert automatisch (Lambda, API GW, DynamoDB On-Demand); kein manuelles Server-Management; Kosten skaliert mit Nutzung.
**Projektbeleg:** ADR-001, `cost/cost-analysis.md`, `reliability/consistency-and-failure-handling.md` §3
**Status:** DOCUMENTED / PLANNED (W4-Messung)

---

### Frage 46 — What business problem does the system solve? (siehe Frage 1)
**Status:** DOCUMENTED

---

### Frage 47 — Why was serverless architecture selected?
**Kurze Antwort:** passt zu Größe (kleiner Händler): Pay-per-use, auto-scaling, kein Server-Betrieb, kostenbewusst; Vergleich mit EC2 in ADR-001.
**Projektbeleg:** ADR-001
**Status:** DOCUMENTED

---

### Frage 48 — Why use API Gateway?
**Kurze Antwort:** verwalteter HTTP-Eingang mit JWT-Autorisierung, Skalierung, kein Server; Client erreicht Backend nie direkt.
**Projektbeleg:** ADR-004, `terraform/main.tf:197`
**Status:** IMPLEMENTED (IaC) / NOT VERIFIED

---

### Frage 49 — Why use Lambda?
**Kurze Antwort:** serverless Compute für Business-Logik, auto-scaling, Pay-per-use, kein Server/Patching.
**Projektbeleg:** ADR-001, `terraform/main.tf:125`
**Status:** IMPLEMENTED / NOT VERIFIED

---

### Frage 50 — Why use DynamoDB?
**Kurze Antwort:** verwalteter NoSQL-Speicher, O(1)-Zugriffe passend zu Access Patterns, On-Demand-Skalierung, kein DB-Server-Betrieb.
**Projektbeleg:** ADR-002, `database/dynamodb-design.md`
**Status:** IMPLEMENTED (IaC) / NOT VERIFIED

---

### Frage 51 — Why not use EC2?
**Kurze Antwort:** feste Kosten, Server-Patching/Wartung, manuelles Auto-Scaling, Overkill für unser Zielvolumen; Lambda erledigt das automatisch und billiger (ADR-001).
**Projektbeleg:** ADR-001
**Status:** DOCUMENTED

---

### Frage 52 — Why not use RDS?
**Kurze Antwort:** relationale DB bräuchte VPC/Subnets, Wartung, kein relationales Modell gefordert; Single-Entity-Modell → DynamoDB ausreichend (ADR-001/002).
**Projektbeleg:** ADR-001
**Status:** DOCUMENTED

---

### Frage 53 — What are the main DynamoDB access patterns? (siehe Frage 10)
**Status:** IMPLEMENTED

---

### Frage 54 — Why should Scan operations be minimized? (siehe Frage 11)
**Status:** IMPLEMENTED

---

### Frage 55 — How is an order's lifecycle represented?
**Kurze Antwort:** Status-Feld im Item + State Machine (Transitionstabelle) in der Lambda; Endzustände; Conditional Write erzwingt Reihenfolge.
**Projektbeleg:** `state_machine.py`, `database/dynamodb-design.md`
**Status:** IMPLEMENTED

---

### Frage 56 — How are invalid state transitions prevented? (siehe Frage 40)
**Status:** IMPLEMENTED

---

### Frage 57 — How are conflicting updates handled? (siehe Frage 38)
**Status:** IMPLEMENTED

---

### Frage 58 — How does the system scale?
**Kurze Antwort:** Lambda (auto-scaling, stateless), API GW (nativ), DynamoDB On-Demand (adaptiv); kein manuelles Provisioning. Grenzen + Hot-Partition siehe W4.
**Projektbeleg:** `reliability/consistency-and-failure-handling.md` §3, `cost/cost-analysis.md`
**Status:** DOCUMENTED / PLANNED (Messung W4)

---

### Frage 59 — How is the application secured?
**Kurze Antwort:** Cognito (Auth) + API-GW-JWT-Authorizer + Lambda-IAM-Rolle (Least Privilege) + kein direkter DB-Zugriff + keine Secrets im Repo + Log-Sanitization.
**Projektbeleg:** `security/authentication-decision.md`, `security/iam-design.md`
**Status:** DOCUMENTED / IMPLEMENTED (IaC) / NOT VERIFIED

---

### Frage 60 — How is the system monitored?
**Kurze Antwort:** CloudWatch Logs (Retention 7 Tage), Metriken (API/Lambda/DynamoDB), 6 Alarme, Dashboard `mays-orders-overview` — alles als Terraform-IaC; live noch nicht erzeugt.
**Projektbeleg:** `terraform/monitoring.tf`, `monitoring/monitoring-design.md`, T011-11-Report
**Status:** VALIDATED (plan PASS) · LIVE NOT RUN

---

### Frage 61 — What are the major cost drivers?
**Kurze Antwort:** API-GW-Requests, Lambda-Execution, DynamoDB-Nutzung, CloudWatch-Logs. Bei 100k Orders/Tag dominiert API GW (≈ 20–40 $/Monat). Kleine Last ≈ 0–1 $/Monat.
**Projektbeleg:** `cost/cost-analysis.md`
**Status:** DOCUMENTED (Planung; Messung W4 PLANNED)

---

### Frage 62 — What are the limitations?
**Kurze Antwort:** kein Live-Betrieb (kein apply), Hot-Partition-GSI1 (theoretisch >10 GB), Lambda-Concurrency/Timeout-Grenzen, Business-Metriken noch nicht implementiert, keine Benachrichtigung bei Alarmen (kein SNS).
**Projektbeleg:** `database/dynamodb-design.md` §6, `docs/reports/T011-11-CLOUDWATCH-MONITORING.md`
**Status:** DOCUMENTED

---

### Frage 63 — What would change if the business grew significantly?
**Kurze Antwort:** GSI-Sharding (Hot Partition), ggf. Step Functions für langlaufende Prozesse, Lambda-Reserved Concurrency, SNS-Benachrichtigungen, Business-Metriken, ggf. Fargate/ECS für spezialisierte Worker; Kosten steigen (API GW).
**Projektbeleg:** `database/dynamodb-design.md` §6, ADR-005 (Migration), `cost/cost-analysis.md` §6
**Status:** DOCUMENTED / PLANNED

---

### Frage 64 — How would Terraform manage the infrastructure?
**Kurze Antwort:** Ressourcen als Code (main.tf, monitoring.tf), Variablen, Outputs, Dependencies; fmt/validate/plan; apply erzeugt AWS-Ressourcen reproduzierbar; State = Quelle der Wahrheit.
**Projektbeleg:** `terraform/README.md`, `docs/features/F011-terraform-infrastructure.md`
**Status:** IMPLEMENTED / VALIDATED (apply NOT RUN)

---

### Frage 65 — How does the architecture align with AWS Well-Architected principles?
**Kurze Antwort:**
- Operational Excellence: Monitoring/Logs/Alarme, IaC, Doku.
- Security: Cognito/JWT, IAM Least Privilege, kein direkter DB-Zugriff, Secret-Audit.
- Reliability: Conditional Writes, managed Services, Endzustand-Konsistenz.
- Performance Efficiency: Query statt Scan, GSI, effiziente Access Patterns.
- Cost Optimization: Free-Tier, kein EC2/SNS/Step Functions, Log-Retention.
**Projektbeleg:** `docs/reports/four-week-plan.md`, `cost/cost-analysis.md`, `reliability/…`
**Status:** DOCUMENTED (W4-Review PLANNED)

---

*Ende der detaillierten Antworten. Alle 65 Fragen abgedeckt.*