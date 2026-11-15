# MO-RC4-UPGRADE-RELEASE-GATES-01

**RC4 Release Gates: P3A-Backup-Evidenz + RC3→RC4-Minor-Matrix (lokal)**

**Datum:** 2026-11-03
**Basis:** `feature/mo-order-ledger-persistence-p3e02` @ `974e29c`
**Arbeitsbranch:** `feature/mo-rc4-upgrade-release-gates`
**Charakter:** lokale Implementierung + Fake-Client-/Datei-Tests.
**Keine AWS-Operation, kein Terraform Apply, kein Push/Merge.**

---

## 1. Git-Ausgangsstand

| Prüfung | Ergebnis |
|---|---|
| Erwarteter Basis-HEAD | `974e29c` — vorhanden |
| Working Tree vor Beginn | CLEAN |
| Installer vorher | 539 PASS |
| Builder vorher | 128 PASS |
| Lambda vorher | 326 PASS |

---

## 2. Umsetzung

### 2.1 P3A-Backup-Evidenz im P1-Gate

Neu: `installer/core/backup_gate.py`.

Geprüft wird die echte P3A-Datei `order-backup-evidence.json`:

| Prüfung | Verhalten |
|---|---|
| Datei vorhanden | sonst `UPGRADE_BACKUP_EVIDENCE_MISSING` |
| JSON/Schema-Version 1 | sonst `..._INVALID` |
| Pflichtfelder | sonst `..._INVALID` |
| `backupStatus == AVAILABLE` | sonst `..._NOT_VERIFIED` |
| `overallStatus == VERIFIED` + `pitrStatus == ENABLED` | sonst `PARTIAL`/`FAILED` |
| Projekt/Environment/Account/Region/Tabelle/ARN | sonst `..._IDENTITY_MISMATCH` |
| State-Lineage/Serial | sonst `..._STATE_MISMATCH` (`STALE`) |
| SHA-256 gegen Manifest | sonst `..._HASH_MISMATCH` |
| `backupVerifiedAt` | gültiger Zeitpunkt erforderlich |

Es werden **keine** AWS-Aufrufe gemacht, keine Evidenz erfunden und keine
Order-Inhalte/PII gelesen.

### 2.2 Readiness

`upgrade-readiness.json/.md` enthält jetzt:

- `backupRequired`
- `backupEvidence` (Status, Code, Meldung, SHA-256, Backup-ARN, PITR, State)
- Status `BLOCKED` bei fehlender/nicht verifizierter Evidenz
- Abschnitt „16. Backup-Evidenz (P3A)“
- Nachweisgrenze: lokale Evidenzprüfung ersetzt keinen realen AWS-Backup-Test

### 2.3 Manifest

`PlanManifest` (v2, additiv) speichert:

- `backup_required` / `backupRequired`
- `backup_evidence` / `backupEvidence` mit `fileName`, `sha256`, `status`,
  `backupArn`, `backupVerifiedAt`, `pitrStatus`, `stateLineage`, `stateSerial`

Alte Manifeste ohne diese Felder bleiben lesbar (`None`).

### 2.4 Apply-Gate

`deploy --plan` prüft nach der State-Baseline und vor der Readiness:

- `backupRequired` **oder** `sourceVersion != targetVersion`
- Evidenzdatei neben dem Plan, Hash gegen Manifest
- Identität inkl. Tabellen-ARN/Account/Region
- State-Lineage/Serial
- `AVAILABLE` + `VERIFIED` + PITR `ENABLED`

Ein manipuliertes `backupRequired=false` im Manifest kann die Prüfung **nicht**
umgehen, weil `requires_backup(source, target)` erneut ausgewertet wird.
`--accept-upgrade-review` hebt keine Backup-Blockade auf.

### 2.5 CLI

```bash
./Mays-Order-AWS-installer \
  --project-name mays-orders-rc4 --environment development \
  --deployment-version 0.2.0 \
  plan --remote --upgrade --out .mays-installer/runs/<run>/plans \
  --backup-evidence /path/to/order-backup-evidence.json

./Mays-Order-AWS-installer deploy --plan <plan.tfplan>
```

Die Evidenz wird in das Plan-Verzeichnis kopiert und im Manifest gebunden; beim
Apply ist kein separater Evidenz-Pfad nötig.

---

## 3. RC3→RC4-Minor-Matrix

Neu: `installer/core/version_matrix.py`; `assess_compatibility` nutzt exakte
Matrix-Einträge vor der generischen Minor-REVIEW-Regel.

| Quelle → Ziel | Status | Evidenz | Bedingungen |
|---|---|---|---|
| `0.1.0` → `0.2.0` | **COMPATIBLE** | GSI3 additiv (`main.tf:94-106`), RC4-P02I-B2, P0B/P1-Versionsbindung, P0A-Schutz | Quelle VERIFIED; Plan 0 replace/0 delete geschützter Typen; P0A/P0C/P1 PASS; keine Migration; Backup-Evidenz separat |
| andere Minor-Paare | `REVIEW_REQUIRED` | keine Matrix | manuelle Prüfung |
| Major / Downgrade / Legacy | `MIGRATION_REQUIRED` / `INCOMPATIBLE` / `UNKNOWN` | unverändert | blockierend |

**Wichtige Grenze:** Release-Tags (`v0.5.0-rc.3`) und Deployment-Versionen
(`mo_version`, z. B. `0.1.0`) sind unterschiedliche Namensräume. Die Matrix
verwendet die tatsächlich vom Installer verglichenen Deployment-Versionen
(`0.1.0` → `0.2.0`, belegt in P0B/P1). Eine Abbildung der RC3/RC4-Release-Tags
auf diese SemVer-Werte muss der Betreiber bestätigen; ist `mo_version` anders,
greift die Matrix nicht und Minor bleibt REVIEW.

Die Matrix ersetzt **keine** P0A/P0C/P1-/Backup-/Privacy-Prüfung.

---

## 4. Sicherheitsgrenzen

- Keine AWS-Operation, kein Backup/Restore, kein Terraform Apply.
- P0A/P0B/P0C/P1 bleiben unverändert verbindlich.
- Kein zweiter Apply-Pfad; nur `deploy --plan`.
- Keine Änderung an Lambda, IAM, Terraform, RIS oder Order-Datenmodell.
- Keine PII in Manifest/Readiness; Evidenz enthält nur Metadaten.
- `PARTIAL` (PITR fehlt) blockiert den Upgrade, nicht nur `FAILED`.
- Alte Pläne mit Versionswechsel ohne Evidenz werden durch die Neuberechnung
  blockiert; alte Pläne ohne Versionswechsel bleiben unberührt.
- Kein `READY`/Cutover: Die Evidenz ist ein Gate, keine Ausführungsfreigabe.

---

## 5. Tests

Neu: `installer/tests/test_rc4_release_gates.py` — **42 Tests**.

Abgedeckt:

- Matrix: exaktes Paar, kein Wildcard/Bereich, unlisted Minor bleibt REVIEW,
  Legacy/Major bleiben blockierend, Matrix-Report/Grenzen.
- Backup: gültig, fehlend, partiell, FAILED, Schema/JSON/Pflichtfelder,
  Identitäts-/Account-/Region-/Environment-/ARN-Mismatch, State-Lineage/Serial,
  Hash-Manipulation, ungültiger Zeitpunkt.
- Manifest: Roundtrip, alte Manifeste ohne Felder, `fileName`/SHA-Bindung.
- Readiness: `MISSING`/`PARTIAL` blockieren, `VERIFIED` wird READY,
  `NOT_REQUIRED` blockiert nicht, Markdown-Abschnitt.
- Apply-Gate: gültig, fehlend, Datei fehlt, nicht erforderlich, Flag-Bypass
  wird verhindert.
- CLI: `--backup-evidence` wird geparst; Plan/Deploy-Wiring per Quellprüfung.

### Regression

| Lauf | Ergebnis |
|---|---|
| Neue Release-Gate-Tests | **42 PASS** |
| Installer gesamt | **582 PASS** |
| Builder | **128 PASS** |
| Lambda | **326 PASS** |
| `compileall installer` | OK |

Keine Terraform-Dateien geändert → kein `fmt/validate`.

---

## 6. Git-Commits

| Commit | Inhalt |
|---|---|
| `3308af6` | Backup-Gate, Readiness, Manifest, Apply-Wiring |
| `e0b8915` | RC3→RC4-Minor-Matrix + P1-Testanpassung |
| `ca6809f` | 42 lokale Release-Gate-Tests |
| *(dieser Commit)* | Bericht, Precheck-Nachtrag, Roadmap, Auditlog |

---

## 7. Bekannte Einschränkungen

1. Kein realer AWS-Backup-Nachweis; `order-backup-evidence.json` muss aus einem
   freigegebenen P3A-`--execute`-Lauf stammen. Lokale Tests erzeugen nur
   synthetische Evidenz.
2. Kein AWS-Upgrade-Plan/E2E gegen einen bestehenden RC3-Stack.
3. Matrix nur exakt `0.1.0 → 0.2.0`; Release-Tag-Mapping ist offen (Q-12).
4. Evidenz/Manifest sind per SHA-256 gebunden, aber **nicht signiert**.
5. Kein Restore, keine Migration, kein Cutover; P3E-01-Sperre bleibt.
6. Die State-Bindung verlangt, dass Backup und Plan denselben State-Serial
   haben; nach einem zwischenzeitlichen Apply ist ein neues Backup nötig.
7. `PARTIAL` blockiert; PITR muss im realen Backup `ENABLED` sein.

---

## 8. RC4-Bewertung

| Prüffrage | Ergebnis |
|---|---|
| Bestehende Order-Tabelle geschützt? | VERIFIED (P0A) |
| Upgrade ohne Datenmigration möglich? | VERIFIED (design; Matrix exakt 0.1.0→0.2.0) |
| Backup-Verfahren lokal getestet? | VERIFIED |
| Echter AWS-Backup-Nachweis? | **NO** |
| Erasure-Ledger für RC4 erforderlich? | NO (`POST_RC4`) |
| Restore-Automatisierung erforderlich? | NO |
| Upgrade-Gates vollständig? | **VERIFIED (lokal)** — Backup-Gate + Matrix implementiert |
| Lokale Regression erfolgreich? | YES |
| RC4-Releasefähigkeit | **CONDITIONAL** |

`READY` wird nicht vergeben: realer AWS-Backup-/Upgrade-Nachweis und die
Release-Tag-/Merge-Entscheidung fehlen weiterhin.

---

## 9. Status

```text
RC4 RELEASE GATES COMPLETE — LOCAL SAFETY VERIFIED
```

Kein AWS-Backup, kein Apply, kein Restore, kein Push. **STOP.**
