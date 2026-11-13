# MO-RC4-P0C-DRIFT-FIX-01

**Behebung der P0C-Drift-False-Positives und deterministische Fingerprint-Bindung**

**Datum:** 2026-11-04
**Branch:** `fix/mo-rc4-p0c-drift-fix-01` (ab `5ca0da4`)
**Modus:** lokale Implementierung/Tests; **keine AWS-Operation, kein Terraform-Plan/Apply,
kein State-Write, kein Backup, kein Push/Merge.**

---

## 1. Git-Ausgangslage

| Feld | Wert |
|---|---|
| Ausgangsbranch | `test/mo-rc4-p0c-drift-forensic-01` |
| Ausgangs-HEAD | `5ca0da4` |
| Arbeitsbranch | `fix/mo-rc4-p0c-drift-fix-01` |
| RC4-Code-Pin | `2e09e72` |
| Working Tree | CLEAN |

---

## 2. Geänderte Dateien

| Datei | Änderung |
|---|---|
| `installer/core/state_fingerprint.py` | neu: kanonischer State-Fingerprint, Version `canonical-sha256-v1` |
| `installer/core/state_baseline.py` | nutzt kanonischen Fingerprint; Version im Baseline-Vertrag |
| `installer/core/drift.py` | gezielte Erkennung der belegten S3-/Cognito-Normalisierungen |
| `installer/core/change_classification.py` | benigne Drift wird SAFE, nicht CRITICAL |
| `installer/cli/main.py` | benigne geschützte Drift blockiert nicht; Fingerprint an Backup-Gate |
| `installer/core/backup_gate.py` | verbindlicher kanonischer Fingerprint + Version |
| `installer/core/order_backup.py` | `stateFingerprintVersion` im Identity-/Evidence-Vertrag |
| `installer/tests/test_drift_fix.py` | 22 neue Normalisierungs-/Fingerprint-/Gate-Tests |
| `installer/tests/test_order_backup.py` | Baseline um kanonische Version ergänzt |
| `installer/tests/test_rc4_release_gates.py` | Evidence/Gate-Tests an Version gebunden |
| `docs/ORDER-BACKUP-LIFECYCLE.md` | Fingerprint-Version und Legacy-Verhalten dokumentiert |

Keine Terraform-Konfiguration, keine AWS-Ressource, kein State geändert.

---

## 3. S3-Normalisierung

Neue Regel in `drift.py` (`_benign_drift_reason`):

Ein `aws_s3_bucket`-Drift gilt **nur** dann als benigne, wenn **alle** Bedingungen
erfüllt sind:

1. einziger geänderter Drift-Attributname ist `policy`,
2. der Bucket selbst ist `no-op`,
3. eine separate `aws_s3_bucket_policy`-Ressource im selben Modul ist `no-op`,
4. deren Policy ist kanonisch (JSON-sortiert) identisch mit dem Refresh-Wert,
5. keine weiteren Drift-Attribute.

Sonst: fail-closed (kein benign).

Damit wird die forensisch belegte Konstellation abgedeckt; echte
Policy-Änderungen, geänderte Policy-Ressourcen oder zusätzliche Bucket-Drift
bleiben kritisch.

---

## 4. Cognito-Normalisierung

Ein `aws_cognito_user_pool`-Drift gilt **nur** dann als benigne, wenn:

1. ausschließlich `auto_verified_attributes` und/oder `username_attributes`
   geändert sind,
2. der Pool im Plan `no-op` ist,
3. jeder geänderte Wert ausschließlich `null` ↔ `[]` ist.

Jede nicht-leere Änderung, zusätzliche Drift oder geplante Pool-Änderung bleibt
kritisch. Keine `ignore_changes`-Regel, keine Cognito-Mutation.

---

## 5. Fingerprint-Algorithmus

`installer/core/state_fingerprint.py`:

```text
FINGERPRINT_VERSION = "canonical-sha256-v1"
```

Kanonisierung:

- JSON-Objektschlüssel sortiert (`sort_keys`)
- `check_results` nach kanonischem JSON-Inhalt sortiert
- `resources` nach `(module, mode, type, name, kanonischer Inhalt)` sortiert
- `instances` je Ressource nach kanonischem Inhalt sortiert
- übrige semantisch geordnete Listen bleiben unverändert

SHA-256 über die kanonische JSON-Repräsentation.

Nachweis mit drei `terraform state pull`-Läufen aus der Forensik:

| Pull | Raw-Hash (alt) | Kanonischer Hash (neu) |
|---|---|---|
| 1 | `b6011034…` | `670bc917…` |
| 2 | `684907f5…` | `670bc917…` |
| 3 | `d44ccfa3…` | `670bc917…` |

Änderungen an Ressourcenattributen, Outputs, Lineage oder Serial ändern den
kanonischen Hash; fehlerhafte State-Daten werden fail-closed abgelehnt.

---

## 6. Fingerprint-Version

- Feld: `stateFingerprintVersion`
- Wert: `canonical-sha256-v1`
- P0C-Baseline: `fingerprintVersion` in `StateBaseline.to_dict()`
- P3A-Evidence: `stateFingerprintVersion` im JSON
- P0C/P3A verwenden dieselbe Versionskonstante; die Berechnung existiert nur
  einmal in `state_fingerprint.py`.

---

## 7. Backup-Gate-Verhalten

Das Gate verlangt jetzt zusätzlich:

- `stateFingerprint` vorhanden
- `stateFingerprintVersion == canonical-sha256-v1`
- kanonischer Fingerprint == erwarteter Fingerprint

Neue Fehlercodes:

- `UPGRADE_BACKUP_EVIDENCE_FINGERPRINT_MISSING`
- `UPGRADE_BACKUP_EVIDENCE_FINGERPRINT_VERSION_UNKNOWN`
- `UPGRADE_BACKUP_EVIDENCE_FINGERPRINT_MISMATCH`

Damit sind SHA, Identität, Tabellen-ARN, `AVAILABLE`, PITR, Lineage, Serial
**und** kanonischer Fingerprint verbindlich.

---

## 8. Legacy-Evidence

Die bestehende Evidence
`9475284f1ac165fed18722506508b360fc7d446c667b89bae5390fdba08a6ce1`
(Schema 1, Raw-Fingerprint `684907f5…`) bleibt **unverändert** als historisches
Dokument erhalten.

Das neue Gate lehnt sie fail-closed ab:

```text
status = INVALID
code   = UPGRADE_BACKUP_EVIDENCE_FINGERPRINT_VERSION_UNKNOWN
```

Sie wird **nicht** stillschweigend als kanonische Evidence interpretiert. Für
einen neuen Upgrade-Plan ist eine neue, kanonisch gebundene Backup-Evidence
erforderlich; in diesem Auftrag wurde kein Backup erzeugt und keine Evidence
überschrieben.

---

## 9. Positive Tests

- S3: separate Policy no-op, Bucket no-op, identische kanonische Policy →
  benigne, Classification SAFE.
- Cognito: `null → []` und `[] → null`, Pool no-op → benigne.
- Fingerprint: unterschiedliche `check_results`-/Resource-Reihenfolge und
  JSON-Key-Reihenfolge → identischer Hash.
- Backup-Gate: passender kanonischer Fingerprint/Version → `VERIFIED`.

---

## 10. Negative Sicherheitstests

- S3: Policy-Ressource geändert, Bucket geändert, abweichende Policy, zusätzliche
  Drift-Attribute → **nicht benigne**.
- Cognito: nicht-leere Werte, geplante Pool-Änderung, zusätzliche Drift →
  **nicht benigne**.
- Fingerprint: geändertes Ressourcenattribut, Output, Lineage oder Serial →
  anderer Hash; ungültiger State → Fehler.
- Backup-Gate: Fingerprint-Mismatch, fehlender Fingerprint, fehlende/unbekannte
  Version, manipulierte Evidence, falsche Identität/Status/PITR → **BLOCKED**.

---

## 11. Regressionsergebnisse

| Lauf | Ergebnis |
|---|---|
| Neue Drift-/Fingerprint-/Gate-Tests | **22 PASS** |
| Installer gesamt | **604 PASS** |
| Builder | **128 PASS** |
| Lambda | **326 PASS** |
| `terraform fmt -check` | PASS |
| `terraform validate` | PASS |
| `python3 -m compileall installer` | PASS |

Keine AWS-Mutationen durch Tests.

---

## 12. Offene Punkte

1. Der vorliegende Upgrade-Plan (`c266ed53…`) ist mit dem alten Readiness-Stand
   blockiert und **nicht apply-fähig**; er wird nicht nachträglich freigegeben.
2. Die alte Backup-Evidence ist absichtlich nicht mehr gate-fähig; ein neuer
   kanonisch gebundener Backup-Nachweis ist erforderlich.
3. Für einen neuen Plan müssen P0A/P0C/P1/P3A erneut vollständig durchlaufen.
4. Keine AWS-Änderungen, keine State-Manipulation, kein neues Backup.

---

## 13. Voraussetzungen für einen neuen RC4-Upgrade-Plan

1. Neuen P3A-Backup mit kanonischer State-Baseline erzeugen (separate Freigabe).
   Baseline-Felder: `status=VERIFIED`, `serial`, `lineage`, `resources`,
   `fingerprint` = `canonical_state_fingerprint(<terraform state pull>)`,
   `fingerprintVersion=canonical-sha256-v1`.
2. `stateFingerprintVersion=canonical-sha256-v1` und kanonischen Fingerprint in
   der Evidence binden.
3. Neuen RC4-Plan mit `--backup-evidence` erstellen; P0C/P1/P3A erneut prüfen.
4. Plan-Hash dokumentieren und separat freigeben.

**Status:**

```text
RC4 P0C DRIFT FIX VERIFIED — NEW UPGRADE PLAN REQUIRED
```

Kein AWS-Zugriff, kein Terraform-Plan/Apply, kein State-Write, kein Backup,
kein Push/Merge. **STOP.**
