# AI Development Guide — May's Orders

Begleiter zu `docs/AI_AGENT_PLAYBOOK.md`.

## Principle

AI unterstützt die Entwicklung. Es ersetzt nicht:

- Produktentscheidungen
- Architektur-Entscheidungen (ADR)
- Tests/QA
- Deployment-/Apply-Entscheidungen

## Workflow

1. Mensch definiert das Ziel.
2. Mensch formuliert den Task-Prompt (siehe `docs/AI_AGENT_PLAYBOOK.md`).
3. AI liest relevanten Kontext (`docs/PROJECT_STATUS.md`, `docs/AGENTS.md`, Fachquelle).
4. AI analysiert den aktuellen Stand.
5. AI implementiert die kleinste korrekte Änderung.
6. AI validiert: Build/Tests → `terraform validate`/`plan` → (nach Deployment) Live-API.
7. Mensch prüft und gibt frei.
8. Iterieren.

## Rules

- Bestehende Architektur und ADR erhalten.
- Keine neuen AWS-Services ohne Architecture Decision (ADR-006).
- Keine unnötigen Dependencies.
- Keys nur über AWS-Services (Cognito/Secrets Manager), nie im Code/Repo.
- Evidenzbasiert: Build ≠ Live-API.
- Nach relevanten Features: `docs/CHANGELOG.md`, `docs/PROJECT_STATUS.md`, Weekly-Report aktualisieren.
- `terraform apply` nur nach menschlicher Freigabe.

## Validation commands

```bash
npm run build          # TypeScript-Build (Woche 2)
npm test               # Unit-Tests (Woche 2)
terraform init && terraform validate && terraform plan
```

Live-Check-Beispiel (nach Deployment):

```bash
curl -H "Authorization: Bearer <TOKEN>" https://<api-id>.execute-api.<region>.amazonaws.com/orders
```

## Documentation

Die Projektakte lebt in `docs/`:

- `PROJECT_STATUS.md` — zentraler Stand
- `PROJECT_PORTFOLIO.md` — Projektweg
- `CHANGELOG.md` — Änderungshistorie
- `AGENTS.md` — Projektübersicht & Regeln
- `features/` — Feature-/Task-Dokumentation
- `reports/` — Weekly Reports, Strategien, Recovery