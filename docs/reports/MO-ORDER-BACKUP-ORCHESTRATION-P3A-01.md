# MO-ORDER-BACKUP-ORCHESTRATION-P3A-01

**P3A — Verifizierbare DynamoDB-On-Demand-Backup-Orchestrierung (lokal)**

**Datum:** 2026-11-03
**Basis:** `feature/mo-order-partiql-diagnostics-p3d` @ `d0c6724`
**Arbeitsbranch:** `feature/mo-order-backup-orchestration-p3a`
**Charakter:** lokale Implementierung + Fake-Client-Tests. **Kein AWS-Aufruf, kein
Backup, kein Restore, keine Migration, kein Terraform, kein Push/Merge.**

---

## 1. Ausgangsstand

| Prüfung | Ergebnis |
|---|---|
| Basis-HEAD | `d0c6724` — vorhanden |
| Working Tree vor Beginn | CLEAN |
| Installer (vorher) | 437 PASS |
| Builder (vorher) | 128 PASS |
| Lambda (vorher) | 326 PASS |
| Terraform-DynamoDB | PITR enabled, kein Streams/TTL, AWS-owned Encryption |
| On-Demand-Backup/Restore | nicht vorhanden |

Der P3-Planungsbericht und der P3D-Bericht wurden geprüft; die dort genannten
Verträge (`pk`/`sk`, GSIs, PITR) stimmen mit dem Code überein.

---

## 2. Architekturentscheidung

- **Kleine Komponente statt Plattform:** `installer/core/order_backup.py`,
  injizierbarer DynamoDB-Client, keine boto3-Abhängigkeit im Kern.
- **Keine zweite Apply-Orchestrierung:** Backup ist ein separater, lesender/
  anlegender Schritt; Terraform bleibt unverändert.
- **Identität aus Kontext, nicht aus Name:** Tabellenname wird aus dem Projekt
  abgeleitet (Terraform: `name = var.project_name`); erwartete ARN wird aus
  Account/Region/Projekt gebildet. Ein frei übergebener Tabellenname ist kein
  gültiger Kontext.
- **State-Bindung:** `--execute` verlangt eine verifizierte Terraform-State-Baseline
  (Lineage/Serial); Evidenz bindet diese Werte. Dry-Run darf ohne Baseline planen,
  behauptet dann aber nichts.
- **Erfolg nur bei `AVAILABLE`:** `CreateBackup` allein ist kein Nachweis.
- **PITR zur Laufzeit:** Terraform `enabled = true` wird nicht als AWS-Nachweis
  übernommen.
- **Doppelte Ausführungssperre:** `ALLOW_AWS_OPERATIONS=true` **und**
  `MAYS_ORDER_BACKUP_ALLOW_EXECUTE=true`; Dry-Run importiert boto3 nie.

---

## 3. Implementierte Komponenten

| Komponente | Datei | Inhalt |
|---|---|---|
| Identität | `installer/core/order_backup.py` | `TableIdentity`, `expected_table_identity`, `verify_table_identity` |
| Backup | ebd. | `build_backup_name`, `execute_order_backup`, `wait_for_backup` |
| PITR | ebd. | `check_pitr`, `PitrEvidence` |
| Evidenz | ebd. | `BackupEvidence`, `write_evidence`, `validate_evidence_binding` |
| Dry-Run | ebd. | `plan_order_backup`, `BackupPlan`, `write_plan` |
| CLI | `installer/cli/main.py` | Subcommand `backup`, Gates, lazy boto3 |

Fehlercodes: `ORDER_BACKUP_TABLE_IDENTITY_MISMATCH`, `..._TABLE_NOT_FOUND`,
`..._TABLE_NOT_ACTIVE`, `..._ACCESS_DENIED`, `..._DESCRIBE_FAILED`,
`..._CREATE_FAILED`, `..._NAME_INVALID`, `..._NAME_CONFLICT`, `..._ARN_MISSING`,
`..._IDENTITY_MISMATCH`, `..._TIMEOUT`, `..._FAILED`, `..._PITR_UNVERIFIED`,
`..._STATE_BASELINE_REQUIRED`, `..._EVIDENCE_MISMATCH`, `..._EXECUTION_BLOCKED`.

---

## 4. Tatsächliche CLI-Syntax

```bash
# Dry-Run (offline, kein boto3, keine Identitäts-/PITR-Behauptung)
./Mays-Order-AWS-installer \
  --project-name mays-orders \
  --environment Development \
  backup --orders --dry-run

# Ausführung (in P3A nicht ausgeführt; doppelt gesperrt)
ALLOW_AWS_OPERATIONS=true \
MAYS_ORDER_BACKUP_ALLOW_EXECUTE=true \
./Mays-Order-AWS-installer \
  --project-name mays-orders \
  --environment Development \
  backup --orders --execute \
  --state-baseline <verified-baseline.json> \
  --poll-interval 10 --timeout 900 --max-attempts 90
```

Globale Optionen stehen vor dem Subcommand. Ohne `--dry-run`/`--execute` verhält
sich `backup` wie Dry-Run. Dry-Run schreibt `order-backup-plan.json/.md`,
`--execute` schreibt `order-backup-evidence.json/.md`.

---

## 5. Backup-Lifecycle

```text
Kontext + State-Baseline
  → DescribeTable (Name/ARN/Account/Region, ACTIVE)
  → CreateBackup (eindeutiger Name, kein Überschreiben)
  → DescribeBackup bis AVAILABLE (Intervall/Timeout/max. Versuche)
  → DescribeContinuousBackups (PITR)
  → Evidenz (VERIFIED/PARTIAL/FAILED)
```

Status: `REQUESTED`, `CREATING`, `AVAILABLE`, `FAILED`, `TIMEOUT`, `UNKNOWN`.
`CreateBackup` mit HTTP-Erfolg ohne ARN → `ORDER_BACKUP_ARN_MISSING`.
`BackupStatus` ungleich `AVAILABLE` → kein Erfolg.

Name: `<project>-<environment>-orders-preupgrade-<UTC>[-<random>]`,
`[A-Za-z0-9_.-]{3,255}`; Kollision wird als Fehler behandelt, nie überschrieben.

---

## 6. PITR-Prüfung

`DescribeContinuousBackups` liefert `ContinuousBackupsStatus` und
`PointInTimeRecoveryDescription`. Unterstützt werden `ENABLED`, `DISABLED`,
`UNKNOWN`; bei `ENABLED` werden earliest/latest gespeichert. Fehlende, unparsbare
oder widersprüchliche Zeitpunkte (`earliest > latest`) → `UNKNOWN` +
`ORDER_BACKUP_PITR_UNVERIFIED`, ohne erfundene Werte. boto3-`datetime`-Objekte
werden ebenso akzeptiert wie ISO-Strings.

**Grenzen:** Fenster zeitlich begrenzt; Restore nicht getestet; PITR kann gelöschte
PII wieder enthalten; kein DSGVO-Nachweis.

---

## 7. Evidenzschema

`order-backup-evidence.json` (Schema 1) enthält u. a.:

`project`, `environment`, `awsAccount`, `region`, `tableName`, `tableArn`,
`backupName`, `backupArn`, `backupStatus`, `backupVerifiedAt`, `pitrStatus`,
`earliestRestorableAt`, `latestRestorableAt`, `overallStatus`, `identityVerified`,
`identityVerifiedAt`, `pitrCheckedAt`, `stateLineage`, `stateSerial`,
`stateFingerprint`, `generatedAt`, `errorCode`, `limitations`.

- `VERIFIED` = Backup `AVAILABLE` + PITR `ENABLED` + gültiges Fenster.
- `PARTIAL` = Backup `AVAILABLE`, PITR `DISABLED`/`UNKNOWN`.
- `FAILED` = Backup `FAILED`/`TIMEOUT`/`UNKNOWN`.
- `UNVERIFIED` = Dry-Run.

`validate_evidence_binding` prüft Projekt, Environment, Account, Region,
Tabellen-ARN, State-Lineage, State-Serial und State-Fingerprint sowie Backup-ARN.
Es gibt **keine Signatur**; das ist in den Limitations ausdrücklich vermerkt.
Keine Order-Inhalte, keine PII, keine Roh-Fehlerantworten.

---

## 8. Sicherheitsgrenzen

- Keine Änderung an Lambda-/Worker-Rollen, keine IAM-Ressource, kein Terraform.
- `--execute` erst nach beiden Env-Gates und verifizierter State-Baseline; danach
  lazy `boto3`-Import + STS-Kontextvalidierung.
- Dry-Run hat keinen Client-Parameter und importiert boto3 nicht (Test mit
  explodierendem `boto3`-Modul).
- Tabellenname/ARN/Account/Region werden gegen den Deployment-Kontext geprüft;
  beliebige Tabellennamen werden abgelehnt.
- Keine PII/Secrets in Plan/Evidenz; Fehler werden klassifiziert, Rohantworten
  nicht persistiert.
- IAM-Empfehlung: separate Rolle, nur `DescribeTable`, `CreateBackup`,
  `DescribeBackup` (Backup-ARN), `DescribeContinuousBackups`; kein `dynamodb:*`,
  kein `Resource: "*"`, keine Schreibrechte auf Items.

---

## 9. Fake-Client-Tests

`installer/tests/test_order_backup.py`: **53 Tests**, kein boto3/AWS/Terraform.

Abgedeckt:

- Identität: Erfolg, fehlende/inkonsistente Erwartung, falscher Name/ARN/Account/
  Region, Tabelle fehlt, Tabelle nicht `ACTIVE`.
- Backup: `CREATING → AVAILABLE`, ARN-Prüfung, FAILED, UNKNOWN, Timeout,
  Create-/Describe-Fehler, AccessDenied, Namenskollision, fehlender ARN,
  widersprüchliche Backup-/Quelltabellen-Identität, eindeutige Default-Namen.
- PITR: `ENABLED` mit gültigem Fenster, `DISABLED`, fehlende Zeitpunkte,
  `earliest > latest`, `datetime`-Objekte, AccessDenied.
- State/Evidenz: fehlende/unverifizierte Baseline, manipulierte Evidenz
  (Projekt/Fingerprint), fehlender Backup-ARN, `VERIFIED` ohne `AVAILABLE`.
- Dry-Run/CLI: keine Identitäts-/PITR-Behauptung, keine Plan-Evidenz, kein
  boto3-Import, `--dry-run`+`--execute` exklusiv, `--orders` erforderlich,
  `--execute` ohne Gates blockiert.

---

## 10. Regression

| Lauf | Ergebnis |
|---|---|
| Neue P3A-Tests | **53 PASS** |
| Installer gesamt | **490 PASS** (437 + 53) |
| Builder | **128 PASS** |
| Lambda | **326 PASS** |
| `compileall installer` | OK |

Keine Terraform-Dateien geändert → kein `terraform fmt/validate`.
Kein AWS-Zugriff, kein Backup/Restore, keine Order-Datenänderung.

---

## 11. Git-Commits

| Commit | Inhalt |
|---|---|
| `1a4b30b` | Kern: Identität, Backup-Polling, PITR, Evidenz |
| `70ac646` | CLI `backup` mit Dry-Run und doppelter Ausführungssperre |
| `254ac2b` | Fake-Client-Tests (52) |
| `4fe5778` | PITR-Lesefehler erhält verifiziertes Backup (53 Tests) |
| *(dieser Commit)* | Lifecycle-Doku, Migrationsfahrplan, Bericht, Auditlog |

---

## 12. Bekannte Einschränkungen

1. Kein echter AWS-Backup-Aufruf; die `--execute`-Strecke ist implementiert, aber
   in P3A nicht gegen AWS verifiziert.
2. Kein Restore, keine Migration, kein Cutover.
3. PITR-Restore wurde nicht getestet; Wiederherstellbarkeit bleibt unbewiesen.
4. Keine Signatur der Evidenz (nur Kontextbindung).
5. Backup-Aufbewahrung/-Löschung und Erasure-Schutz vor Restore sind offen (P3E).
6. P1-Integration (`backupEvidence` im Readiness-/Manifest-Gate) ist nur geplant.
7. Environment ist im Tabellennamen nicht enthalten (nur Tag/Kontext); Bindung
   erfolgt über Projekt/ARN/Account/Region/State.

---

## 13. Empfehlungen für P3E/P3B

**P3E (vor produktivem Restore/Cutover):**

1. Erasure-Ledger entscheiden und implementieren (Hash-Item vs. externes Ledger).
2. Retention-Frist und kontrolliertes Löschverfahren für Backups festlegen.
3. Restore-Prüfung: Ledger gegen Restore-Tabelle, erneute Löschung/Anonymisierung
   **vor** Cutover.
4. Backup-Rolle separat provisionieren; keine Lambda-Rechte erweitern.

**P3B (Restore):**

1. Restore nur in `<table>-restore-<timestamp>`, Original nie überschreiben.
2. Nach Restore PITR, Tags, TTL (falls eingeführt), IAM auf neue ARN prüfen;
   App nie automatisch umschalten.
3. Restore-Evidenz an dieselbe Identität/State-Baseline binden.
4. Restore erst nach P3E-Freigabe; PITR-Zeitpunkt und Datenverlustrisiko
   dokumentieren.

---

## 14. Status

```text
P3A COMPLETE — BACKUP ORCHESTRATION LOCALLY VERIFIED
```

Lokal verifiziert (Fake-Clients, 53 Tests, Installer 490, Builder 128, Lambda 326);
**keine** AWS-Backup-Ausführung. **STOP — keine weiteren P3-Phasen ohne Freigabe.**
