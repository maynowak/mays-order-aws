# MAYS-ORDERS-MODULE-BUILDER-CLI-CLEANUP-01

- **Current Status:** COMPLETE — veraltete CLI-Option entfernt, alle Regressionen GREEN, Git CLEAN.
- **Date/Time:** 2026-10-19 (UTC-Kontext)
- **Git Branch + HEAD:** main; Baseline `451f14d` (EXTERNAL-COGNITO) → Implementierungs-Commit (dieser Report folgt im Doku-Commit)
- **Scope:** Bereinigung der toten Option `--no-policy-check`; Dokumentation „B3 minimal: FUNCTIONALLY COVERED / NO SEPARATE PRESET". Keine Funktionsänderung an Builder, Installer-Gates, Stamm-Orders-Service.

## Completed Sections

1. WP1 Bestandsaufnahme (repo-weit, Installer, module_builder, Tests, Doku, CI, RIS-Aufrufer)
2. WP2 Entscheidung (Entfernung — nachweislich funktionslos, aufruferfrei)
3. WP3 Sicherheit (Policy-Gate unverändert; keine Abschwächung)
4. WP4 Regression (Builder/Installer/Lambda + Live-Smoke Modul & Wrapper)
5. WP5 Dokumentation (Report, AI_AUDITLOG, B3-Entscheidung)

## Actual Findings (WP1)

1. **Wo existiert `--no-policy-check`?** Ausschließlich im INSTALLER-CLI: `installer/cli/main.py` (plan-Subparser, `store_true`, „Skip policy gate check"). **KEIN Vorkommen in `module_builder/`** — der Module Builder besaß das Flag nie (seine CLI: build/presets mit --target/--project-name/--preset/--source/--force/--validate/--modules/--with-deps).
2. **Wirkung?** **Keine.** `parsed.no_policy_check` wird an keiner Stelle gelesen (grep über installer/: kein Konsum). Der Policy-Gate-Aufruf in `_cmd_deploy` (validate-plan.py, Z. 759–788) läuft bedingungslos; FAIL blockiert vor dem Approval. Bestätigt den Research-B-Befund (HARDENING-01): „totes Flag".
3. **Noch verwendet?** Nein — keine Tests, Skripte, CI-Jobs oder Dokumentation referenzieren es (repo-weiter grep: nur die Definition + historische Evidence-Nennung im HARDENING-01-Report, die den Tot-Befund dokumentiert und bewusst nicht rückwirkend umgeschrieben wird).
4. **Aufrufer?** Keine. RIS-Prüfung (read-only): einziger Treffer ist `installer/projects/mays_orders/installer/cli/main.py:166` — der **eingefrorene gepinnte MO-Clone** mit derselben toten Definition; **keine** RIS-Invocation übergibt das Flag (kein Treffer in deren Aufruf-Code).
5. **Rückwärtskompatibel?** Ja: Ein nicht funktionsfähiges Flag zu entfernen kann kein Verhalten brechen; theoretisch brechen nur Aufrufer, die es übergeben — solche existieren nachweislich nicht. Der gepinnte RIS-Clone behält seine eigene Kopie (eingefrorener Stand) und ist von unserem Repo-Change unberührt.

## WP2 — Entscheidung

**Entfernt** (Fall „nachweislich funktionslos und ohne relevante Aufrufer" vollständig erfüllt):
- `installer/cli/main.py`: Flag-Definition (4 Zeilen) entfernt; ersetzt durch erklärenden Kommentar (absichtlich KEIN Skip-Flag; Verweis auf diesen Checkpoint). Tests: keine Referenzen → keine Anpassung nötig. Doku: keine Erwähnung in INSTALLER_GUIDE/TERRAFORM_POLICY_GATE → nichts zu bereinigen.

## WP3 — Sicherheit

- Policy-Gate-**Aufruf** in `_cmd_deploy` unverändert (grep: `validate-plan.py` genau 1×, Deploy-Gate bedingungslos).
- Keine Abschwächung: das Flag hatte nie Wirkung; die Entfernung beseitigt eine **Irreführung** („Skip policy gate check" suggerierte Umgehbarkeit, die es nicht gab).
- Resource-Allowlist, Plan-Verifikation, Exit-Codes: unangetastet.

## WP4 — Checks Actually Executed (alle real)

| Prüfung | Ergebnis |
|---|---|
| `python3 -m compileall -q installer` | OK |
| `plan --help` enthält `--no-policy-check` | 0 Treffer (entfernt ✓) |
| Policy-Gate-Aufruf vorhanden | ✓ (1×, bedingungslos) |
| Builder-Suite (B1 --modules, B2 --with-deps, complete, orders-service, MANAGED, EXTERNAL) | **87/87 PASS** |
| Installer-Regression (inkl. Collision/Guide/Artifact/Parallel/Discovery/Runner + Policy-Gate-Positiv-/Negativtests über generierte Projekte) | **129/129 PASS** |
| Lambda-Regression | **76/76 PASS** |
| Live: `--preset orders-service … --validate` | fmt/init/validate **PASS** |
| Live: Wrapper-Integration (EXTERNAL Cognito) | validate **PASS** |

## Classification

**GREEN** — Aufräumziel erreicht; null Funktions- und null Verhaltensänderung; alle bisherigen Nutzungswege (B1/B2/complete/orders-service/MANAGED/EXTERNAL, Wrapper, Installer-Deploy-Gate) nachweislich unverändert funktionsfähig.

## Git Status / Files Changed

- Geändert: `installer/cli/main.py` (Flag-Entfernung + Kommentar).
- Doku: dieser Report + `docs/AI_AUDITLOG.md`.
- **Keine** Änderungen an: module_builder/, Terraform (Stamm + Module), Worker, Cognito, Lambda, RIS, States.

## Open Questions

Keine aus diesem Checkpoint. (Bestehende OPEN-Items bleiben unverändert: Queue-Policy-Härtung, Boundary-IaC, EXTERNAL-Cognito-Optional-Felder, MANAGED→EXTERNAL-Migration, RIS-Backend-Hygiene.)

## Risks

Kein Restrisiko. Theoretischer Einzelfall eines fremden Aufrufers, der das tote Flag übergab, würde jetzt einen argparse-Fehler erhalten — nachweislich existiert ein solcher Aufrufer nicht; die Fehlermeldung wäre zudem klarer als das vorherige Schein-Verhalten.

## B3 minimal — Funktionale Abdeckungserklärung

**FUNCTIONALLY COVERED / NO SEPARATE PRESET.** Der in Foundation/Plan-B aufgeführte Kandidat „Preset `minimal`" wird **nicht** als eigenes Preset gebaut, da vollständig abgedeckt durch:
1. `--modules` + `--with-deps` — jede Minimalkombination (z. B. `--modules dynamodb,iam,lambda --with-deps`) mit transativer Pflicht-Dep-Auflösung, fail-closed;
2. `--preset orders-service` — der vollständige Orders-Service als sourcebares Terraform-Modul, mit MANAGED- **und** EXTERNAL-Cognito.
Ein zusätzliches `minimal`-Preset wäre ein Synonym ohne Mehrwert (Benennungs-/Pflege-Overhead).

## Recommended Next Actions / Resume Point

Checkpoint abgeschlossen; keine Folgearbeit aus diesem Auftrag. Nächste mögliche Freigaben: die bestehenden OPEN-Items (siehe Open Questions).
