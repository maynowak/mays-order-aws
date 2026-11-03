# MO-BUILDER-UPGRADE-P2-01

**Sicherer Builder-Upgrade-Modus (Manifest, Diff, Konfigurationserhalt, Apply)**

**Datum:** 2026-11-03
**Branch:** `feature/mo-builder-upgrade-p2` (von P1 `9ae4558`)
**Basis:** `main` @ `f597d14` + P0A/P0B/P0C/P1
**Modus:** lokale Implementierung + Tests; keine AWS-/Terraform-Ausführung, kein Push/Merge

---

## 1. Ausgangsstand

| Prüfung | Ergebnis |
|---|---|
| `main` | `f597d14` |
| P1-Branch | `feature/mo-installer-upgrade-orchestration-p1` @ `9ae4558` |
| P2-Branch | davon abgezweigt |
| Working Tree vor Start | CLEAN |
| Regression vor P2 | 422 Installer-Tests PASS (Builder: 93) |
| Auditlog/Reports/Migrationsplan | gelesen und berücksichtigt |

---

## 2. Tatsächliche Builder-Architektur

- `python -m module_builder {build,presets}`; `build` kopiert Root-Wiring,
  Kindmodule, Artefakte und schreibt `module-builder.manifest.json`.
- Module-/Preset-Auswahl (`--preset`, `--modules`, `--with-deps`), `--force`
  überschreibt nur Builder-Dateien.
- Kein Terraform-Aufruf, kein AWS; `backend.tf` wird bewusst nicht kopiert.
- Manifest v1 enthielt `files_written`, aber **keine Datei-Fingerprints** →
  Eigentum war nicht prüfbar.

**Abweichung von der Zielsyntax:** Statt eines neuen `.mays-builder/manifest.json`
wurde das **bestehende** `module-builder.manifest.json` auf Schema 2 erweitert
(kein paralleler Vertrag). Die Zielsyntax `builder upgrade --project …` wurde als
`python -m module_builder upgrade --project …` umgesetzt (vorhandene CLI-Struktur).

---

## 3. Implementierte Funktionen

| Abschnitt | Komponente | Datei |
|---|---|---|
| P2A | Manifest Schema 2 + Projektstatus | `module_builder/builder.py`, `module_builder/upgrade.py` |
| P2B | Datei-Diff + Ownership | `module_builder/upgrade.py` |
| P2C | Konfigurationserhalt + Parameterhinweise | `module_builder/upgrade.py` |
| P2D | Dry-Run/Apply + Dateisystem-Sicherheit | `module_builder/upgrade.py`, `module_builder/cli.py` |
| P2E | Berichte, Tests, Doku | `upgrade.py`, Tests, `README.md` |

**Commit-Aufteilung (Abweichung dokumentiert):** Der Kern liegt in einem Modul;
daher ein Commit für die P0B-Regression (`deployment_version`) und ein Commit für
P2A–P2D; P2E als Doku-Commit. Keine künstlichen Zwischen-Commits.

---

## 4. Manifest-Vertrag

`module-builder.manifest.json` (Schema `manifest_version: 2`):

```json
{
  "manifest_version": 2,
  "builder_version": "0.1.0",
  "preset": "complete|custom",
  "modules": ["..."],
  "project_name": "...",
  "generated_at": "...",
  "source": {"repo": "...", "commit": "..."},
  "artifacts_sha256": {"...": "..."},
  "files_written": ["..."],
  "files": {"terraform/main.tf": "<sha256>", "...": "..."}
}
```

- Bestehende Felder bleiben erhalten (Tests unverändert grün).
- Keine Dateiinhalte, keine Secrets, keine tfvars-Werte im Manifest.
- v1-Manifeste (ohne `files`) → `LEGACY_PROJECT`, keine automatische Übernahme.
- Manifest wird erst nach erfolgreichen Schreibvorgängen ersetzt und erhält
  `upgraded_from` (Builder-Version/Zeitpunkt).

---

## 5. Datei-Diff-Klassifikation

| Kategorie | Bedeutung |
|---|---|
| `UNCHANGED` | Datei unverändert |
| `ADD` | neue, konfliktfreie Datei |
| `UPDATE_SAFE` | verwaltete, unveränderte Datei mit neuer Version |
| `USER_MODIFIED` | Benutzer hat verwaltete Datei geändert (bleibt erhalten) |
| `USER_OWNED` | nicht Builder-verwaltete Datei (bleibt erhalten) |
| `REMOVE_CANDIDATE` | wird nicht mehr erzeugt; **keine** automatische Löschung |
| `CONFLICT` | Überschreiben würde Benutzeränderung/ungeklärten Bestand zerstören |

Status: `READY` · `REVIEW_REQUIRED` (nur USER_MODIFIED/REMOVE_CANDIDATE) ·
`BLOCKED` (Konflikt/Legacy/unverifiziert) · `NO_CHANGES`.
Codes: `BUILDER_UPGRADE_READY`, `BUILDER_UPGRADE_CONFLICT`,
`BUILDER_PROJECT_UNVERIFIED`, `BUILDER_LEGACY_REVIEW_REQUIRED`,
`BUILDER_UPGRADE_NO_CHANGES`.

---

## 6. Konfigurationserhalt

- `*.tfvars`, `*.auto.tfvars`, `.env*`, `.terraform*`, State-/Plan-Dateien werden
  **nie** geschrieben, überschrieben oder gelöscht; sie erscheinen als
  `configChanges.preserved`.
- Neue/entfernte Terraform-Variablen werden per statischer Namensanalyse
  (`variable "…"`) als **Vorschlag** gemeldet (`newParameters`/`removedParameters`)
  — ohne Textersetzung an bestehenden Dateien.
- Keine automatische Auflösung von Konfigurationskonflikten.

---

## 7. Kontrollierter Upgrade-Modus

```bash
python -m module_builder upgrade --project ./generated/my-orders --dry-run
python -m module_builder upgrade --project ./generated/my-orders --apply
```

- Genau einer der Modi ist Pflicht (`--dry-run` xor `--apply`), sonst Exit 2.
- Dry-Run: erkennt Projekt/Manifest, generiert den Zielbestand **temporär**,
  vergleicht, schreibt den Bericht — **keine** Projektdateiänderung.
- Apply: schreibt ausschließlich `ADD`/`UPDATE_SAFE`, aktualisiert das Manifest;
  `BLOCKED` wird abgelehnt, `NO_CHANGES` schreibt nichts.
- Preset/Module werden aus dem Manifest übernommen; abweichende CLI-Angaben und
  eine nicht passende `--target-version` werden abgelehnt.
- Kein `--force`-Bypass, keine automatische Löschung.

---

## 8. Dateisystem-Sicherheit

- Pfadnormalisierung; absolute Pfade, `..` und leere Pfade werden abgelehnt.
- Jede Pfadkomponente wird auf Symlinks geprüft; Ziele müssen im Projekt liegen
  (`safe_target`).
- Schreiben über Staging-Verzeichnis (`.mays-builder/staging/<ts>`) und
  `os.replace`; bei Fehler kein Manifest-Update und keine Erfolgsmeldung.
- Kein Rollback über Einzeldateien hinaus (dokumentierte Grenze).

---

## 9. Builder-/Installer-Übergabe

Der Builder liefert ausschließlich den aktualisierten Projektbestand. Der
Installer bleibt für Infrastruktur verantwortlich:

```text
Builder upgrade (dry-run/apply) → Manifest v2
        ↓
installer plan --remote --upgrade
        ↓
P0A (Safety) / P0B (Version) / P0C (Baseline/Drift) / P1 (Kompatibilität)
        ↓
upgrade-readiness.json/.md → deploy --plan (separate Freigabe)
```

Keine AWS-Kopplung, keine zweite Orchestrierung, kein automatischer Apply.

---

## 10. Testergebnisse

| Suite | Ergebnis |
|---|---|
| `module_builder/tests/test_builder_upgrade.py` (neu) | **35 PASS** |
| Builder gesamt (93 + 35) | **128 PASS** |
| Installer gesamt | **422 PASS** (unverändert) |
| Terraform fmt/validate | nicht erforderlich (keine `.tf`-Änderung) |

Abgedeckt: Manifest v2, Projektstatus (new/empty/unverified/invalid/legacy/
conflicted/managed/traversal), alle Diff-Kategorien, Konfigurationserhalt,
Parameterhinweise, Dry-Run ohne Änderung, Apply (ADD/UPDATE_SAFE), Konflikt-Refusal,
keine Löschung, Pfad-/Symlink-Schutz, Schreibfehler, Idempotenz, Bericht ohne
Secrets/Inhalte, CLI-Fälle.

Zusätzlich behoben: `deployment_version` fehlte in Custom-Selections, wodurch
`mo_version` auf eine undefinierte Variable zeigte (P0B-Regression).

---

## 11. Git-Commits

| Commit | Inhalt |
|---|---|
| `c6ba187` | `fix(builder)`: `deployment_version`/`mo_version` in Custom-Selections |
| `12ab308` | `feat(builder)`: Manifest v2, Diff, Controlled Apply, CLI, 35 Tests |
| (folgt) | `docs(builder)`: README, Migrationsplan, Auditlog, dieser Report |

Kein Push, kein Merge.

---

## 10. Bekannte Einschränkungen

| ID | Einschränkung |
|---|---|
| L-01 | Kein vollständiger Rollback (nur Einzeldateien via Staging/`os.replace`) |
| L-02 | Parameterhinweise sind Namensvergleiche, keine semantische HCL-Analyse |
| L-03 | Legacy-Projekte (Manifest ohne Fingerprints) werden nicht automatisch übernommen |
| L-04 | Kein Merge von Benutzeränderungen in generierte Dateien |
| L-05 | Bericht ist keine Terraform-Freigabe |

---

## 12. Empfehlungen für P3

1. Legacy-Übernahme (Fingerprints aus Bestand erzeugen) mit Review-Workflow.
2. HCL-basierter Parameter-/Strukturvergleich statt Namensliste.
3. Transaktionaler Rollback über alle Dateien (Manifest+Backup).
4. Builder-Report an den Installer-Readiness-Bericht anhängen (Nachweiskette).
5. Optional: Signatur/Attestation des Builder-Manifests.

---

## 13. Status

```text
P2 COMPLETE — BUILDER UPGRADE VERIFIED
```

Implementierung und Tests erfolgreich; Installer-Gates unverändert.
Kein AWS-Zugriff, kein Terraform, kein Push. **STOP.**
