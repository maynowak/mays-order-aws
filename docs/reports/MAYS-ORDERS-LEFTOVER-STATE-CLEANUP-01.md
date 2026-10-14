# MAYS-ORDERS-LEFTOVER-STATE-CLEANUP-01

**Checkpoint:** MAYS-ORDERS-LEFTOVER-STATE-CLEANUP-01
**Datum:** 2026-10-14
**Baseline:** f387b3e (remote main)
**AWS-Kontext:** Profil mayaws, Konto 240571105849, Region eu-central-1
**Status:** VERIFIED — Cleanup vollständig, RIS-Bestand unangetastet

## 1. Ausgangslage (User-Kontext)

Die Entwicklung (Cognito-Backup-Feature) war im Projekt Mays-Orders-AWS abgeschlossen;
der Eindruck war, der Development-Bestand sei aufgeräumt. Tatsächlich blieb der
**Cognito-Backup-Stack im S3-Backend-Workspace `mays-orders`** (Serial 18, seit
2026-09-27) bestehen. Parallel hatte ein Model auf der **RIS-Seite** während der
RIS-Installation den vollen MO-Stack unter demselben Projektnamen `mays-orders`
mit **lokalem State** installiert (RIS-Reports GATE-2/GATE-3; Report
MAYS-ORDERS-INSTALLER-COLLISION-PREFLIGHT-01 dokumentiert den Incident).
Ergebnis: zwei Cognito-Pools mit identischem Namen `mays-orders-users`
(`xhjl0PxEH` = unser Rest, `ENMwxNFS9` = RIS-verwaltet).

**Aufgabentrennung (User-Entscheidung):** Unseren Rest räumen **wir** hier auf;
die RIS-Installation gehört dem **anderen Team** und bleibt unangetastet.

## 2. Pre-Destroy Safety (VERIFIED)

- Identity: 240571105849 / `arn:aws:iam::240571105849:user/Mayaws` ✓
- Workspace: `mays-orders` (S3-Backend `env:/mays-orders/terraform.tfstate`) ✓
- Unser State: 25 Blöcke (nur cognito/cognito_backup/cognito_backup_automation) ✓
- RIS-State (Serial 129, lokal im RIS-Repo): 0 Backup-Ressourcen → keine Überschneidung ✓

## 3. Cleanup-Ausführung

1. **Backup-Bucket geleert** (9 Objekt-Versionen, 3.538 Bytes — wertlose
   Sep-27-JSON-Backups des leeren Pools; Modul hat kein `force_destroy`):
   `s3api delete-objects` mit Versions-Manifest, danach Bucket leer verifiziert.
2. **Destroy-Plan** über Installer: `plan-destroy` →
   `mays-orders-development-0.1.0-H2-240571105849-destroy-0003.tfplan`
3. **Plan-Isolation (vor Apply):** 20 Deletes, ausschließlich
   `module.cognito`, `module.cognito_backup[0]`, `module.cognito_backup_automation[0]`;
   RIS-Schutz-Check: `mays-ris`, `module.api`, `module.dynamodb`, `module.lambda`,
   `module.sqs`, `module.sqs_worker`, `module.cloudtrail`, `module.monitoring`,
   `module.iam` — **alle nicht im Plan** ✓; Pool im Plan: `eu-central-1_xhjl0PxEH` (unser) ✓
4. **Destroy:** Safety Analysis PASS, `Destruction successful!`

## 4. Post-Destroy Verification (VERIFIED)

| Prüfung | Ergebnis |
|---|---|
| `terraform state list` (Workspace mays-orders) | **0 Ressourcen** ✓ |
| Pool `eu-central-1_xhjl0PxEH` | gelöscht ✓ |
| `mays-orders-cognito-backup-lambda` | gelöscht ✓ |
| Backup-Bucket `mays-orders-cognito-backup-development-mays-orders` | gelöscht ✓ |
| Scheduler `mays-orders-cognito-backup-schedule` | gelöscht ✓ (kein tägliches Backup-Cron mehr) |
| SNS Topic `mays-orders-cognito-backup-notifications` | gelöscht ✓ |
| IAM-Rollen `mays-orders-cognito-backup-role` / `-scheduler-role` | gelöscht ✓ |
| **RIS-Pool `eu-central-1_ENMwxNFS9`** | **unangetastet, aktiv** ✓ |
| RIS DynamoDB `mays-orders`, Lambda `mays-orders-handler`/`-sqs-worker`, SQS `mays-orders-orders-queue` | **unangetastet** ✓ |

**Collision-Check nach Cleanup** (`aws_project_collision`): **keine Duplikate mehr**
— nur noch 1 Pool `mays-orders-users` (RIS-verwaltet). Der Check meldet
informationell 9 Projektnamen-Treffer, sämtlich mit klarer Ownership (s. §5).

## 5. Verbleibender Bestand mit Projektnamen-Bezug (READ-ONLY inventarisiert)

| Ressource | Ownership | Umgang |
|---|---|---|
| Pool `eu-central-1_ENMwxNFS9` + Client/Gruppe | RIS-verwaltet (lokaler State Serial 129, anderes Team) | NICHT unser Cleanup — Team RIS |
| DynamoDB `mays-orders` | RIS-verwaltet (MO-Stack) | NICHT unser Cleanup — Team RIS |
| Lambda `mays-orders-handler`, `mays-orders-sqs-worker` | RIS-verwaltet | NICHT unser Cleanup — Team RIS |
| SQS `mays-orders-orders-queue` | RIS-verwaltet | NICHT unser Cleanup — Team RIS |
| S3 `mays-orders-cloudtrail-240571105849` | RIS-verwaltet (MO-CloudTrail) | NICHT unser Cleanup — Team RIS |
| S3 `mays-orders-tfstate-central-240571105849` + DynamoDB `mays-orders-terraform-locks` | **Geteilte Backend-Infra** (auch andere Workspaces) | **Nicht löschen** |
| S3 `mays-orders-ci-artifacts-dev` (+ CodeBuild-Projekte) | Nicht in unserem State; vermutlich D8-CI-CD-Checkpoint | Offen — separater Review empfohlen |

## 6. Handoff-Empfehlung an Team RIS (damit es nicht wieder passiert)

1. **Eigener Projektnamen** für die RIS-verwaltete MO-Installation verwenden
   (z. B. `ris-mo` / `mays-orders-ris`) statt des MO-Default-Namens — erst dann
   ist Ownership an Namen/Tags eindeutig unterscheidbar.
2. **Kollisions-Preflight übernehmen:** Der MO-Installer meldet seit
   `f387b3e` (`aws_project_collision`) doppelte Namen und Projektnamen-Treffer
   bei jedem `validate`/`plan`. Dasselbe Muster (read-only List-Scans +
   Duplikat/Match-Klassifikation, siehe `installer/core/collision_scan.py`)
   lässt sich in den RIS-Installer portieren.
3. **Kein Cross-Repo-Installieren unter fremdem Projektnamen:** Die
   RIS-GATE-Berichte zeigen den Pfad (gepinnter Clone, kein backend.tf → lokaler
   State, Installer-Default `project_name=mays-orders`). Genau das erzeugte die
   Kollision. Gepinnte Clone-Installationen müssen Backend + Projektnamen
   explizit und **eindeutig** setzen.

## 6a. Begleitende Dokumentations-/Tooling-Arbeiten (gleiche Session)

- **Installer-Handbuch detailliert aktualisiert** (`docs/INSTALLER_GUIDE.md`):
  Ablauf-Diagramm um Kollisionsscan + Post-Destroy-Re-Check erweitert;
  §4 CLI-Einstieg mit `--guide`; §5 um historischen mays-orders-Kontext und
  Parallel-Installations-Warnung erweitert; §9a um das Live-Beispiel nach
  Cleanup (9 Ownership-Treffer, keine Duplikate); §10 um zweiten Destroy-Nachweis
  (destroy-0003, 20 Deletes) + Betriebs hinweis zu Buckets ohne `force_destroy`;
  §13 Testmatrix aktualisiert (129 Installer-Tests).
- **Neuer CLI-Flag `--guide`:** zeigt Pfad + Inhaltsverzeichnis des
  Installer-Handbuchs an und beendet read-only mit Exit 0
  (`installer/cli/guide.py`; keine AWS-/Terraform-Nebenwirkungen).
  Es gibt keinen allgemeinen CLI-Standard für Doku-Verweise — `--guide` ist die
  projektspezifische Konvention neben `--help`.
- **Tests:** 9 neue `--guide`-Tests (`installer/tests/test_guide_flag.py`);
  Voll-Regression **129/129 Installer-Tests + 76/76 Lambda-Tests GREEN**.

## 7. Status

**VERIFIED / COMPLETE** — Unser Rest ist vollständig aufgeräumt; Duplikat-Kollision
beseitigt; RIS-Bestand nachweislich unangetastet; Empfehlungen für das andere Team
dokumentiert. Kein Destroy der geteilten Backend-Infra.
