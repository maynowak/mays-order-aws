# Mays-Orders-AWS — Installer-Handbuch

- **Stand:** 14.10.2026 · **Referenz:** `v0.5.0-rc.1` + Nachzügler auf main: Kollisions-Preflight (`f387b3e`)
- **CLI:** `./Mays-Order-AWS-installer` (Repository-Root)

## 1. Zweck

Der Installer steuert den Terraform-Lebenszyklus mit **Preflight-Validierung, Plan-Erzeugung, Policy Gate, Kontextbindung, menschlicher Freigabe, Deployment und Destroy**. Er schützt vor versehentlichen Operationen im falschen AWS-Konto oder Terraform-Workspace. Er ersetzt weder IAM noch Terraform oder eine menschliche Freigabe.

## 2. Ablauf

```text
Source / Release-Tag
        │
        ▼
AWS-Identität + Projekt + Workspace prüfen
        │
        ▼
AWS-Namenskollisionen scannen (aws_project_collision, read-only)
        │
        ▼
Lambda-Artefaktintegrität + Terraform validate
        │
        ▼
Terraform Plan → Policy Gate → Plan-/State-Kontextprüfung
        │
        ▼
Explizite Freigabe → Apply / Deploy
        │
        ▼
Smoke- und E2E-Tests → Evidence sichern
        │
        ▼
Destroy-Plan → Safety Gate → Explizite Destroy-Freigabe
        │
        ▼
Destroy → State- und AWS-Cleanup verifizieren → Kollisions-Check erneut ausführen
```

## 3. Voraussetzungen

Git, Python 3, Terraform entsprechend den Constraints in `terraform/`, AWS CLI mit konfiguriertem benannten Profil und passende IAM-Rechte. Zugangsdaten bleiben **außerhalb** des Repositories. Die Zielregion ist im Projekt typischerweise `eu-central-1`; sie muss für die konkrete Installation geprüft werden.

## 4. CLI und read-only Einstieg

```bash
./Mays-Order-AWS-installer --help
./Mays-Order-AWS-installer --guide      # Guide-Pfad + Inhaltsverzeichnis (read-only, kein AWS)
./Mays-Order-AWS-installer validate
./Mays-Order-AWS-installer plan
./Mays-Order-AWS-installer plan-destroy
```

**`--guide`** zeigt Pfad und Inhaltsverzeichnis dieses Handbuchs an und
beendet den Installer sofort (Exit 0) — ohne AWS-Kontakt, ohne Terraform.
Nützlich als schneller Verweis auf die Pflicht-Checks vor jeder Mutation.
Kein eigener `--docs`/`--manual`-Standard existiert; `--guide` ist die
projekteigene Konvention.

Die tatsächliche Optionssyntax und Argumentreihenfolge immer mit `--help` der ausgecheckten Version abgleichen. `terraform init` kann lokale Dateien anlegen und Backend-Metadaten abrufen; Planung ist kein vollständiger Offline-Modus.

`validate` enthält seit dem Collision-Preflight auch den read-only AWS-Scan
`aws_project_collision` (Abschnitt 9a) — er meldet Namens-Duplikate und
Projektnamen-Treffer im Zielkonto, bevor geplant oder deployt wird.

AWS-Identität explizit prüfen:

```bash
aws sts get-caller-identity --profile <AWS_PROFIL>
```

## 5. Sicherheitskontext

Vor **jeder** Mutation müssen zusammenpassen:

- AWS-Profil und per STS ermittelte Konto-ID;
- Region;
- Projektname und Terraform-Workspace;
- Backend und State-Key;
- gespeicherter Plan und aktueller State;
- Freigabe für **genau diesen** Plan und dieses Projekt.

**Historische Testkontexte (beide vollständig abgebaut):**

1. **Privacy-Test:** Profil `mayaws`, Konto `240571105849`, Region `eu-central-1`,
   Workspace `mays-orders-privacy-test` — vollständiger Stack, Destroy 2026-10-11
   (37 Ressourcen). Diese Werte sind **keine universellen Installer-Defaults**
   für andere AWS-Konten.
2. **mays-orders Backup-Stack-Rest:** gleiche Konto-/Region-Konstellation,
   Workspace `mays-orders` (S3-Backend) — Cognito-Backup-Stack aus der
   Feature-Entwicklung, Destroy 2026-10-14 (20 Ressourcen, Report
   `MAYS-ORDERS-LEFTOVER-STATE-CLEANUP-01.md`).

**Parallel-Installations-Warnung (Incident 2026-10):** Im selben Konto betreibt
das Team RIS eine **eigene, lokal verwaltete MO-Installation** unter demselben
Projektnamen `mays-orders` (lokaler State im RIS-Repo, Serial 129, Pool
`eu-central-1_ENMwxNFS9`). Vor jedem plan/apply für `mays-orders` ist die
Ownership der Projektnamen-Treffer zu klären — genau das übernimmt der Check
aus Abschnitt 9a. Die RIS-Installation gehört **nicht** diesem Repo und darf
von hier aus nie angefasst werden.

Ein früherer Profilauflösungsfehler wurde behoben; der Installer muss widersprüchliche Identitätsinformationen fail-closed behandeln.

## 6. Mutationsschalter

Die bestehende README dokumentiert:

| Variable | Dokumentierter Wert | Funktion |
|---|---|---|
| `AWS_PROFILE` | `mayaws` | Benanntes Profil, per `--profile` überschreibbar |
| `AWS_REGION` | `eu-central-1` | Region |
| `ALLOW_AWS_OPERATIONS` | `false` | Erforderliche zusätzliche Freigabe für Mutationen |
| `DRY_RUN` | `true` | Standardmäßig kein tatsächlicher Apply/Destroy |

`--yes` überspringt **nur** eine interaktive Rückfrage, nicht die Sicherheitsprüfungen. Die tatsächlichen Defaults sind bei Änderungen am Installer-Code erneut zu prüfen.

### Dokumentierte Deploy-Syntax (nur nach Freigabe)

```bash
export ALLOW_AWS_OPERATIONS=true
export DRY_RUN=false
./Mays-Order-AWS-installer deploy --plan <GEPRUEFTER_PLAN> --yes
```

**Nicht blind ausführen.** Konto, Workspace, State, Policy Gate und Plan müssen zuvor explizit geprüft werden.

## 7. Terraform Policy Gate

Das Gate prüft definierte Ressourcen-, Regions-, Tagging- und Kostenregeln. **PASS** ist keine Kosten- oder IAM-Garantie. Ein FAIL darf nicht umgangen werden, um ein Deployment zu erzwingen.

Quellen: `docs/TERRAFORM_POLICY_GATE.md`, `terraform/policy/resource-policy.json`, `terraform/policy/validate-plan.py`.

## 8. Workspace-Isolation und Backups

Projektbezogene Terraform-Workspaces trennen die State-Dateien, auch wenn ein gemeinsames Backend verwendet wird. Vor einem Destroy ist die Isolierung gegen alle anderen Projekte nachzuweisen. Ein gemeinsamer Backend-Bucket darf nicht gelöscht werden, solange andere Workspaces ihn verwenden.

Cognito-Backup-Module können optional sein. Die Privacy-Testinstallation nutzte deaktivierte Backup-Module; andere Installationen können davon abweichen.

## 9. Lambda-Artefaktintegrität

Ein historischer Fehler entstand durch ein veraltetes `lambda/dist/lambda.zip`, obwohl der Quellcode bereits korrigiert war. Das **Staleness Gate** prüft deshalb das Paket gegen den Source vor der Planung.

```bash
cd lambda
python3 build_zip.py
```

Der dokumentierte Release-Hash für `v0.5.0-rc.1` lautet:

```text
b1018a3bd03455ede329ffaa3c66ca8115c6077741c8aad5282ee5f5fbd00e2b
```

Dieser Hash gilt für den dokumentierten Release Candidate, nicht für beliebige spätere Builds.

## 9a. AWS-Namenskollisions-Check (`aws_project_collision`)

**Hintergrund (Incident 2026-10):** Zwei unabhängige Deployments verwendeten
dasselbe `project_name` (`mays-orders`) im selben AWS-Konto. Das Ergebnis waren
zwei Cognito User Pools mit identischem Namen `mays-orders-users` — eines aus
dem S3-State-Workspace dieses Repos, eines aus einer parallel betriebenen,
lokal verwalteten Installation. Kein Tooling machte das sichtbar; die Fehlersuche
kostete erheblich Zeit.

Der Preflight-Check (`validate` und Plan-Vorprüfung) listet deshalb read-only
die Ressourcen des Kontos (Cognito-Pools, DynamoDB-Tabellen, Lambda-Funktionen,
SQS-Queues, S3-Buckets) und meldet:

- **Doppelte Namen innerhalb eines Service** (z. B. zwei Pools gleichen Namens)
  → `WARNING` mit IDs — stärkstes Kollisionssignal.
- **Vorhandene Ressourcen, die den Projektnamen enthalten** → `WARNING` mit
  Ownership-Hinweis: prüfen, ob sie zu *diesem* State gehören oder zu einer
  Parallel-Installation (z. B. RIS-verwaltete Installation).
- **Keine Treffer** → `PASS` (Konto für dieses Projekt sauber).

Der Check ist **best-effort**: ohne validierten AWS-Kontext oder bei CLI-Fehlern
degradiert er auf `WARNING` (Skip), niemals auf `FAIL`. Er führt ausschließlich
List-Aufrufe aus (`list-user-pools`, `list-tables`, `list-functions`,
`list-queues`, `list-buckets`) und verändert nichts.

**Wichtig:** Ein `WARNING` hier blockiert nicht, ist aber vor jedem `plan`/`apply`
zu klären — genau wie Workspace, State und Policy Gate.

**Live-Beispiel (Stand 2026-10-14, nach dem Cleanup des Backup-Stack-Rests):**
Für `mays-orders` meldet der Check jetzt **keine Duplikate mehr**, sondern nur
noch die Ownership-Klärung der 9 verbleibenden Treffer:

```text
⚠ aws_project_collision: 9 existing AWS resource(s) match project name 'mays-orders'
  — confirm they belong to this project's state or document the parallel
    owner (e.g. RIS-managed installation) before plan/apply
    cognito_pools_matching_project: 1     (RIS-verwalteter Pool ENMwxNFS9)
    dynamodb_tables_matching_project: 2   (RIS-MO-Tabelle + geteilte Lock-Tabelle)
    lambda_functions_matching_project: 2 (RIS-verwaltete MO-Funktionen)
    sqs_queues_matching_project: 1       (RIS-verwaltete Queue)
    s3_buckets_matching_project: 3       (CI-Artefakte, CloudTrail, Backend-Bucket)
```

Solange die RIS-Installation unter diesem Projektnamen läuft, **bleibt diese
Warning gewollt sichtbar** — sie ist der ständige Hinweis, dass ein Parallel-Bestand
existiert, der nicht diesem State gehört. Details zum Incident und zur
Ownership-Tabelle: `docs/reports/MAYS-ORDERS-LEFTOVER-STATE-CLEANUP-01.md`.

## 10. Kontrollierter Destroy

**Pflicht-Gates:** AWS-Identität, Region, Projekt, Workspace, Backend-State, unveränderter aktueller Plan, ausschließlich freigegebene Ressourcen, keine fremden Projektressourcen, gesicherte Evidence und explizite menschliche Freigabe.

```bash
# NUR nach ausdrücklicher Destroy-Freigabe:
export ALLOW_AWS_OPERATIONS=true
export DRY_RUN=false
./Mays-Order-AWS-installer destroy --plan <GEPRUEFTER_DESTROY_PLAN> --yes
```

Im dokumentierten Privacy-Test wurden 37 Ressourcen kontrolliert entfernt. Der betroffene Terraform-State war danach leer; die projektspezifischen DynamoDB-, Cognito-, Lambda-, SQS-, API-Gateway-, CloudWatch-, IAM- und S3-Ressourcen waren nicht mehr vorhanden. Das ist ein **historischer Nachweis**, keine Garantie für künftige Installationen.

**Zweiter historischer Nachweis (mays-orders Backup-Stack-Rest, 2026-10-14):**
Destroy-Plan `destroy-0003`, **20 Deletes** — ausschließlich
`module.cognito`, `module.cognito_backup`, `module.cognito_backup_automation`;
Plan-Isolation vorher explizit gegen die RIS-verwalteten Bestände geprüft
(keine `module.api`/`dynamodb`/`lambda`/`sqs`/`sqs_worker`/`cloudtrail`/
`monitoring`/`iam`-Adressen im Plan). Danach: State leer, Duplikat-Pool
beseitigt, RIS-Installation nachweislich unangetastet (Report
`MAYS-ORDERS-LEFTOVER-STATE-CLEANUP-01.md`).

**Betriebs hinweis — Buckets ohne `force_destroy`:** Das Cognito-Backup-Modul
setzt kein `force_destroy`. Vor einem Destroy müssen versionierte Objekte
zuerst geleert werden (z. B. `s3api list-object-versions` → `s3api
delete-objects` mit Versions-Manifest), sonst scheitert die Bucket-Löschung
mit `BucketNotEmpty`.

## 11. Post-Deploy- und Post-Destroy-Prüfungen

**Nach Deploy:** Lambda-Code-Hash, JWT-Authentifizierung, API-Aufrufe, Statusübergänge, SQS-Worker, DynamoDB-Indizes, Logs und IAM-Berechtigungen verifizieren; Testdaten anschließend entfernen.

**Nach Destroy:** `terraform state list` im **richtigen Workspace** prüfen; projektspezifische AWS-Ressourcen suchen; asynchrone Löschungen und mögliche Kostenreste dokumentieren; fremde Workspaces und gemeinsame Backends unangetastet lassen; **zum Abschluss `validate` erneut ausführen** und den `aws_project_collision`-Status interpretieren — er zeigt jetzt den sauberen Ist-Zustand (keine Duplikate; verbleibende Projektnamen-Treffer = dokumentierte Parallel-/Backend-Bestände).

## 12. Security und Einschränkungen

- Keine Secrets, Tokens, Terraform-State- oder Plan-Dateien committen.
- Secrets nicht in CLI-Argumenten, Logs oder Shell-History offenlegen.
- Policy Gate ersetzt nicht IAM, Kostenüberwachung oder menschliche Freigabe.
- Der interne Privacy-Invoke-Pfad ist **nicht produktiv freigegeben**.
- Dauerhaftes Secret-Management und Rotation sind offen.
- Neue Ressourcentypen erfordern neue Sicherheits- und Destroy-Tests.

## 13. Release-Testnachweise

| Prüfung | Ergebnis |
|---|---|
| Installer Unit Tests (RC-Checkpoint) | 81 PASS |
| Installer Unit Tests (main, inkl. Kollisions-Preflight + `--guide`) | **129 PASS** (120 Suite inkl. 19 Collision-Tests + 9 Guide-Tests, Stand 2026-10-14) |
| Lambda Unit Tests | 76 PASS |
| Artifact Integrity | 5 PASS |
| Terraform fmt / validate | PASS |
| Privacy AWS E2E | Historisch P-01 bis P-03 PASS |
| AWS Regression | Historisch 12/12 PASS |
| Destroy Lifecycle (Privacy-Test) | 37 Deletes, State leer, 0 projektspezifische Reste |
| Destroy Lifecycle (mays-orders Backup-Rest) | 20 Deletes, State leer, RIS-Bestand unangetastet, Kollisions-Duplikat beseitigt |
| Collision-Preflight Live | VERIFIED (Duplikat-Erkennung + Ownership-Warning gegen Konto 240571105849) |
| `--guide` Flag | VERIFIED (Pfad + Inhaltsverzeichnis, Exit 0, 9/9 Tests) |

## 14. Wartung und Dokumentationspflicht

Änderungen an CLI-Flags, Profilauflösung, Planformat, Workspace-Auswahl, Policy Gate oder Artefaktprüfung erfordern Aktualisierung dieses Guides, der README, der Reports und `docs/AI_AUDITLOG.md`. Abgeschlossene Arbeitsschritte werden nachvollziehbar committed.

**Weiterlesen:** [Produktübersicht](PRODUCT_OVERVIEW.md) · [Policy Gate](TERRAFORM_POLICY_GATE.md) · [Release Notes](RELEASE_NOTES.md) · [RC-Report](reports/MAYS-ORDERS-RELEASE-CANDIDATE-HARDENING-01.md)
