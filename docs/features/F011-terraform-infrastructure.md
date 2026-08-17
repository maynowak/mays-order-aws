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
| T011-05 | Cognito (Pool, Client, Gruppe) | ⏳ PLANNED |
| T011-06 | HTTP API + Routen + Authorizer | ⏳ PLANNED |
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
T011-04 — Lambda (Zip-Build) + Permission (COMPLETE)

Completed Tasks:
- T011-01 Terraform-Gerüst             ✅
- T011-02 DynamoDB-Tabelle + GSI1       ✅
- T011-03 IAM-Rolle + Policy            ✅
- T011-04 Lambda (Zip-Build) + Permission ✅

In Progress:
None (T011-04 abgeschlossen; T011-05 wird separat gestartet)

Pending Tasks:
- T011-05 Cognito (Pool, Client, Gruppe)
- T011-06 HTTP API + Routen + Authorizer
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

Tests:
- Terraform init: PASS (aws provider v6.60.0, `~> 6.0`)
- Terraform validate: PASS (ohne Warnungen)
- Vitest `npm test`: PASS (45 Tests — stateMachine 14, validation 19, orderService 12)
- Build `npm run build` (tsc --noEmit + esbuild): PASS
- Package `npm run package` (bestzip → `dist/lambda.zip`): PASS (nur `dist/index.js`, ~156 KB)
- `npm audit`: PASS (0 vulnerabilities)
- LSP-Test terraform-ls 0.39.0 (serve, Root = Repo): Root-Erkennung `terraform/` PASS;
  Provider nur 6.60.0; ObtainSchema/SchemaModuleValidation/ReferenceValidation err=nil;
  keine Diagnostics; Completion im GSI-Block schlägt `key_schema` vor → PASS
- Terraform plan: NOT RUN (gehört zu T011-07)

Validation:
- Terraform plan: NOT RUN (gehört zu T011-07)
- Terraform apply: NOT RUN (Freigabe erforderlich)
- Live-API: NOT RUN (kein apply; Lambda-Bundle nicht deployed)
- git diff --check: PASS
- Secret-Audit: PASS (inkl. lambda/-Quelltext, package.json, terraform/)

Known Issues:
- API-GW→Lambda Invoke-Permission (`aws_lambda_permission`) fehlt bewusst bis T011-06
  (HTTP API existiert noch nicht; keine API-GW-Implementierung in T011-04).
- Beträge als ganze Cent finalisiert (Vorab-Definition `database/dynamodb-design.md` §7;
  `api/api-documentation.md` §3 ist die maßgebliche Schemadarstellung). Die float-Beispiele
  in `api/endpoints.md` (§2.1) sind inkonsistent und bewusst NICHT geändert (keine
  Architekturänderung in T011-04).

Blockers:
- None

Current Checkpoint:
T011-04 Commit (Hash siehe Git Checkpoint / CHANGELOG)

Next Step:
T011-05 — Cognito (Pool, Client, Gruppe) (separater Prompt / Task)
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

## T011-04 — Lambda Order Handler (Zip-Build)

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

- Branch: `main` · Commit: T011-04 (Hash siehe CHANGELOG) · Push: SUCCESS

## Next Step

T011-05 — Cognito (Pool, Client, Gruppe) (separater Task nach Checkpoint T011-04).