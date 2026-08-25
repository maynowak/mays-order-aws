# Friday Cheat Sheet — May's Orders

> Für jede zentrale Originalfrage: **FRAGE → 1-Satz-Antwort → wichtigstes AWS-Konzept → May's-Orders-Bezug**

---

**Was ist das Problem?** → OrderFlow braucht ein skalierbares Order-Backend ohne Server-Wartung.
→ Serverless. → README, requirements/.

**Was ist der Order-Lebenszyklus?** → PENDING→CONFIRMED→PROCESSING→SHIPPED→DELIVERED (+CANCELLED).
→ State Machine. → `state_machine.py`.

**Welche Transitions erlaubt?** → 6 erlaubte (inkl. 2 Storno-Pfade), Rest 409.
→ Transitionstabelle. → `transition-rules.md`.

**Warum DynamoDB?** → Persistenter NoSQL-Speicher passend zu Access Patterns. → Managed NoSQL.
→ `dynamodb-design.md`.

**Warum GSI?** → Listing ohne Scan. → GSI + Query. → `access-patterns.md` AP3.

**Warum Query statt Scan?** → Query = nur passende Items, effizient. → Query vs Scan.
→ `access-patterns.md` §3.

**Welche API-Endpunkte?** → POST/GET/GET/PATCH /orders… → REST + HTTP API V2. → `endpoints.md`.

**Warum Lambda?** → Serverless Compute, auto-scaling, Pay-per-use. → Lambda. → `index.py`.

**Warum API Gateway?** → Verwalteter Eingang mit JWT-Check. → HTTP API. → `main.tf`.

**Warum Cognito?** → Benutzer + JWT verwaltet. → Authentication. → `authentication-decision.md`.

**Auth vs AuthZ?** → „Wer bist du?" vs „Darfst du das?". → Cognito + Claims. → `security/`.

**Was ist JWT?** → Signiertes Identitäts-Token. → JWT/Claims. → API-GW-Authorizer.

**Wer prüft JWT?** → API Gateway Authorizer. → Authorizer. → `terraform/main.tf` (JWT).

**JWT = DynamoDB-Zugriff?** → NEIN, DB läuft über IAM-Rolle. → IAM vs JWT. → `iam-design.md`.

**Nicht existierende Order?** → 404 ORDER_NOT_FOUND. → GetItem ohne Item. → `order_service.py`.

**Ungültige Transition?** → 409 INVALID_TRANSITION. → State Machine. → `errors.py`.

**Konkurrierende Updates?** → Conditional Write entscheidet; Verlierer 409. → Conditional Write.
→ `order_service.py` + R-01-Test.

**Warum `version`?** → Optimistic-Locking-Reserve. → version-Feld. → `dynamodb-design.md`.

**Was passiert bei Fehler?** → strukturierte Antwort, Details nur in Logs. → Error Mapping.
→ `errors.py`, `endpoints.md` §3.

**Traffic-Spikes?** → auto-scaling ohne manuellen Eingriff. → Serverless scaling. → ADR-001.

**Keine laufenden Server?** → Serverless, Pay-per-use. → Lambda. → `cost-analysis.md`.

**Was macht Terraform?** → beschreibt AWS-Infrastruktur als Code, erzeugt sie bei apply.
→ IaC. → `terraform/`, T011-07/11.

**Was bedeutet IaC?** → Infrastruktur als Code (AWS existiert weiterhin). → Terraform.
→ `terraform/README.md`.

**Was überwacht CloudWatch?** → Logs, Metriken, 6 Alarme, Dashboard. → CloudWatch.
→ `monitoring.tf`, `monitoring-design.md`.

**Was ist getestet?** → Lokal: Lambda 51/51, Seed 28/28, fmt/validate/plan. → Unit-Tests.
→ `tests/test-results.md`.

**Was ist NICHT in AWS getestet?** → Alles Live (kein apply). → NOT RUN. → `PROJECT_STATUS.md`.

---

## DIE 10 WICHTIGSTEN BEGRIFFE

1. **Serverless** — keine Server-Verwaltung, Pay-per-use, auto-scaling (Lambda, API GW, DynamoDB).
2. **API Gateway** — verwalteter HTTP-Eingang, JWT-Validierung, HTTP API V2.
3. **Lambda** — serverless Compute, Python 3.14, Business-Logik, stateless.
3. **DynamoDB** — Managed NoSQL, Single-Table, On-Demand, GSI1.
4. **GSI** — Global Secondary Index für effizientes Listing (Query statt Scan).
5. **JWT** — JSON Web Token, signiert, Claims, von API-GW-Authorizer geprüft.
6. **IAM** — Service-Berechtigungen (Lambda→DynamoDB), Least Privilege.
7. **State Transition** — erlaubte/verbotene Statusübergänge in einer Transitionstabelle.
8. **Conditional Write** — atomarer Schutz gegen konkurrierende Updates (`status = :current`).
8. **Infrastructure as Code (IaC)** — AWS-Infrastruktur als Terraform-Code, reproduzierbar.

---

*Erstellt am 2026-08-20 auf Basis von Ausgangsdokument (PROJECT_6) + aktuellem Repo-Stand.*
*Alle Statusangaben entsprechen dem Repo-Stand (kein apply, kein Live-Test).*