# MO-INSTALLER-UPGRADE-ORCHESTRATION-P1-01

**Expliziter Upgrade-Lifecycle, Kompatibilität, Klassifikation, Readiness**

**Datum:** 2026-11-03
**Branch:** `feature/mo-installer-upgrade-orchestration-p1` (von P0C `db73e17`)
**Basis:** `main` @ `f597d14` + P0A/P0B/P0C
**Modus:** lokale Implementierung + Tests; kein AWS, kein Apply/Destroy, kein Push/Merge

---

## 1. Ausgangsstand und Branch

| Prüfung | Ergebnis |
|---|---|
| `main` | `f597d14` |
| P0C | `feature/mo-installer-upgrade-drift-safety-p0c` @ `db73e17` |
| P1-Branch | `feature/mo-installer-upgrade-orchestration-p1` (von `db73e17`) |
| Working Tree vor Start | CLEAN |
| Regression vor P1 | 377 Installer-Tests PASS |
| Auditlog/Reports/Migrationsplan | gelesen und berücksichtigt |

---

## 2. Implementierte Funktionen

| Abschnitt | Komponente | Datei |
|---|---|---|
| P1A | Upgrade-Modus + Quellvoraussetzungen | `installer/core/upgrade_mode.py`, `installer/cli/main.py` |
| P1B | Versionskompatibilität | `installer/core/compatibility.py` |
| P1C | Change-Klassifikation | `installer/core/change_classification.py` |
| P1D | Readiness-Bericht + Apply-Gate | `installer/core/upgrade_readiness.py`, `installer/core/plan_manifest.py`, `installer/cli/main.py` |

Kein zweiter Apply-Mechanismus: `deploy --plan` bleibt der einzige Pfad.

---

## 3. Tatsächliche CLI-Syntax

```bash
./Mays-Order-AWS-installer \
  --project-name mays-orders-rc4 --environment development \
  --deployment-version 0.2.0 \
  plan --remote --upgrade --out .mays-installer/runs/<run>/plans
```

- `--upgrade` ist eine Option des `plan`-Subcommands (nicht global).
- Ohne `--remote`: `UPGRADE_REQUIRES_REMOTE`.
- Ohne bestehende Installation: `UPGRADE_SOURCE_INSTALLATION_MISSING`.
- Apply: `deploy --plan <artefakt>`; bei `REVIEW_REQUIRED`
  zusätzlich `--accept-upgrade-review` (global).

---

## 4. Versionsvergleich

Basis: `SemanticVersion.parse`; Regeln:

| Quelle → Ziel | Status |
|---|---|
| gleich | COMPATIBLE |
| Patch | COMPATIBLE |
| Minor (ohne Evidenz) | REVIEW_REQUIRED |
| Minor (`known_compatible=True`) | COMPATIBLE |
| Major | MIGRATION_REQUIRED |
| Downgrade | INCOMPATIBLE |
| Legacy/unbekannt | UNKNOWN |
| ungültig | UNKNOWN |

`MIGRATION_REQUIRED`, `INCOMPATIBLE`, `UNKNOWN` blockieren den Plan.
`COMPATIBLE` ersetzt keine P0A/P0B/P0C-Prüfung.

---

## 5. Change-Klassifikation

- **SAFE:** neue unkritische Ressourcen, verifizierter No-op.
- **REVIEW:** Updates, neue öffentliche/sicherheitsrelevante Ressourcen
  (API/Cognito/IAM/CloudTrail/SNS), DELETE/REPLACE nicht geschützter Typen,
  nicht-kritische Drift, `REVIEW_REQUIRED`-Kompatibilität.
- **CRITICAL:** P0A-Findings, Drift geschützter Typen, unbekannte Aktionen,
  `DRIFT_UNKNOWN`, `NO_OP_UNVERIFIED`, blockierende Kompatibilität.
- Gesamtbewertung = Maximum; Begründung je Eintrag.

P0A-Typenliste wird nicht dupliziert (Safety-Findings werden übernommen).

---

## 6. Readiness-Berichte

`upgrade-readiness.json` + `.md` im Run-Verzeichnis mit allen 15 geforderten
Punkten (Projekt/Environment, AWS, Backend/Workspace, Lineage/Serial,
Ausgangs-/Zielversion, Commit, Kompatibilität, Drift, No-op, geplante Änderungen,
SAFE/REVIEW/CRITICAL, migrationspflichtig, blockierende Gründe, nächste Schritte).

Gesamtstatus:

| Status | Bedingung |
|---|---|
| BLOCKED | blockierende Gründe oder CRITICAL |
| REVIEW_REQUIRED | Kompatibilität/Classification REVIEW |
| NO_CHANGES | verifizierter No-op ohne Änderungen |
| READY | alle Prüfungen bestanden (keine Ausführungsfreigabe) |

**Bindung:** Die Readiness-Datei ist **keine** Freigabe. Der Apply-Pfad liest sie
nicht; er prüft Manifest, Plan-Hash, Versionsbindung, State-Baseline,
Kompatibilität (neu berechnet) und P0A erneut.

---

## 7. Integration mit P0A/P0B/P0C

| Gate | Verhalten |
|---|---|
| P0A | blockt DELETE/REPLACE geschützter Typen; Findings fließen in Classification/Readiness |
| P0B | Manifest/Commit/Zielversion/Dirty/Quelle unverändert verbindlich |
| P0C | Baseline, Drift, No-op unverändert; `DRIFT_UNKNOWN` blockt |
| P1 | ergänzt Kompatibilität, Classification, Readiness; kein Gate wird abgeschwächt |

Reihenfolge im Plan: P0A/P0B → Baseline → Drift/No-op → Classification →
Readiness → (bei Blockade Abbruch **vor** Manifest).
Reihenfolge im Apply: Manifest → Version → Baseline → Readiness/Kompatibilität →
P0A → Apply.

---

## 8. Testergebnisse

| Suite | Ergebnis |
|---|---|
| `installer/tests/test_upgrade_orchestration.py` (neu) | **45 PASS** |
| Installer gesamt (23 Module) | **422 PASS** |
| P0A-/P0B-/P0C-Suiten | weiterhin PASS |
| Builder / Lambda | unverändert, nicht betroffen |
| Terraform fmt/validate | nicht erforderlich (keine `.tf`-Änderung) |

Abgedeckt: Upgrade-Modus/Voraussetzungen; alle Kompatibilitätskonstellationen;
SAFE/REVIEW/CRITICAL; Readiness-Status/Bericht; Review-Gate; Migrations-Blockade;
**kein Apply bei BLOCKED** (Mock-Assertion).

---

## 9. Git-Commits

| Commit | Inhalt |
|---|---|
| `981a317` | P1A: `--upgrade`, Quellvoraussetzungen |
| `43a94b6` | P1B: Versionskompatibilität |
| `23332df` | P1C: Change-Klassifikation |
| `462518f` | P1D: Readiness-Bericht + Apply-Gate |
| (folgt) | P1E: Doku, Migrationsplan, Auditlog, Report |

Kein Push, kein Merge.

---

## 10. Bekannte Einschränkungen

| ID | Einschränkung |
|---|---|
| L-01 | Keine Kompatibilitätsmatrix/Evidenz: Minor-Upgrades sind REVIEW_REQUIRED |
| L-02 | Legacy-Installationen (`LEGACY_UNKNOWN`) blockieren als UNKNOWN (kein Legacy-Übernahmeverfahren) |
| L-03 | Keine Datenmigration, kein Rollback/Resume |
| L-04 | Readiness-Datei nicht signiert; Apply-Gates sind maßgeblich |
| L-05 | SemVer-Differenz bleibt kein technischer Kompatibilitätsnachweis |
| L-06 | TOCTOU-Grenze aus P0C bleibt |

---

## 11. Empfehlungen für P2

1. Kompatibilitätsmatrix/Evidenz (z. B. versionsspezifische Migrationshinweise),
   damit Minor-Upgrades belastbar COMPATIBLE werden können.
2. Kontrollierte Legacy-Übernahme (`LEGACY_UNKNOWN` → verifizierte Baseline).
3. Feinere Change-Klassifikation (IAM-Diff, Datenmodell, öffentliche Routen).
4. Upgrade-Abschlussreport/Changelog + Attestation.
5. Datenintegritäts-/No-op-Verifikation nach Apply.

---

## 12. Status

```text
P1 COMPLETE — UPGRADE ORCHESTRATION VERIFIED
```

Implementierung und Tests erfolgreich; P0A/P0B/P0C unverändert aktiv.
Kein AWS-Zugriff, kein Apply/Destroy, kein Push. **STOP.**
