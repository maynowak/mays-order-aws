# Changelog — May's Orders

> Nur tatsächliche Änderungen. Jeder Eintrag referenziert einen echten Checkpoint.

## 2026-08-17 — Checkpoint 4515029 (Woche 1)

### Foundation
- Git-Repo initialisiert, GitHub-Remote `maynowak/mays-order-aws` eingerichtet.
- Remote-„Initial commit" (LICENSE, README, .gitignore) per `--allow-unrelated-histories` zusammengeführt; Konflikte gelöst.

### Dokumentation (Woche 1)
- `requirements/`: Business-, Technical-Requirements, Assumptions & Constraints.
- `order-lifecycle/`: State Machine, Transition Matrix (18 Fälle), Konkurrenz-Schutz-Konzept.
- `api/`: Endpoint-Design, API-Dokumentation, Testfälle (T-01…16, A-01…04).
- `database/`: Single-Table-Design (GSI1), Access-Pattern-Analyse.
- `security/`: Auth-Entscheidung (Cognito, HTTP API, JWT-Flow), IAM-Least-Privilege-Design.
- `architecture/`: ADR-001…007, Request-Flow, Architekturdiagramm (SVG).
- `monitoring/`, `reliability/`, `cost/`: Monitoring-, Konsistenz-, Kosten-Konzept.
- `docs/reports/`: Vier-Wochen-Plan, Test-/Kosten-/Recovery-Strategie, Weekly-Report, Feature-Report.

### Status
- Woche 1 — COMPLETE. Keine AWS-Ressourcen. Keine Implementierung.
- Build: NOT APPLICABLE · Live-API: NOT RUN (kein Code) · Secret-Audit: PASS · `git diff --check`: PASS.

## 2026-08-17 — Dokumentations-Transfer (neuer Checkpoint, offen)

### Dokumentation
- Zentrales Statusdokument `docs/PROJECT_STATUS.md`.
- Portfolio `docs/PROJECT_PORTFOLIO.md`, Changelog `docs/CHANGELOG.md`.
- AI-/Projektkontext-Dokumente nach Mays-Jobsearch-Muster (`docs/AGENTS.md`, `docs/AI_CONTEXT.md`, …).
- Feature-Dokumentation `docs/features/` (F001–F011).
- Weekly-Reports strukturiert als `docs/reports/WEEK-01…04.md`.
- `docs/BUILD.md`, `docs/DEPLOYMENT.md` (Planung, Status offen).