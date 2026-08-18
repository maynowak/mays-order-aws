# T011-04 Lambda Runtime Documentation Cleanup

> Dokumentations-Cleanup hinsichtlich der aktiven Lambda-Runtime. **Keine
> Codeänderung, kein `terraform plan`, kein `terraform apply`, keine
> AWS-Ressourcen.** Git bleibt Source of Truth.

## Anlass

Beim Lesen der Projektdokumentation durfte kein Eindruck entstehen, dass AWS
Lambda aktuell noch mit Node.js/TypeScript betrieben wird. Ziel: die aktive
Runtime eindeutig als **Python 3.14** darzustellen und alle Node.js/TypeScript-
Erwähnungen klar als **historisch / ursprünglich / Migrationsstand** zu
kennzeichnen — ohne die Projektgeschichte zu entfernen.

## Verifizierter aktueller Runtime-Stand

Tatsächlich im Repository geprüft (`terraform/main.tf`, `lambda/`, `git`):

```text
runtime = "python3.14"
handler = "index.handler"
```

- `terraform/main.tf:125–129` (`aws_lambda_function.handler`): `runtime =
  "python3.14"`, `handler = "index.handler"`.
- `lambda/src/*` enthält ausschließlich Python-Module (`index.py`,
  `order_service.py`, `state_machine.py`, `validation.py`, `errors.py`,
  `order_types.py`).
- `lambda/dist/lambda.zip` ist der Python-Build (6 Module; `build_zip.py`).
- Kein Node-/TypeScript-Code im aktiven Lambda-Projekt.

## Historischer Node.js/TypeScript-Stand

Die ursprüngliche Lambda-Implementierung (T011-04) nutzte **Node.js 22 +
TypeScript** (`nodejs22.x`, esbuild-Bundle, Vitest 45/45, ZIP ~156 KB). Sie
wurde funktional identisch auf **Python 3.14** portiert
(`feature/lambda-python-314`) und im Cleanup (T011-04-CLEANUP,
`feature/lambda-python-cleanup`) aus dem aktiven Lambda-Projekt entfernt. Die
Baseline bleibt über Git-Historie (Commit `449cdd7`) und die Reports
(`LAMBDA-PYTHON-3.14-MIGRATION.md`, `T011-04-PYTHON-CLEANUP.md`) nachvollziehbar.

## Gefundene missverständliche Stellen

| Datei | Abschnitt | Problem |
|-------|-----------|---------|
| `README.md` | Architektur (Zielbild) | `Lambda` ohne Runtime-Angabe → konnte aktive Runtime nicht erkennen |
| `docs/reports/WEEK-02.md` | §2 Erledigte Features / Tasks (T011-04) | T011-04 als „TypeScript, nodejs22.x" ohne expliziten Historisch-Hinweis |
| `docs/features/F011-terraform-infrastructure.md` | §Runtime / Handler (T011-04) | Tabelle nannte `nodejs22.x` ohne Historisch-Kennzeichnung |
| `docs/features/F011-terraform-infrastructure.md` | Lambda-Lernbezug (T011-04) | „hier: Node.js 22 (nodejs22.x)" / „gebündeltes JS-File" ohne Historisch-Hinweis |
| `docs/reports/PRESENTATION-TECHNICAL-QA.md` | Node.js vs Python 3.14 | Abschnitt war chronologisch, aber ohne explizite Dreiteilung „Historischer Stand / Migration / Aktueller Stand" |

## Durchgeführte Dokumentationsänderungen

| Datei | Änderung |
|-------|----------|
| `README.md` | Architektur-Zielbild: `Lambda` → `Lambda (Python 3.14, Handler: index.handler)` |
| `docs/reports/WEEK-02.md` | T011-04-Zeile: als „**historischer Stand:** TypeScript/nodejs22.x … inzwischen durch Python 3.14 ersetzt (LAMBDA-PY-314)" gekennzeichnet |
| `docs/features/F011-terraform-infrastructure.md` | §Runtime / Handler: Überschrift „(historischer T011-04-Stand)"; Runtime/Handler-Zeilen mit „**historisch**, inzwischen `python3.14`"/Python-Handler markiert |
| `docs/features/F011-terraform-infrastructure.md` | Lambda-Lernbezug: Runtime- und Deployment-Package-Einträge auf „historische T011-04-Baseline" + aktuellen Python-Stand bezogen |
| `docs/reports/PRESENTATION-TECHNICAL-QA.md` | Abschnitt „Node.js vs Python 3.14" in `### Historischer Stand` / `### Migration` / `### Aktueller Stand` strukturiert; explizit: „**Node.js/TypeScript ist kein Bestandteil des aktuellen Lambda-Deployments.**"; Tabelle „Node-Baseline (historisch)" vs. „Python 3.14 (aktuell)" |

Keine Änderungen an: `lambda/README.md`, `terraform/README.md`, `AGENTS.md`,
`BUILD.md`, `tests/test-results.md`, `docs/architecture/
LAMBDA_RUNTIME_COMPARISON.md`, Migrations-/Cleanup-Report, CHANGELOG — diese
kennzeichnen die Node-Baseline bereits eindeutig als historisch/entfernt.

## Nicht geänderte Dateien

Absolut unverändert (keine Codeänderung):

- `terraform/main.tf` — Runtime `python3.14`, Handler `index.handler` (nur verifiziert, nicht geändert)
- Lambda Python-Code: `lambda/src/*.py` (unverändert)
- `lambda/build_zip.py` (unverändert)
- Terraform-Ressourcen (DynamoDB, IAM, Cognito, API Gateway) (unverändert)
- Kein `terraform plan`, kein `terraform apply`, keine AWS-Ressourcen erzeugt
- Kein Node.js/TypeScript wieder eingeführt, kein FastAPI eingeführt

## Verification

Repository-weite Suche nach Runtime-Hinweisen (Node.js / TypeScript /
nodejs22 / index.ts / orderService.ts / stateMachine.ts / validation.ts /
errors.ts / types.ts / Python / python3.14 / index.py):

- Alle verbleibenden Node.js/TypeScript-Erwähnungen stehen in **historischen
  Kontexten**: Migrationsbericht, Cleanup-Report, CHANGELOG-Einträge,
  F011-Sektion „historische Baseline", Vergleichsdokument, Plan-Review
  („kein nodejs22.x").
- Aktive Architektur-Darstellungen nennen eindeutig **Python 3.14** mit
  Handler `index.handler` (README, PROJECT_STATUS, F011, terraform/README,
  lambda/README, PRESENTATION-TECHNICAL-QA).
- Keine aktuelle Sektion behauptet oder suggeriert `Lambda = Node.js`.

## Final Status

- **AWS Lambda:** Python 3.14 (`python3.14`), Handler `index.handler` — aktiver
  Stand, dokumentiert.
- **Node.js/TypeScript:** historisch / Migrationsstand / NICHT mehr aktiv —
  eindeutig gekennzeichnet, über Git-Historie (`449cdd7`) nachvollziehbar.
- Keine Statusänderung: T011-01…T011-07 COMPLETE · T011-08 PLANNED (Freigabe
  erforderlich) · T011-09 OPTIONAL.
- AWS Resources: NONE · kein apply.