# Mays-Orders-AWS – Terraform-Modul: Integration, Git-Verteilung und Testleitfaden

- **Stand:** 19.10.2026
- **Zweck:** Ein vollständiges Orders-Service-Modul generieren, in einem getrennten Terraform-Projekt lokal testen und anschließend einen Git-Vertriebsweg vorbereiten.
- **Evidenz:** Hochgeladener Originalbericht `MAYS-ORDERS-MODULE-CONTRACT-01.md` (18.10.2026) sowie die späteren Checkpoints zu EXTERNAL Cognito und CLI-Cleanup. **Diese wurden am 19.10.2026 gegen das Repository verifiziert** — beide existieren dort als Reports mit Commits (`MAYS-ORDERS-EXTERNAL-COGNITO-INTEGRATION-01.md`, Commit `451f14d`; `MAYS-ORDERS-MODULE-BUILDER-CLI-CLEANUP-01.md`, Commit `736886a`).

> **Wichtige Trennung:** Der bestehende Mays-Orders-AWS-Installer, das Terraform-Stammprojekt, seine CI/CD-Pipeline und seine laufenden Deployments bleiben unverändert. Das nachfolgend beschriebene Angebot betrifft das **neu generierte** Terraform-Child-Modul. Kein `terraform apply`, `destroy`, Import oder State-Migration in diesem Test.

## 1. Was wir gebaut haben

Mays-Orders-AWS ist **ein vollständiger Orders-Service**, kein Katalog einzeln vermarkteter AWS-Ressourcen. Der Generator erzeugt ein eigenständiges, von einem Terraform-Root-Projekt aufrufbares Child-Modul.

**Fest enthalten:** HTTP API v2 mit JWT-Authorizer, Orders-Handler-Lambda, Orders-Worker-Lambda, SQS, eigene DynamoDB-Tabelle, Orders-IAM und Cognito-Anbindung. Die fachliche Orders-Verarbeitung wird nicht abgewählt. Insbesondere sind Worker, Queue und eigene Orders-Tabelle Pflichtbestandteile.

**Beim Aufrufer:** AWS-Provider und Region, Backend/State, optionale ergänzende Infrastruktur, übergeordnete Monitoring-/CloudTrail-/Backup-Strategien und das Policy-Gate für den Root-Plan. Der generierte Modulvertrag enthält dennoch die bestehenden Inputs `monitoring_enabled` und `log_retention_days` für die modulinternen Log-Einstellungen; dies ist **nicht** mit einem umfassenden Monitoring-Stack gleichzusetzen.

**Cognito-Betriebsarten:**

- **MANAGED (Standard):** Ohne zusätzliche Angabe stellt das generierte Modul seinen Cognito selbst bereit.
- **EXTERNAL:** Das aufrufende Projekt liefert `user_pool_endpoint` und `user_pool_client_id`; das generierte Modul nutzt diese Referenzen für den JWT-Authorizer und erstellt selbst keine Cognito-Ressourcen. Die API wird dadurch **nicht** öffentlich/ungeschützt. Die Validierung lehnt unvollständige Referenzen ab.

Die EXTERNAL-Funktion ist umgesetzt und repo-verifiziert (Report `docs/reports/MAYS-ORDERS-EXTERNAL-COGNITO-INTEGRATION-01.md`, Commit `451f14d`); der hochgeladene Modulvertragsbericht vom 18.10. dokumentiert sie noch als damalige Lücke. Dieser zeitliche Unterschied ist beabsichtigt, nicht ein Widerspruch in der Zielarchitektur.

## 2. Was nachgewiesen ist – und was nicht

| Funktion | Stand | Evidenzgrenze |
|---|---|---|
| `--preset orders-service` erzeugt ein Terraform-Child-Modul | **VERIFIED** | Originalbericht: generierte Struktur und Wrapper-`validate` |
| Lokales `source = "../module/Mays-Order-AWS"` | **VERIFIED** | Originalbericht: `terraform init -backend=false` und `validate` |
| 19 benannte Outputs | **VERIFIED** | Originalbericht, additive Queue-/Worker-Outputs |
| MANAGED / EXTERNAL Cognito | **VERIFIED** | Repo-Report `MAYS-ORDERS-EXTERNAL-COGNITO-INTEGRATION-01.md` (Commit `451f14d`): 87 Builder-, 129 Installer-, 76 Lambda-Tests; Wrapper MANAGED/EXTERNAL/Negativ live validiert |
| Stammprojekt von EXTERNAL-Änderung unberührt | **VERIFIED** | Repo-Report (s. o.): Änderungen nur in `module_builder/` — Scope-Korrektur eingehalten |
| CLI-Cleanup `--no-policy-check` | **VERIFIED** | Repo-Report `MAYS-ORDERS-MODULE-BUILDER-CLI-CLEANUP-01.md` (Commit `736886a`): totes Installer-Flag entfernt, Policy-Gate unverändert bedingungslos |
| Git-`source` aus veröffentlichtem Modulordner | **NOCH NICHT NACHGEWIESEN** | Git-Inhalt, Modulordner und Ref müssen erst geprüft werden |
| Terraform Registry | **NICHT IMPLEMENTIERT** | Separater späterer Vertriebsweg |
| AWS-Live-Deployment und echter Token-Test mit externem Pool | **NICHT DURCHGEFÜHRT** | Erfordert eigene Freigabe und kontrollierten Test |

## 3. Voraussetzungen

Auf der Entwicklungsmaschine:

- Lokaler Checkout des Repositories `Mays-Orders-AWS` mit dem aktuellen `main`-Stand.
- Python zum Aufruf `python -m module_builder`.
- Terraform in einer mit `versions.tf` kompatiblen Version.
- Git für die spätere Quellenprüfung.
- Schreibrechte für den Ausgabeordner.
- Für reine `fmt`-/`init -backend=false`-/`validate`-Tests ist **kein AWS-Apply** vorgesehen. `init` kann jedoch Terraform-Provider herunterladen und benötigt gegebenenfalls Netzwerkzugang.

**Nicht voraussetzen:** dass `module/Mays-Order-AWS/` bereits im Git-Repository committed ist. Der Builder generiert einen **Ausgabeordner**. Ein generierter Ordner ist nicht automatisch ein veröffentlichtes Git-Modul.

## 4. Generierung des Orders-Moduls

Im Root des lokalen Mays-Orders-AWS-Checkouts:

```bash
python -m module_builder build \
  --preset orders-service \
  --target ./module/Mays-Order-AWS \
  --project-name demo-orders \
  --validate
```

Erwartet wird ein eigenständiges Modul unter `module/Mays-Order-AWS/` mit `main.tf`, `variables.tf`, `outputs.tf`, `versions.tf`, `README.md`, Manifest, Lambda-Artefakten und sieben Untermodulen. Der ursprüngliche Report nennt **34 Dateien** für den damaligen generierten Stand — dieser Umfang wurde am 19.10.2026 erneut bestätigt (reine Builder-Ausgabe ohne Init-Artefakte). Hinweis: Ein anschließendes `terraform init` legt zusätzlich `.terraform/`-Dateien an, sodass `find` dann mehr Dateien zählt (z. B. 40).

**Achtung bei Wiederholung:** Nicht blind über einen bestehenden Ausgabeordner schreiben. Zunächst die CLI-Hilfe prüfen (`python -m module_builder build --help`) und vorhandene Daten sichern. Die Verwendung von `--force` ist nur sinnvoll, wenn du den Zielinhalt bewusst ersetzen willst.

### Struktur prüfen

```bash
find module/Mays-Order-AWS -maxdepth 2 -type f | sort
cat module/Mays-Order-AWS/module-builder.manifest.json
```

Soll-Struktur (schematisch):

```text
module/Mays-Order-AWS/
├── main.tf
├── variables.tf
├── outputs.tf
├── versions.tf
├── README.md
├── module-builder.manifest.json
├── lambda/
│   ├── dist/lambda.zip
│   └── ...
└── modules/
    ├── api/
    ├── cognito/
    ├── dynamodb/
    ├── iam/
    ├── lambda/
    ├── sqs/
    └── sqs-worker/
```

Der Lambda-Artefaktpfad ist modulrelativ über `path.module` aufgebaut. **Prüfen, dass `lambda/dist/lambda.zip` wirklich vorhanden und nicht durch `.gitignore` ausgeschlossen ist**, bevor ein Git-Vertriebsweg versucht wird.

## 5. Input-Vertrag

Der ursprüngliche generierte Vertrag hatte vier Inputs; der neuere EXTERNAL-Cognito-Checkpoint ergänzt **einen fünften optionalen Input nur im generierten Modul**.

| Variable | Typ / Default | Zweck |
|---|---|---|
| `project_name` | `string`, vom Builder vorbelegt | Projektisolierung, Ressourcennamen, Project-Tag |
| `tags` | `map(string)`, `{}` | Ergänzende Tags; bestehende Maker-/Environment-Regeln bleiben |
| `monitoring_enabled` | `bool`, `true` | Modulinternes Logging |
| `log_retention_days` | `number`, `7` | CloudWatch-Log-Retention |
| `external_cognito` | `object(...)`, `null` | Optional: bestehenden Cognito-Pool/App-Client nutzen |

**Exakter EXTERNAL-Typ (repo-verifiziert aus der generierten `variables.tf`):**

```hcl
external_cognito = object({
  user_pool_endpoint  = string
  user_pool_client_id = string
})
```

Der `user_pool_endpoint` wird **ohne `https://`** übergeben, weil das vorhandene API-Untermodul das Schema ergänzt. Die konkrete Syntax und Validierung stehen in der **generierten** `variables.tf`; diese Datei ist vor dem Versuch die maßgebliche Quelle.

## 6. Lokaler Integrationstest: MANAGED

Erstelle außerhalb des generierten Moduls einen separaten Wrapper-Ordner, beispielsweise als Geschwisterordner von `module/`:

```text
<arbeitsordner>/
├── module/
│   └── Mays-Order-AWS/
└── integration-test/
    └── main.tf
```

`integration-test/main.tf`:

```hcl
terraform {
  required_version = ">= 1.6.0"
}

provider "aws" {
  region = "eu-central-1"
}

module "orders" {
  source       = "../module/Mays-Order-AWS"
  project_name = "demo-orders"
  tags         = { ManagedBy = "terraform" }
}

output "orders_api_endpoint" {
  value = module.orders.api_gateway_endpoint
}

output "orders_queue_url" {
  value = module.orders.sqs_queue_url
}

output "orders_worker_arn" {
  value = module.orders.sqs_worker_lambda_arn
}
```

**Versionshinweis:** `required_version` im Wrapper ist ein Beispiel; die tatsächlich generierte `versions.tf` kann engere Grenzen festlegen. Die AWS-Provider-Version muss zu beiden Konfigurationen passen.

Dann:

```bash
cd integration-test
terraform fmt -check
terraform init -backend=false
terraform validate
```

**Erwartung:** `Success! The configuration is valid.` Dies prüft HCL-Struktur und Modulverschaltung, **nicht** die AWS-Laufzeit oder Ressourcenänderungen. Kein `apply` ausführen.

## 7. Lokaler Integrationstest: EXTERNAL

Für den zweiten Test einen getrennten Wrapper verwenden oder das `module "orders"`-Argument ergänzen:

```hcl
module "orders" {
  source       = "../module/Mays-Order-AWS"
  project_name = "demo-orders-external"

  external_cognito = {
    user_pool_endpoint  = "cognito-idp.eu-central-1.amazonaws.com/eu-central-1_EXAMPLE"
    user_pool_client_id = "exampleclientid123"
  }
}
```

Die Platzhalter sind **nur für syntaktische Validierung**, nicht für einen realen Token-Test geeignet. Für echte Authentifizierung sind die korrekten Werte eines vorhandenen Cognito-Pools und App-Clients nötig. Diese bleiben Eigentum des integrierenden Projekts.

```bash
terraform init -backend=false
terraform validate
```

Negativtest: `user_pool_client_id = ""` setzen und erneut `terraform validate` ausführen. Die Variablenvalidierung schlägt dann verständlich fehl (live belegt: `Error: Invalid value for variable`). Danach den gültigen Wert wiederherstellen.

**Wichtig:** EXTERNAL bedeutet nur **Referenzieren**, nicht Importieren, Taggen, Aktualisieren oder Löschen des fremden Cognito-Pools.

## 8. Outputs für integrierende Projekte

Der Vertrag hat **19 Output-Namen**. Im Originalbericht sind die folgenden explizit nachgewiesen:

| Output | Nutzen |
|---|---|
| `api_gateway_endpoint` | Orders-API-Basisendpunkt |
| `api_gateway_id` | API-ID |
| `dynamodb_table_name` | Orders-Tabelle |
| `dynamodb_table_arn` | Orders-Tabellen-ARN |
| `sqs_queue_url` | Orders-Queue-URL |
| `sqs_queue_arn` | Orders-Queue-ARN |
| `sqs_worker_lambda_arn` | Worker-Lambda-ARN |
| `lambda_function_arn` | Handler-Lambda-ARN |

Zusätzlich sind fünf Cognito-bezogene Outputs im Bericht beschrieben (Pool-ID, ARN, Endpoint, Client-ID, Gruppenname). **Die genauen Output-Bezeichner der übrigen Outputs bitte aus der generierten `outputs.tf` übernehmen; der Originalbericht nennt nicht alle 19 Namen einzeln.** Keine Namen aus einer Vermutung übernehmen.

Im EXTERNAL-Modus geben Endpoint und Client-ID die verwendeten externen Referenzen zurück (repo-verifiziert). Pool-ID, Pool-ARN und Gruppenname liefern `null`, da diese Werte nicht Teil des EXTERNAL-Input-Vertrags sind. **Diese drei Outputs dürfen nicht als garantiert vorhandene Werte behandelt werden.**

## 9. Git-Sourcing: erst veröffentlichen, dann referenzieren

### 9.1 Warum die bisherige lokale Validierung nicht ausreicht

Ein lokaler `source`-Pfad beweist, dass Terraform die Dateien im Dateisystem verwenden kann. Ein Git-`source`-Pfad funktioniert erst, wenn **alle benötigten Dateien in einem erreichbaren Git-Commit enthalten** sind. Der Bericht bestätigt ausdrücklich nur lokale Quellen; Git-Sourcing war ein offener Punkt.

Prüfe im Mays-Orders-AWS-Checkout:

```bash
git status --short
git ls-files module/Mays-Order-AWS
git check-ignore -v module/Mays-Order-AWS/lambda/dist/lambda.zip || true
```

- Wenn `git ls-files` keine Moduldateien zeigt, ist das generierte Modul **noch nicht** über das Repository verfügbar.
- Wenn das Lambda-ZIP ignoriert wird, fehlt dem Git-Konsumenten gegebenenfalls das Artefakt. Vor Veröffentlichung die Artefaktstrategie entscheiden.
- Generierte Moduldateien nicht unbesehen in `main` committen: Sie müssen reproduzierbar, vollständig und von bestehenden Installer-/Pipeline-Pfaden isoliert sein.

### 9.2 Git-URL – erst nach tatsächlicher Veröffentlichung

Wenn der Ordner im Git-Commit vorhanden ist, lautet das Schema:

```hcl
module "orders" {
  source       = "git::https://github.com/maynowak/mays-order-aws.git//module/Mays-Order-AWS?ref=<COMMIT_SHA>"
  project_name = "demo-orders"
}
```

`<COMMIT_SHA>` muss durch den **tatsächlichen Commit mit den vollständigen Moduldateien** ersetzt werden. Dieser Code ist eine **Vorlage**, keine Behauptung, dass der Ordner heute auf GitHub vorhanden ist. Ein Tag ist nicht notwendig; für erste Versuche ist ein Commit-SHA eine präzise Versionsbindung.

Die beiden Schrägstriche `//` trennen das Repository vom Unterverzeichnis. Die Groß-/Kleinschreibung von `module/Mays-Order-AWS` muss exakt mit dem veröffentlichten Pfad übereinstimmen.

```bash
terraform init -backend=false
terraform validate
```

Für einen neuen Ref oder eine geänderte Quelle kann `terraform init -upgrade -backend=false` erforderlich sein. **Nicht blind gegen bestehende produktive State-Verzeichnisse ausführen.**

### 9.3 Alternative für einen risikofreien ersten Git-Versuch

Ein **separates Test-Repository** nur mit dem generierten Modul ist ebenfalls möglich. Bei einer Veröffentlichung als Repository-Root entfällt `//module/Mays-Order-AWS`:

```hcl
module "orders" {
  source       = "git::https://github.com/<OWNER>/<TEST-REPO>.git?ref=<COMMIT_SHA>"
  project_name = "demo-orders"
}
```

Auch hier gilt: Nur als Beispiel, nicht als bereits existierende URL. Keine geheimen Werte oder lokalen Terraform-State-Dateien committen.

## 10. Upgrade- und Versionsregeln

1. **Source-Version fixieren.** Für Integrationen Git-Commit-SHA oder später bewusst gesetzte Release-Tags verwenden, nicht unkontrolliert `main`.
2. **MANAGED bleibt Standard.** Bestehende Wrapper ohne `external_cognito` sollen unverändert funktionieren.
3. **Cognito-Adressänderung beachten.** Laut neuerem Checkpoint führt das bedingte Modul zu `module.cognito[0]` statt `module.cognito`. Die Aussage über einen impliziten Move ist noch **nicht durch einen realen Upgrade-Plan belegt**. Vor einem Upgrade eines bestehenden Moduldeployments ist ein genauer Plan-Review Pflicht.
4. **MANAGED → EXTERNAL ist eine Migration**, keine harmlose Parameteränderung. Terraform könnte bisher verwaltete Cognito-Ressourcen zur Entfernung vorschlagen. Ohne separates Migrationsverfahren nicht durchführen.
5. **Lambda-ZIP-Hash kann sich ändern.** Ein neuer Modulstand kann dadurch einen Lambda-In-Place-Update-Plan auslösen; das ist kein automatisch freigegebener Deploy.
6. **Tags, Naming, Worker, SQS, Tabelle und Integrationsverträge** bleiben wie bisher. Keine ungewollte Übernahme fremder Ressourcen.
7. **Policy-Gate** bleibt verpflichtend im Terraform-Root des aufrufenden Projekts. Das frühere Installer-Flag `--no-policy-check` war funktionslos (nie konsumiert) und wurde entfernt (Report `docs/reports/MAYS-ORDERS-MODULE-BUILDER-CLI-CLEANUP-01.md`).

## 11. Fehlerdiagnose

| Symptom | Wahrscheinliche Ursache | Vorgehen |
|---|---|---|
| `Module not found` beim lokalen `source` | Relativer Pfad aus dem Wrapper stimmt nicht | `pwd`, `ls ../module/Mays-Order-AWS` prüfen |
| `Failed to download module` bei Git | Repo/Pfad/Ref nicht vorhanden oder Zugriff fehlt | URL, `//`-Unterpfad, Commit und Git-Rechte prüfen |
| `Invalid value for variable` bei EXTERNAL | Endpoint oder Client-ID leer/ungültig | Exaktes Objektformat aus generierter `variables.tf` verwenden |
| Unbekannter Output | Name im Beispiel nicht Teil des generierten Vertrags | `outputs.tf` lesen; keine Namen raten |
| Lambda-ZIP fehlt | Generiertes Artefakt nicht vorhanden oder von Git ausgeschlossen | `lambda/dist/` und `.gitignore` prüfen |
| `terraform init` benötigt Provider | Provider nicht im lokalen Cache | Netzwerk/Provider-Installation prüfen; kein AWS-Apply erforderlich |
| Unbeabsichtigte Cognito-Löschung im Plan | MANAGED/EXTERNAL-Wechsel oder Adressänderung | **STOP**, Plan sichern, Migration gesondert klären |
| Terraform will vorhandene Orders-Ressourcen neu erstellen | Neues Modul in separatem State ohne Import/Migration | **STOP**, nicht anwenden; kein impliziter Besitzwechsel |

## 12. Abnahmecheckliste für deinen Versuch

- [ ] Aktueller Mays-Orders-AWS-Checkout und sauberer Git-Status geprüft.
- [ ] Modul mit `--preset orders-service` generiert.
- [ ] `module-builder.manifest.json`, `variables.tf`, `outputs.tf` geprüft.
- [ ] Lambda-ZIP vorhanden.
- [ ] MANAGED-Wrapper: `init -backend=false` und `validate` erfolgreich.
- [ ] EXTERNAL-Wrapper: `init -backend=false` und `validate` erfolgreich.
- [ ] EXTERNAL-Negativtest lehnt leere Client-ID ab.
- [ ] Keine AWS-Mutationen und kein `apply/destroy` durchgeführt.
- [ ] Vor Git-Test: mit `git ls-files` nachgewiesen, dass Moduldateien im gewünschten Commit vorhanden sind.
- [ ] Git-Test verwendet echten Commit-SHA und exakten Modulpfad.
- [ ] `terraform validate` über Git-Quelle erfolgreich.
- [ ] Für spätere Deployments: Sicherheits-/Policy-Gate, Ressourcenplan und Upgrade-Risiken separat bewertet.

## 13. Roadmap und offene Punkte

| Thema | Stand |
|---|---|
| B1: freie technische Modulauswahl | VERIFIED (Repo-Report `MAYS-ORDERS-MODULE-BUILDER-B1-SELECTION-01.md`) |
| B2: automatische Pflichtabhängigkeiten | VERIFIED (Repo-Report `MAYS-ORDERS-MODULE-BUILDER-B2-WITH-DEPS-01.md`) |
| Orders-Service als Child-Modul | VERIFIED lokal |
| EXTERNAL Cognito nur im generierten Modul | VERIFIED (s. o., Commit `451f14d`) |
| B3 `minimal` | Funktional abgedeckt, **kein separates Preset** |
| CLI-Cleanup | VERIFIED (Commit `736886a`) |
| Git-Veröffentlichung / Git-Sourcing | **Nächster Test; nicht als erledigt behaupten** |
| Terraform Registry | Später optional |
| S3-Artefakt-Sourcing | Optional |
| MANAGED→EXTERNAL-Migration | Separat freigeben |
| Queue-Policy-Härtung / Boundary-IaC | Offene, gesonderte Sicherheitsentscheidungen |
| RIS-Backend-Hygiene | Separater Auftrag; nicht Teil der Modulverteilung |

## 14. Quellen und Evidenzhistorie

1. **Originalbericht:** `docs/reports/MAYS-ORDERS-MODULE-CONTRACT-01.md`, 18.10.2026; 7-Module-Vertrag, Struktur, vier ursprüngliche Inputs, 19 Outputs, lokaler Wrapper-Test und offene Git-/Cognito-Themen.
2. **Checkpoint:** `docs/reports/MAYS-ORDERS-EXTERNAL-COGNITO-INTEGRATION-01.md`, Commits `54de18d` (Implementierung) / `451f14d` (Report); EXTERNAL-Input, MANAGED/EXTERNAL-Validierung, 87/129/76 Tests, nur Builder-Code geändert.
3. **Checkpoint:** `docs/reports/MAYS-ORDERS-MODULE-BUILDER-CLI-CLEANUP-01.md`, Commit `736886a`; totes Installer-Flag entfernt, 87/129/76 Tests.
4. **Konsistenz-Sicherung:** `docs/reports/MAYS-ORDERS-AUDITLOG-CONSISTENCY-SCAN-01.md`, Commit `5bdde18`; dieser Leitfaden wurde am 19.10.2026 gegen das Repository gegengeprüft (Dateizahl 34, Git-Ignore-Status, Report-Existenz).

**Evidenzregel:** Die im Originalbericht noch als offen bezeichnete Cognito-Integration wurde nach diesem Bericht umgesetzt und ist seither repo-verifiziert. Der Git-Vertriebsweg wurde bislang **nicht** durch einen veröffentlichten Modulcommit und einen erfolgreichen Remote-`terraform init` belegt.
