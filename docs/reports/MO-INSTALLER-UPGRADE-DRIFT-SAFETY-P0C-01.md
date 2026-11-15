# MO-INSTALLER-UPGRADE-DRIFT-SAFETY-P0C-01

**State-Baseline, Drift-Erkennung und No-op-Sicherheit**

**Datum:** 2026-11-03
**Branch:** `feature/mo-installer-upgrade-drift-safety-p0c` (von P0B `da99f6f`)
**Basis:** `main` @ `f597d14` + P0A `209d0da` + P0B `d6b26ad` (+2 OpenCode-Chores)
**Modus:** lokale Implementierung + Tests; kein AWS, kein Terraform Apply/Destroy, kein Push/Merge

---

## 1. Ausgangsbasis

| Prüfung | Ergebnis |
|---|---|
| `main` | `f597d14` |
| P0A | `feature/mo-installer-upgrade-safety-p0a` @ `209d0da` |
| P0B | `feature/mo-installer-upgrade-versioning-p0b` @ `d6b26ad` |
| P0B tatsächlicher HEAD | `da99f6f` (2 OpenCode-Chores danach) |
| P0C-Branch | von `da99f6f` (P0A/P0B vollständig enthalten) |
| Working Tree vor Start | CLEAN |
| Auditlog/Reports gelesen | `docs/AI_AUDITLOG.md`, P0A-/P0B-Report, Migration-Plan |

---

## 2. Implementierte Komponenten

| Komponente | Datei | Zweck |
|---|---|---|
| State-Baseline | `installer/core/state_baseline.py` | Serial, Lineage, Ressourcenanzahl, SHA-256-Fingerprint aus `terraform state pull`; Status `VERIFIED`/`NO_STATE`/`MISSING_LINEAGE`/`MISSING_SERIAL`/`UNREADABLE`; Vergleich mit Manifest |
| Drift + No-op | `installer/core/drift.py` | `resource_drift` vs. `resource_changes`, Output-Änderungen, Plan-Vollständigkeit; `NO_DRIFT`/`DRIFT_DETECTED`/`DRIFT_UNKNOWN`, `NO_OP_VERIFIED`/`CHANGES_PLANNED`/`NO_OP_UNVERIFIED` |
| Drift-Bericht | `installer/core/drift.py` | `upgrade-drift-report.json` + `.md` (ohne State-Inhalte) |
| Manifest-Erweiterung | `installer/core/plan_manifest.py` | optionale Felder `state_baseline`, `drift_status`, `noop_status` (v2 bleibt kompatibel) |
| Plan-Integration | `installer/cli/main.py::_cmd_plan` | Baseline erfassen, Drift bewerten, Bericht schreiben, fail-closed bei `DRIFT_UNKNOWN`/Drift an geschützten Typen |
| Apply-Gate | `installer/cli/main.py::_cmd_deploy` | Baseline-Vergleich (Serial/Lineage/Fingerprint) vor P0A und Apply |
| Fehlerkennungen | — | `UPGRADE_STATE_BASELINE_MISMATCH`, `UPGRADE_STATE_BASELINE_MISSING`, `UPGRADE_STATE_UNREADABLE`, `UPGRADE_DRIFT_UNVERIFIED` |

---

## 3. Wiederverwendete Terraform-Funktionen

| Funktion | Nutzung |
|---|---|
| `terraform state pull` | Serial/Lineage/Ressourcenanzahl (nur Metadaten + Fingerprint) |
| `terraform show -json` | `resource_drift`, `resource_changes`, `output_changes`, `complete`/`errored` |
| Terraform-eigene Plan-/State-Bindung | bleibt aktiv; Installer erstellt **keinen** neuen Plan während Apply |
| P0A-Gate (`upgrade_safety`) | unverändert; blockt DELETE/REPLACE geschützter Typen |
| P0B-Bindung (`version_binding`) | unverändert; Manifest/Commit/Zielversion |

Keine eigene State-Verwaltung; keine State-Inhalte in Manifest/Berichten.

---

## 4. State-Baseline-Vertrag

Manifest v2 (kompatibel erweitert):

```json
"state_baseline": {
  "schemaVersion": 1,
  "status": "VERIFIED",
  "serial": 7,
  "lineage": "…",
  "resources": 58,
  "fingerprint": "<sha256>",
  "captured_at": "2026-11-03T…",
  "source": "terraform_state_pull",
  "reason": ""
}
```

Regeln:

- Fehlende Lineage/Serial ⇒ eigener Status (keine Erfindung).
- Unlesbarer State ⇒ `UPGRADE_STATE_UNREADABLE`, keine Neuinstallations-Annahme.
- Leerer State ⇒ `NO_STATE` **mit** Serial/Lineage (gültige Baseline).
- Fingerprint = SHA-256 des Roh-States; keine Werte, keine Secrets.

---

## 5. Drift-Klassifikation

| Status | Bedingung |
|---|---|
| `NO_DRIFT` | Refresh-Nachweis vorhanden, keine Drift-Aktionen; oder kein vorheriger State (dokumentiert) |
| `DRIFT_DETECTED` | `resource_drift` mit Aktionen außerhalb `no-op`/`read` |
| `DRIFT_UNKNOWN` | `resource_drift` fehlt/ungültig, unbekannte Aktion |

Bei `DRIFT_UNKNOWN` blockiert der Plan `UPGRADE_DRIFT_UNVERIFIED` (fail-closed).
Drift an geschützten Typen (DynamoDB/S3/Cognito/SQS) ⇒
`UPGRADE_BLOCKED_MIGRATION_REQUIRED`.

---

## 6. No-op-Klassifikation

| Status | Bedingung |
|---|---|
| `NO_OP_VERIFIED` | keine relevanten Resource-/Output-Änderungen **und** Drift geprüft/ohne Drift **und** Plan vollständig |
| `CHANGES_PLANNED` | geplante Ressourcen- **oder** Output-Änderungen |
| `NO_OP_UNVERIFIED` | unvollständiger Plan, unbekannte Aktion, fehlende Drift-Bewertung oder erkannte Drift |

Dokumentiert: Ein leerer `resource_changes`-Block allein ist kein No-op-Nachweis.

---

## 7. Manifest-Änderungen

- `manifest_version` bleibt **2** (additive optionale Felder; kein stiller Bruch).
- Neu: `state_baseline`, `drift_status`, `noop_status`.
- Ältere v2-Pläne ohne Baseline werden beim Deploy blockiert
  (`UPGRADE_STATE_BASELINE_MISSING`) und müssen neu geplant werden; Destroy
  bleibt möglich.

---

## 8. Plan-/Apply-Gates

```text
plan --remote
  → Source-Preflight (P0B) → terraform plan
  → P0A DELETE/REPLACE-Gate
  → installierte Version (P0B)
  → State-Baseline erfassen
  → Drift/No-op bewerten, upgrade-drift-report.{json,md} schreiben
  → DRIFT_UNKNOWN / geschützte Drift ⇒ Abbruch
  → Manifest v2 mit Baseline/Drift/No-op

deploy --plan
  → Manifest + Plan-Hash (E2B)
  → Versionsbindung (P0B)
  → State-Baseline (Serial/Lineage/Fingerprint)      ← P0C
  → P0A-Safety (DELETE/REPLACE)
  → Apply
```

**TOCTOU-Grenze:** Die Prüfung unmittelbar vor Apply verhindert keine Änderungen
danach; Terraform lehnt einen veralteten Plan zusätzlich selbst ab.

---

## 9. Testergebnisse

| Suite | Ergebnis |
|---|---|
| `installer/tests/test_drift_safety.py` (neu) | **30 PASS** |
| Installer gesamt (22 Module) | **377 PASS** |
| P0A-/P0B-Suiten | weiterhin PASS (enthalten) |
| Builder / Lambda | unverändert, nicht betroffen |
| Terraform fmt/validate | nicht erforderlich (keine `.tf`-Änderung) |

Abgedeckt: gültige Baseline; fehlende Lineage/Serial; unlesbarer State;
Serial-/Lineage-Mismatch; fehlende Baseline; Drift leer/fehlend/erkannt;
unbekannte Aktion; geplante GSI-Änderung; Output-Änderung; unvollständiger Plan;
No-op verifiziert/unverifiziert; Manifest-Roundtrip; Apply nicht gestartet bei
blockierender Baseline; Gate-Reihenfolge (Baseline vor Apply, Drift vor
Manifest).

---

## 10. Git-Commits

| Commit | Inhalt |
|---|---|
| `066697c` | `feat(installer)`: State-Baseline, Drift-/No-op-Bewertung, Manifest-Erweiterung, Plan-/Apply-Gates, 30 Tests |
| (folgt) | `docs(installer)`: Lifecycle-Doku, Migrationsfahrplan, Auditlog, dieser Report |

Kein Push, kein Merge.

---

## 11. Bekannte Einschränkungen

| ID | Einschränkung |
|---|---|
| L-01 | TOCTOU: Änderungen nach der Prüfung sind nicht ausgeschlossen |
| L-02 | Drift deckt nur Ressourcen ab, die Terraform beim Refresh liest |
| L-03 | Fingerprint erkennt State-Schreibvorgänge, keine semantische Integrität |
| L-04 | Keine automatische Datenintegritätsprüfung |
| L-05 | Ältere v2-Pläne ohne Baseline müssen neu geplant werden |
| L-06 | Kein `--upgrade`-Modus, kein Rollback/Resume |

---

## 12. Empfehlungen für P1

1. Automatisierte Inventur und Datenintegritätsprüfung (No-op + Stichproben).
2. `DevelopmentState.compare` verdrahten und Kompatibilitätsmatrix.
3. Vollständige Change-Klassifikation (`safe`/`review`/`critical`).
4. Upgrade-Abschlussreport/Attestation.
5. Optional: Builder-Upgrade-Modus.

---

## 13. Status

```text
P0C COMPLETE — DRIFT AND STATE BASELINE VERIFIED
```

Implementierung und Tests erfolgreich; P0A/P0B-Schutz unverändert aktiv.
Kein AWS-Zugriff, kein Apply/Destroy, kein Push. **STOP.**
