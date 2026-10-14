# Release v0.5.0-rc.2 — Mays-Orders-AWS

**Release:** v0.5.0-rc.2 (Pre-Release Candidate)
**Datum:** 2026-10-14
**Basline:** v0.5.0-rc.1 → `f6e737b` · Remote main `adddca8` + dieser Release-Commit
**Projekt:** Mays-Orders-AWS · Repository `maynowak/mays-order-aws`
**Produktive Privacy-Aktivierung:** **BLOCKED** (unverändert)

---

## 1. Release Overview

v0.5.0-rc.2 ist ein Härungs-Release auf Basis von v0.5.0-rc.1. Es enthält
**keine neuen Produktfunktionen** der Order-Plattform, sondern Installer-Härtung,
Incident-Aufarbeitung und Betriebs-Dokumentation: Nach dem AWS-Namenskollision-
Incident (Oktober 2026) wurde ein read-only Kollisions-Preflight in den Installer
integriert, der seitlich liegen gebliebene Development-Ressourcen unseres S3-State
kontrolliert abgebaut und das Installer-Handbuch detailliert modernisiert.

**Kernpunkte:** Collision-Preflight (`aws_project_collision`) · Cleanup von 20
Ressourcen im Workspace `mays-orders` · RIS-Isolation nachgewiesen · `--guide`
CLI-Flag · 129 Installer-Tests · 76 Lambda-Tests.

## 2. Changes seit v0.5.0-rc.1

| Commit | Inhalt |
|---|---|
| `514c808` | Docs Final Review (MAYS-ORDERS-RC-DOCUMENTATION-FINAL-REVIEW-01) |
| `450ad94` | Umbenennung RC auf v0.5.0-rc.1, Doku-/Tag-Migration |
| `26db092` | Release-Beschreibung v0.5.0-rc.1 (Markdown + PDF-Platzhalter) |
| `f387b3e` | **Feature:** AWS-Namenskollisions-Preflight (Installer), CLI-Ausgabe-Fix |
| `adddca8` | **Cleanup + Docs:** 20-Ressourcen-Abbau mays-orders-Rest, Guide-Detailupdate, `--guide` |

Alle Änderungen sind in remote main enthalten (Quelle: `git log v0.5.0-rc.1..main`).

## 3. AWS-Ressourcenkollisions-Incident

Im AWS-Konto 240571105849 betrieben zwei unabhängige Deployments denselben
Projektnamen `mays-orders`: (a) der Cognito-Backup-Stack-Rest aus der Entwicklung
dieses Repos (S3-Backend-Workspace `mays-orders`, State Serial 18, seit
2026-09-27) und (b) eine von der RIS-Seite gepinnte MO-Vollinstallation mit
**lokalem State** (Serial 129, Pool `eu-central-1_ENMwxNFS9`). Ergebnis: zwei
Cognito User Pools mit identischem Namen `mays-orders-users`
(`xhjl0PxEH` vs. `ENMwxNFS9`) und identischen Project-Tags — per Tag nicht
unterscheidbar, von keinem Tooling signalisiert. Die Klärung kostete erhebliche
Zeit. Forensik: RIS-Reports GATE-2/GATE-3 (unser Backup-Stack dort als
„vorgefunden, nicht angefasst" dokumentiert) und
`MAYS-ORDERS-INSTALLER-COLLISION-PREFLIGHT-01.md`.

## 4. Collision-Preflight im Installer

Neu in `f387b3e`: Der Validierungslayer führt bei jedem `validate` und Plan-
Preflight den read-only Check `aws_project_collision` aus
(`installer/core/collision_scan.py`):

- **Duplikat-Erkennung:** identische Namen innerhalb eines Service
  (z. B. zwei Pools `mays-orders-users`) → WARNING mit IDs — stärkstes Signal.
- **Ownership-Warnung:** vorhandene Ressourcen mit Projektnamen-Match → WARNING
  mit Hinweis, den Owner zu klären (eigenes State vs. Parallel-Installation).
- **Clean Account:** keine Treffer → PASS.
- Best-effort: ohne AWS-Kontext oder bei CLI-Fehlern degradiert der Check auf
  WARNING, nie FAIL. Ausschließlich List-Aufrufe, keinerlei Mutationen.

## 5. Grenzen der Ownership-Klassifikation

Die Klassifikation ist in dieser Phase **namensbasiert**: Ein Projektnamen-Match
beweist keine Ownership. Der Check cross-checkt **nicht** gegen den Terraform-
State (MANAGED/UNMANAGED), sondern meldet Treffer zur menschlichen Klärung.
Projekte mit gleichem Namenspräfix (z. B. `mays-order` vs. `mays-orders`)
produzieren gewollt Matches. Geplant (Phase 2): Abgleich des Inventars gegen
`terraform show -json` für eine echte MANAGED/UNMANAGED-Klassifikation.

## 6. Kontrollierter Abbau von 20 Ressourcen

Freigegebener Destroy des Backup-Stack-Rests (Report
`MAYS-ORDERS-LEFTOVER-STATE-CLEANUP-01.md`):

- Pre-Destroy-Safety: Identity 240571105849, Workspace `mays-orders`, State 25
  Blöcke (nur cognito/cognito_backup/cognito_backup_automation), RIS-State ohne
  Backup-Ressourcen.
- Backup-Bucket vorab geleert (9 Objekt-Versionen, 3.538 Bytes — wertlose
  Sep-27-Backups des leeren Pools), da das Modul kein `force_destroy` setzt.
- Destroy-Plan `destroy-0003`: **20 Deletes**, ausschließlich aus den drei
  Backup-Modulen; RIS-Schutz-Check (api/dynamodb/lambda/sqs/sqs_worker/
  cloudtrail/monitoring/iam) ohne Treffer; betroffener Pool `xhjl0PxEH`.
- Destroy: Safety Analysis PASS, „Destruction successful".
- Post-Destroy: State leer; Pool, Backup-Lambda, Bucket, Scheduler (täglicher
  Cron), SNS, Alarme, IAM-Rollen gelöscht; Collision-Check danach: **0 Duplikate**.

## 7. RIS-Deployment-Isolation

Die RIS-verwaltete MO-Installation (lokaler State Serial 129 im RIS-Repo,
Pool `ENMwxNFS9`, DynamoDB `mays-orders`, Lambda `mays-orders-handler`/
`-sqs-worker`, SQS `mays-orders-orders-queue`, CloudTrail-Bucket) wurde vor,
während und nach dem Destroy als unangetastet verifiziert und ist **nicht
Bestandteil dieses Repos**. Empfehlungen ans RIS-Team (Report §6): eigener
Projektnamen für die MO-Installation, Portierung des Preflight-Musters in den
RIS-Installer, kein Cross-Repo-Installieren unter fremdem Projektnamen.
Geteilte Backend-Infra (State-Bucket, Lock-Tabelle) bleibt bestehen.

## 8. Installer-Flag `--guide`

Neu in `adddca8`: `./Mays-Order-AWS-installer --guide` zeigt Pfad und
Inhaltsverzeichnis des Installer-Handbuchs und beendet read-only mit Exit 0 —
ohne AWS-/Terraform-Kontakt. Implementierung `installer/cli/guide.py`
(repo-root-Auflösung, Heading-Extraktion), 9 Unit-Tests. Es existiert kein
allgemeiner CLI-Standard für Doku-Verweise; `--guide` ist die projektspezifische
Konvention neben `--help`.

## 9. Aktualisierte Installer-Dokumentation

`docs/INSTALLER_GUIDE.md`, Stand 14.10.2026: Ablauf-Diagramm um
Kollisionsscan und Post-Destroy-Re-Check erweitert; §4 CLI mit `--guide`;
§5 beide historischen Testkontexte + Parallel-Installations-Warnung; §9a
Live-Beispiel nach Cleanup (9 Ownership-Treffer, 0 Duplikate); §10 zweiter
Destroy-Nachweis + Betriebshinweis zu Buckets ohne `force_destroy`; §11
Collision-Re-Check nach Destroy; §13 Testmatrix (129 Installer-Tests).

## 10. Testergebnisse und Evidence

Alle Prüfungen für diesen Release am 2026-10-14 real ausgeführt:

| Prüfung | Ergebnis |
|---|---|
| Installer Unit Tests (inkl. 19 Collision- + 9 Guide-Tests) | **129/129 PASS** |
| Lambda Unit Tests | **76/76 PASS** |
| Artifact Integrity Tests | **5/5 PASS** |
| Terraform fmt -check | PASS |
| Terraform validate | PASS (v1.16.1, AWS-Provider ~> 6.0) |
| git diff --check | CLEAN |
| Secret-Audit | CLEAN (kein echter Secret; nur maskierter Format-Platzhalter in `docs/ai-developer-profile.md`) |
| Getrackte State-/Plan-Dateien | KEINE |

## 11. Security und Governance

- Keine AWS-Mutationen in dieser Release-Vorbereitung; kein Apply/Destroy
  (der dokumentierte Destroy war separater, freigegebener Checkpoint).
- Keine Änderungen an Mays-RIS oder RIS-verwalteten Ressourcen.
- Keine Terraform-State-Mutationen; Backend-Infra bleibt erhalten.
- **Produktive Privacy-Aktivierung bleibt BLOCKED** — dauerhaftes
  Secret-Management und Rotation sind nicht implementiert.
- Tags v0.5.0-rc.1 (`f6e737b`) unverändert; v0.2.0-rc.1 bleibt gelöscht.

## 12. Bekannte Einschränkungen

1. **Kein produktives Secret-Management/Rotation** für die internen
   Privacy-Funktionen (Produktivaktivierung BLOCKED).
2. **Ownership-Klassifikation namensbasiert** — kein State-Cross-Check (Phase 2
   offen).
3. **9 bestehende Projektnamen-Treffer** im Konto gehören zur RIS-verwalteten
   Installation bzw. geteilten Backend-Infra; der Preflight meldet sie als
   WARNING, solange RIS diesen Namen nutzt.
4. **S3 `mays-orders-ci-artifacts-dev`** (+ CodeBuild-Projekte): Ownership
   ungeklärt (vermutlich D8-CI-CD), nicht im State — separater Review offen.
5. **GitHub-Pre-Release** muss manuell veröffentlicht werden (keine
   GitHub-Credentials in der Autarkie-Umgebung).
6. Lambda-ZIP-Hash `b1018a3b…` gilt für den RC-Stand, nicht für beliebige Builds.

## 13. Nächste Entwicklungsziele

1. Secrets Manager + Rotation für `PRIVACY_INTERNAL_SECRET` entwerfen und
   umsetzen; danach Security- und AWS-E2E-Abnahme → Production Privacy Gate.
2. Collision-Preflight Phase 2: MANAGED/UNMANAGED-Klassifikation über
   `terraform show -json`.
3. RIS-Team: Projektnamen der RIS-verwalteten MO-Installation trennen und
   Preflight-Muster in den RIS-Installer portieren.
4. Ownership-Review für `mays-orders-ci-artifacts-dev` und CodeBuild-Projekte.
5. Finale Release-Abnahme v0.5.0 nach Schließen der Produktions-Blocker.

---

**Dokumentenstatus:** Dieses Markdown ist die inhaltliche Quelle; das PDF
(`docs/release/RELEASE-v0.5.0-rc.2.pdf`) wurde aus diesem Markdown generiert
(LibreOffice-Konvertierung) und inhaltlich konsistent erzeugt.
