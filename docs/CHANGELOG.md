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

## 2026-08-17 — Dokumentations-Transfer (Checkpoint 2a89e73)

### Dokumentation
- Zentrales Statusdokument `docs/PROJECT_STATUS.md`.
- Portfolio `docs/PROJECT_PORTFOLIO.md`, Changelog `docs/CHANGELOG.md`.
- AI-/Projektkontext-Dokumente nach Mays-Jobsearch-Muster (`docs/AGENTS.md`, `docs/AI_CONTEXT.md`, …).
- Feature-Dokumentation `docs/features/` (F001–F011).
- Weekly-Reports strukturiert als `docs/reports/WEEK-01…04.md`.
- `docs/BUILD.md`, `docs/DEPLOYMENT.md` (Planung, Status offen).

### Status
- Woche 1 weiterhin COMPLETE; kein Code, keine AWS-Ressourcen.
- Checkpoint `2a89e73` gepusht.
- Statusnachzug Checkpoint `729ae73` gepusht (Checkpoint-Historie aktualisiert).

## 2026-08-17 — Korrektur Review-Inkonsistenzen (Checkpoint 4a0a6e7)

### Dokumentation
- `docs/PROJECT_STATUS.md`: `729ae73` als aktueller letzter Checkpoint (Historie: `4515029 → 2a89e73 → 729ae73`).
- `README.md` + `docs/reports/four-week-plan.md`: Woche-1-Status eindeutig **COMPLETE** (kein „in Arbeit").
- Commit-/Push-Regel vereinheitlicht (normale Tasks: Checkpoint-Commit/-Push selbstständig;
  kosten-/sicherheitsrelevante AWS-Aktionen weiterhin nur mit menschlicher Freigabe):
  `docs/AGENTS.md`, `docs/AI_TEAM.md`, `docs/AI_AGENT_PLAYBOOK.md`, `docs/AI_DEVELOPMENT_GUIDE.md`.
- Konsistenz-Nachzug in `docs/features/F001-project-foundation.md`, `docs/reports/documentation-transfer-report.md`.

### Status
- Week 1 COMPLETE · Documentation COMPLETE · AWS NO RESOURCES · Application NOT STARTED ·
  Terraform Apply NOT RUN · Live API NOT RUN.

## 2026-08-17 — Persistent Feature Progress & Crash-Recovery-Regel

### Workflow
- Verbindliche Regel eingeführt: Arbeitsstand wird während der Bearbeitung **fortlaufend**
  in der Feature-Dokumentation aktualisiert (`docs/features/_progress-template.md`).
- Feature-Doku (FXXX) führt künftig: Status, Current Task, Completed/In Progress/Pending Tasks,
  Changes Made, Tests, Validation, Known Issues, Blockers, Current Checkpoint, Next Step.
- Status-Disziplin: aktive Features `IN PROGRESS`; Feature erst `COMPLETE` nach Implementation,
  Tests, Validation, Doku, bekannte Probleme, Git-Checkpoint und Push.
- Recovery-Regel erweitert: semantischer Stand aus Feature-Doku ist die maßgebliche
  Recovery-Quelle; bei Unsicherheit `UNKNOWN / NEEDS VERIFICATION`, nicht raten.

### Geänderte Dateien
- `docs/AI_AGENT_PLAYBOOK.md` (neue Sektion), `docs/AGENTS.md`, `docs/AI_DEVELOPMENT_GUIDE.md`
- `docs/features/README.md`, `docs/features/_progress-template.md` (neu)
- `docs/reports/recovery-checkpoint-strategy.md`, `docs/PROJECT_STATUS.md`

### Status
- Keine AWS-Aktionen; Freigabepflichtige Aktionen unverändert (apply/destroy, Produktions-
  deployment, destruktive Operationen, kostenrelevante Ressourcen, Architekturänderungen).