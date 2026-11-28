# MO-GH-SEC-02 — CI Orchestration & CodeQL Configuration Remediation

**Status:** `CONTRACT VERIFIED / LOCAL VERIFICATION PENDING`

**Datum:** 2026-11-28
**Branch:** `feature/mo-github-security-cleanup-01`
**Baseline:** `77a92cd` (MO-GH-SEC-04)
**Main-Basis:** `8830da2` (unverändert)
**Scope:** `.github/workflows/security.yml`, `.github/workflows/codeql.yml`,
`.github/workflows/dependency-check.yml`, Dokumentation.

## Ergebnis

`security.yml` ist jetzt der einzige Trigger- und Orchestrierungs-Workflow.
`codeql.yml` und `dependency-check.yml` sind reine
`workflow_call`-Reusable-Workflows. Damit gibt es pro Push-/PR-Event genau
einen CodeQL- und einen Dependency-Pfad statt der bisherigen Doppelausführung.

| Schritt | Commit | Inhalt |
|---|---|---|
| 1 | `bd5e48c` | Trigger-Konsolidierung, Reusable-only-Verträge, manuelle Scan-Auswahl, stabile Kategorien, `secrets: inherit` entfernt |
| 2 | `b2ef6be` | Concurrency, Timeouts, Least-Privilege-Permissions, Orchestrierungs-Gate statt echo-only-Freigabe |
| 3 | dieser Report | CodeQL-/SARIF-Vertrag, Kategorie-Migration, Alert-Schutz |

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

Die vollständige lokale Regression und die GitHub-Verifikationsvorbereitung
folgen in Step 4/5.

## Nächste Schritte

1. Vollständige lokale Regression ausführen.
2. Report mit exakten Testergebnissen und Abschlussstatus aktualisieren.
3. Feature-Branch pushen; keinen PR ohne Freigabe erstellen.
4. Kontrollierten PR-Lauf vorbereiten und #296/#298/Doppelanalysen prüfen.

**Vorläufiger Status:** `CONTRACT VERIFIED / LOCAL VERIFICATION PENDING`
