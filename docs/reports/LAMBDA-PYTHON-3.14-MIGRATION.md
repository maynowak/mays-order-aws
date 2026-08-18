# LAMBDA PYTHON 3.14 MIGRATION REPORT

> Migrationsbericht: Lambda-Order-Handler von Node.js/TypeScript (`nodejs22.x`)
> auf Python 3.14 (`python3.14`) portiert. Git bleibt Source of Truth.

## Summary

Der in F011/T011-04 implementierte Lambda-Order-Handler (`mays-orders-handler`,
AP1 Create / AP2 Get by ID / AP3 Listing / AP4 Status-Update) wurde vollständig
und funktional identisch von Node.js/TypeScript auf Python 3.14 portiert. Die
Node.js/TypeScript-Implementierung (T011-04, `nodejs22.x`) bleibt als
**historische Baseline** vollständig im Repository erhalten (Sources, Tests,
`package.json`/`tsconfig.json`, Vitest 45/45 weiterhin grün). Die aktive Lambda
verwendet jetzt die Python-3.14-Runtime mit boto3 (von der Lambda-Runtime
bereitgestellt) und einem reproduzierbaren ZIP-Build (`lambda/build_zip.py` →
`dist/lambda.zip`).

Terraform, DynamoDB-Architektur und IAM wurden **nicht** unnötig verändert:
einzig `runtime` wurde von `nodejs22.x` auf `python3.14` umgestellt. Kein
`apply`, keine AWS-Ressourcen erzeugt, keine Kosten.

## Baseline

| Komponente | Pfad | Detail |
|------------|------|--------|
| Git Branch (vor Migration) | `main` | HEAD `ce4b62e` (docs-Checkpoint zu T011-04 `449cdd7`) |
| Lambda Resource | `terraform/main.tf` | `aws_lambda_function.handler` |
| Runtime (vorher) | `terraform/main.tf` | `runtime = "nodejs22.x"` |
| Handler (vorher) | `terraform/main.tf` | `handler = "index.handler"` (CommonJS-Bundle) |
| ZIP-Pfad | `terraform/main.tf` | `filename = "${path.module}/../lambda/dist/lambda.zip"` |
| Source-Dateien | `lambda/src/*.ts` | `index.ts`, `orderService.ts`, `stateMachine.ts`, `validation.ts`, `errors.ts`, `types.ts` |
| Build | `lambda/package.json` | `npm run build` = `tsc --noEmit` + esbuild-Bundle |
| Packaging | `lambda/package.json` | `npm run package` = bestzip → `dist/lambda.zip` (~156 KB, nur `dist/index.js`) |
| Tests | `lambda/tests/*.test.ts` | Vitest 45/45 PASS (stateMachine 14, validation 19, orderService 12) |
| IAM Role | `terraform/main.tf` | `aws_iam_role.handler` (T011-03, Least Privilege) |
| DynamoDB | `terraform/main.tf` | `aws_dynamodb_table.orders` + GSI1 (unverändert) |
| Env-Variablen | `terraform/main.tf` | `ORDERS_TABLE`; zur Laufzeit zusätzlich `AWS_REGION` |

## Node.js → Python Mapping

| Node.js/TypeScript | Python | Funktion |
|---|---|---|
| `lambda/src/index.ts` | `lambda/src/index.py` | Lambda-Handler, Routing (API-GW-v2-Event), Body-Parsing (Base64), Fehler→HTTP-Mapping |
| `lambda/src/orderService.ts` | `lambda/src/order_service.py` | Order-Service AP1..AP4 (PutItem/GetItem/Query GSI1/UpdateItem conditional), Pagination-Tokens |
| `lambda/src/stateMachine.ts` | `lambda/src/state_machine.py` | Transition-Matrix + `can_transition` (pure Funktion) |
| `lambda/src/validation.ts` | `lambda/src/validation.py` | Request-/Path-/Query-Validierung (gleiche Regeln & Fehlermeldungen) |
| `lambda/src/errors.ts` | `lambda/src/errors.py` | `OrderError`-Klasse + Fehler-Factorys + `error_body`-Format |
| `lambda/src/types.ts` | `lambda/src/order_types.py` | Konstanten + Typdefinitionen (TypedDict). **Kein `types.py`** — Name kollidiert mit Python-Stdlib `types` und würde boto3 im ZIP brechen |
| `lambda/tests/stateMachine.test.ts` | `lambda/tests/test_state_machine.py` | State-Machine-Tests (gleiche Fälle) |
| `lambda/tests/validation.test.ts` | `lambda/tests/test_validation.py` | Validierungs-Tests (gleiche Fälle) |
| `lambda/tests/orderService.test.ts` | `lambda/tests/test_order_service.py` | Order-Service-Tests mit Fake-DynamoDB-Client (wie Node-`FakeDocClient`) |
| — (kein Handler-Test in Node) | `lambda/tests/test_index.py` | **neu:** Handler-Verhalten (Routing, Body-Parsing, Fehler-Mapping, `ORDERS_TABLE`-Check) — gefordert in der Migrations-Vorgabe |
| `lambda/package.json` (`build`/`package`) | `lambda/build_zip.py` | Python-ZIP-Build (Stdlib `zipfile`, reproduzierbar) |

Keine Datei ohne realen Bezug erzeugt. Die Node-Vorgänger-Dateien bleiben
unverändert als Baseline bestehen.

## Changed Files

Neue/geänderte Dateien (Branch `feature/lambda-python-314`):

| Datei | Art | Zweck |
|-------|-----|-------|
| `lambda/src/index.py` | neu | Python-Handler |
| `lambda/src/order_service.py` | neu | Order-Service (boto3) |
| `lambda/src/state_machine.py` | neu | Transition-Matrix |
| `lambda/src/validation.py` | neu | Validierung |
| `lambda/src/errors.py` | neu | Fehler-Modell |
| `lambda/src/order_types.py` | neu | Konstanten/Typen |
| `lambda/tests/test_state_machine.py` | neu | Tests (portiert) |
| `lambda/tests/test_validation.py` | neu | Tests (portiert) |
| `lambda/tests/test_order_service.py` | neu | Tests (portiert) |
| `lambda/tests/test_index.py` | neu | Handler-Tests (neu) |
| `lambda/build_zip.py` | neu | Reproduzierbarer ZIP-Build |
| `terraform/main.tf` | geändert | `runtime = "python3.14"` (einzige Terraform-Änderung) |
| `.gitignore` | geändert | `__pycache__/`, `*.pyc` ergänzt |
| `docs/architecture/LAMBDA_RUNTIME_COMPARISON.md` | neu | Node.js vs. Python-Vergleich |
| `docs/reports/LAMBDA-PYTHON-3.14-MIGRATION.md` | neu | dieser Bericht |
| `docs/PROJECT_STATUS.md` | geändert | Status aktualisiert |
| `docs/features/F011-terraform-infrastructure.md` | geändert | Migrationsabschnitt ergänzt |
| `docs/reports/WEEK-02.md` | geändert | Wochenreport aktualisiert |
| `docs/CHANGELOG.md` | geändert | Changelog-Eintrag |
| `terraform/README.md` | geändert | Lambda §2.3: Python-Runtime/Build |
| `lambda/README.md` | neu | Build-/Test-Anleitung (Node-Baseline + Python aktiv) |

## Python 3.14 Runtime

- **DATEI:** `terraform/main.tf`
- **ÄNDERUNG:** `runtime = "python3.14"` (vorher `nodejs22.x`) im Block
  `aws_lambda_function.handler`.
- **Handler-Eintrag:** `handler = "index.handler"` bleibt gültig — Python-Lambda
  löst `index.handler` als `from index import handler` auf; `index.py` liegt am
  ZIP-Root.
- Weitere Argumente unverändert: `timeout = 10`, `environment.ORDERS_TABLE`,
  `filename = ../lambda/dist/lambda.zip`, `source_code_hash` (berechnet bei
  `plan`/`apply` aus dem Zip), `role = aws_iam_role.handler.arn`.

## Lambda Handler

`lambda/src/index.py` liefert `def handler(event, context) -> dict`:

- Akzeptiert das API-Gateway-HTTP-API-v2-Eventformat (`routeKey`, `httpMethod`,
  `rawPath`, `pathParameters`, `queryStringParameters`, `body`,
  `isBase64Encoded`) und gibt v2-Proxy-Responses zurück.
- Routing identisch zu Node: `POST /orders`, `GET /orders`,
  `GET /orders/{orderId}`, `PATCH /orders/{orderId}/status`, sonst 400.
- Body: JSON-Parsing inkl. Base64-Decodierung; ungültiges JSON → 400
  `VALIDATION_ERROR`.
- Fehler: `OrderError` → `{ error: { code, message, details? } }` mit
  zugehörigem HTTP-Status; unbekannte Fehler → 500 `INTERNAL_ERROR` + Log auf
  stderr.
- `ORDERS_TABLE` aus Env; fehlt sie → 500 mit klarer Meldung.
- Boto3-DynamoDB-Resource wird **lazy** erzeugt und über Warm-Starts
  wiederverwendet (Standard-Lambda-Praxis; im Node-Baseline-Stand wurde je
  Invocation ein neuer Client erzeugt — bewusste, dokumentierte Verbesserung,
  keine Architekturänderung).

## DynamoDB Integration

Architektur **unverändert** (keine Änderung an Table Design, PK/SK, GSI1,
Access Patterns, Conditional Writes):

- `lambda/src/order_service.py` nutzt boto3 (`dynamodb.Table`-API analog zum
  Node-DocumentClient).
- AP1 `PutItem` (PENDING, `totalAmount` server-seitig, GSI1-Eintrag)
- AP2 `GetItem` (`pk=ORDER#<id>`, `sk=#ORDER`) → 404 `ORDER_NOT_FOUND`
- AP3 `Query` auf GSI1 (`gsi1pk=LIST`, `ScanIndexForward=False`, `Limit`,
  `ExclusiveStartKey`; `nextToken` = Base64-kodierter `LastEvaluatedKey`,
  serialisiert wie `JSON.stringify` ohne Leerzeichen)
- AP4 `GetItem` → `can_transition` → `UpdateItem` mit
  `ConditionExpression: attribute_exists(pk) AND #status = :currentStatus`,
  `version + 1`; boto3-`ClientError` `ConditionalCheckFailedException` → 409
  `CONFLICTED_UPDATE`; `ValidationException` → 400 `VALIDATION_ERROR`.
- Kein `Scan`, kein `DeleteItem` (konsistent zur Least-Privilege-Policy).

## IAM

- `aws_iam_role.handler` (T011-03) wird **unverändert** weiterverwendet —
  **keine zweite Execution Role**.
- **Keine neuen Permissions erforderlich:** Die Python-Funktion nutzt exakt
  dieselben DynamoDB-Aktionen (`PutItem`/`GetItem`/`UpdateItem`/`Query`) auf
  Tabelle + GSI1 und dieselben Log-Rechte (`logs:CreateLogGroup`/
  `CreateLogStream`/`PutLogEvents`). Boto3 benötigt keine zusätzliche
  Permission gegenüber dem AWS-SDK for JavaScript.
- Least Privilege bleibt erhalten (kein Scan/DeleteItem/BatchWriteItem, keine
  s3/sqs/iam-Rechte).

## Packaging

- Node-Baseline-Build (`npm run build` + `npm run package`, esbuild + bestzip)
  nachvollzogen; Baseline-Zip `dist/lambda.zip` ~156 KB (nur `dist/index.js`).
- Neuer Python-Build: `lambda/build_zip.py` (reine Stdlib `zipfile`) →
  `dist/lambda.zip` mit den 6 Python-Modulen am ZIP-Root (6.779 Bytes / ~6,6 KB,
  sha256 `0af0c4d2…`).
- **Entscheidung boto3:** wird von der AWS-Python-Lambda-Runtime bereits
  bereitgestellt → **keine** zusätzliche Version ins ZIP paketiert, **kein**
  `requirements.txt` nötig. (Lokal ist boto3 nicht installiert; Tests nutzen
  Fake-Clients wie im Node-Baseline-Stand.)
- **Keine Secrets im ZIP** (nur Source-Module; Secret-Audit PASS).
- ZIP-Integrität: `unzip -t` PASS; Handler-Import-Smoke-Test aus ZIP-Root-Layout
  PASS.

## Tests

Ausgeführt mit lokalem `python3` (3.12.3) — Ziel-Runtime bleibt `python3.14`:

```text
cd lambda && PYTHONPATH=src python3 -m unittest discover -s tests -v
```

| Bereich | Datei | Testergebnis |
|---------|-------|--------------|
| State Machine | `tests/test_state_machine.py` | PASS (4 Test-Methoden, parametrisiert: 6 erlaubt, 6 verboten, 12 Endzustand, 6 Idempotenz) |
| Validation | `tests/test_validation.py` | PASS (19 Test-Methoden) |
| Order Service | `tests/test_order_service.py` | PASS (12 Test-Methoden, Fake-DynamoDB) |
| Handler-Verhalten | `tests/test_index.py` | PASS (14 Test-Methoden, Routing/Fehler/Parsing) |
| **Gesamt** | | **49 Test-Methoden, 0 Fehler (OK)** |

Hinweis zur Zählweise: Vitest (Node-Baseline) zählt jedes `it()` = 45 Tests.
Python-`unittest` zählt Test-Methoden; parametrisierte Fälle (SubTests) sind
Teil der Methoden. Sämtliche fachlichen Fälle der Baseline sind abgedeckt.
`python3 -m compileall` (Syntax-Check) PASS. Node-Baseline unverändert:
Vitest 45/45 PASS, `tsc --noEmit` PASS.

## Terraform Validation

- `terraform fmt` — PASS
- `terraform init` (AWS-Provider ~> 6.0 / 6.60.0) — PASS
- `terraform validate` — PASS (ohne Warnungen)
- `terraform plan` — NOT RUN (gehört laut Projektplan zu T011-07, nicht
  vorgezogen)
- `terraform apply` — NOT RUN (keine AWS-Ressourcen erzeugen)
- AWS-Provider bleibt 6.x (`~> 6.0`, 6.60.0) — kein Downgrade auf 5.x

## Node.js vs Python Comparison

Detaillierte Gegenüberstellung: `docs/architecture/LAMBDA_RUNTIME_COMPARISON.md`.

## Performance / Cost

Nur tatsächlich gemessene Werte; nicht gemessene Werte ausdrücklich markiert:

| Metrik | Node.js (Baseline) | Python 3.14 | Quelle |
|--------|--------------------|-------------|--------|
| Package Size (ZIP) | ~156 KB (nur `dist/index.js`) | 6.779 Bytes (~6,6 KB) | gemessen (`ls`/`zipinfo`) |
| Unit-Tests | 45/45 | 49/49 | gemessen (ausgeführt) |
| Cold Start | nicht gemessen | nicht gemessen | kein AWS-Runtime-Einsatz |
| Init Duration | nicht gemessen | nicht gemessen | kein apply/keine Invocation |
| Memory Size | nicht gemessen (Terraform: Default) | nicht gemessen (Terraform: Default) | kein apply |
| Max Memory Used | nicht gemessen | nicht gemessen | kein apply |
| Duration | nicht gemessen | nicht gemessen | kein apply |
| Invocation Count | 0 | 0 | kein apply |
| geschätzte Lambda-Kosten | 0 (nicht deployed) | 0 (nicht deployed) | keine Ressourcen |

Für einen späteren kontrollierten Vergleich sind Baseline und Python-Stand
hinsichtlich Memory/Duration/Init Dauer vergleichbar messbar (gleiche
AP1..AP4-Arbeitslast, gleicher `timeout`). Der Messplan ist in
`docs/architecture/LAMBDA_RUNTIME_COMPARISON.md` §Performance beschrieben.

## Known Limitations

- `dist/lambda.zip` wird jetzt vom Python-Build erzeugt; der Node-Baseline-Build
  (`npm run package`) würde denselben Pfad überschreiben. Beide Builds sind
  reproduzierbar; für den aktiven Python-Runtime-Stand gilt
  `python3 build_zip.py`. `dist/` ist gitignored.
- Tests laufen lokal unter Python 3.12.3 (System-Python); die Lambda-Ziel-
  Runtime ist `python3.14`. Ein echter 3.14-Runtime-Test ist erst nach `apply`
  möglich (nicht durchgeführt).
- Boto3-`ClientError`-Erkennung ist an `response.Error.Code` gekoppelt (boto3-
  Standard). Der Fake-Client in den Tests bildet das nach.
- API-GW→Lambda Invoke-Permission fehlt weiterhin bewusst (T011-06).

## Git Checkpoint

- Branch: `feature/lambda-python-314` (Feature-Branch wird **nicht** gelöscht)
- Commit: `64130a9` (feat: F011 Lambda-Handler auf Python 3.14 portieren) +
  Docs-Nachzug (Status/Changelog/WEEK-02)
- Baseline-Commits: `449cdd7` (T011-04 Node-Code), `ce4b62e` (Docs-Nachzug)

## Push Status

- PENDING (Push wird nach dem Docs-Nachzug ausgeführt und hier dokumentiert)

## Current Project State

- Lambda Runtime: **Python 3.14** (Terraform `runtime = "python3.14"`)
- Migration: **COMPLETE** (Code, Tests, Packaging, Terraform, Doku validiert)
- Node.js/TypeScript T011-04: historische Baseline, weiterhin im Repo, 45/45
  Tests grün
- AWS Resources: NONE (kein apply)
- Week 2 IN PROGRESS · F011 IN PROGRESS (T011-01…04 COMPLETE · T011-05 NEXT)

## Next Step

T011-05 — Cognito (Pool, Client, Gruppe) — separater Task / Prompt. STOP.
