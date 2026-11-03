# MO-RC4-READINESS-PRECHECK-01

**RC4-Readiness-Precheck (lokal, vor Release-Entscheidung)**

**Datum:** 2026-11-03
**Basis:** `feature/mo-order-erasure-ledger-p3e` @ `f7f61cd`
**Branch:** `feature/mo-order-ledger-persistence-p3e02`
**Charakter:** lokaler Precheck. **Kein AWS-Test, kein Deployment, kein Release.**
**Ergänzend:** `docs/reports/MO-ORDER-LEDGER-PERSISTENCE-P3E-02.md`
**Nachtrag:** `docs/reports/MO-RC4-UPGRADE-RELEASE-GATES-01.md` — lokale
Backup-/Matrix-Gates implementiert; RC4 bleibt `CONDITIONAL` ohne realen
AWS-Backup-/Upgrade-Nachweis. Die Zeile „Upgrade-Gates vollständig“ wurde auf
`VERIFIED (lokal)` aktualisiert.

---

## 1. Prüftabelle

| Prüffrage | Ergebnis | Beleg / Einschränkung |
|---|---|---|
| Bestehende Order-Tabelle geschützt? | **VERIFIED** | P0A blockt `aws_dynamodb_table`-DELETE/REPLACE (`installer/core/upgrade_safety.py:35-40`); Tests `test_upgrade_safety.py`; P1 klassifiziert CRITICAL. Schutz gilt für Terraform-Planaktionen, nicht für manuelle AWS-Eingriffe. |
| Upgrade ohne Datenmigration möglich? | **VERIFIED (design)** | RC4 ergänzt GSI3 additiv (`terraform/modules/dynamodb/main.tf:94-106`), keine Key-/Tabellenänderung; `LEGACY_UNKNOWN` blockiert. Ein konkreter AWS-Plan gegen einen bestehenden RC3-Stack wurde **nicht** ausgeführt. |
| Backup-Verfahren lokal getestet? | **VERIFIED** | P3A: 53 Fake-Client-Tests; `AVAILABLE`-only, Identitätsprüfung, PITR; keine AWS-Ausführung. |
| Echter AWS-Backup-Nachweis vorhanden? | **NO** | `backup --orders --execute` wurde nie gegen AWS ausgeführt; kein `order-backup-evidence.json` aus einem realen Lauf. |
| Erasure-Ledger für RC4 erforderlich? | **NO** | Scope-Gate `POST_RC4`: Ledger schützt nur Restore/Migration/Cutover; RC4 ist In-place-Upgrade ohne diese Schritte. |
| Restore-Automatisierung erforderlich? | **NO** | P3B nicht implementiert; Restore/Cutover bleiben durch P3E-01 blockiert (`CUTOVER_BLOCKED`). |
| Upgrade-Gates vollständig? | **VERIFIED (lokal)** | P0A/P0B/P0C/P1 implementiert; seit `MO-RC4-UPGRADE-RELEASE-GATES-01` sind P3A-Backup-Evidenz und Minor-Matrix `0.1.0→0.2.0` in Readiness/Manifest/Apply verdrahtet. Realer AWS-Upgrade-Plan weiterhin offen. |
| Lokale Regression erfolgreich? | **YES** | Installer **539 PASS**, Builder **128 PASS**, Lambda **326 PASS**. |
| **RC4-Releasefähigkeit** | **CONDITIONAL** | Lokal belastbar, aber ohne realen AWS-Upgrade-/Backup-Nachweis und mit offenen Gate-/Retention-Entscheidungen nicht `READY`. |

---

## 2. Einordnung der Prüfungen

### 2.1 Order-Tabelle

- P0A schützt vor `delete` und `create+delete` (Replace) der Tabelle.
- Eine **in-place** Änderung (GSI3 hinzufügen, Attribute/Projektionen ändern) wird nicht
  blockiert und ist für RC4 vorgesehen.
- Der Schutz ist planbasiert; manuelle AWS-Konsole/CLI-Eingriffe sind nicht abgedeckt.
- Ein RC4-Plan gegen einen bestehenden Stack muss weiterhin manuell auf
  `0 replace / 0 delete` geprüft werden; P0A blockiert nur die geschützten Typen.

### 2.2 Upgrade ohne Datenmigration

- RC4 fügt GSI3 (`gsi3pk`/`gsi3sk`, `KEYS_ONLY`) und neue Item-Felder hinzu; die
  Primärschlüssel `pk`/`sk` bleiben unverändert.
- GSI-Add ist ein Online-Update, kein Backfill. Bestehende Items werden vom Index
  erfasst, sobald die Attribute gesetzt sind.
- `LEGACY_UNKNOWN`-Installationen bleiben durch P1 blockiert; eine pauschale
  „upgradebar“-Aussage für alle Bestände ist nicht belegt.
- **Kein** AWS-Plan gegen einen bestehenden RC3-Stack in diesem Precheck.

### 2.3 Backup

- P3A ist lokal verifiziert: Identität, `CreateBackup`-Polling, `AVAILABLE`-only,
  PITR-Laufzeitprüfung, Evidenz.
- Es gibt **keinen** realen AWS-Backup-Nachweis. `--execute` ist doppelt gesperrt und
  wurde nicht aufgerufen.
- Ein lokaler Test ersetzt keinen Release-Nachweis.

### 2.4 Ledger / Restore

- Scope-Gate: `POST_RC4` (siehe P3E-02).
- Keine Ledger-Persistenz, keine neue Tabelle, kein Key-Management.
- Restore/Cutover bleiben gesperrt: P3E-01 trennt `PLAN_VERIFIED`,
  `EXECUTION_NOT_VERIFIED`, `CUTOVER_BLOCKED`.
- Es wird **nicht** behauptet, dass Löschungen restore-fest nachgewiesen sind.

### 2.5 Upgrade-Gates

Vorhanden:

- P0A: DELETE/REPLACE-Schutz.
- P0B: Versionsbindung/Legacy-Erkennung.
- P0C: State-Baseline/Drift/No-op.
- P1: Kompatibilität, SAFE/REVIEW/CRITICAL, Readiness, Review-Gate.
- P3A: lokale Backup-Orchestrierung (nicht integriert).
- P3E-01: Restore-Privacy-Gate (nicht in P1 verdrahtet).

**Nicht vollständig im strengen Release-Sinn:**

1. P3A-Backup ist kein Bestandteil des Readiness-/Apply-Gates.
2. Es gibt keine Minor-Kompatibilitätsmatrix (Minor = REVIEW).
3. `LEGACY_UNKNOWN` blockiert, ist aber nicht migrierbar.
4. Ein realer AWS-Upgrade-Plan/E2E für einen Bestandsstack fehlt.
5. P3E-01 ist bewusst nicht in P1 integriert; Restore bleibt gesperrt.

---

## 3. Release-Bedingungen (CONDITIONAL)

RC4 kann nur freigegeben werden, wenn **alle** Punkte belegt sind:

1. **AWS-Upgrade-Plan** gegen einen bestehenden RC3-Stack: `0 replace / 0 delete` auf
   `aws_dynamodb_table`, `aws_s3_bucket`, `aws_cognito_user_pool`, `aws_sqs_queue`;
   P0A/P0C/P1 PASS.
2. **Backup-Entscheidung:** reales P3A-Backup vor dem Upgrade **oder** dokumentierte,
   freigegebene Entscheidung, dass für diesen In-place-Upgrade kein Backup verlangt
   wird. Ein lokaler Test zählt nicht als AWS-Nachweis.
3. **Kein CRITICAL/MIGRATION_REQUIRED** im Upgrade-Plan; `--accept-upgrade-review`
   darf nur REVIEW freigeben.
4. **P3E-01-Sperre bleibt aktiv:** kein Restore, kein Cutover, keine Ledger-Behauptung.
5. **Retention R-01/R-02** bleiben offen; keine TTL, keine DSGVO-Konformitätsbehauptung.
6. **Merge-/Release-Entscheidung:** die gestapelten Feature-Branches (P0A–P3E) sind
   nicht automatisch in `main`; RC4-Release setzt eine kontrollierte Integration voraus.

---

## 4. Nicht behauptet

- Kein erfolgreicher AWS-E2E-Test nach dem aktuellen Branch-Stand.
- Kein reales DynamoDB-Backup.
- Kein Restore, keine Migration, kein Cutover.
- Keine DSGVO-Konformität, keine vollständige Löschung, keine Restore-Festigkeit.
- Kein `READY` — nur `CONDITIONAL`.

---

## 5. Empfehlung

1. RC4-Scope als **In-place-Upgrade ohne Ledger-Persistenz** bestätigen.
2. Einen realen AWS-Plan gegen einen RC3-Bestandsstack erzeugen und P0A/P0C/P1
   auswerten — ohne Apply.
3. Vor einem späteren Apply ein reales P3A-Backup durchführen oder die
   Backup-Ausnahme schriftlich freigeben.
4. Restore/Cutover bis P3E-02/P3B strikt gesperrt lassen.
5. Erst danach Release-Gate-Report und Dossier erstellen.

---

## 6. Status

```text
RC4 READINESS: CONDITIONAL
```

Lokal verifiziert, aber **nicht** release-fertig ohne AWS-Upgrade-/Backup-Nachweis und
formale Gate-/Retention-Entscheidungen. **Kein Release, kein Push, kein Merge.**
