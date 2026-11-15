# MO-RC4-P3A-EVIDENCE-REBIND-01

**Revalidierung des bestehenden RC3-Testbackups gegen `canonical-sha256-v1`**

**Datum:** 2026-11-04
**Branch:** `test/mo-rc4-p3a-evidence-rebind-01` (ab `bd40a3d`)
**Modus:** read-only AWS/State-Prüfung + neue Evidence; **kein Backup, kein
Restore, kein Plan/Apply, kein Push/Merge.**

```text
RC4 P3A EVIDENCE REBIND BLOCKED — CONTRACT DECISION REQUIRED
```

---

## 1. Git-Ausgangslage

| Feld | Wert |
|---|---|
| Ausgangsbranch | `fix/mo-rc4-p0c-drift-fix-01` |
| Ausgangs-HEAD | `bd40a3d` |
| Arbeitsbranch | `test/mo-rc4-p3a-evidence-rebind-01` |
| RC4-Code-Pin | `2e09e72` + Fix `3f789ef`/`bd40a3d` |
| Working Tree | CLEAN |

---

## 2. Tatsächliche Code-Version

- `installer/core/state_fingerprint.py`: `canonical-sha256-v1`
- `installer/core/order_backup.py`: `stateFingerprintVersion` im Evidence-Vertrag
- `installer/core/backup_gate.py`: Fingerprint + Version verbindlich
- Historische Evidence (Schema 1, Raw-Fingerprint) bleibt unverändert

---

## 3. AWS-Identität

| Feld | Wert |
|---|---|
| Profil | `mayaws` |
| Account | `240571105849` — VERIFIED |
| Region | `eu-central-1` |
| ARN | `arn:aws:iam::240571105849:user/Mayaws` |
| Zeitpunkt | `2026-11-04T16:28:56Z` |

Keine AWS-Mutation; ausschließlich Describe/Get/List und `terraform state pull`.

---

## 4. Bestehende Backup-ARN

```text
arn:aws:dynamodb:eu-central-1:240571105849:table/mays-orders-rc4-test/backup/01793737895744-2f886092
```

AWS `DescribeBackup` bestätigt:

| Feld | Wert |
|---|---|
| Backup-Name | `mays-orders-rc4-test-rc4-test-orders-preupgrade-20261103T203135Z-544920` |
| Status | **AVAILABLE** |
| Typ | `USER` |
| Größe | 0 Byte |
| Backup-Erstellung | `2026-11-03T20:31:35.744000+00:00` |
| Quelltabellen-ARN | `arn:aws:dynamodb:eu-central-1:240571105849:table/mays-orders-rc4-test` |
| Quelltabellen-Status | ACTIVE, 0 Items |

Es wurde **kein neues Backup** erstellt.

---

## 5. Backup-Status

`AVAILABLE` (AWS, erneut gelesen).

## 6. PITR-Status

`ENABLED`; aktuelles Fenster:

- EarliestRestorable: `2026-11-03T20:01:26+00:00`
- LatestRestorable: `2026-11-04T16:25:02.966000+00:00`

## 7. State-Lineage

`45f61e6a-a0a4-d9ce-1427-8c9a3fad6cad`

## 8. State-Serial

`4` (unverändert)

---

## 9. Kanonischer Fingerprint

Dreimaliger `terraform state pull` bei identischem logischem State
(46 State-Objekte, 37 managed) ergab jeweils:

```text
670bc917fe4671df2ecb7b317068160c8fc452e02e87aa7a63b3b63e864f2a4a
```

## 10. Fingerprint-Version

```text
canonical-sha256-v1
```

---

## 11. Historische Evidence

| Feld | Wert |
|---|---|
| Pfad | `/tmp/opencode/rc3-version-marker/.mays-installer/runs/20261103-213125/order-backup-evidence.json` |
| SHA-256 | `9475284f1ac165fed18722506508b360fc7d446c667b89bae5390fdba08a6ce1` |
| Status | historisch, **unverändert** |
| `stateFingerprint` | `684907f580df3c441d837827cddcf2a506538ea3d4b43e40e029e5002b2ced73` |
| `stateFingerprintVersion` | **fehlt** (Raw-Fingerprint) |
| Gate-Ergebnis | **INVALID** / `UPGRADE_BACKUP_EVIDENCE_FINGERPRINT_VERSION_UNKNOWN` |

Die historische Evidence wird nicht als kanonisch interpretiert.

---

## 12. Neue Evidence

| Feld | Wert |
|---|---|
| Pfad | `docs/reports/MO-RC4-P3A-EVIDENCE-REBIND-01/order-backup-evidence.json` |
| SHA-256 | `4e2129ffb3828a7a6555a7107bacc6874a4a6936d6432f13557474a8770fad94` |
| `evidenceKind` | `EXISTING_BACKUP_REVALIDATION` |
| `revalidatedAt` | `2026-11-04T16:30:16+00:00` |
| `backupVerifiedAt` | `2026-11-04T16:30:16+00:00` (Revalidierungszeit) |
| `originalBackupVerifiedAt` | `2026-11-03T20:31:35+00:00` |
| sourceEvidenceSha256 | `9475284f…` |
| `noNewBackupCreated` | `true` |

Die neue Datei ist ausdrücklich als Revalidierung gekennzeichnet und enthält
keine erfundenen Werte. Sie bindet:

- Account/Region, Tabellen-ARN
- Backup-ARN, `AVAILABLE`, Typ, Größe, Erstellungszeit
- PITR `ENABLED` und aktuelles Fenster
- State-Lineage `45f61e6a…`, Serial 4
- kanonischen Fingerprint `670bc917…`, Version `canonical-sha256-v1`
- Referenz und SHA der historischen Evidence

---

## 13. Ergebnis des Backup-Gates

Mit der neuen Evidence und dem erwarteten Kontext:

```text
status   = VERIFIED
code     = None
message  = Backup-Evidenz ist vollstaendig VERIFIED.
sha256   = 4e2129ffb3828a7a6555a7107bacc6874a4a6936d6432f13557474a8770fad94
```

Damit sind Fingerprint-Version, Fingerprint, SHA, Identität, Status und PITR
für die **Revalidierung** korrekt gebunden.

---

## 14. Negative Tests

| Mutation | Ergebnis |
|---|---|
| Falscher Fingerprint | **STALE** / `..._FINGERPRINT_MISMATCH` |
| Falsche Fingerprint-Version | **INVALID** / `..._FINGERPRINT_VERSION_UNKNOWN` |
| Manipulierte Evidence (SHA) | **INVALID** / `..._HASH_MISMATCH` |
| Falsche Tabellen-ARN | **IDENTITY_MISMATCH** |
| Falsche State-Lineage | **STALE** / `..._STATE_MISMATCH` |
| Falsche State-Serial | **STALE** / `..._STATE_MISMATCH` |
| Backup nicht `AVAILABLE` | **FAILED** / `..._NOT_VERIFIED` |
| PITR nicht `ENABLED` | **PARTIAL** / `..._NOT_VERIFIED` |
| **Falsche Backup-ARN** | **VERIFIED — nicht blockiert** |
| Legacy-Evidence ohne Version | **INVALID** / `..._FINGERPRINT_VERSION_UNKNOWN` |

### Regressionsbasis

| Lauf | Ergebnis |
|---|---|
| Installer gesamt (Fix-Stand) | **604 PASS** |
| Builder | **128 PASS** |
| Lambda | **326 PASS** |
| `terraform fmt -check` / `validate` | PASS |
| `compileall installer` | PASS |

### Vertragskonflikt

Das Backup-Gate prüft die **Backup-ARN nicht gegen die Tabellen-ARN**. Eine
Evidence mit einer fremden Backup-ARN, aber korrekter Tabellen-ARN/Status/PITR
wird akzeptiert. Das ist ein konkretes Sicherheitsdefizit und der Grund für den
Status `CONTRACT DECISION REQUIRED`.

Ebenso wird `evidenceKind=EXISTING_BACKUP_REVALIDATION` vom Gate nicht
ausgewertet; die Kennzeichnung ist im Dokument vorhanden, aber nicht
gate-erzwungen.

---

## 15. Offene Vertragsfragen

1. Soll das Gate `backupArn` strukturell gegen `tableArn` prüfen
   (`<tableArn>/backup/<id>`)?
2. Soll das Gate eine erwartete Backup-ARN (z. B. im Plan-Manifest) verbindlich
   vergleichen?
3. Soll `evidenceKind` ein Pflichtfeld mit Allowlist
   (`CREATED` / `EXISTING_BACKUP_REVALIDATION`) werden?
4. Soll `backupName`/`backupType`/`backupCreationDateTime` geprüft werden?

Eine minimale Vertragserweiterung wurde **nicht** implementiert, um den
bestehenden Gate-Vertrag nicht ungeprüft zu verändern.

---

## 16. Voraussetzungen für den neuen RC4-Testplan

1. Entscheidung über die Backup-ARN-Bindung (strukturell oder explizit).
2. Gate-Erweiterung mit Regressionstests, falls erforderlich.
3. Danach die neue Evidence (oder eine nach der Entscheidung neu gebundene
   Evidence) im Upgrade-Plan verwenden.
4. Neuen Plan mit `--backup-evidence` erstellen und P0A/P0C/P1/P3A erneut prüfen.
5. Separater Apply-Freigabe.

**Status:**

```text
RC4 P3A EVIDENCE REBIND BLOCKED — CONTRACT DECISION REQUIRED
```

Kein neues Backup, keine AWS-Mutation, kein Terraform-Plan/Apply, kein
State-Write, kein Push/Merge. **STOP.**
