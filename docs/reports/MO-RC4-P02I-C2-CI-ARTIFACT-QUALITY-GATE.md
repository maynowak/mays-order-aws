# MO-RC4-P02I-C2-CI-ARTIFACT-QUALITY-GATE

**Lambda-Artefakt-Gate in der bestehenden Validate-Stage**

**Datum:** 2026-11-01
**Branch:** `feature/mo-rc4-kms-privacy-retention`
**Basis:** `293cea8b914515891561fad175a0cb3d02e890f7`
**Typ:** Implementierung + lokale Verifikation — **keine AWS-Operation**, kein Push, kein Deployment

---

## 1. Git-Baseline

| Prüfung | Ergebnis |
|---|---|
| Branch | `feature/mo-rc4-kms-privacy-retention` ✔ |
| HEAD | `293cea8` ✔ |
| Working Tree | CLEAN ✔ |
| Ausgangstests | 508 (326 + 93 + 89) |

---

## 2. Bestehende Pipeline (VERIFIED)

| Element | Befund |
|---|---|
| Pipeline | `ci/pipeline/main.tf`: **Source → Validate → Plan → Approval → Deploy → Verify** (Terraform, CodePipeline) |
| Validate | `ci/buildspecs/validate.yml`, CodeBuild, Python **3.12**, Terraform via dnf |
| Bisherige Validate-Schritte | `resolve_context.py` (AWS STS), `installer ... validate`, `py_compile`, `terraform init/fmt/validate` |
| Tests in CI | **explizit übersprungen** („Skipping unit tests in CI") |
| Artefakte Validate | nur `deployment_context.json`, `validation_result.json` |
| Quellartefakt | alle Stages nutzen `source_output` (gleicher Commit) als PrimarySource |
| Lambda-ZIP | **eingecheckt** (`lambda/dist/lambda.zip`), wird nicht in CI gebaut |
| GitHub Actions | nur `codeql.yml`, `dependency-check.yml`, `security.yml` — **kein** Test-/TF-Lauf |

**Ausgangsrisiko:** Die Validate-Stage verließ sich auf `installer validate` (das die
Artefaktprüfung enthält) — aber CI hätte ein **fehlendes/defektes** ZIP nur indirekt
bemerkt, **kein** Reproduzierbarkeitsvergleich, **keine** Packaging-Tests. Ein manuelles
Rebuild außerhalb der CI konnte zudem unbemerkt vom eingecheckten Artefakt abweichen.

---

## 3. Implementiertes Quality Gate (IMPLEMENTED)

In `ci/buildspecs/validate.yml`, **vor** der bisherigen Installer-Validierung, in dieser Reihenfolge:

```text
1. verify_lambda_zip('lambda')           # EINGECHECKTES Artefakt (fail-closed, KEIN Rebuild zuvor)
2. build_zip.build(/tmp/lambda-rebuild.zip)   # deterministischer Rebuild
3. cmp lambda/dist/lambda.zip /tmp/lambda-rebuild.zip  # byte-identisch
4. Packaging-Tests:
   - lambda/tests/test_build_zip
   - installer/tests/test_artifact_integrity
   - module_builder/...TestArtifactIntegrityGate
5. bisherige Installer-Validierung, py_compile, terraform init/fmt/validate (unverändert)
```

- **Gate A (Quellstruktur):** über die kanonische `verify_lambda_zip` (vergleicht alle
  `src/*.py`, inkl. Pflicht-Handler) — **keine** zweite Modul-Whitelist.
- **Gate B (Rebuild):** `lambda/build_zip.py` (deterministisch), Ziel `/tmp` → Workspace
  bleibt unverändert; Fehler brechen mit Exit ≠ 0 ab.
- **Gate C (Integrität):** kanonische Prüfung des Installers (ZIP fehlt/korrupt/leer/
  unvollständig/Handler fehlt/veraltet → FAIL).
- **Gate D (Konsistenz):** `cmp` zwischen eingechecktem und neu gebautem ZIP → jede
  Abweichung zwischen Quelle, Buildskript und versioniertem Artefakt ist ein **FAIL**.

**Kein Fehler wird durch Rebuild verdeckt:** Schritt 1 prüft den eingecheckten Stand,
bevor irgendetwas gebaut wird.

---

## 4. Geänderte Dateien

| Datei | Änderung |
|---|---|
| `ci/buildspecs/validate.yml` | Artefakt-Gate + Packaging-Tests in der Build-Phase (18 Build-Kommandos) |
| `installer/tests/test_ci_buildspec.py` | **neu**: strukturelle Absicherung des Gates (Reihenfolge, `cmp`, Tests, Terraform-Erhalt, keine Fehlerunterdrückung, YAML-Parse) |

Keine neue Stage, kein neuer CodeBuild-Job, keine neue AWS-Ressource, keine Änderung an
Plan/Deploy/Destroy/Verify.

---

## 5. Artefaktprüfung & Reproduzierbarkeit (VERIFIED lokal)

Lokale Simulation der CI-Kommandos (AWS-frei):

```text
Lambda artifact current (11 modules)          # verify_lambda_zip
CI-Simulation: Artefakt ist reproduzierbar    # Rebuild + cmp
test_build_zip: OK
test_artifact_integrity: OK
TestArtifactIntegrityGate: OK
```

- ZIP: **11 Module**, sha256 `bd6f279538c077d6fe1778d8a7ed67b0a6760314416030429de5e14a69dcd323`
- Rebuild erzeugt **byte-identische** Datei (fester Zeitstempel 1980, sortierte Reihenfolge).

---

## 6. Negative Tests (VERIFIED, lokal)

Bereits vorhanden (P02I-C1) und in CI mitlaufend:

| Fall | Test | Ergebnis |
|---|---|---|
| ZIP fehlt | `test_missing_zip_detected` | FAIL ✔ |
| ZIP korrupt | `test_corrupt_zip_detected` | FAIL ✔ |
| ZIP leer | `test_empty_zip_detected` | FAIL ✔ |
| Modul fehlt (`identity`, `order_handlers`, `recovery`, generisch) | `test_missing_module_detected`, `test_stale_archive_fails_closed` | FAIL ✔ |
| Handler fehlt | `test_missing_handler_module_detected` | FAIL ✔ |
| Veraltetes ZIP (7 Module) | Suite aus C1 (`test_missing_module_detected` / `test_stale_archive_fails_closed`) | FAIL ✔ |
| Build-Skript bricht ab | `test_build_zip` (Pflicht-Handler-Prüfung im Build) | Exit ≠ 0 ✔ |

Alle Tests nutzen temporäre Verzeichnisse — **kein** produktives Artefakt wird verändert.

---

## 7. Artefaktfluss zwischen Stages (VERIFIED / OPEN)

| Frage | Befund |
|---|---|
| Alle Stages nutzen denselben Commit? | **Ja** — jede Stage hat `source_output` als PrimarySource |
| Validiert Validate das Artefakt? | **Ja** (neues Gate + `installer validate`) |
| Baut Validate ein ZIP neu? | nur nach `/tmp` zum Vergleich — **kein** Überschreiben |
| Nutzen spätere Stages dasselbe ZIP? | **Ja** (eingechecktes ZIP im Source-Artefakt) |
| Geben Stages Build-Artefakte weiter? | `validate_output` (Context/Ergebnis), `plan_output` (Plan) — nicht das ZIP |
| Terraform nutzt das versionierte ZIP? | **Ja** (`filename = .../lambda/dist/lambda.zip`, `source_code_hash` daraus) |
| ZIP-Hash-Änderung korrekt? | **Ja** — `source_code_hash` ändert sich → Lambda-Update im Plan |

**OPEN (Risiko):** Die Pipeline erzwingt die Artefaktprüfung nur in **Validate**; Plan/Deploy
übernehmen den geprüften Commit, aber **bauen/ändern** das ZIP nicht. Würde jemand die
Pipeline-Konfiguration ändern (oder ein Rebuild in Plan/Deploy ergänzen), wäre das Gate
umgehbar. Für C2 dokumentiert, nicht umgebaut.

---

## 8. Python-/CodeBuild-Kompatibilität

| Aspekt | Befund |
|---|---|
| Runtime | CodeBuild Python **3.12**; Code nutzt nur stdlib + boto3/pytest (installiert) |
| Syntax | f-strings, `pathlib`, `zipfile` — kompatibel |
| Arbeitsverzeichnis | Repo-Root; Gate nutzt relative Pfade (`lambda`, `installer`, `module_builder`) |
| Dependencies | `boto3` wird in `install` installiert; Packaging-Tests brauchen kein AWS |
| AWS-Credentials | Gate **nicht** erforderlich (nur `installer validate` danach) |
| PyYAML | nur optional im Test (skip, falls nicht vorhanden) |

---

## 9. Regressionsergebnisse

| Suite | Vorher | Nachher |
|---|---|---|
| Lambda | 326 | **326** |
| Builder | 93 | **93** |
| Installer (`test_installer` + `artifact_integrity` + `ci_buildspec`) | 89 | **95** (+6) |
| **Gesamt** | 508 | **514** |

- `terraform validate` → **PASS**
- `terraform fmt -check -recursive` → **PASS**
- `git diff --check` → clean
- YAML: `validate.yml`, `plan.yml`, `deploy.yml` syntaktisch gültig (PyYAML)

---

## 10. Offene Risiken

| Risiko | Status |
|---|---|
| Gate nur in Validate; spätere Stages ohne eigene Artefaktprüfung | **OPEN** (dokumentiert) |
| GitHub Actions prüft weder Tests noch Artefakt | **OPEN** |
| Keine echte CodeBuild-Ausführung in diesem Checkpoint | **OPEN** (AWS-E2E) |
| `pip install -r requirements.txt \|\| true` (bestehend, außerhalb Scope) | **OPEN** |

---

## 11. Deployment-Readiness-Auswirkung

- Der P02I-C-Blocker (Artefakt unvollständig) bleibt behoben; die CI **erkennt** ihn jetzt
  zuverlässig, bevor Plan/Deploy laufen.
- Ein CI-GREEN bedeutet künftig: „Artefakt vorhanden **und** vollständig **und** aktuell
  **und** reproduzierbar“.
- **NOT DEPLOYED**: keine Pipeline-Ausführung, keine AWS-Operation.

---

## 12. Commit

Commit-SHA: siehe Abschlussbericht (dieser Commit). Working Tree nach Commit CLEAN.

---

## 13. Statusübersicht

| Element | Status |
|---|---|
| Validate-Buildspec erweitert | **IMPLEMENTED** |
| Artefaktprüfung vor Rebuild | **IMPLEMENTED / VERIFIED** |
| Reproduzierbarkeit (`cmp`) | **VERIFIED** |
| Packaging-Tests in CI | **IMPLEMENTED** |
| Kanonische Prüfung (keine Whitelist) | **VERIFIED** |
| Negative Fälle | **VERIFIED** |
| Terraform-Validierung erhalten | **VERIFIED** |
| Artefaktfluss | **VERIFIED**, Restrisiko OPEN |
| CI-Lauf in CodeBuild | **OPEN** (nicht ausgeführt) |
| Deployment | **NOT DEPLOYED** |
