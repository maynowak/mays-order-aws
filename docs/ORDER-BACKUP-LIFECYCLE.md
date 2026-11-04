# Order-Backup-Lifecycle (P3A)

**Status:** lokal implementiert und mit Fake-Clients getestet (2026-11-03).
**Nicht Teil dieses Stands:** echter AWS-Aufruf, Restore, Migration, Cutover.

Die Komponente liegt in `installer/core/order_backup.py`, die CLI-Anbindung in
`installer/cli/main.py` (`backup`). Sie ist bewusst klein und ohne boto3-Abhängigkeit
im Kern; der DynamoDB-Client wird injiziert.

---

## 1. Tabellenidentität

Die Order-Tabelle wird aus dem Deployment-Kontext abgeleitet, **nicht** aus einem
frei übergebenen Tabellennamen:

| Feld | Quelle |
|---|---|
| Projekt | `--project-name` / `PROJECT_NAME` |
| Environment | `--environment` / `ENVIRONMENT` |
| AWS-Account | validierter AWS-Kontext (STS), nur bei `--execute` |
| Region | `--aws-region` / `AWS_REGION` |
| Tabellenname | **= Projektname** (Terraform: `name = var.project_name`) |
| Tabellen-ARN | `arn:aws:dynamodb:<region>:<account>:table/<project>` |
| Zeitpunkt | `identityVerifiedAt` in der Evidenz |

Vor jedem Backup wird `DescribeTable` aufgerufen und geprüft:

- Tabellenname, Tabellen-ARN, Account und Region müssen exakt passen.
- Die Tabelle muss `ACTIVE` sein.
- Eine unvollständige oder inkonsistente Erwartung blockiert.
- Abweichung → `ORDER_BACKUP_TABLE_IDENTITY_MISMATCH`.

Environment ist im aktuellen Terraform **nicht** Teil des Tabellennamens (nur Tag);
die Bindung erfolgt über Projekt/ARN/Account/Region und die State-Baseline. Das ist
keine Isolation durch den Namen — die Evidenz dokumentiert beides.

## 2. Ablauf

```text
Deployment-Kontext + verifizierte State-Baseline
        |
        v
DescribeTable (Identität, Status ACTIVE)
        |
        v
CreateBackup (eindeutiger Name, kein Überschreiben)
        |
        v
DescribeBackup pollen (Intervall/Timeout/max. Versuche)
        |
   +----+------------------+
   |                       |
   v                       v
AVAILABLE               FAILED / TIMEOUT / UNKNOWN
   |                       |
   v                       v
PITR prüfen             Evidenz FAILED (kein Erfolg)
   |
   +--> ENABLED + gültiges Fenster --> VERIFIED
   +--> DISABLED/UNKNOWN -----------> PARTIAL
```

**Regel:** Ein HTTP-Erfolg von `CreateBackup` ist kein Nachweis. Nur
`BackupStatus = AVAILABLE` zählt als verfügbares On-Demand-Backup.

### Statuswerte

| Status | Bedeutung |
|---|---|
| `REQUESTED` | angefordert (nur intern) |
| `CREATING` | Backup wird erstellt; weiter pollen |
| `AVAILABLE` | verfügbar und verifiziert |
| `FAILED` | Backup fehlgeschlagen |
| `TIMEOUT` | Timeout beim Polling |
| `UNKNOWN` | unerwarteter/unklarer Status |

### Polling

- Intervall, Timeout und maximale Versuche sind konfigurierbar.
- Keine unbegrenzte Schleife; `ResourceNotFoundException` direkt nach dem Anlegen
  wird bis zum Timeout als eventuelle Konsistenz behandelt.
- Zeit/Sleep sind injizierbar; Tests laufen ohne Warten.

### Backup-Name

```text
<project>-<environment>-orders-preupgrade-<UTC-Zeitstempel>[-<random>]
```

- Zeichen `[A-Za-z0-9_.-]`, Länge 3–255.
- Bei `--execute` wird ein kurzer Zufallssuffix ergänzt; vorhandene Backups werden
  nie überschrieben. Namenskollision → `ORDER_BACKUP_NAME_CONFLICT`.

## 3. PITR-Verifikation

`DescribeContinuousBackups` wird zur Laufzeit gelesen — die Terraform-Konfiguration
`point_in_time_recovery { enabled = true }` ist **kein** Nachweis.

| Status | Bedeutung |
|---|---|
| `ENABLED` | PITR aktiv, Zeitfenster gelesen |
| `DISABLED` | PITR nicht aktiv |
| `UNKNOWN` | Status oder Zeitfenster nicht belastbar |

Bei `ENABLED` werden `EarliestRestorableDateTime` und
`LatestRestorableDateTime` gespeichert. Fehlen sie, sind sie unparsbar oder ist
`earliest > latest`, gilt `UNKNOWN` + `ORDER_BACKUP_PITR_UNVERIFIED`; es werden
keine Zeitpunkte erfunden.

**Grenzen:** Das Fenster ist zeitlich begrenzt; ein Restore wurde nicht getestet;
PITR ersetzt keine DSGVO-Wiederherstellungsstrategie und kann gelöschte
personenbezogene Daten nach dem gewählten Zeitpunkt wieder enthalten.

## 4. Evidenzvertrag

Dateien im Run-Verzeichnis (`.mays-installer/runs/<run-id>/`):

- `order-backup-evidence.json` (Schema-Version 1)
- `order-backup-evidence.md`
- bei Dry-Run stattdessen `order-backup-plan.json` / `.md` (bewusst `UNVERIFIED`)

JSON-Felder (Auszug):

```json
{
  "schemaVersion": 1,
  "project": "<project>",
  "environment": "<environment>",
  "awsAccount": "<account>",
  "region": "<region>",
  "tableName": "<table>",
  "tableArn": "<arn>",
  "backupName": "<name>",
  "backupArn": "<arn>",
  "backupStatus": "AVAILABLE",
  "backupVerifiedAt": "<timestamp>",
  "pitrStatus": "ENABLED",
  "earliestRestorableAt": "<timestamp>",
  "latestRestorableAt": "<timestamp>",
  "overallStatus": "VERIFIED",
  "identityVerified": true,
  "identityVerifiedAt": "<timestamp>",
  "pitrCheckedAt": "<timestamp>",
  "stateLineage": "<lineage>",
  "stateSerial": 42,
  "stateFingerprint": "<sha256>",
  "generatedAt": "<timestamp>",
  "errorCode": null,
  "limitations": ["..."]
}
```

### Gesamtstatus

| Status | Bedingung |
|---|---|
| `VERIFIED` | Backup `AVAILABLE` **und** PITR `ENABLED` mit gültigem Fenster |
| `PARTIAL` | Backup `AVAILABLE`, PITR `DISABLED`/`UNKNOWN` |
| `FAILED` | Backup `FAILED`/`TIMEOUT`/`UNKNOWN` |
| `UNVERIFIED` | Dry-Run / keine Laufzeitprüfung |

Backup- und PITR-Status bleiben getrennt; ein fehlendes PITR-Fenster macht ein
verifiziertes Backup nicht „nicht vorhanden“, und PITR macht ein fehlgeschlagenes
Backup nicht erfolgreich.

### Bindung und Integrität

Die Evidenz wird gegen Projekt, Environment, Account, Region, Tabellen-ARN,
State-Lineage, State-Serial, State-Fingerprint und Fingerprint-Version geprüft.
Es gibt **keine kryptografische Signatur**; die Datei ist an den
Deployment-Kontext gebunden, nicht signiert. Es werden keine Order-Inhalte, PII,
Tokens oder Roh-Fehlerantworten gespeichert.

Seit `MO-RC4-P0C-DRIFT-FIX-01` gilt `stateFingerprintVersion =
canonical-sha256-v1`: Der Fingerprint wird über eine kanonische State-Repräsentation
(sortierte Ressourcen/Instanzen, sortierte `check_results`, sortierte JSON-Keys)
berechnet. Rohe `terraform state pull`-Bytes sind wegen nichtdeterministischer
`check_results`-Reihenfolge **kein** gültiger kanonischer Fingerprint.

Legacy-Evidenz ohne `stateFingerprintVersion` bleibt als historisches Dokument
erhalten, wird vom neuen Gate aber **fail-closed** abgelehnt. Für einen neuen
Upgrade-Plan ist eine neue, kanonisch gebundene Backup-Evidence erforderlich.

## 5. CLI

```bash
# Offline-Planung: kein AWS-Aufruf, keine Identitäts-/PITR-Behauptung
./Mays-Order-AWS-installer \
  --project-name mays-orders \
  --environment Development \
  backup --orders --dry-run

# Nur mit doppelter Freigabe (in P3A nicht ausgeführt):
#   ALLOW_AWS_OPERATIONS=true
#   MAYS_ORDER_BACKUP_ALLOW_EXECUTE=true
#   --state-baseline <verified-baseline.json>
./Mays-Order-AWS-installer \
  --project-name mays-orders \
  --environment Development \
  backup --orders --execute \
  --state-baseline .mays-installer/runs/<id>/state-baseline.json \
  --poll-interval 10 --timeout 900 --max-attempts 90
```

Globale Optionen (`--project-name`, `--environment`, `--aws-region`) stehen **vor**
dem Subcommand. Ohne `--dry-run`/`--execute` verhält sich `backup` wie Dry-Run.

### Ausführungssperre

`--execute` ist **dreifach** geschützt:

1. `MAYS_ORDER_BACKUP_ALLOW_EXECUTE=true`
2. `ALLOW_AWS_OPERATIONS=true`
3. verifizierte State-Baseline (`status = VERIFIED`, Lineage/Serial)

Erst danach wird `boto3` lazy importiert und der AWS-Kontext (STS) validiert. Im
Dry-Run wird `boto3` nie importiert; die Tests erzwingen das. Ohne alle Gates:
`ORDER_BACKUP_EXECUTION_BLOCKED`, Exit-Code 2, kein AWS-Aufruf.

## 6. IAM (Least Privilege)

Separate administrative Backup-Rolle; **keine** Änderung an Order-Lambda- oder
Worker-Rollen, kein `dynamodb:*`, kein `Resource: "*"`.

| Aktion | Ressource |
|---|---|
| `dynamodb:DescribeTable` | Tabellen-ARN |
| `dynamodb:CreateBackup` | Tabellen-ARN |
| `dynamodb:DescribeBackup` | `arn:aws:dynamodb:<region>:<account>:table/<table>/backup/*` |
| `dynamodb:DescribeContinuousBackups` | Tabellen-ARN |

Zusätzlich für den Deployment-Kontext: `sts:GetCallerIdentity` (bereits im
bestehenden Validierungspfad). Keine Schreibrechte auf Items, kein Restore.
Ressourcen-ARNs enthalten Platzhalter, keine echten Kontonummern.

## 7. DSGVO und Aufbewahrung

- Backups enthalten personenbezogene Daten (`customer`, pseudonyme IDs).
- Eine **Aufbewahrungsfrist** und ein kontrolliertes Löschverfahren sind noch nicht
  entschieden (P3E/O-04); ohne sie ist ein Backup kein DSGVO-Nachweis.
- Ein Restore darf Erasure-/Anonymisierungsentscheidungen nicht umgehen. Da es
  aktuell **kein Erasure-Ledger** gibt, muss P3E vor jedem produktiven
  Restore/Cutover gelöst werden.
- Evidenz enthält nur Metadaten, keine Order-Inhalte.

## 8. Fehlercodes

| Code | Bedeutung |
|---|---|
| `ORDER_BACKUP_TABLE_IDENTITY_MISMATCH` | Tabelle/ARN/Account/Region passt nicht |
| `ORDER_BACKUP_TABLE_NOT_FOUND` | Tabelle existiert nicht |
| `ORDER_BACKUP_TABLE_NOT_ACTIVE` | Tabelle nicht `ACTIVE` |
| `ORDER_BACKUP_ACCESS_DENIED` | fehlende IAM-Berechtigung |
| `ORDER_BACKUP_DESCRIBE_FAILED` | Describe-/Netzwerkfehler |
| `ORDER_BACKUP_CREATE_FAILED` | CreateBackup fehlgeschlagen |
| `ORDER_BACKUP_NAME_INVALID` | Name ungültig |
| `ORDER_BACKUP_NAME_CONFLICT` | Name bereits belegt |
| `ORDER_BACKUP_ARN_MISSING` | Backup-ARN fehlt |
| `ORDER_BACKUP_IDENTITY_MISMATCH` | Backup-/Quelltabellen-Identität widersprüchlich |
| `ORDER_BACKUP_TIMEOUT` | Polling-Timeout |
| `ORDER_BACKUP_FAILED` | Backup `FAILED`/`UNKNOWN` |
| `ORDER_BACKUP_PITR_UNVERIFIED` | PITR-Status/-Fenster nicht belastbar |
| `ORDER_BACKUP_STATE_BASELINE_REQUIRED` | State-Baseline fehlt/nicht verifiziert |
| `ORDER_BACKUP_EVIDENCE_MISMATCH` | Evidenz passt nicht zum Kontext |
| `ORDER_BACKUP_EXECUTION_BLOCKED` | Ausführungssperre |

## 9. Integration mit P1 (implementiert, lokal)

- `plan --remote --upgrade --backup-evidence <order-backup-evidence.json>`
  bindet die Evidenz in das Plan-Manifest: `backupRequired`, `backupEvidence`
  mit `fileName`, `sha256`, `status`, `backupArn`, `backupVerifiedAt`,
  `pitrStatus`, State-Lineage/Serial.
- `upgrade-readiness.json/.md` enthält `backupRequired` und `backupEvidence`;
  `MISSING`/`PARTIAL`/`FAILED`/`INVALID`/`STALE`/`IDENTITY_MISMATCH` blockieren
  den Readiness-Status mit `UPGRADE_BACKUP_EVIDENCE_*`.
- `deploy --plan` prüft die Evidenz erneut: Datei-Hash, Deployment-Identität,
  Tabellen-ARN, Account/Region, State-Lineage/Serial und `AVAILABLE`/`VERIFIED`.
  `backupRequired` wird zusätzlich aus `sourceVersion != targetVersion`
  berechnet; ein manipuliertes Manifest-Flag kann die Prüfung nicht umgehen.
- `--accept-upgrade-review` hebt **keine** Backup-/Migrations-/Privacy-Blockade auf.
- Es gibt weiterhin keinen zweiten Apply-Pfad; die Evidenz stammt aus dem
  separaten P3A-Backup-Schritt.

## 10. Grenzen

- Kein echter AWS-Aufruf in P3A; nur Fake-Client-Tests.
- Kein Restore, keine Migration, kein Cutover.
- PITR-Restore ist nicht getestet.
- Keine Signatur der Evidenz.
- Backup-Aufbewahrung/Löschung und PII-Restore-Schutz sind offen (P3E).
