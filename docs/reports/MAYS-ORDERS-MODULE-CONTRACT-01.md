# MAYS-ORDERS-MODULE-CONTRACT-01

**Checkpoint:** MAYS-ORDERS-MODULE-CONTRACT-01
**Datum:** 2026-10-18
**Baseline:** main `cffd85c` (B2) → `9ec7f84` (WP5-Outputs) → `4f0ab17` (Builder) → Doku-Commit
**Status:** VERIFIED — 205/205 Installer+Builder, 76/76 Lambda, Modul `terraform validate` PASS, **Wrapper-Integration live bewiesen** (lokales Modul referenzierbar)

## 1. Architektur-/Vertragsübersicht

**Orders-Service-Vertrag (verbindlich, nicht abwählbar):**

| Pflichtbestandteil | Terraform-Modul | Anmerkung |
|---|---|---|
| Orders-API (HTTP API v2 + JWT) | `api` | benötigt `cognito` + `lambda` |
| Orders-Handler-Lambda | `lambda` | Python 3.14, Artefakt `lambda.zip` |
| Orders-Worker-Lambda | `sqs_worker` | SQS-Consumer, eigene Rolle (self-contained) |
| Orders-SQS-Queue | `sqs` | `${project_name}-orders-queue` (Naming-Contract) |
| Eigene Orders-DynamoDB-Tabelle | `dynamodb` | GSI1/GSI2, Tabelle == `project_name` |
| Orders-IAM | `iam` | Handler-Rolle, SQS count-gated (PHASE2) |
| Cognito (JWT-Grundlage) | `cognito` | vom Modul verwaltet (api-Modul-Injektion extern möglich, s. §6) |

**Nicht Vertragsbestandteil** (Verantwortung des integrierenden Projekts):
Monitoring, CloudTrail, Cognito-Backups, Seed, Remote-Backend, Region/Provider,
Policy-Gate-Ausführung (Root-Ebene). Externe AWS-Infrastruktur bleibt beim Aufrufer.

## 2. Tatsächliche Verzeichnisstruktur (WP2 — generiert, verifiziert)

```text
<target>/                       # z. B. module/Mays-Order-AWS
├── main.tf                      # locals(+default_tags) + DIE 7 Modulblöcke — KEIN provider-/terraform-Block
├── variables.tf                 # exakt 4 Vertrags-Inputs (auditiert)
├── outputs.tf                   # 19 Outputs (16 Bestand + 3 Vertrag)
├── versions.tf                  # terraform-Block (required_version/providers)
├── README.md                    # Vertrag + Nutzung + Variablen-/Output-Tabellen
├── module-builder.manifest.json # Provenance (preset orders-service)
├── lambda/                      # dist/lambda.zip + src/ + build_zip.py (path.module-relativ)
└── modules/{api,cognito,dynamodb,iam,lambda,sqs,sqs-worker}/
```

## 3. Input-Audit (WP4 — nur tatsächlich existierende Variablen)

| Variable | Typ | Default | Verwendung |
|---|---|---|---|
| `project_name` | string | (substituiert, z. B. `my-orders`) | Präfix aller Orders-Ressourcen + `Project`-Tag |
| `tags` | map(string) | `{}` | Zusatz-Tags; Maker/Environment intern ergänzt |
| `monitoring_enabled` | bool | `true` | Log-Group-Steuerung (lambda/sqs_worker) |
| `log_retention_days` | number | `7` | CloudWatch-Retention |

**Keine neuen Variablen** — keine Lücke nachgewiesen (Modul-Inputs ergeben sich vollständig aus dem Bestandswiring). **Keine Umbenennungen.** Entfallen im Modus: `aws_region` (Region liefert der Aufrufer-Provider), Seed-/Backup-/Alarm-Variablen (kein Vertragsbestandteil).

## 4. Output-Audit (WP5 — aus vorhandenen Ressourcen/Modul-Outputs, keine neuen Ressourcen)

| Geforderter Output | Quelle | Status |
|---|---|---|
| Orders-API-Endpunkt | `api_gateway_endpoint` | ✅ bestand |
| API-ID | `api_gateway_id` | ✅ bestand |
| Tabellenname/ARN | `dynamodb_table_name/_arn` | ✅ bestand |
| **SQS-Queue-URL** | `module.sqs.queue_url` | ➕ **neu ergänzt** (Quell-Root-Outputs, additiv) |
| **SQS-Queue-ARN** | `module.sqs.queue_arn` | ➕ **neu ergänzt** |
| **Worker-Lambda-ARN** | `module.sqs_worker.function_arn` (Modul-Output bestand ✓) | ➕ **neu ergänzt** |
| Handler-Lambda-ARN | `lambda_function_arn` | ✅ bestand |
| Cognito-Referenzen | 5 Outputs (id/arn/endpoint/client_id/group_name) | ✅ bestand |

Referenzen in allen unterstützten Konfigurationen gültig (feste 7-Modul-Zusammensetzung); Upgrade-stabil über `module.orders.*`-Adressen.

## 5. Integrationsbeispiel (WP6 — live validiert)

```hcl
provider "aws" { region = "eu-central-1" }

module "orders" {
  source = "../module/Mays-Order-AWS"
  project_name = "wrapper-orders"
  tags         = { ManagedBy = "terraform" }
}

output "orders_api_endpoint" { value = module.orders.api_gateway_endpoint }
output "orders_queue_url"    { value = module.orders.sqs_queue_url }
output "orders_worker_arn"   { value = module.orders.sqs_worker_lambda_arn }
```

**Live-Beweis:** Wrapper-Root mit `terraform init -backend=false` + `validate` → **PASS** — das Modul ist als lokale Quelle referenzierbar.

## 6. Upgrade-Risiken & Einschränkungen (WP7)

- **Stabile Adressen:** `module.orders.<output>` bleibt stabil; Ressourcen-Identitäten/Naming unverändert (`${project_name}-*`, Tags inkl. Maker/Environment via `local.default_tags` → Tag-Parität zum Stamm-Deploy).
- **Provider-Block bewusst nicht im Modul** (Terraform-Regel für Child-Module); Region/default_tags = Aufrufer.
- **Artefakte modulrelativ** (`${path.module}/lambda/…`) — bei Quell-Modul-Austausch ändert sich ggf. der ZIP-Hash → Lambda-In-Place-Update im Plan des Aufrufers (dokumentiert, kein Apply durch den Builder).
- **Keine State-Migration, keine Ressourcenübernahme** — das Modul verwaltet nur eigene Ressourcen; Einbindung bestehender Ressourcen ist nicht Teil des Vertrags.
- **Externe Cognito-Injektion möglich, aber nicht Teil des Vertrags** (api-Modul nimmt `cognito_user_pool_endpoint/_client_id` als Variablen — Lücke dokumentiert, Lösung: zusätzliche Wiring-Variablen im Modul-Root; Freigabe abwarten).
- **Policy-Gate** läuft beim Aufrufer auf dessen Root-Plan (MO-Gate im Quell-Repo verfügbar).

## 7. Testergebnisse (alle real ausgeführt)

| Prüfung | Ergebnis |
|---|---|
| Builder-Unit-Tests (inkl. 12 neuer Modul-Vertrags-Tests) | **76/76 PASS** |
| Installer-Regression | **129/129 PASS** (205 gesamt) |
| Lambda-Regression | **76/76 PASS** |
| Modul-`--validate` (fmt -check / init -backend=false / validate) | **PASS** |
| Wrapper-Integration (Modul als lokale Quelle) | **PASS** |
| B1/B2 unverändert | ✓ (Bestandstests grün, `--with-deps`/`--modules` unangetastet) |
| Complete-Preset unverändert | ✓ (validate PASS; einzige Quell-Änderung: additive Outputs) |
| Policy-Gate | unverändert funktionsfähig (Bestandstests) |
| STOP-Schutzgrenzen | ✓ eingehalten (kein apply/destroy, keine AWS-Mutation, kein RIS, keine Worker-/Runtime-Änderung, keine Queue-Policy-/Boundary-Änderung, keine Privacy-Aktivierung, keine Tags-Änderung, keine State-Migration, keine Release-Tags) |

## 8. Commits & Git

| Commit | Paket |
|---|---|
| `9ec7f84` | WP5: additive Root-Outputs `sqs_queue_url`/`sqs_queue_arn`/`sqs_worker_lambda_arn` |
| `4f0ab17` | WP2/WP3: Builder `orders-service`-Modus (Modul-Generator, CLI, 12 Tests) |
| (folgt) | WP9: dieser Report + AI_AUDITLOG + README/AGENTS |

Git CLEAN nach jedem Paket; main gepusht; keine Release-Tags.

## 9. Offene Punkte

1. **Externe-Cognito-Injektion** als Vertragsvariante (api-Modul-Variablen existieren; Modul-Root-Wiring + Freigabe erforderlich).
2. RIS-seitiger Backend-Hygiene: 8 leere Composite-Test-States + Lock-Digest-Reste in OUR Bucket (16./18.10., read-only verifiziert; Aufräumung = RIS-seitig bzw. separate Freigabe).
3. Modul-Registry/Git-Sourcing als Vertriebsweg (aktuell: lokale Quelle).
