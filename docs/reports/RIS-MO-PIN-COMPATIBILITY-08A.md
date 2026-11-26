# RIS-MO-PIN-COMPATIBILITY-08A — RIS-relevanter Vertragsvergleich (386d741 vs. Baseline/Main)

**Datum:** 2026-11-26
**Typ:** Read-only Vertragsvergleich + eine minimale, lokale IAM-Portabilitätskorrektur
**Branch:** `fix/mo-ris-pin-compat-08a` (Basis `386d741`)
**Ergebnis:** Matrix vollständig. **Eine** notwendige IAM-Portabilitätslücke in
`386d741` geschlossen (Result-Consumer-Rolle des `agent_transport`-Moduls konnte
keine Permissions-Boundary erhalten). Keine Main-Migration, keine Änderung an
GSI-/HMAC-/`apply_result`-Verträgen, keine Änderung an SQS-Policies.
Kein AWS-/Terraform-Apply, kein Plan, kein Main-Merge, kein Deploy.

## 1. Vergleichsbasis (verifiziert)

| Ref | Rolle | Beziehung |
|---|---|---|
| `386d741` | getestete Modulversion (`016cdfd` + Preset-Fix 07A) | 22 Commits seit Merge-Base `9627eb2`, 275 hinter `main` |
| `1dbb0cb` | reviewed live baseline | **Ancestor von `main`** (kein Merge-Base von `386d741`) |
| `570bbe7` | Main-Linie + `orders-service`-Terraform-Fix 07B | `main` (`8830da2`) + 1 Commit |
| `8830da2` (main) | aktueller Main-Stand | enthält `1dbb0cb` |

Merge-Base `386d741` ↔ `1dbb0cb` = `9627eb2`. Die beiden Linien sind **nicht**
superset-voneinander: der Pin enthält die Agent-Transport-/Result-Grenze, die
Main-Linie enthält RC4-Härtung (DLQ, Privacy-Gates, 07B-Builder-Fixes).

## 2. Vertragsmatrix

| Vertrag | `386d741` (Pin) | Main/Live-Baseline (`1dbb0cb` / `570bbe7` / `8830da2`) | Entscheidung |
|---|---|---|---|
| **`agent_transport`-Modul** (Result-Queue + DLQ + HMAC-Secret + Consumer) | vorhanden, `count = var.enable_agent_transport` (Default `false`); im `orders-service`-Preset als 8. Vertragsmodul | **nicht vorhanden** (Verzeichnis fehlt in allen 12 Main-Modulen) | Pin behalten — RIS-Result-Pfad braucht es. Kein Rückport in Main in diesem Task. |
| **Result-Consumer-Lambda** (`result_consumer.handler`, ESM Batch 10, `ReportBatchItemFailures`, HMAC über Envelope-`messageId`) | vorhanden (`b83f130`) | nicht vorhanden (`result_consumer.py` in Main entfernt) | Pin behalten. Signatur-/Batch-Semantik unverändert. |
| **`lambda_execution_boundary` — Root-Default** | **hartcodiert** `arn:aws:iam::240571105849:policy/Mays-Orders-Lambda-Execution-Boundary` | `null` + ARN-Regex-Validierung (`f3e78d0`, `95f8921`) | **Nicht geändert.** Der von RIS konsumierte `orders-service`-Preset neutralisiert den Default beim Generieren auf `""` (Test `test_lambda_boundary_default_is_neutralised`). Rest-Risiko: `complete`-/Custom-Builds verschiffen weiterhin die fremde Account-ARN — eigene Pin-Entscheidung. |
| **SQS-Worker-Rolle — Boundary** | Default `""`, `!= "" ? … : null` (portabel) | Default `null` + Validierung (semantisch äquivalent) | Keine Änderung nötig. |
| **Result-Consumer-Rolle — Boundary** | **kein Input, keine Boundary** → in Boundary-pflichtigen Konten scheitert `CreateRole`; Operator konnte die Boundary gar nicht übergeben | n/a (Rolle existiert nicht) | **KORRIGIERT auf diesem Branch** (§3). |
| **Handler-Rolle (`module.iam`)** | keine Boundary | keine Boundary (identisch) | Nicht geändert — identische Lücke in allen vier Refs, kein Pin-Delta. |
| **Result-Consumer-Rolle — Name/Policy** | `${project}-agent-result-consumer`, eigene Policy (Logs, DDB Get/Update, Secret-Read, SQS Consume) | n/a | Unverändert. Namespace-konform zum Policy-Gate. |
| **Orders-Queue-Policy (Ressource)** | `aws_sqs_queue_policy.orders` mit Account-Root-Principal (Send/Receive/Delete/GetAttributes, `dad69ea`) | Ressource **entfernt** (`a2fb385`, F-03); Zugriff nur über IAM-Identity-Policies | **Nicht geändert.** Live-Policy-Outcome bleibt offene Entscheidung (§5.1): live = Wildcard, Main/RC2 = DELETE, Pin = UPDATE auf Account-Root. |
| **Orders-Queue-Reliability** | keine DLQ, Retention 120 s, Visibility 30 s | DLQ + Redrive, 4 d / 14 d, Visibility 60 s, 4 konfigurierbare Variablen | Nicht geändert (außerhalb IAM-Scope) — als Pin-Delta dokumentiert (§5.2). |
| **Modul-Inputs (Root-Variablen)** | 7 Vertragseingaben (`project_name`, `tags`, `monitoring_enabled`, `log_retention_days`, `enable_agent_transport`, `ris_result_producer_role_arns`, `lambda_execution_boundary`) | 11 (`570bbe7`: + `deployment_version` + 4 `sqs_*`) | Nicht portiert (07B ist Main-Fix). RIS-Wiring darf auf dem Pin `deployment_version`/`sqs_*` **nicht** referenzieren. |
| **Modul-Outputs** | 20 Outputs inkl. `sqs_queue_url`/`_arn`/`_name`, `sqs_worker_lambda_arn`; **kein** `mo_version`, **kein** `privacy_secret_arn`; `agent_transport`-Outputs (`results_queue_url`, `results_queue_arn`, `results_dlq_arn`, `result_hmac_secret_arn`, `result_consumer_function_name`) existieren **nur im Kindmodul**, nicht am Modul-Root | 22 Outputs inkl. `mo_version`, `privacy_secret_arn`; keine Agent-Outputs | Nicht geändert. Kein Ref hat einen Output `order_dispatch_queue_url`. Offene Vertragsfrage §5.3. |
| **Cognito-Wiring (Handler)** | `ORDERS_COGNITO_ISSUER` + `ORDERS_COGNITO_CLIENT_ID` aus `module.cognito`; `identity.py` erzwingt `iss`+`sub` gegen erwarteten Issuer/Client (fail-closed) | kein Cognito-Env im Lambda-Modul; eigene `identity.py` (OrderIdentity consumer/owner/actor) ohne erwarteten Issuer/Client | Nicht geändert (Identity-Vertrag ist eigene Entscheidung). Pin behält die striktere Bindung. |
| **Builder-Vertragstabelle** | 07A-Fix: `agent_transport` in Preset + Custom, Gate-/Producer-Variablen gebunden | 07B: Referenz-Audit, `privacy_secret`-Stripping, +5 Root-Variablen | Pin behält 07A. 07B nicht portiert (Main-Fix). |
| **GSI / HMAC / `apply_result`** | gsi1+gsi2 | gsi1+gsi2+gsi3 (Main) | **Unangetastet** (per Auftrag ausgeschlossen). |

## 3. Änderung auf diesem Branch (minimal)

**Problem:** `terraform/modules/agent_transport` erzeugte
`aws_iam_role.result_consumer` **ohne** `permissions_boundary` und hatte keinen
Input dafür. Die Root-Variable `lambda_execution_boundary` wurde nur an
`module.sqs_worker` übergeben. In einem Konto, das eine Permissions-Boundary
erzwingt, wäre die Rolle (und damit der gesamte RIS-Result-Pfad) nicht
erstellbar; der Aufrufer hatte keine Möglichkeit, die Boundary zu setzen.

**Änderung (4 Dateien + 2 Tests):**

- `terraform/modules/agent_transport/main.tf`: neuer optionaler Input
  `lambda_execution_boundary` (Typ `string`, Default `""`, keine Account-ARN).
- `terraform/modules/agent_transport/lambda.tf`: `permissions_boundary =
  var.lambda_execution_boundary != "" ? var.lambda_execution_boundary : null`
  (gleiche Konvention wie `modules/sqs-worker` im Pin).
- `terraform/main.tf`: `lambda_execution_boundary = var.lambda_execution_boundary`
  im `module "agent_transport"`-Block.
- `module_builder/catalog.py`: `VARIABLE_MODULES["lambda_execution_boundary"]`
  zusätzlich an `agent_transport` gebunden — sonst wäre in einer freien Auswahl
  `agent_transport` ohne `sqs_worker` die Variable referenziert, aber nicht
  deklariert (`terraform validate`-Fehler). Kommentar korrigiert (der
  `orders-service`-Preset neutralisiert den Default sehr wohl).
- Tests: `module_builder/tests/test_module_builder.py` (2) und
  `lambda/tests/test_terraform_transport_module.py` (1 neue Klasse, 2 Tests).

**Nicht** geändert: SQS-Queue-Policy, Queue-Attribute, GSI, HMAC-/Envelope-
Prüfung, `apply_result`, `identity.py`, Root-Boundary-Default, Main-Wiring.
Verhalten bei Default (`enable_agent_transport = false`) und bei leerer Boundary
unverändert: `permissions_boundary = null`.

## 4. Verifikation (lokal, keine AWS-Mutation)

| Prüfung | Ergebnis |
|---|---|
| `python3 -m unittest module_builder.tests.test_module_builder` | **96 OK** (Basis 94 + 2 neu) |
| `cd lambda && PYTHONPATH=src python3 -m unittest discover -s tests` | **227 OK** |
| `python3 -m unittest installer.tests.test_installer` | **81 OK** |
| `terraform fmt -check -recursive` (Root) | **PASS** |
| `terraform init -backend=false` + `terraform validate` (Root) | **PASS** |
| `module_builder build --preset orders-service --validate` | **PASS** (fmt/init/validate) |
| `module_builder build --preset complete --validate` | **PASS** |
| `module_builder build --modules agent_transport,dynamodb --validate` | **PASS** |
| `git diff --check` | **PASS** |
| Secret-Audit (Diff) | keine Secrets/ARNs/Keys; nur ein optionaler, leerer Boundary-Input |

Hinweis: Die Builder-Tests bauen `lambda/dist/lambda.zip` neu. Das Ergebnis
(`fa0dee9e…`) weicht in dieser Umgebung byte-mäßig vom committeten Artefakt
(`48ddd5e5…`) ab, obwohl alle 13 Module und deren Größen identisch sind
(zlib-/Python-Version der Umgebung). Das Artefakt wurde daher **nicht**
mitcommittet (zurückgesetzt auf `HEAD`).

## 5. Offene Entscheidungen (nicht in diesem Task entschieden)

1. **Live-SQS-Policy der Orders-Queue.** Pin `386d741` plant ein *UPDATE* der
   Queue-Policy auf Account-Root; Main/RC2 plant deren *DELETE*; live liegt
   weiterhin die F-03-Wildcard-Policy. `0 DELETE/REPLACE` ist mit dem Pin nicht
   erreichbar. Entscheidung liegt beim Release-Owner (getrennte F-03-Remediation).
2. **Queue-Reliability im Pin.** Pin hat keine DLQ und 120 s Retention; ein Plan
   gegen den Live-Stand würde Queue-Attribute ändern bzw. die DLQ entfernen.
   Eigene Entscheidung, nicht Teil der IAM-Portabilität.
3. **Fehlende Result-Transport-Outputs am Modul-Root.** RIS kann
   `agent_transport.results_queue_url` / `result_hmac_secret_arn` nicht über
   Modul-Outputs beziehen; ein Output `order_dispatch_queue_url` existiert in
   keinem der vier Refs. Braucht eine explizite Vertragsentscheidung
   (Outputs ergänzen vs. RIS-Wiring anders lösen).
4. **Root-Boundary-Default.** Portierung von `f3e78d0` (Default `null` +
   Validierung) wäre möglich, ändert aber den Default des Quell-Repos und den
   Custom-/`complete`-Pfad. Nicht Teil der minimalen Korrektur.
5. **Boundary der Handler-Rolle (`module.iam`).** In allen Refs ohne Boundary;
   nur relevant, wenn das Zielkonto Boundaries erzwingt.
6. **Policy-Gate-Abdeckung des Agent-Transports.** `aws_secretsmanager_secret` /
   `..._secret_policy` stehen nicht in der Allowlist von
   `terraform/policy/resource-policy.json`; bei `enable_agent_transport = true`
   würde das Root-Gate die Ressourcen ablehnen. Gate ist Root-Verantwortung des
   Integrators — für RIS separat zu klären.
7. **Leerer Principal.** `ris_result_producer_role_arns = []` erzeugt Queue-/
   Secret-Policy-Statements mit leerem `Principal.AWS` (Apply-Fehler). RIS setzt
   die Rollen-ARNs, daher nicht blockierend; fail-closed-Verhalten offen.

## 6. Evidenz

- `git diff 386d741 1dbb0cb -- terraform module_builder`
- `git diff 386d741 main -- terraform module_builder`
- `/tmp/opencode/08a-preset2` (generiertes Modul, `terraform validate` PASS)
- Testläufe und Terraform-Kommandos aus §4
