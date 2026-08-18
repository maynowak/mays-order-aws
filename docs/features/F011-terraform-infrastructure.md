# F011 — Terraform Infrastructure

| Feld | Wert |
|------|------|
| **ID** | F011 |
| **Name** | Terraform Infrastructure |
| **Status** | 🔵 IN PROGRESS |
| **Week** | 2 |
| **Abhängigkeiten** | F001 |
| **Fachquelle** | `terraform/README.md`, `architecture/architecture-decisions.md` |

## Beschreibung

IaC für DynamoDB, IAM, Lambda, Cognito, HTTP API, CloudWatch. `terraform validate`/`plan`
vor jedem Apply; `apply` nur nach menschlicher Freigabe. Keine manuell erzeugte Infrastruktur.

## Tasks

| ID | Task | Status |
|----|------|--------|
| T011-01 | Terraform-Gerüst (main/variables/outputs/README) | ✅ COMPLETE |
| T011-02 | DynamoDB-Tabelle + GSI1 | ✅ COMPLETE |
| T011-03 | IAM-Rolle + Policy | ✅ COMPLETE |
| T011-04 | Lambda (Zip-Build) + Permission | ✅ COMPLETE |
| T011-05 | Cognito (Pool, Client, Gruppe) | ✅ COMPLETE |
| T011-06 | HTTP API + Routen + Authorizer | ✅ COMPLETE |
| T011-07 | `terraform validate` + `plan` (Review) | ⏳ PLANNED |
| T011-08 | `terraform apply` (nach Freigabe) + Outputs dokumentieren | ⏳ PLANNED |
| T011-09 | (Optional) S3-Backend-Entscheidung | ⏳ PLANNED |

## Progress — laufender Arbeitsstand (Persistent Feature Progress)

```text
Feature:
F011 — Terraform Infrastructure

Status:
🔵 IN PROGRESS

Current Task:
T011-07 — terraform validate + plan (Review) (separater Prompt / Task)

Completed Tasks:
- T011-01 Terraform-Gerüst             ✅
- T011-02 DynamoDB-Tabelle + GSI1       ✅
- T011-03 IAM-Rolle + Policy            ✅
- T011-04 Lambda (Zip-Build) + Permission ✅ (Node.js/TypeScript-Baseline)
- LAMBDA-PY-314 Lambda-Handler auf Python 3.14 portiert ✅
- T011-05 Cognito (Pool, Client, Gruppe) ✅ (merged nach main)
- T011-06 HTTP API + Routen + Authorizer ✅ (merged nach main via 8a85b5e)

In Progress:
- (keine — T011-07 beginnt mit separatem Task)

Pending Tasks:
- T011-07 terraform validate + plan (Review)
- T011-08 terraform apply (nach Freigabe)
- T011-09 (Optional) S3-Backend-Entscheidung

Changes Made:
- (T011-01) terraform/main.tf erstellt (terraform-Block, AWS-Provider, Region, Default-Tags)
- (T011-01) terraform/variables.tf erstellt (project_name, aws_region, tags)
- (T011-01) terraform/outputs.tf erstellt (leer; Outputs folgen je Ressource ab T011-02)
- (T011-01) terraform/README.md aktualisiert (Struktur auf T011-01-Stand)
- (T011-01) terraform/.terraform.lock.hcl committet
- (T011-02) terraform/main.tf: `aws_dynamodb_table.orders` ergänzt (Name, On-Demand,
  PK `pk`/`sk`, GSI1 `gsi1pk`/`gsi1sk` mit INCLUDE-Projection)
- (T011-02) terraform/outputs.tf: `dynamodb_table_name`, `dynamodb_table_arn` ergänzt
- (T011-02) terraform/README.md: DynamoDB-Design (T011-02) dokumentiert
- (PROVIDER-UPGRADE) terraform/main.tf: AWS-Provider `~> 5.0` → `~> 6.0`
- (PROVIDER-UPGRADE) terraform/main.tf: GSI1 von `hash_key`/`range_key` auf `key_schema`-Blocks umgestellt
- (PROVIDER-UPGRADE) terraform/.terraform.lock.hcl: aws provider 5.100.0 → 6.60.0
- (PROVIDER-UPGRADE) terraform/README.md: Provider-Hinweis aktualisiert
- (T011-03) terraform/main.tf: `data.aws_iam_policy_document.handler_trust` (lambda.amazonaws.com)
  + `data.aws_iam_policy_document.handler` (DynamoDB auf Tabelle+GSI1, Logs)
  + `aws_iam_role.handler` (${var.project_name}-handler-role) + `aws_iam_role_policy.handler`
- (T011-03) terraform/outputs.tf: `iam_handler_role_name`, `iam_handler_role_arn` ergänzt
- (T011-03) terraform/README.md: IAM-Design (T011-03) mit Least-Privilege-Tabelle dokumentiert
- (KORREKTUR-CHECK) Gemeldeter Fehler `Required attribute "hash_key" not specified` auf
  `aws_dynamodb_table.orders` verifiziert: Tabelle hat `hash_key = "pk"` + `range_key = "sk"`,
  GSI1 nutzt weiterhin `key_schema`-Blocks (nicht deprecated), `terraform validate` PASS →
  keine Code-Änderung erforderlich
- (FINAL-DIAGNOSTIC) terraform-ls 0.39.0 direkt per LSP (serve, Root = Repo) getrieben:
  Root-Modul `terraform/` korrekt erkannt; Provider-Erkennung sieht nur noch 6.60.0;
  `ObtainSchema`/`SchemaModuleValidation`/`ReferenceValidation` → err = nil (keine Diagnostics)
- (FINAL-DIAGNOSTIC) `textDocument/completion` IM GSI-Block → schlägt `key_schema` vor
  (modernes Schema aktiv) ⇒ main.tf mit 6.60.0 valide; Fehlerursache = veraltetes
  In-Memory-Schema 5.100.0 eines laufenden Language-Server-Sessions (GSI-`key_schema`
  existiert erst ab Provider 6.29.0, PR #46602)
- (FINAL-DIAGNOSTIC) Altlast `/tmp/terraform-provider1730277575` identifiziert
  (Distributions-Zip aws 5.100.0, 149 MB, T011-01-Ära) — optional löschbar
- (T011-04) lambda/ neu: TypeScript-Source (`src/index.ts` Handler, `src/orderService.ts`,
  `src/stateMachine.ts`, `src/validation.ts`, `src/errors.ts`, `src/types.ts`) + Unit-Tests
  (`tests/stateMachine.test.ts`, `tests/validation.test.ts`, `tests/orderService.test.ts`)
- (T011-04) lambda/package.json: `npm run build` (tsc --noEmit + esbuild-Bundle) /
  `npm run package` (bestzip → `dist/lambda.zip`) / `npm test` (Vitest)
- (T011-04) lambda/package-lock.json committet (Reproduzierbarkeit des Zip-Builds)
- (T011-04) terraform/main.tf: `aws_lambda_function.handler` ergänzt (nodejs22.x,
  `index.handler`, Timeout 10, `ORDERS_TABLE`-Env, `source_code_hash`, Execution Role
  `aws_iam_role.handler` aus T011-03)
- (T011-04) terraform/outputs.tf: `lambda_function_name`, `lambda_function_arn` ergänzt
- (T011-04) terraform/README.md: Lambda-Abschnitt (§2.3) + Ressourcentabelle aktualisiert
- (T011-04) Order-Operationen umgesetzt: AP1 Create (PutItem, totalAmount server-seitig),
  AP2 Get by ID (GetItem), AP3 Listing (Query GSI1, absteigend, paginiert), AP4 Status-Update
  (UpdateItem + Conditional Write, Race-Schutz). Beträge als ganze Cent (Integer).
- (T011-04) API-GW→Lambda Invoke-Permission bewusst NICHT in T011-04 — folgt in T011-06
  (HTTP API existiert noch nicht; nur dann Teil, wenn ausdrücklich dokumentiert)
- (LAMBDA-PY-314) lambda/src/*.py neu (Python-Port des Handlers): index.py, order_service.py,
  state_machine.py, validation.py, errors.py, order_types.py (bewusst NICHT types.py —
  Stdlib-`types`-Kollision im Lambda-ZIP)
- (LAMBDA-PY-314) lambda/tests/test_*.py neu (unittest): state_machine, validation,
  order_service, index (Handler-Verhalten)
- (LAMBDA-PY-314) lambda/build_zip.py neu: reproduzierbarer Python-ZIP-Build → dist/lambda.zip
  (6 Module, ~6,6 KB; boto3 von der Runtime, kein requirements.txt)
- (LAMBDA-PY-314) lambda/README.md neu (Build-/Test-Anleitung Python + Node-Baseline)
- (LAMBDA-PY-314) terraform/main.tf: `runtime = "nodejs22.x"` → `"python3.14"` (einzige
  Terraform-Änderung; DynamoDB/IAM unverändert)
- (LAMBDA-PY-314) .gitignore: `__pycache__/`, `*.pyc` ergänzt
- (LAMBDA-PY-314) docs/architecture/LAMBDA_RUNTIME_COMPARISON.md neu
- (LAMBDA-PY-314) docs/reports/LAMBDA-PYTHON-3.14-MIGRATION.md neu
- (PY314-INTEGRATION) `feature/lambda-python-314` nach `main` integriert
  (`git merge --no-ff`, Commit `20bfb05`, Push SUCCESS) — Pflicht-Voraussetzung für T011-05;
  Feature-Branch bleibt erhalten
- (T011-05) terraform/main.tf: `aws_cognito_user_pool.users` ergänzt
  (`${var.project_name}-users`, admin_create_user_config.allow_admin_create_user_only = true,
  Passwortrichtlinie Standardwerte, MFA OFF)
- (T011-05) terraform/main.tf: `aws_cognito_user_pool_client.app` ergänzt
  (`${var.project_name}-client`, explicit_auth_flows ALLOW_USER_PASSWORD_AUTH +
  ALLOW_REFRESH_TOKEN_AUTH, generate_secret = false — Public Client wegen USER_PASSWORD_AUTH)
- (T011-05) terraform/main.tf: `aws_cognito_user_group.staff` ergänzt (Gruppe `staff` →
  Claim `cognito:groups`; Ressourcenname `aws_cognito_user_group` in Provider 6.60.0,
  nicht `aws_cognito_user_pool_group`)
- (T011-05) terraform/outputs.tf: `cognito_user_pool_id`, `cognito_user_pool_arn`,
  `cognito_user_pool_client_id`, `cognito_user_pool_group_name` ergänzt
- (T011-05) terraform/README.md: Cognito-Abschnitt (§2.4) + Ressourcentabelle aktualisiert
- (T011-05) docs/features/F002-cognito-authentication.md: T002-01…03 COMPLETE (Terraform) nachgezogen
- (T011-06) terraform/main.tf: `aws_apigatewayv2_api.orders` (${var.project_name}-api,
  protocol_type HTTP) + `aws_apigatewayv2_stage.default` ($default, auto_deploy = true)
- (T011-06) terraform/main.tf: `aws_apigatewayv2_authorizer.jwt` (JWT, identity_sources
  `$request.header.Authorization`, jwt_configuration issuer = https://<cognito-endpoint>
  aus `aws_cognito_user_pool.users.endpoint`, audience = `aws_cognito_user_pool_client.app.id`)
- (T011-06) terraform/main.tf: `aws_apigatewayv2_integration.lambda` (AWS_PROXY,
  payload_format_version "2.0", integration_uri = aws_lambda_function.handler.invoke_arn)
- (T011-06) terraform/main.tf: vier `aws_apigatewayv2_route.*` (POST /orders,
  GET /orders/{orderId}, GET /orders, PATCH /orders/{orderId}/status), alle
  authorization_type JWT + authorizer_id
- (T011-06) terraform/main.tf: `aws_lambda_permission.api_gateway`
  (principal apigateway.amazonaws.com, source_arn ${execution_arn}/*/*)
- (T011-06) terraform/outputs.tf: `api_gateway_endpoint`, `api_gateway_id`,
  `api_gateway_authorizer_id` ergänzt
- (T011-06) terraform/README.md: §2.5 HTTP API (Ressourcentabelle, Routen, Entscheidungen),
  Ressourcentabelle §3 aktualisiert
- (T011-06) docs/features/F003-api-gateway.md: T003-01…06 COMPLETE (Terraform) nachgezogen
- (T011-06-RECOVERY) Nach VS-Code-/Agent-Absturz: T011-06-Stand evidenzbasiert verifiziert
  (Git: 9a332bf + 8a85b5e existieren, 9a332bf ancestor von main; Code: HTTP API/Routen/
  Authorizer/Integration/Permission in main; fmt/validate/diff-check/Secret-Audit PASS).
  Task-Tabelle + Progress-Block auf COMPLETE korrigiert; Report: docs/reports/T011-06-RECOVERY.md

Tests:
- Terraform init: PASS (aws provider v6.60.0, `~> 6.0`)
- Terraform validate: PASS (ohne Warnungen) — inkl. Cognito T011-05 + HTTP API T011-06
- Terraform fmt: PASS
- Python unittest (49 Test-Methoden): PASS (state_machine 4, validation 19,
  orderService 12, index 14) — lokal Python 3.12.3, Ziel `python3.14`
- Python compileall (Syntax): PASS
- Python ZIP-Build (`python3 build_zip.py`): PASS (~6,6 KB, 6 Module)
- ZIP-Integrität (`unzip -t`) + Handler-Import-Smoke aus ZIP-Root: PASS
- Node-Baseline unverändert: Vitest `npm test` PASS (45/45) · `tsc --noEmit` PASS
- LSP-Test terraform-ls 0.39.0 (serve, Root = Repo): PASS (keine Diagnostics, `key_schema` in Completion)
- Terraform plan: NOT RUN (gehört zu T011-07)

Validation:
- Terraform plan: NOT RUN (gehört zu T011-07)
- Terraform apply: NOT RUN (Freigabe erforderlich)
- Live-API: NOT RUN (kein apply; Lambda-Bundle nicht deployed)
- git diff --check: PASS
- Secret-Audit: PASS (inkl. lambda/ Python-Quelltext, build_zip.py, terraform/)

Known Issues:
- `index.py` unverändert: Der Handler routet bereits exakt über den HTTP-API-v2-Contract
  (`routeKey`, `pathParameters`, `queryStringParameters`, v2-Proxy-Response) — keine
  Anpassung für T011-06 erforderlich.
- Kein `aws_cognito_user_pool_domain` in T011-05: Login via USER_PASSWORD_AUTH benötigt
  kein Hosted-UI/OAuth-Redirect (terraform/README.md — Domain nur "falls nötig").
- Keine offene Selbst-Registrierung: `admin_create_user_config.allow_admin_create_user_only = true`
  (Staff-Benutzer werden administrativ angelegt, T002-04; keine Signup-Anforderung dokumentiert).
- Terraform-Provider 6.60.0 nutzt `aws_cognito_user_group` (nicht `aws_cognito_user_pool_group`)
  — Ressourcen-Renaming im Provider; dokumentiert in terraform/README.md.
- `cognito:groups`-Authorization (A-09) wird in T011-06 NICHT im Lambda ausgewertet:
  JWT-Authorizer validiert Issuer+Audience; Gruppenscoping bleibt für Woche 3 (Security) offen.
- Beträge als ganze Cent finalisiert (Vorab-Definition `database/dynamodb-design.md` §7;
  `api/api-documentation.md` §3 ist die maßgebliche Schemadarstellung). Die float-Beispiele
  in `api/endpoints.md` (§2.1) sind inkonsistent und bewusst NICHT geändert (keine
  Architekturänderung).
- `dist/lambda.zip` wird vom Python-Build erzeugt; `npm run package` würde den Pfad
  überschreiben (gitignored; beide Builds reproduzierbar). Aktiver Stand: `python3 build_zip.py`.
- Python-Tests laufen lokal unter 3.12.3 (System-Python); Ziel-Runtime `python3.14`.
  Ein echter 3.14-Runtime-Test ist erst nach `apply` möglich.

Blockers:
- None

Current Checkpoint:
`9a332bf` (Branch `feature/http-api` — T011-06 HTTP API + Routen + Authorizer;
Push SUCCESS auf origin/feature/http-api; gemerged nach main via `8a85b5e`)

Next Step:
T011-07 — terraform validate + plan (Review) (separater Prompt / Task)
```

## GSI1 — Begründung (T011-02)

```text
Access Pattern AP3 (GET /orders, Listing)
       ↓
Key Structure: gsi1pk = LIST (konstant), gsi1sk = createdAt (ISO-8601)
       ↓
Global Secondary Index "gsi1" (Projection INCLUDE: orderId, status, customer,
totalAmount, createdAt, updatedAt)
       ↓
Query(gsi1, gsi1pk = :LIST, ScanIndexForward = false, Limit, ExclusiveStartKey)
```

- **Warum GSI1 vorhanden:** Ohne Index wäre `GET /orders` ein `Scan` der gesamten
  Tabelle — linear wachsend mit der Datenmenge (siehe `database/dynamodb-design.md` §5).
- **Welches Access Pattern:** AP3 (Order Listing, paginiert, neueste zuerst).
- **Key-Struktur:** konstanter PK `LIST`, SK `createdAt` → alle Orders in einer
  GSI-Partition, sortiert nach Erstellzeit, lexikografisch korrekt absteigend.
- **Warum kein Scan:** Der Index liefert exakt die gewünschten Items als partitionierten
  `Query` mit nativem `LastEvaluatedKey`-Pagination — kein Scan, kosten- und
  latenzstabil bei wachsender Datenmenge (ADR-002).

Keine weiteren GSIs; keine weitere Index-Struktur (keine Architekturerweiterung).

## Provider 6.x Compatibility & Toolchain Verification (Diagnose-Task)

```text
Observation:
CLI:  terraform validate = PASS (AWS Provider 6.60.0)
VS Code: "Required attribute 'hash_key' not specified" + "Blocks of type 'key_schema' are not expected here" im GSI-Block
→ CLI- und Editor-Schema weichen ab.

Commands/Results:
- terraform version            → Terraform v1.15.8, aws v6.60.0
- terraform providers          → aws ~> 6.0
- .terraform.lock.hcl          → version = 6.60.0, constraints = ~> 6.0
- terraform providers schema -json (CLI, autoritativ):
    aws_dynamodb_table top-level: hash_key optional (nicht deprecated), range_key optional
    global_secondary_index: hash_key/range_key optional + deprecated=True,
                            key_schema block unterstützt (attribute_name/key_type required)
    aws_iam_role / aws_iam_role_policy / data.aws_iam_policy_document / provider region+default_tags: kompatibel
- terraform-ls (VS-Code-Extension 2.40.0): v0.39.0 — unterstützt key_schema grundsätzlich
- .terraform/providers enthielt ALTLIGEND 5.100.0 UND 6.60.0 (5.100.0 aus T011-01)

Conclusion:
Der Terraform-Code ist vollständig AWS-Provider-6.60.0-kompatibel — KEINE Code-Änderung nötig.
Die VS-Code-Diagnostics entsprechen dem AWS-Provider-Schema < 6.29.0 (5.100.0), d. h. ein
veraltetes Schema wurde vom Language Server/Editor-Cache bedient (lokale Altlast 5.100.0).

Fix (minimal-invasiv, nur Cache, keine Projektdatei):
- terraform/.terraform/providers/.../aws/5.100.0 entfernt
- terraform init: PASS → nur noch 6.60.0 installiert
- terraform validate: PASS
- VS Code: Terraform: init current folder + Fenster neu laden / Language Server neu starten
```

Compatibility-Matrix (nur tatsächlich vorhandene Bausteine):

| Bereich | Provider 6.x Status | Änderung nötig | Ergebnis |
|---------|--------------------|----------------|----------|
| Provider (`aws`, region, default_tags) | kompatibel | nein | OK |
| DynamoDB Table (`hash_key`/`range_key` top-level) | kompatibel, nicht deprecated | nein | OK |
| DynamoDB GSI1 (`key_schema`-Blocks) | kompatibel (≥ 6.29.0) | nein | OK |
| IAM Role (`aws_iam_role` + Trust) | kompatibel | nein | OK |
| IAM Policy (`aws_iam_role_policy` + `aws_iam_policy_document`) | kompatibel | nein | OK |
| Policy Attachment | nicht vorhanden (inline) | – | n/a |
| Outputs (`outputs.tf`) | kompatibel | nein | OK |
| Tags (Default-Tags, merge) | kompatibel | nein | OK |

## Final Diagnostic — VS Code / terraform-ls zeigt veraltetes AWS-Provider-Schema (5.100.0)

```text
Observation:
VS Code zeigte trotz AWS-Provider-6.60.0-Code weiterhin:
  "Required attribute 'hash_key' not specified" (GSI-Ebene) +
  "Blocks of type 'key_schema' are not expected here" (Zeile 48/53/58)
Terraform CLI (v1.15.8 + AWS 6.60.0) validierte dagegen ohne Fehler.

Root Cause (belegt):
- GSI-`key_schema` in aws_dynamodb_table existiert erst seit AWS-Provider v6.29.0
  (PR #46602; vor 6.29.0 sind für GSI nur `hash_key`/`range_key` erlaubt → exakt die
  gemeldeten Fehler). Die Altversion 5.100.0 (T011-01-Stand) kennt kein GSI-`key_schema`.
- terraform-ls (Extension 2.40.0 / LS 0.39.0) bezieht das Provider-Schema aus der
  LOKALEN Provider-Installation (.terraform/providers), ausgewählt über das Lockfile.
  Mit installiertem 5.100.0 wurde das alte Schema bedient.
- Der Language Server übernimmt Provider-/Lockfile-Änderungen NICHT zur Laufzeit
  (Initialize-Log: "Client doesn't support dynamic watched files registration, provider
  and module changes may not be reflected at runtime"); das Schema wird in-memory pro
  Session gehalten (kein Disk-Cache nachweisbar). ⇒ Nach dem Upgrade blieben die
  Fehler bestehen, bis der Language Server neu gestartet wird.

LSP-Verifikation (terraform-ls serve, LSP over stdio, Root = Repo):
- Root-Modul korrekt erkannt: /home/dci-student/projects/Mays-Orders-AWS/terraform
- Provider-Erkennung: .terraform/providers/.../hashicorp/aws/6.60.0 (nur noch 6.60.0)
- Jobs: GetTerraformVersion / ParseProviderVersions / ObtainSchema / SchemaModuleValidation
  / ReferenceValidation → alle err = nil → KEINE Diagnostics
- textDocument/completion IM GSI-Block → schlägt `key_schema` (sowie deprecated
  hash_key/range_key) vor ⇒ modernes 6.60.0-Schema aktiv, Datei valide
- textDocument/hover / workspace/executeCommand validate: kein Fehler

Befund:
- terraform-ls 0.39.0 validiert main.tf im aktuellen Zustand FEHLERFREI.
- Die gemeldeten VS-Code-Fehler stammen vom veralteten 5.100.0-Schema eines noch
  laufenden/gecachten Language-Server-Sessions — kein Code-Problem.

Abschluss:
- Altes Plugin 5.100.0 entfernt (Cache-Cleanup, erledigt); init → nur 6.60.0; validate PASS
- Optionale Altlast: /tmp/terraform-provider1730277575 (149 MB, Distributions-Zip
  aws 5.100.0 aus der T011-01-Ära) — kann gelöscht werden
- VS Code: Fenster neu laden (Developer: Reload Window) bzw. "Terraform: Restart
  Language Server" → stale Diagnostics verschwinden (CLI- und LSP-seitig belegt)
```

### Warum CLI vs. Editor unterschiedlich urteilten

| Quelle | Schema-Quelle | Ergebnis |
|--------|---------------|----------|
| Terraform CLI `validate` | lokale Provider-Installation (6.60.0, Lockfile) | PASS |
| terraform-ls 0.39.0 (frischer LSP-Session) | lokale Provider-Installation (6.60.0) | PASS (keine Diagnostics, `key_schema` in Completion) |
| VS-Code-Diagnostics (vor Reload) | veraltetes In-Memory-Schema 5.100.0 (< 6.29.0) | 2 Fehler (GSI `key_schema`/`hash_key`) |

## IAM-Lernbezug (T011-03, wiederverwendbar für Vortrag/Zertifizierung)

```text
IAM Role
→ IAM-Rolle
→ Identität mit Berechtigungsrahmen, die ein AWS-Service (Lambda) zur Ausführung übernehmen kann

IAM Policy
→ Berechtigungsrichtlinie
→ beschreibt erlaubte Aktionen (Actions) und Ziel-Ressourcen (Resources)

Trust Policy
→ Vertrauensrichtlinie (Assume Role)
→ bestimmt, welcher AWS-Service/Principal die Rolle übernehmen darf (hier: lambda.amazonaws.com)

Least Privilege
→ Prinzip der minimal erforderlichen Berechtigungen
→ Lambda erhält nur DynamoDB-Aktionen für Tabelle+GSI1 und Log-Rechte — kein Scan/DeleteItem, keine s3/sqs/iam-Rechte
```

## T011-04 — Lambda Order Handler (Zip-Build, Node.js/TypeScript — historische Baseline)

### Summary

Die in der Architektur vorgesehene Lambda-Funktion (`mays-orders-handler`) wurde als
TypeScript-Handler mit reproduzierbarem ZIP-Build umgesetzt. Sie implementiert die vier
Order-Operationen (AP1 Create, AP2 Get by ID, AP3 Listing, AP4 Status-Update) exakt nach
`api/endpoints.md` und `database/access-patterns.md` und nutzt die IAM Execution Role aus
T011-03 (`aws_iam_role.handler`). Kein `apply`, keine AWS-Ressourcen.

### Lambda Design

```text
Client (später: API Gateway HTTP API)
  ↓  Event (routeKey / httpMethod + rawPath, body, queryStringParameters, pathParameters)
index.ts (Handler, Routing, Fehler-Mapping → HTTP)
  ↓
orderService.ts (AP1..AP4: PutItem / GetItem / Query GSI1 / UpdateItem conditional)
  ↓                       ↓
validation.ts           stateMachine.ts (Transition-Matrix, pure Funktion)
  ↓
DynamoDB (mays-orders, GSI1)
```

- Handler akzeptiert das API-Gateway-HTTP-API-v2-Eventformat (`routeKey`, `rawPath`,
  `pathParameters`, `queryStringParameters`, `body`, `isBase64Encoded`) und gibt
  v2-Proxy-Responses zurück (kein API-Gateway-/Cognito-Feature in T011-04).
- AP1: Server berechnet `lineTotal` und `totalAmount` (nie der Client); Status `PENDING`;
  `gsi1pk=LIST`, `gsi1sk=createdAt`, `version=1`.
- AP2: `GetItem` auf `pk=ORDER#<id>`, `sk=#ORDER`; fehlt → 404 `ORDER_NOT_FOUND`.
- AP3: `Query` auf GSI1 (`gsi1pk=LIST`, `ScanIndexForward=false`, `Limit`, `ExclusiveStartKey`);
  `nextToken` = Base64-kodierter `LastEvaluatedKey`; kompakte Order-Darstellung.
- AP4: `GetItem` → Transition via State Machine prüfen (ungültig → 409 `INVALID_TRANSITION`
  mit `currentStatus`/`requestedStatus`) → `UpdateItem` mit Conditional Write
  (`attribute_exists(pk) AND #status = :current`, `version = version + 1`);
  `ConditionalCheckFailedException` → 409 `CONFLICTED_UPDATE` (Race-Schutz, R-01).
- Fehlerformat einheitlich `{ error: { code, message, details? } }` (api/endpoints.md §3).

### Runtime / Handler

| Eigenschaft | Wert |
|-------------|------|
| Runtime | `nodejs22.x` (AWS Lambda) |
| Handler | `index.handler` (CommonJS-Bundle, `lambda/dist/index.js`) |
| Env-Variable | `ORDERS_TABLE` (Tabellenname aus Terraform) |
| Timeout | 10 s (Cold-Start + DynamoDB-Latenz) |

### Packaging / ZIP

- `cd lambda && npm install && npm run package`
- `npm run package` = `tsc --noEmit` (Typecheck) + esbuild-Bundle (ein File, minified)
  + `bestzip` → `dist/lambda.zip` (nur `dist/index.js`, ~156 KB; keine Secrets,
  keine node_modules im Zip).
- Reproduzierbar: `package-lock.json` committet, Versionen fixiert, `npm audit` 0.
- Terraform referenziert `../lambda/dist/lambda.zip` + `source_code_hash`
  (`filebase64sha256`) → Update-Erkennung beim `apply`.

### IAM Execution Role

- Verwendet: `aws_iam_role.handler` aus T011-03 (Trust: `lambda.amazonaws.com`).
- Keine zweite Execution Role, keine neuen Permissions, keine Access Keys.
- API-GW→Lambda Invoke-Permission (`aws_lambda_permission`): bewusst **nicht** in T011-04,
  folgt in T011-06 (HTTP API + Routen + Authorizer), da nur dort der API-GW-ARN bekannt ist.

### DynamoDB Integration

- `@aws-sdk/lib-dynamodb` (DocumentClient) gegen `mays-orders` (Tabelle + GSI1).
- Operations exakt gemäß `database/access-patterns.md` §2 (PutItem/GetItem/Query/UpdateItem),
  kein `Scan`, kein `DeleteItem` — konsistent mit der Least-Privilege-Policy (T011-03).
- Beträge als ganze Cent (Integer) — Vorab-Definition `database/dynamodb-design.md` §7
  finalisiert; maßgebliches Schema: `api/api-documentation.md` §3.

## Lambda-Lernbezug (T011-04, wiederverwendbar für Vortrag/Zertifizierung)

```text
Lambda
→ Serverless Compute
→ Ausführung von Code auf Anfrage ohne Server-Verwaltung; nur für die Laufzeit der
  Invocation bezahlt; skaliert automatisch (ADR-001)

Execution Role
→ IAM-Rolle, die die Lambda-Funktion zur Laufzeit übernimmt
→ bestimmt, welche AWS-Services die Funktion aufrufen darf (hier: DynamoDB + Logs, Least Privilege)

Handler
→ Einstiegspunkt der Lambda-Funktion
→ "index.handler" = exportierte async-Funktion, die das Event empfängt und eine Antwort liefert

Runtime
→ Ausführungsumgebung der Lambda-Funktion
→ hier: Node.js 22 (nodejs22.x); steuert Sprach- und Laufzeit-Verhalten

Deployment Package / ZIP
→ verpackter Lambda-Code
→ hier: dist/lambda.zip (ein gebündeltes JS-File); Terraform lädt es per filename/source_code_hash
```

## Lambda Python-3.14-Migration (Branch `feature/lambda-python-314`)

### Summary

Der in T011-04 gebaute Lambda-Order-Handler (AP1..AP4) wurde funktional
identisch auf Python 3.14 portiert. Die Node.js/TypeScript-Implementierung
bleibt als **historische Baseline** vollständig im Repo (Sources, Tests,
Vitest 45/45 grün, `tsc --noEmit` PASS). Die aktive Lambda nutzt jetzt
`runtime = "python3.14"` mit boto3 (von der Runtime bereitgestellt).
DynamoDB-Architektur und IAM unverändert (Least Privilege). Kein `apply`.

### Mapping (Auswahl; vollständige Tabelle in `docs/reports/LAMBDA-PYTHON-3.14-MIGRATION.md`)

| Node.js/TypeScript | Python | Funktion |
|---|---|---|
| `lambda/src/index.ts` | `lambda/src/index.py` | Handler + Routing + Fehler→HTTP |
| `lambda/src/orderService.ts` | `lambda/src/order_service.py` | Order-Service AP1..AP4 (boto3) |
| `lambda/src/stateMachine.ts` | `lambda/src/state_machine.py` | Transition-Matrix |
| `lambda/src/validation.ts` | `lambda/src/validation.py` | Validierung |
| `lambda/src/errors.ts` | `lambda/src/errors.py` | OrderError + Factorys |
| `lambda/src/types.ts` | `lambda/src/order_types.py` | Konstanten + Typen (kein `types.py` — Stdlib-Kollision) |

### Terraform / Handler

- `terraform/main.tf` `aws_lambda_function.handler`: `runtime = "python3.14"`
  (einzige Terraform-Änderung; `handler = "index.handler"`, `timeout = 10`,
  `ORDERS_TABLE`, `source_code_hash`, Role T011-03 unverändert).
- Python-Handler `index.handler` = `from index import handler`; `index.py` am
  ZIP-Root.

### DynamoDB / IAM

- DynamoDB: exakt dieselben Operationen (PutItem/GetItem/Query GSI1/UpdateItem
  conditional); `ConditionalCheckFailedException` → 409 `CONFLICTED_UPDATE`,
  `ValidationException` → 400. Kein Scan/DeleteItem.
- IAM: `aws_iam_role.handler` unverändert; keine zweite Role, keine neuen
  Permissions (boto3 braucht keine zusätzlichen Rechte).

### Packaging

- `lambda/build_zip.py` (Stdlib `zipfile`) → `dist/lambda.zip` (6 Module,
  ~6,6 KB; sha256 `0af0c4d2…`). Boto3 von der Runtime → kein
  `requirements.txt`, kein Boto3-Bundling. Keine Secrets.

### Tests / Validation

- Python unittest 49/49 PASS (state_machine 4, validation 19, orderService 12,
  index 14) — lokal Python 3.12.3; Ziel-Runtime `python3.14`.
- `compileall` PASS · ZIP-Integrität + Handler-Import-Smoke PASS ·
  Node-Baseline Vitest 45/45 PASS.
- Terraform `fmt`/`init`/`validate` PASS · `plan` NOT RUN (T011-07) · `apply`
  NOT RUN · `git diff --check` PASS · Secret-Audit PASS.

Detaillierter Bericht: `docs/reports/LAMBDA-PYTHON-3.14-MIGRATION.md` ·
Vergleich: `docs/architecture/LAMBDA_RUNTIME_COMPARISON.md`.

## Testnachweise

| Prüfung | Status |
|---------|--------|
| Terraform init | PASS (aws provider v6.60.0) |
| Terraform validate | PASS (ohne Warnungen) |
| Vitest `npm test` | PASS (45 Tests: stateMachine 14, validation 19, orderService 12) |
| Build `npm run build` (tsc --noEmit + esbuild) | PASS |
| Package `npm run package` (bestzip → `dist/lambda.zip`) | PASS |
| `npm audit` | PASS (0 vulnerabilities) |
| LSP-Test terraform-ls 0.39.0 (serve, Root = Repo) | PASS (keine Diagnostics, `key_schema` in Completion) |
| Terraform plan | NOT RUN (zu T011-07) |
| Terraform apply | NOT RUN (Freigabe erforderlich) |
| Terraform destroy (Cleanup) | NOT RUN |
| Live-API / Lambda-Invocation | NOT RUN (kein apply) |
| `git diff --check` | PASS |
| Secret-Audit | PASS |

## Git Checkpoint

- Branch: `main` · Commit: `449cdd7` · Push: SUCCESS

## Next Step

T011-05 — Cognito (Pool, Client, Gruppe) (separater Task nach Checkpoint T011-04).