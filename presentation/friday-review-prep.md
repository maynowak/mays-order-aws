# Friday Review — Prüfungsvorbereitung May's Orders

> **Primärquelle:** `PROJECT_6-AWS Serverless Order Management System.docx` (Ausgangsdokument)
> **Sekundärquelle:** aktueller Repo-Stand (main, HEAD `ec831d9`, Stand 2026-08-20)
> **Hinweis:** Alle Fragen stammen aus dem Ausgangsdokument. Nicht aus anderen Projekten.
> **Detailantworten:** Siehe `docs/learning/exam-answers.md`
> **Requirements-Traceability:** Siehe `docs/learning/requirements-traceability.md`
> **Glossar:** Siehe `docs/learning/glossary.md`
> **Future Extensions:** Siehe `docs/roadmap/future-extensions.md`
> **Cheat Sheet:** Siehe `presentation/friday-cheat-sheet.md`

## 0. Projekt auf einen Blick

| Ebene | Was | Implementiert (Code/IaC) | Live in AWS |
|-------|-----|:---:|:---:|
| API | HTTP API V2, 4 Routen, JWT-Authorizer | ✅ Terraform | ❌ kein apply |
| Auth | Cognito User Pool, Client, Gruppe `staff` | ✅ Terraform | ❌ kein apply |
| Lambda | Python 3.14 Handler (`index.handler`) | ✅ Code | ❌ nicht deployed |
| Daten | DynamoDB Single-Table + GSI1, On-Demand | ✅ Terraform + Code | ❌ kein apply |
| State Machine | `state_machine.py` (Transitionstabelle) | ✅ Code + Tests | ❌ nicht deployed |
| Fehler | `errors.py` (400/404/409/500) | ✅ Code + Tests | ❌ nicht deployed |
| IAM | Execution Role, Least Privilege | ✅ Terraform | ❌ kein apply |
| Monitoring | Dashboard `mays-orders-overview` + 6 Alarme + Log-Retention | ✅ Terraform (IaC) | ❌ kein apply |
| Tests | Lambda 51/51, Seed 28/28, compileall | ✅ lokal | ❌ Live-API-Tests offen |
| Terraform | fmt/init/validate/plan PASS | ✅ Plan: 24 add, 0 change, 0 destroy | ❌ apply NOT RUN |

> **Wichtige Status-Trennung (nie vermischen):**
> - **IMPLEMENTED** = Code/IaC vorhanden (lokal getestet/validiert)
> - **VALIDATED** = fmt/validate/plan erfolgreich
> - **NOT VERIFIED / NOT RUN** = nicht in AWS live getestet (kein apply)

---

## 1. Original-Fragenliste aus dem Ausgangsdokument

Wortgetreu aus dem Ausgangsdokument übernommen (Abschnitte „Friday Review — Week 1/2/3" und
„Friday Review / Final Presentation — Week 4").

### Friday Review — Week 1

1. What problem is OrderFlow trying to solve?
2. What are the main functional requirements?
3. What are the non-functional requirements?
4. What is the complete order lifecycle?
5. Which status transitions are allowed?
6. Which status transitions must be rejected?
7. What API endpoints are required?
8. What information needs to be stored?
9. Why is DynamoDB appropriate?
10. What are the main DynamoDB access patterns?
11. Why should the application avoid unnecessary Scan operations?
12. What alternatives were considered?
13. Why was the proposed architecture selected?

### Friday Review — Week 2 (Demonstrate)

14. Creating an order.
15. Retrieving an order.
16. Retrieving orders.
17. Updating order status.
17. Invalid request handling.
19. DynamoDB records.
20. Lambda execution.
21. API Gateway requests.
22. CloudWatch logs.

### Friday Review — Week 2 (Explain)

23. API Gateway
24. Lambda
25. DynamoDB
26. IAM
27. API request/response flow
28. Database access pattern
29. Why the client does not directly access DynamoDB

### Friday Review — Week 3 (Demonstrate)

30. Valid order-state transition.
31. Invalid order-state transition.
32. Rejection of an invalid update.
33. Retrieval of a non-existent order.
34. Invalid input handling.
35. IAM permissions.
36. CloudWatch logs.
37. Monitoring/alarms.
38. Concurrent/conflicting update considerations.

### Friday Review — Week 3 (Explain)

39. Why business rules belong in the application logic.
40. How invalid state transitions are prevented.
41. How DynamoDB can help protect data consistency.
42. Why the database should not be publicly accessible.
43. How IAM controls service access.
44. How errors are detected.
45. How the system handles increasing traffic.

### Friday Review / Final Presentation — Week 4

46. What business problem does the system solve?
47. Why was serverless architecture selected?
48. Why use API Gateway?
49. Why use Lambda?
50. Why use DynamoDB?
51. Why not use EC2?
52. Why not use RDS?
53. What are the main DynamoDB access patterns?
54. Why should Scan operations be minimized?
55. How is an order's lifecycle represented?
56. How are invalid state transitions prevented?
57. How are conflicting updates handled?
58. How does the system scale?
59. How is the application secured?
60. How is the system monitored?
61. What are the major cost drivers?
62. What are the limitations?
63. What would change if the business grew significantly?
64. How would Terraform manage the infrastructure?
65. How does the architecture align with AWS Well-Architected principles?

---

## 2. Demo Matrix

| # | Demonstration | LOCAL TEST | TERRAFORM PLAN | AWS LIVE |
|---|---------------|:---:|:---:|:---:|
| 1 | Gültige State Transition (PENDING→CONFIRMED) | ✅ Unit-Test T-13 | – | ❌ NOT RUN |
| 2 | Ungültige State Transition (→409 INVALID_TRANSITION) | ✅ Test T-14 | – | ❌ NOT RUN |
| 3 | Ungültiges Update (Concurrent →409 CONFLICTED_UPDATE) | ✅ Test R-01 | – | ❌ NOT RUN |
| 4 | Nicht existierende Order (→404) | ✅ Test T-08 | – | ❌ NOT RUN |
| 5 | Ungültige Eingabe (→400) | ✅ 19 Validierungs-Tests | – | ❌ NOT RUN |
| 6 | Unauthorized Request (→401) | ⚠️ nur Code/JWT-Authorizer definiert | ✅ Terraform-Ressource | ❌ NOT RUN |
| 7 | IAM (Least Privilege) | ⚠️ Policy-Code | ✅ Terraform-Plan zeigt Policy | ❌ NOT RUN |
| 8 | CloudWatch Logs | ⚠️ Log-Group IaC | ✅ Terraform-Plan (Log-Group) | ❌ NOT RUN |
| 9 | Monitoring / Alarms | ⚠️ IaC (6 Alarme, Dashboard) | ✅ Terraform-Plan (24 add) | ❌ NOT RUN |
| 10 | Terraform plan | – | ✅ **24 add, 0 change, 0 destroy** | – |
| 11 | Request-Flow (Diagramm + Code) | ✅ `architecture/request-flow.md`, `index.py` | – | – |
| 12 | Seed-Daten (Demo 50) | ✅ dry-run Tests, JSON vorhanden | ✅ Seed opt-in (seed_example_data) | ❌ NOT RUN |

**Wichtig:** Für Live-Demos (curl, echtes JWT, echte Metriken) fehlt das Deployment. Ich kann
diesen Zustand ehrlich benennen und stattdessen Code/Tests/Plan demonstrieren.

---

## 3. Freitag-Falle — Top-15 Stolpersteine

**Frage → kurze Antwort → technische Vertiefung**

1. **Warum DynamoDB?** → Persistenter Speicher mit klaren Access Patterns. → O(1)-Punktzugriffe, On-Demand-Skalierung, kein DB-Server; Single-Table-Design (ADR-002).
2. **Warum GSI?** → Listing effizient ohne Scan. → GSI1 `LIST→createdAt`, Query absteigend, paginiert via LastEvaluatedKey.
3. **Warum Query statt Scan?** → Query liest nur passende Items über Index. → Scan linear mit Datenmenge; kein Pattern braucht Scan; IAM verbietet `dynamodb:Scan`.
4. **Warum Lambda?** → Serverless Compute. → Pay-per-use, auto-scaling, stateless, Python 3.14.
5. **Warum API Gateway?** → Verwalteter HTTP-Eingang. → JWT-Validierung am Gateway, Skalierung, Client erreicht Backend nie direkt.
6. **Warum Cognito?** → Verwalteter Benutzer-Store + JWT. → Kostenlos bis 50k MAU, native API-GW-Integration, Gruppe `staff` für Authorization.
7. **Authentication vs Authorization?** → „Wer bist du?" vs „Darfst du das?". → Cognito authentifiziert, Claims (Gruppen) autorisieren; beides getrennt von IAM.
8. **Was ist ein JWT?** → Signiertes Token mit Claims. → Beweist Identität/Sitzung; NICHT automatisch Zugriff auf AWS-Ressourcen.
7. **Wer prüft das JWT?** → API-Gateway-Authorizer. → Prüft Signatur, Ablauf, Issuer, Audience; reicht Claims an Lambda weiter.
10. **Nicht existierende Order?** → 404 ORDER_NOT_FOUND. → GetItem liefert kein Item → OrderError(404).
11. **Warum HTTP 404?** → Ressource existiert nicht. → getrennt von 400 (Eingabe) und 409 (Konflikt).
12. **Ungültige State Transitions verhindern?** → State Machine + Conditional Write. → Code-Prüfung + atomare DB-Bedingung (`status = :current`).
13. **Konkurrierende Updates?** → Conditional Write entscheidet, Verlierer 409. → `ConditionalCheckFailedException` → CONFLICTED_UPDATE.
14. **Warum `version`?** → Optimistic-Locking-Reserve. → Wird bei AP4 inkrementiert; zusätzliche Sicherheit, falls Status-Bedingung nicht reicht.
15. **Was passiert bei einem Fehler?** → Strukturierte HTTP-Antwort. → 400/404/409/500 je nach Ursache; interne Details nur in Logs.

**Detailantworten & Vertiefungen:** Siehe `docs/learning/exam-answers.md`  
**Requirements-Traceability:** Siehe `docs/learning/requirements-traceability.md`  
**Glossar:** Siehe `docs/learning/glossary.md`  
**Future Extensions:** Siehe `docs/roadmap/future-extensions.md`  
**Cheat Sheet:** Siehe `presentation/friday-cheat-sheet.md`

---

## Friday 2 — Was hat sich seit letztem Freitag (2026-08-22) geändert?

**Letzter Freitag (2026-08-22) Baseline:** `ec831d9` (T011-11 CloudWatch Monitoring auf main gemerged, T011-10 Seed, T011-07 Plan Review, T011-06 API GW, T011-05 Cognito, T011-04 Lambda Python 3.14)

**Aktueller Stand (HEAD `8512fbd`, main):** Alle T011-12 Änderungen auf main gemerged.

---

### Was hat sich seit letztem Freitag geändert?

| Thema | Was hat sich geändert? | Warum? | Aktuelle Implementation | Mögliche Freitag-2-Fragen | Doku/Code |
|-------|------------------------|--------|------------------------|---------------------------|-----------|
| **T011-12: Terraform Module Refactoring** | 6 Child Modules erstellt (dynamodb, iam, lambda, cognito, api, monitoring). Root main.tf zu Orchestrator reduziert. | Bessere Wartbarkeit, Wiederverwendbarkeit, klare Verantwortlichkeiten. 6 Child Modules statt monolithischem main.tf. | 6 Module unter `terraform/modules/` mit je `main.tf`, `variables.tf`, `outputs.tf`. Root `main.tf` nur noch Orchestrator. | • Welche Module gibt es? • Wie sind Dependencies verdrahtet? • Warum Modularisierung? | `terraform/modules/`, `terraform/main.tf`, `terraform/README.md` |
| **Clean Target Architecture** | 26 `moved` Blöcke entfernt. Root hat 0 moved blocks. | Moved Blöcke sind Migrations-Mechanismen für bestehende States, nicht Teil der Zielarchitektur. Clean Deployment braucht keine moved blocks. | `terraform/main.tf` hat 0 moved blocks, 6 Module Calls, Seed Resource. | • Warum wurden moved blocks entfernt? • Was sind moved blocks? • Wann braucht man sie? | `terraform/main.tf`, `terraform/README.md` (State Migration Section) |
| **Terraform Module Dependencies** | Saubere Dependency-Kette: dynamodb → iam → lambda → (api + monitoring) + cognito unabhängig. | Saubere DAG, keine Zirkel. Reflektiert tatsächliche Abhängigkeiten. | `module.dynamodb` → `module.iam` → `module.lambda` → `module.api` + `module.monitoring` | • Wie sind Dependencies verdrahtet? • Warum dynamodb zuerst? • Warum cognito unabhängig? | `terraform/main.tf` (Module Calls), `terraform/README.md` (Dependency Graph) |
| **Monitoring Module** | Aus `monitoring.tf` extrahiert in `terraform/modules/monitoring/`. | Log Group in Lambda Module verschoben (Lebenszyklus-Kopplung). Monitoring bleibt Read-Only Consumer. | `terraform/modules/monitoring/` (Dashboard + 6 Alarms). Root `monitoring.tf` nur Placeholder. | • Warum Log Group in Lambda Module? • Warum Monitoring als Consumer? | `terraform/modules/monitoring/`, `terraform/modules/lambda/main.tf` |
| **Friday Preview Dokumentation Separation** | `friday-review-prep.md` auf ~175 Zeilen reduziert. 65 detaillierte Answers, Traceability, Glossary, Future Extensions, Cheat Sheet in separate Files. | Trennung: Preview (Prüfung) vs. Lernmaterial (Lernen) vs. Roadmap (Planung). Bessere Wartbarkeit. | `presentation/friday-review-prep.md` (~175 Zeilen), neue Files unter `docs/learning/`, `docs/roadmap/`, `presentation/friday-cheat-sheet.md`. | • Warum Separation? • Wo finde ich Details? | `presentation/`, `docs/learning/`, `docs/roadmap/` |

---

### Was ist NEU für Freitag 2 relevant?

Die oben genannten Themen waren **letztes Freitag noch nicht existent oder nicht abgeschlossen**. Für Freitag 2 sind besonders relevant:

1. **Terraform Modul-Architektur** — Verständnis der 6 Module, Dependencies, Root Orchestration
2. **Clean Target Architecture** — Warum moved blocks entfernt wurden, Unterschied Migration vs. Clean Deploy
2. **State Migration Konzept** — Moved Blöcke als Migrations-Mechanismus vs. Target Architecture
4. **Monitoring Modul** — Trennung Log Group (Lambda) vs. Dashboard/Alarms (Monitoring)
5. **Dokumentation-Separation** — Wo finde ich was?

---

## New Friday 2 Questions

*Diese Fragen kommen durch die neuen Entwicklungen seit letztem Freitag hinzu.*

| # | Frage | Kurze Antwort | Vertiefung | Projektbeleg |
|---|-------|---------------|------------|--------------|
| 66 | **Welche Terraform Module gibt es und was machen sie?** | 6 Module: dynamodb, iam, lambda, cognito, api, monitoring. Jedes kapselt eine Domäne. | Root orchestriert nur noch. Module unter `terraform/modules/`. | `terraform/modules/`, `terraform/main.tf` |
| 67 | **Wie sind die Module miteinander verdrahtet?** | DAG: dynamodb → iam → lambda → {api, monitoring}. Cognito unabhängig. | Root `main.tf` Module Calls mit Outputs als Inputs. | `terraform/main.tf`, `terraform/README.md` |
| 68 | **Warum wurden die 26 moved Blöcke entfernt?** | Sie sind Migrations-Mechanismen für bestehende States, nicht Teil der Zielarchitektur. Clean Deployment braucht sie nicht. | Moved Blocks sind Migration, nicht Architektur. | `terraform/README.md` (State Migration Section) |
| 69 | **Wann braucht man moved Blöcke?** | Nur bei Migration eines bestehenden flat Terraform States in Module. Nicht bei Neu-Deployment. | Ohne moved blocks: destroy + create. Mit moved blocks: Adress-Migration im State. | `terraform/README.md` (State Migration Section) |
| 69b | **Was passiert bei Migration ohne moved blocks?** | Terraform plant destroy + create der Ressourcen (echte AWS-Änderung). | Mit moved blocks: 0 Änderungen, nur Adress-Update im State. | `terraform/README.md` |
| 70 | **Warum ist die Lambda Log Group im Lambda Module und nicht im Monitoring?** | Lebenszyklus-Kopplung: Lambda erzeugt Log Group, Monitoring konfiguriert nur Retention. Log Group gehört zum Lambda-Lebenszyklus. | `terraform/modules/lambda/main.tf` (Log Group Resource) | `terraform/modules/lambda/main.tf`, `terraform/modules/monitoring/` |
| 71 | **Wie ist das Monitoring Modul verdrahtet?** | Read-Only Consumer: liest `lambda.function_name`, `api.api_id`, `api.api_stage_name`, `dynamodb.table_name` aus anderen Modulen. | Keine eigenen Ressourcen erzeugen, nur Metriken konsumieren. | `terraform/modules/monitoring/main.tf`, `terraform/main.tf` (module.monitoring call) |
| 72 | **Was ist der Unterschied zwischen Migrations-Mechanismus und Zielarchitektur?** | Moved Blöcke = Migration (History). Module + Root = Zielarchitektur (Target). Zielarchitektur hat 0 moved blocks. | Zielarchitektur = saubere Modul-Struktur ohne Migrations-Artefakte. | `terraform/main.tf` (0 moved blocks), `terraform/README.md` |
| 73 | **Wie wurde die Friday Preview Dokumentation separiert?** | In 6 Files aufgeteilt: Preview (175 Zeilen), Cheat Sheet, Exam Answers, Traceability, Glossary, Future Extensions. | Navigation-Links in Preview zu Detail-Files. | `presentation/`, `docs/learning/`, `docs/roadmap/` |
| 74 | **Was ist der Unterschied zwischen Preview, Learning und Roadmap?** | Preview = Prüfungsfragen + Demo-Matrix + Top-15. Learning = Antworten, Traceability, Glossary. Roadmap = Future Extensions. | Trennung der Anliegen (Presentation vs. Learning vs. Planning). | `presentation/`, `docs/learning/`, `docs/roadmap/` |
| 75 | **Wo finde ich die detaillierte Antwort auf Frage X?** | `docs/learning/exam-answers.md` (65 detaillierte Antworten mit Belegen) | Fragen im Preview verlinken auf Answers. | `docs/learning/exam-answers.md` |
| 76 | **Wo finde ich die Requirements-Traceability?** | `docs/learning/requirements-traceability.md` (17 BR → Umsetzung → Nachweis → Status) | 17 BR aus Ausgangsdokument → Code/IaC/Doku. | `docs/learning/requirements-traceability.md` |
| 77 | **Wo finde ich das Glossar?** | `docs/learning/glossary.md` (10 Kernbegriffe + erweiterte Liste + Status-Legende) | Zentrale Begriffsdefinitionen. | `docs/learning/glossary.md` |
| 78 | **Wo finde ich Future Extensions?** | `docs/roadmap/future-extensions.md` (10 Extensions + Migration Pfade + Priorisierung) | Nicht Prüfungsstoff, nur Portfolio-Ausblick. | `docs/roadmap/future-extensions.md` |

---

**Detailantworten & Vertiefungen:** Siehe `docs/learning/exam-answers.md` (inkl. neue Fragen 66–78)  
**Requirements-Traceability:** Siehe `docs/learning/requirements-traceability.md`  
**Glossar:** Siehe `docs/learning/glossary.md` (inkl. erweiterte Begriffsliste)  
**Future Extensions:** Siehe `docs/roadmap/future-extensions.md` (mit Migration Pfaden & Priorisierung)  
**Cheat Sheet:** Siehe `presentation/friday-cheat-sheet.md` (inkl. 65 Fragen + neue 13 Fragen kompakt)

---

*Stand: 2026-08-25 — Freitag 2 Update auf Basis von Repo-Stand (main, HEAD `8512fbd`).*
*Alle Statusangaben entsprechen dem Repo-Stand (kein apply, kein Live-Test).*