# AGENTS.md — May's Orders

## Project Overview

May's Orders ist ein serverloses Order-Management-System für den fiktiven Händler
**OrderFlow GmbH**. Es bildet den vollständigen Lebenszyklus einer Bestellung ab:

```text
PENDING → CONFIRMED → PROCESSING → SHIPPED → DELIVERED
```

inkl. definierter Cancellation-Pfade und Ablehnung ungültiger Statusübergänge.

Architektur: **Client → (Cognito JWT) → API Gateway (HTTP API) → Lambda → DynamoDB → CloudWatch**.
Infrastruktur vollständig per **Terraform**.

## Tech Stack

- Python 3.14 (Lambda-Handler) — aktiv (boto3, `python3.14`); Node.js/TypeScript historisch (Baseline, via Git `449cdd7`)
- API Gateway HTTP API (V2) mit Cognito-JWT-Autorisator
- AWS Lambda (Order Handler)
- DynamoDB (Single-Table, GSI1)
- Cognito User Pool (Authentication)
- CloudWatch (Logs, Metriken, Alarme)
- Terraform (IaC)
- Git / GitHub

## Folder Structure

```text
mays-orders/
├── README.md
├── requirements/     Business-/Technical-Requirements, Assumptions
├── architecture/     ADR, Request-Flow, Diagramm
├── api/              Endpoint-Design, API-Doku, Test-Cases
├── order-lifecycle/  State Machine, Transition Rules
├── database/         DynamoDB-Design, Access Patterns
├── security/         Auth-Entscheidung, IAM-Design
├── monitoring/       Monitoring-Design
├── reliability/      Konsistenz & Failure Handling
├── cost/             Kostenanalyse
├── terraform/        Infrastructure as Code (geplant, W2)
├── tests/            Test-Ergebnisse
├── docs/             Projektakte (Status, Portfolio, Features, Reports)
└── docs/features/    Feature-Dokumentation F001–F011
```

## Fachliche Single Source of Truth

| Thema | Quelle |
|-------|--------|
| State Machine / Transitions | `order-lifecycle/` |
| API-Vertrag | `api/endpoints.md` |
| Datenmodell | `database/` |
| Auth / IAM | `security/` |
| ADR | `architecture/architecture-decisions.md` |
| Entwicklungsstand | `docs/PROJECT_STATUS.md` |

## Regeln

- **Authentication ≠ IAM:** Cognito für Benutzer, IAM nur für Service-Berechtigungen (Least Privilege).
- **Keine IAM Access Keys als Benutzer-Login.**
- **Keine Secrets** in Code, Logs, README, Reports. Keys nur über AWS-Services (Cognito/Secrets Manager).
- **Keine unnötigen AWS-Services.** Jede Erweiterung braucht eine Architecture Decision (ADR-006).
- **Evidenzbasiert:** keine erfundenen Tests/Ergebnisse/Ressourcen. Testnachweise mit Zuständen
  (PLANNED / IMPLEMENTED / TESTED / VERIFIED / COMPLETE / BLOCKED / NOT TESTED / NOT APPLICABLE).
- **Kostenbewusst:** Free-Tier beachten, keine dauerhaft laufenden Ressourcen ohne Begründung.
- **Checkpoint-Regel:** Report → Tests → Build → `git status` → `git diff --check` → Secret-Audit → Commit → Push.
- **Persistent Feature Progress:** Während der Bearbeitung wird der Arbeitsstand **fortlaufend**
  in der Feature-Dokumentation (`docs/features/FXXX-*.md`) aktualisiert — nicht erst am Ende.
  Aktive Features → `IN PROGRESS`; Feature erst `COMPLETE`, wenn Implementation, Tests,
  Validation, Doku, bekannte Probleme, Git-Checkpoint und Push abgeschlossen sind.
  Der Chatverlauf ist keine Recovery-Quelle; der semantische Stand steht in der Feature-Doku
  (siehe `docs/features/_progress-template.md`).

## Git Workflow

- Branch: `main` (aktuell). Feature-Arbeit optional auf Branches (`feature/...`).
- Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `style:`, `test:`, `chore:`.

### Commit-/Push-Regel

- **Normale Engineering-Tasks:** Wenn ein Task zur eigenständigen Bearbeitung freigegeben
  wurde, führt der Agent nach erfolgreicher Validierung den Checkpoint selbstständig aus:
  `git status` → `git diff --check` → Secret-Audit → Tests → Build/Validation → Commit → Push.
  Commit/Push ist Bestandteil des kontrollierten Task-Checkpoints.
- **Menschliche Freigabe erforderlich** (der Agent leitet daraus KEINE automatische
  Deployment-Berechtigung ab):
  - `terraform apply` / `terraform destroy`
  - Erzeugen kostenpflichtiger oder potenziell kostenpflichtiger AWS-Ressourcen
  - Produktionsdeployment
  - Destruktive AWS-Operationen
  - Änderungen an der freigegebenen Zielarchitektur
  - Hinzufügen wesentlicher neuer AWS-Services
  - Änderungen mit erheblicher Kosten- oder Sicherheitsauswirkung

## Validation

- Python: `python3 -m compileall -q src tests` + `PYTHONPATH=src python3 -m unittest discover -s tests -v` (Lambda, aktiv).
- Terraform: `terraform init` → `terraform validate` → `terraform plan` (→ `apply` nur nach Freigabe).
- Live-API: `curl` gegen deployed Gateway nach Deployment (Woche 2).
- Klare Trennung: `Build: PASS` ≠ `Live API: PASS`. Nie unbelegte Behauptungen.

## AI Instructions

- Vor Änderungen: `docs/PROJECT_STATUS.md` und relevante Fachquelle lesen.
- Minimal-invasiv arbeiten; Architektur und dokumentierte Entscheidungen erhalten.
- Nur Dateien ändern, die für die Aufgabe nötig sind.
- Nach Änderungen: Validation ausführen, Report aktualisieren, Checkpoint folgen.
- Wiederholte Prompts nutzen `docs/AI_AGENT_PLAYBOOK.md`.

## Future Roadmap

- Woche 2: Core Implementation (Terraform, Cognito, API GW, Lambda, DynamoDB) — ⏳ PLANNED
- Woche 3: State Machine, Reliability, Security, Monitoring — ⏳ PLANNED
- Woche 4: Skalierung, Kosten, Well-Architected, Präsentation — ⏳ PLANNED