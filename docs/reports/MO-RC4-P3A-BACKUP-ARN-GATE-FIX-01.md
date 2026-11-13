# MO-RC4-P3A-BACKUP-ARN-GATE-FIX-01

**Backup-ARN-Identitätsbindung im RC4-P3A-Gate**

**Datum:** 2026-11-11
**Branch:** `fix/mo-rc4-p3a-backup-arn-gate-fix-01` (ab `b9ac02a`)
**Modus:** lokale Implementierung/Tests; **keine AWS-Operation, kein Backup, kein
Terraform-Plan/Apply, kein State-Write, kein Push/Merge.**

---

## 1. Git-Ausgangslage

| Feld | Wert |
|---|---|
| Ausgangsbranch | `test/mo-rc4-p3a-evidence-rebind-01` |
| Ausgangs-HEAD | `b9ac02a` |
| Arbeitsbranch | `fix/mo-rc4-p3a-backup-arn-gate-fix-01` |
| Working Tree | CLEAN |
| P0C-/Fingerprint-Fix | `bd40a3d` |

---

## 2. Root Cause

Das bisherige Backup-Gate verlangte nur ein nichtleeres `backupArn`; es prüfte
weder die Zugehörigkeit zur Tabellen-ARN noch eine unabhängig gebundene
Backup-Identität. Eine Evidence mit einer fremden Backup-ARN wurde deshalb
`VERIFIED`.

Der forensische Negativtest aus `MO-RC4-P3A-EVIDENCE-REBIND-01` bestätigte
genau diesen Fehler.

---

## 3. Geänderte Dateien

| Datei | Änderung |
|---|---|
| `installer/core/backup_gate.py` | strukturelle ARN-Prüfung, erwartete ARN, evidenceKind |
| `installer/core/plan_manifest.py` | `backupExpectedArn` im Manifest |
| `installer/core/order_backup.py` | `evidenceKind` im Evidence-Vertrag |
| `installer/cli/main.py` | `--backup-arn`, Bindung im Plan/Apply-Gate |
| `installer/tests/test_rc4_release_gates.py` | ARN-/Kind-Negativtests |
| `installer/tests/test_drift_fix.py` | bestehende Revalidierungs-Evidence |
| `docs/ORDER-BACKUP-LIFECYCLE.md` | Vertragsdokumentation |

---

## 4. Tatsächliche Vertragsänderungen

1. `backupExpectedArn` ist ein neues Feld im Plan-Manifest.
2. `--backup-arn` ist für Upgrade-Pläne mit erforderlicher Backup-Evidence
   verbindlich.
3. `evidenceKind` ist Pflicht und akzeptiert:
   - `CREATED`
   - `EXISTING_BACKUP_REVALIDATION`
4. Das Gate prüft `backupArn` strukturell gegen die Tabellen-ARN und exakt
   gegen `backupExpectedArn`.

---

## 5. Vertrauenswürdige Backup-Identitätsquelle

Die erwartete Backup-ARN wird **unabhängig von der Evidence** als
`--backup-arn` übergeben und im Plan-Manifest `backupExpectedArn` gebunden.
Sie stammt damit aus dem Operator-/Plan-Kontext, nicht aus dem zu prüfenden
Evidence-JSON.

Zusätzlich wird die Evidence-ARN strukturell gegen die erwartete Tabellen-ARN
geprüft. Eine fremde Tabelle oder ein fremder Ressourcentyp kann nicht durch
eine korrekte Tabellen-ARN im Evidence-Feld kaschiert werden.

**Grenze:** Das Manifest ist nicht signiert; ein Angreifer mit Schreibzugriff
auf den Run-Bereich könnte beide Werte ändern. Das ist die bestehende
Manifest-Vertrauensgrenze und wird hier nicht als Signaturlösung ausgegeben.

---

## 6. ARN-Validierungsregeln

Akzeptiert wird nur:

```text
arn:<partition>:dynamodb:<region>:<account>:table/<table>/backup/<backup-id>
```

Geprüft werden:

- Partition `aws*`
- Service `dynamodb`
- Region
- Account
- Tabellenname
- Ressourcentyp `table/.../backup/...`
- nichtleere Backup-ID
- keine zusätzlichen `/`-Segmente
- exakte Übereinstimmung mit `backupExpectedArn`

Fehlende, malformed oder abweichende ARN → fail-closed.

---

## 7. Evidence-Kind-Regeln

- `evidenceKind` fehlt → **BLOCKED**
- unbekannter Wert → **BLOCKED**
- `CREATED` → akzeptiert
- `EXISTING_BACKUP_REVALIDATION` → akzeptiert
- Revalidierungs-Evidence bleibt ausdrücklich als solche erkennbar
- historische Evidence ohne Fingerprint-Version bleibt **BLOCKED**

Die neue Revalidierungs-Evidence aus `MO-RC4-P3A-EVIDENCE-REBIND-01` hat
`EXISTING_BACKUP_REVALIDATION` und bleibt unverändert.

---

## 8. Positive Tests

- korrekte Backup-ARN + Tabellenbindung → `VERIFIED`
- korrekte explizite Manifest-Bindung → `VERIFIED`
- bestehende Revalidierungs-Evidence (`4e2129ff…`) → `VERIFIED`
- `CREATED` und `EXISTING_BACKUP_REVALIDATION` akzeptiert
- Fingerprint/Version/Lineage/Serial korrekt

---

## 9. Negative Tests

| Fall | Ergebnis |
|---|---|
| fehlende Backup-ARN | **BLOCKED** |
| fehlerhafte ARN | **BLOCKED** |
| falsche Region | **BLOCKED** |
| falscher Account | **BLOCKED** |
| falsche Tabelle | **BLOCKED** |
| falscher Ressourcentyp | **BLOCKED** |
| fehlende Backup-ID | **BLOCKED** |
| andere Backup-ARN derselben Tabelle (explizite Bindung) | **BLOCKED** |
| manipulierte Evidence | **BLOCKED** |
| falscher Fingerprint | **BLOCKED** |
| falsche Fingerprint-Version | **BLOCKED** |
| ungültiger/fehlender evidenceKind | **BLOCKED** |
| Legacy-Evidence | **BLOCKED** |

Der ursprünglich fehlgeschlagene Fall „falsche Backup-ARN“ ist jetzt
ausdrücklich abgedeckt und blockiert.

---

## 10. Ergebnis der bestehenden Revalidierungs-Evidence

Die Evidence
`docs/reports/MO-RC4-P3A-EVIDENCE-REBIND-01/order-backup-evidence.json`
(SHA-256 `4e2129ffb3828a7a6555a7107bacc6874a4a6936d6432f13557474a8770fad94`)
besteht das korrigierte Gate mit erwarteter Backup-ARN:

```text
status = VERIFIED
```

Historische Evidence mit Raw-Fingerprint bleibt weiterhin **BLOCKED**.

---

## 11. Regressionsergebnisse

| Lauf | Ergebnis |
|---|---|
| Installer gesamt | **610 PASS** |
| Builder | **128 PASS** |
| Lambda | **326 PASS** |
| `terraform fmt -check` | PASS |
| `terraform validate` | PASS |
| `python3 -m compileall installer` | PASS |

Keine AWS-Mutation, kein Terraform-Plan/Apply.

---

## 12. Offene Punkte

1. Manifest/Evidence sind nicht signiert; die Identitätsbindung schützt gegen
   falsche Evidence, nicht gegen einen kompromittierten Run-Bereich.
2. Die erwartete Backup-ARN muss vom Operator korrekt übergeben werden.
3. Das Gate liest keine AWS-API; die AWS-Verifikation des Backups bleibt ein
   separater, dokumentierter Preflight.
4. Ein neuer RC4-Testplan muss die neue Evidence und `--backup-arn` verwenden.

---

## 13. Voraussetzungen für den RC4-Testplan

```bash
plan --remote --upgrade \
  --backup-evidence docs/reports/MO-RC4-P3A-EVIDENCE-REBIND-01/order-backup-evidence.json \
  --backup-arn arn:aws:dynamodb:eu-central-1:240571105849:table/mays-orders-rc4-test/backup/01793737895744-2f886092
```

Danach P0A/P0C/P1/P3A erneut prüfen und den neuen Plan-Hash separat freigeben.
Kein Apply in diesem Auftrag.

**Status:**

```text
RC4 P3A BACKUP ARN GATE FIX VERIFIED — NEW RC4 TEST PLAN REQUIRED
```

Keine AWS-Operation, kein Backup, kein Terraform-Plan/Apply, kein Push/Merge.
**STOP.**
