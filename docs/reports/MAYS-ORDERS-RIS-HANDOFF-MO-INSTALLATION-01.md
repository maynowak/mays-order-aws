# MAYS-ORDERS-RIS-HANDOFF-MO-INSTALLATION-01

**Dokumenttyp:** Übergabe-/Empfehlungsbericht an Team RIS
**Datum:** 2026-10-16
**Autor:** Mays-Orders-AWS (Repo `maynowak/mays-order-aws`, Remote main `6fd76e4`)
**Adressat:** Team Mays-Recruiting-Intelligent-System (Repo `Mays-Recruiting-Intelligent-System`)
**AWS-Konto (gemeinsam):** 240571105849 · Region eu-central-1
**Klassifikation:** Empfehlung — keine Aktion ohne Freigabe des RIS-Teams

---

## 1. Zusammenfassung (Executive Summary)

Im gemeinsamen AWS-Konto existiert eine **MO-Vollinstallation (Mays-Orders-Stack)**,
die vom RIS-Team betrieben wird — verwaltet über einen **lokalen Terraform-State im
RIS-Repo** unter dem Projektnamen `mays-orders`. Diese Installation ist nachweislich
**produktiv genutzt** (GATE-6: RIS-Orders-Pfad läuft über die MO-Tabelle). Gleichzeitig
verursachte das Namensdoppel mit unserem Projekt im Oktober 2026 einen dokumentierten
Kollisions-Incident (zwei Cognito-Pools `mays-orders-users`).

Unsererseits ist alles aufgeräumt: Unser Anteil am Incident (Backup-Stack-Rest im
S3-Workspace `mays-orders`) ist kontrolliert abgebaut (20 Ressourcen), unser Installer
warnt seitdem bei jedem Preflight vor Namenskollisionen. **Was bleibt, ist die
RIS-verwaltete MO-Installation mit lokalem State und generischem Projektnamen.**

Dieser Bericht legt dar, wie sie diese Installation sicher überführen, absichern oder
— falls gewünscht — geordnet zurückbauen können, ohne ihre Produktion zu gefährden.

## 2. Ausgangslage und Incident (Fakten)

1. **2026-09-27:** Unser Projekt deployte den Cognito-Backup-Stack in den S3-Backend-
   Workspace `mays-orders` (Pool `eu-central-1_xhjl0PxEH`) — Feature-Entwicklung,
   nach Abschluss als Rest stehen geblieben.
2. **2026-10-01 (RIS GATE-3):** RIS installierte den MO-Stack aus einem gepinnten Clone
   (Stand `9c61237`). Der Clone enthielt **kein `backend.tf`** → **lokaler State**;
   der Installer-Default `project_name=mays-orders` wurde übernommen. Ergebnis:
   parallel ein zweiter Cognito-Pool mit identischem Namen (damals `8HrAMWpB2`,
   später neu erstellt als `eu-central-1_ENMwxNFS9`, State inzwischen Serial 129).
3. **Folge:** Zwei Pools `mays-orders-users` mit identischem Tag `Project=mays-orders`
   — per Tag nicht unterscheidbar, von keinem Tooling signalisiert. Mehrere RIS-Reports
   (GATE-3, RIS-AWS-STATE-INVENTORY-01) vermischten daraufhin die Zuordnung beider
   Bestände; die Klärung kostete auf beiden Seiten erhebliche Zeit.
4. **2026-10-13 (RIS-Report MAYS-RIS-CLEANUP-AND-VERIFY-mitluftposter-01):**
   Dokumentiert u. a. einen separaten Paralleltest-Zwischenfall (Produktions-Queues
   neu erstellt, historische Nachrichten unwiederbringlich verloren) und führt die
   MO-Installation als „Protected Orders" mit lokalem State (Serial 129).

**Wichtig:** Beide Teams haben korrekt dokumentiert. Der Vorfall ist ein
**Strukturproblem** (gleicher Projektname + lokaler State im selben Konto), keine
Einzelfehlleistung.

## 3. Ist-Zustand (Ownership-Klartabelle, Stand 2026-10-16)

| Bestand | Owner | State | Anmerkung |
|---|---|---|---|
| MO-Vollinstallation (API `mays-orders-api`/`vmmqrwcb26`, Pool `ENMwxNFS9`, DynamoDB `mays-orders`, Lambda `mays-orders-handler`/`-sqs-worker`, SQS `mays-orders-orders-queue`, CloudTrail-Bucket `mays-orders-cloudtrail-240571105849`, Monitoring, IAM; 45 State-Blöcke) | **Team RIS** | Lokal: `installer/projects/mays_orders/terraform/terraform.tfstate`, Serial 129, Lineage `945c0b35…` | **Produktiv genutzt** (GATE-6-Pfad) |
| RIS-Produktion (`mays-ris-dev-*`: Queues + DLQ, Lambda `mays-ris-dev-agent`/`-orders-reader`, DynamoDB `mays-ris-dev-*`, Pool `dgQXgwUbv`, API `aboqolpm0f`) | **Team RIS** | Remote: `mays-ris-tf-state-dev`, Serial 21 | **Unbedingt schützen** |
| S3 `mays-orders-ci-artifacts-dev` + CodeBuild-Projekte | ungeklärt (prä-GATE-3, vermutlich D8-CI) | keinem State bekannt | Review offen |
| S3 `mays-orders-tfstate-central-240571105849` + DynamoDB `mays-orders-terraform-locks` | geteilte Backend-Infra (MO) | — | **Nicht löschen**, solange Workspaces sie nutzen |
| Ehemaliger Backup-Stack (Pool `xhjl0PxEH` etc.) | Mays-Orders-AWS | — | **Am 2026-10-14 kontrolliert abgebaut** (20 Deletes, Report `MAYS-ORDERS-LEFTOVER-STATE-CLEANUP-01.md`) |

## 4. Kritische Abhängigkeit — bitte zuerst prüfen

RIS GATE-6 (2026-10-01, GREEN) belegt den **produktiven Pfad**:
`SQS → Worker → Orders-Function → Port → Real-Adapter → eigene API → MO-Tabelle → Result`.

**Konsequenz:** Ein Abbau der MO-Installation ist **keine reine Aufräum-Maßnahme**,
sondern degradiert den RIS-Orders-Port. Vor jeder Destroy-Entscheidung ist intern zu
klären: Soll der Orders-Port (a) dauerhaft auf echter MO-Infrastruktur laufen,
(b) auf einen DevelopmentOrdersAdapter zurückfallen oder (c) stillgelegt werden?

## 5. Lösungsvarianten

### Option A — Kontrolle übernehmen statt zerstören (**Empfehlung**)

Die Installation behalten, aberOwnership, State und Naming sauber machen:

1. **State in Remote-Backend überführen** (z. B. eigener Prefix im
   `mays-orders-tfstate-central`-Bucket oder ein RIS-eigener Bucket): Backup der
   State-Datei, `terraform init` mit Backend + `terraform state push`.
2. **Distinkten Projektnamen** für die Installation wählen (z. B. `ris-mo` oder
   `mays-orders-ris`) — Cognito-Pool, IAM-Rollen etc. werden dadurch eindeutig
   dem RIS zuordenbar; kein Namensdoppel mit dem MO-Default mehr.
3. **Collision-Preflight übernehmen** (Abschnitt 7): künftig schlägt jeder
   Namenskonflikt beim Preflight sichtbar an.
4. State serial 129 danach per `terraform plan` auf Drift prüfen.

*Vorteile:* kein Produktionsbruch, Kollisionsquelle dauerhaft beseitigt, State
recoverable. *Aufwand:* moderat (Backend-Migration + Rename-Rollout).

### Option B — Geordneter Rückbau (nur wenn Orders-Port zurückgefahren wird)

1. Interne Entscheidung dokumentieren (Orders-Port-Stillegung oder Dev-Adapter-Fallback).
2. **Vor jedem terraform run:** State-Backup (`cp terraform.tfstate{,.bak-$(date +%s)}`).
3. `terraform plan -destroy -out=destroy-mo.tfplan` im RIS-Clone.
4. **Pflicht-Isolationsprüfung des Plans** (siehe Abschnitt 6) — insbesondere:
   keine Adresse mit `mays-ris-dev-*`, keine Berührung des Production-States.
5. Freigabe + `terraform apply destroy-mo.tfplan`; danach Live-Verifikation
   (Ressourcen weg, RIS-Produktion intakt) und State archivieren.

### Option C — Sofort-Mindestmaßnahmen (ohne Migration)

Falls A/B kurzfristig nicht machbar sind:

- Die MO-Installation mit Owner-Tags versehen (z. B. `Owner=RIS`, `Managed-By=RIS-MO-Local-State`) — aber nicht im State ändern, sondern als dokumentierte Zuordnung.
- Naming-Konflikt in eurer Doku prominent verankern (unser Installer warnt bereits).
- **State-Backup vor jedem terraform run** — der lokale State ist die einzige
  Verwaltung dieser 45 Ressourcen; Verlust = verwaiste Ressourcen.

## 6. Pflicht-Sicherheitschecks (für jede Variante)

| Check | Kriterium |
|---|---|
| AWS-Identität | `aws sts get-caller-identity` → 240571105849 |
| Arbeitsverzeichnis | Ausschließlich der RIS-Clone-Pfad mit dem Serial-129-State |
| Plan-Isolation | Keine Adresse/ID aus `mays-ris-dev-*`, kein Production-State (Serial 21) |
| Geteilte Infra | `mays-orders-tfstate-central-*` und `mays-orders-terraform-locks` unberührt |
| State-Backup | Vor `init`/`plan`/`apply`/`destroy` lokale Kopie des Serial-129-State |
| Post-Run | Live-Verifikation aller kritischen Ressourcen (Queues, Mappings, Pool) |
| Kein Cross-Repo-Install | Niemals aus einem Repo unter dem Projektnamen eines anderen installieren |

## 7. Was ihr von uns übernehmen könnt (bewährt, mit Tests)

Unser Installer (Repo `maynowak/mays-order-aws`) hat genau die Gates, die diesen
Incident verhindert hätten — gerne als Muster oder direkt als Referenz:

1. **AWS-Namenskollisions-Preflight** (`installer/core/collision_scan.py`, Commit
   `f387b3e`): read-only List-Scans (Cognito/DynamoDB/Lambda/SQS/S3), meldet
   Duplikat-Namen (mit IDs) und Projektnamen-Treffer zur Ownership-Klärung.
   19 Unit-Tests, portierbar als Modul in euren Installer.
2. **Prüflauf-Disziplin:** Preflight-Validierung (Profil/Konto/Region/Workspace/
   State) **vor** jedem Plan; Destroy-Safety-Gate mit Plan-Isolation vor jedem
   Destroy; human approval (`--yes` ersetzt keine Prüfung).
3. **Artefakt-Integrität** (`installer/core/artifact_integrity.py`): verhindert
   Stale-Deployments nach Code-Änderungen.
4. **Plan-Metadaten** (Projekt/Konto/Operation/Sequenz je Plan-Datei) für
   Wiederholbarkeit und Fehlzuordnungsschutz.
5. **`--guide`-Flag** als Doku-Verweis im CLI (Commit `adddca8`).

Da ihr aktuell einen eigenen Installer aufbaut: diese Bausteine sind klein,
unabhängig voneinander übernehmbar und erheblich schneller übernommen als
neu konzipiert. Unser collisions_scan-Pattern (reine Funktionen + injizierbarer
Runner) ist direkt testbar ohne AWS-Zugriff.

## 8. Empfohlene Reihenfolge (Zusammenfassung)

1. Klären: Zukunft des Orders-Ports (Nutzung ja/nein) → Variante A oder B wählen.
2. Sofort: State-Backup-Disziplin etablieren (Option C ist gratis).
3. Kurzfristig: Collision-Preflight in den RIS-Installer portieren; bei jedem
   Preflight laufen lassen.
4. Mittelfristig: Variante A umsetzen (Remote-State + distinkter Name) oder
   Variante B geordnet zurückbauen.
5. Ownership `mays-orders-ci-artifacts-dev` + CodeBuild klären (separater Punkt).

## 9. Referenzen

- Unser Incident-Report: `MAYS-ORDERS-INSTALLER-COLLISION-PREFLIGHT-01.md`
- Unser Cleanup-Report: `MAYS-ORDERS-LEFTOVER-STATE-CLEANUP-01.md`
- RIS GATE-3: `GATE-3-MO-LIVE-INSTALLATION-AND-VERIFICATION-01.md`
- RIS GATE-6 (Abhängigkeitsnachweis): `GATE-6-ORDERS-PORT-REAL-MAYS-ORDERS-ADAPTER-01.md`
- RIS Incident/Inventory: `MAYS-RIS-CLEANUP-AND-VERIFY-mitluftposter-01.md`,
  `RIS-AWS-STATE-INVENTORY-01.md`

---

*Dieser Bericht enthält keine Secrets, keine State-Inhalte und keine Zugangsdaten.
Alle Angaben sind durch die referenzierten Reports bzw. read-only AWS-Checks belegt.*
