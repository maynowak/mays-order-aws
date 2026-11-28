# MO-GH-SEC-02 — CI Orchestration & CodeQL Configuration Remediation

**Status:** `CI ORCHESTRATION LOCALLY VERIFIED / GITHUB VERIFICATION PENDING`

**Datum:** 2026-11-28
**Branch:** `feature/mo-github-security-cleanup-01`
**Baseline:** `77a92cd` (MO-GH-SEC-04)
**Main-Basis:** `8830da2` (unverändert)
**Scope:** `.github/workflows/security.yml`, `.github/workflows/codeql.yml`,
`.github/workflows/dependency-check.yml`, Dokumentation.
**Doku-Checkpoint:** `git log -1` auf dem Feature-Branch.

## Ergebnis

`security.yml` ist jetzt der einzige Trigger- und Orchestrierungs-Workflow.
`codeql.yml` und `dependency-check.yml` sind reine
`workflow_call`-Reusable-Workflows. Damit gibt es pro Push-/PR-Event genau
einen CodeQL- und einen Dependency-Pfad statt der bisherigen Doppelausführung.

| Schritt | Commit | Inhalt |
|---|---|---|
| 1 | `bd5e48c` | Trigger-Konsolidierung, Reusable-only-Verträge, manuelle Scan-Auswahl, stabile Kategorien, `secrets: inherit` entfernt |
| 2 | `b2ef6be` | Concurrency, Timeouts, Least-Privilege-Permissions, Orchestrierungs-Gate statt echo-only-Freigabe |
| 3 | `b0011e4` | CodeQL-/SARIF-Vertrag, Kategorie-Migration, Alert-Schutz |
| 4 | Doku-Checkpoint | Vollständige lokale Regression, Report/Auditlog/PROJECT_STATUS/Wiki |

## Trigger-Matrix

`security.yml` behält die bisherigen Frequenzen bei:

| Ereignis | CodeQL | Dependency | Gate |
|---|---|---|---|
| Push auf `main` | ja | ja | beide müssen `success` sein |
| Pull Request auf `main` | ja | ja | beide müssen `success` sein |
| Schedule `0 3 * * 1` (Mo 03:00 UTC) | ja | nein | CodeQL muss `success` sein |
| Schedule `0 6 * * *` (täglich 06:00 UTC) | nein | ja | Dependency muss `success` sein |
| Dispatch `run_codeql=true`, `run_dependency=true` | ja | ja | beide |
| Dispatch `true`, `false` | ja | nein | CodeQL |
| Dispatch `false`, `true` | nein | ja | Dependency |
| Dispatch `false`, `false` | nein | nein | **FAIL** (keine Prüfung ausgewählt) |

Der Gate wertet `needs.<job>.result` aus. `failure`, `cancelled` und
`skipped` gelten für eine ausgewählte Prüfung **nicht** als Erfolg.
Nicht ausgewählte Prüfungen werden ignoriert; beide abgewählt ist ein Fehler.

## CodeQL-/SARIF-Vertrag

| Vertrag | Nachweis |
|---|---|
| Genau ein CodeQL-Analysepfad pro Event/Ref/Sprache | `security.yml` ruft `codeql.yml` genau einmal auf; `codeql.yml` hat genau einen `analyze`-Job mit einer Sprache (`python`) und einem `analyze`-Step |
| Stabile CodeQL-Kategorie | `category: "/language:${{ matrix.language }}"` → `/language:python` |
| Stabile Dependency-Kategorie | `upload-sarif` mit `category: dependency-check` |
| Konsistente SARIF-Automation-ID | `security/sarif_adapter.py`: `AUTOMATION_ID = "dependency-check"` |
| MO-GH-SEC-04-Fixes erhalten | `git diff 77a92cd..HEAD -- security/sarif_adapter.py security/dependency_detector.py` ist leer; relative URIs, stabile Rule-IDs/Fingerprints und `CURRENT`-Omission bleiben unverändert |
| Keine doppelten Uploads | Nur `dependency-check.yml` enthält `upload-sarif`; nur `codeql.yml` enthält `codeql-action/analyze` |
| Keine Pfad-Filter | Kein `paths:` in den Workflows; Security-Checks werden nicht durch Doku-Änderungen übersprungen |
| Kein Secret-Weiterreichen | Kein `secrets: inherit` mehr |

## Kategorie- und Check-Migration

Es werden **keine** Scan-Konfigurationen, Analysen oder Alerts gelöscht.

| Element | Vorher | Nachher |
|---|---|---|
| CodeQL-Kategorie | `/language:python` | `/language:python` (unverändert) |
| Dependency-Kategorie | `dependency-check` | `dependency-check` (unverändert) |
| CodeQL-Orchestrator-Check | `CodeQL Analysis / Analyze (python)` | bleibt |
| CodeQL-Standalone-Check | `Analyze (python)` | entfällt als neuer Check; alte Historie bleibt |
| Dependency-Orchestrator-Check | `Security & Dependency Analysis / Dependency Change Detection` | bleibt |
| Dependency-Standalone-Check | `Dependency Change Detection` | entfällt als neuer Check; alte Historie bleibt |
| Security Gate | `Security Gate` (echo-only) | `Security Gate (orchestration only)` mit ausdrücklichem Nicht-Freigabe-Hinweis |

Historische Analysen und Check-Runs bleiben in GitHub erhalten. Es gibt
keinen Alert-Dismissal und keine Löschung von Scan-Konfigurationen. Die
Alerts #296 (AWS) und #298 (time) bleiben offen, bis ein korrigierter Scan
sie automatisch auflöst; #296 kann durch den echten
`LOCK_CONSTRAINT_DRIFT`-Warning für AWS ersetzt werden.

## Security-Gate-Abgrenzung

Der bisherige Gate gab „All security checks passed - ready for deployment“ aus,
ohne Findings zu prüfen. Der neue Gate:

- prüft nur, ob die **ausgewählten** Scans erfolgreich abgeschlossen wurden;
- schlägt bei `failure`, `cancelled` oder `skipped` einer ausgewählten Prüfung
  fehl;
- schlägt fehl, wenn keine Prüfung ausgewählt wurde;
- gibt ausdrücklich `Findings evaluation is NOT implemented` und
  `This is not a security approval` aus;
- verweist auf MO-GH-SEC-03 für die vollständige Findings-Auswertung.

Der Gate ist damit ein **Orchestrierungs-Gate**, keine Security-Freigabe.

## Lokale Vertragsprüfung (Step 3)

Ausgeführt mit PyYAML 6.0.1 (nur lokal, keine neue Projekt-Dependency):

- YAML-Parsing aller drei Workflows: PASS
- Trigger-Matrix und `workflow_call`-Only-Vertrag: PASS
- Genau ein CodeQL-`analyze`-Step, eine Sprache, Kategorie
  `/language:python`: PASS
- Genau ein Dependency-`upload-sarif`, Kategorie `dependency-check`: PASS
- Kein `secrets: inherit`, kein `paths:`: PASS
- `bash -n` für alle `run`-Steps: PASS
- `jq`-Filter des Dependency-Reports mit Fixture: PASS
- Gate-Smoke-Tests: success→0, failed scan→1, skipped selected scan→1,
  selected-only manual run→0, no selection→1: PASS
- Detector-/SARIF-Regression: **33/33 OK**

## Vollständige lokale Verifikation (Step 4)

Alle Befehle wurden im Checkout auf
`feature/mo-github-security-cleanup-01` ausgeführt. Es wurden keine neuen
Dependency-Versionen installiert oder festgeschrieben.

| Prüfung | Ergebnis |
|---|---|
| `python3 -m unittest -q installer.tests.test_installer.TestDependencyDetector installer.tests.test_installer.TestSarifAdapter` | **33/33 OK** (0,124 s) |
| `python3 -m unittest installer.tests.test_installer` | **98/98 OK** (9,399 s) |
| `python3 -m unittest discover -s installer/tests` | **691 Tests OK, 2 skipped** (10,581 s) |
| Lambda `python3 -m compileall -q src tests` | **PASS** |
| Lambda `PYTHONPATH=src python3 -m unittest discover -s tests` | **456/456 OK** (0,523 s) |
| Lambda `python3 build_zip.py` | **PASS**, `dist/lambda.zip` 47.552 Bytes, SHA-256 `117299c97c775038fa2ccdedf3ecc2515a3d2c2e6a537bf9ede3fff1a5b425af` |
| `python3 -m unittest discover -s module_builder/tests` | **129/129 OK** (1,357 s) |
| `cd scripts && python3 -m unittest discover -s tests` | **28/28 OK** (0,181 s) |
| `python3 -m unittest tests.test_e2e_harness tests.test_privacy_e2e_harness` | **32/32 OK** (0,003 s) |
| Workflow-Vertrag (PyYAML, Trigger-Matrix, `workflow_call`, Kategorien, Permissions, Timeouts, `secrets`, `paths`) | **PASS** |
| `bash -n` für alle fünf `run`-Steps | **PASS** |
| Gate-Fälle: success, failed scan, skipped selected scan, selected-only, no selection | **5/5 PASS** |
| `git diff 77a92cd..HEAD -- security/sarif_adapter.py security/dependency_detector.py` | **leer** (MO-GH-SEC-04-Fixes unverändert) |

Die lokale E2E-Harness ist kein AWS-Live-Test. Es wurden **keine** Terraform-
Kommandos und **keine** AWS-Operationen ausgeführt.

## GitHub-Verifikationsplan (Step 5, vorbereitet)

Feature-Branch-Pushes triggern diesen Workflow nicht. Die Verifikation benötigt
einen freigegebenen PR-Lauf auf `main` oder einen manuellen Dispatch. Es wurde
**kein PR erstellt** und **kein Main-Merge** durchgeführt.

1. Nach Freigabe einen kontrollierten PR gegen `main` öffnen (nicht mergen).
2. Im PR genau einen Lauf von `Security & Dependency Analysis` prüfen.
3. Erwartete Check-Namen:
   - `CodeQL Analysis / Analyze (python)` (genau einmal),
   - `Security & Dependency Analysis / Dependency Change Detection`
     (genau einmal),
   - `Security Gate (orchestration only)`.
   Keine neuen Standalone-Checks `Analyze (python)` oder
   `Dependency Change Detection`.
4. CodeQL-Kategorie `/language:python` und Dependency-Kategorie
   `dependency-check` in den Analyse-/SARIF-Metadaten prüfen.
5. Alerts #296/#298 beobachten: Auto-Resolution durch den korrigierten Scan
   erwarten; für AWS kann stattdessen der echte `LOCK_CONSTRAINT_DRIFT`-Warning
   erscheinen. **Kein Dismissal.**
6. Prüfen, dass der Gate bei fehlgeschlagenen, abgebrochenen oder
   übersprungenen ausgewählten Scans rot wird und nur bei erfolgreicher
   Orchestrierung grün ist; der Warning-Text darf keine Findings-Freigabe
   behaupten.
7. Run-IDs, Check-Namen und Alert-Status im Report nachtragen.

## Grenzen und nicht geänderte Bereiche

- Kein PR, kein Main-Merge, keine Alert-Dismissals, keine Löschung von
  Scan-Konfigurationen oder Analysen.
- Keine Änderung an GitHub-Security-Settings, Branch Protection oder Rulesets.
- Keine Terraform-/AWS-Operation, keine Änderung am Order-Modul, keine
  Dependency-Versionen.
- Der Gate bleibt ein Orchestrierungs-Gate; die vollständige
  Findings-Auswertung ist **MO-GH-SEC-03**.
- GitHub-Scan-Verifikation und Alert-Auto-Resolution bleiben **PENDING**.
- Der AWS-Constraint-/Lock-Drift (`main.tf >= 6.0` vs. Lock `~> 6.0`) bleibt
  ein separater, freizugebender Reconcile-Task.

## Nächste Schritte

1. Feature-Branch pushen.
2. Nach Freigabe kontrollierten PR-Lauf durchführen und #296/#298/
   Doppelanalysen prüfen.
3. AWS-Constraint-/Lock-Drift in separatem Task reconciliieren.
4. MO-GH-SEC-03 (Findings-Gate) starten.
5. Kein Main-Merge ohne ausdrückliche Freigabe.

**Abschlussstatus:** `CI ORCHESTRATION LOCALLY VERIFIED / GITHUB VERIFICATION PENDING`
