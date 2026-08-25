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

*Erstellt am 2026-08-20 auf Basis von Ausgangsdokument (PROJECT_6) + aktuellem Repo-Stand.*
*Alle Statusangaben entsprechen dem Repo-Stand (kein apply, kein Live-Test).*