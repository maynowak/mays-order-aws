# MO-INSTALLER-UPGRADE-VERSIONING-P0B-01

**Versionsbindung für Installationen und Upgrades (P0B)**

**Datum:** 2026-11-03
**Branch:** `feature/mo-installer-upgrade-versioning-p0b` (von P0A `209d0da`)
**Basis:** `main` @ `f597d14` + P0A-Branch
**Modus:** lokale Implementierung + Tests; kein AWS, kein Terraform Apply/Destroy, kein Push/Merge

---

## 1. Tatsächliche Ausgangsbasis

| Prüfung | Ergebnis |
|---|---|
| `main` | `f597d14` |
| P0A-Branch | `feature/mo-installer-upgrade-safety-p0a` @ `209d0da` |
| P0B-Branch | `feature/mo-installer-upgrade-versioning-p0b` (von `209d0da`) |
| P0A vorhanden | Safety-Gate, Migrationsplan, Destroy-Guard, 315 Tests ✅ |
| Working Tree vor Start | CLEAN |
| Auditlog gelesen | `docs/AI_AUDITLOG.md` (Execution-Log-/Index-Regeln) |

---

## 2. Implementierte Komponenten

| Komponente | Datei | Zweck |
|---|---|---|
| Quellcode-Identität | `installer/core/source_identity.py` | vollständige Commit-SHA aus dem Installer-Repo, Dirty-Status (getrackte Dateien), Detached HEAD, fail-closed ohne Git |
| Installationsversion | `installer/core/version_binding.py` | `state list` + `output -json` → `VERIFIED`/`LEGACY_UNKNOWN`/`UNVERIFIED`/`UNREADABLE` |
| Bindungsprüfung | `installer/core/version_binding.py` | Zielversion, Commit, Dirty, Quellversion, Legacy, Konsistenz |
| Manifest-Schema 2 | `installer/core/plan_manifest.py` | neue Felder, v1 bleibt lesbar (nicht upgradefähig) |
| Plan-Integration | `installer/cli/main.py::_cmd_plan` | Source-Preflight, Dirty-Schutz, Versionserkennung, Manifest-Felder |
| Apply-Integration | `installer/cli/main.py::_cmd_deploy` | Manifest **und** Versionsbindung vor Apply |
| Destroy-Abgrenzung | `installer/cli/main.py::_cmd_destroy` | Legacy-Manifeste/kein Manifest zulässig (kein Upgrade) |
| Versionskennung im Stack | `terraform/variables.tf`, `terraform/outputs.tf` | `deployment_version` → Output `mo_version` |

---

## 3. Manifest-Schema

`manifest_version = 2` (Feldname bleibt konsistent zum bestehenden Modell;
die Spec-Bezeichnung „manifestSchemaVersion" wird nicht als zweites Feld eingeführt).

Neu:

```json
{
  "manifest_version": 2,
  "source_version": null,
  "target_version": "0.2.0",
  "git_commit": "0123456789abcdef0123456789abcdef01234567",
  "git_dirty": false,
  "version_status": "LEGACY_UNKNOWN",
  "version_source": "state_without_version"
}
```

Unverändert: `deployment_id`, `operation`, `region`, `workspace`, `backend`,
`state_key`, `plan_file`, `plan_sha256`, `plan_size`, `variables`, `created_at`.

**Kompatibilität:** `from_dict` akzeptiert snake_case und camelCase;
v1-Manifeste laden weiterhin, werden aber beim Deploy **blockiert**
(`UPGRADE_VERSION_BINDING_MISSING`), beim Destroy akzeptiert.
Keine automatische Migration.

---

## 4. Git-Commit-Bindung

| Anforderung | Umsetzung |
|---|---|
| Vollständige SHA | 40-Hex-Validierung; kein Kürzen im Manifest |
| Richtiges Repository | `Path(__file__).resolve().parents[2]` (Installer-Repo), nicht CWD/HEAD eines fremden Repos |
| Detached HEAD | unterstützt (`rev-parse HEAD`; `symbolic-ref` nur zur Info) |
| Dirty Working Tree | `git status --porcelain --untracked-files=no` (nur getrackte Dateien) |
| Fehlende Git-Metadaten | `available=False` → Remote-Plan blockiert (`UPGRADE_SOURCE_UNVERIFIED`) |
| Keine erfundene SHA | nur echte `rev-parse`-Ausgabe; sonst `null` |

Dirty-Verhalten: Remote-Plan/Apply standardmäßig blockiert
(`UPGRADE_SOURCE_DIRTY`); Freigabe nur mit `--allow-dirty-source`, der Zustand
wird im Manifest dokumentiert. Offline-Dry-Run bleibt unberührt.

---

## 5. Versionskennung im Stack

- Neue Root-Variable `deployment_version` (SemVer, Default `0.1.0`,
  Validierung `^[0-9]+\.[0-9]+\.[0-9]+$`).
- Neuer Output `mo_version` (Wert = `var.deployment_version`).
- Der Installer injiziert `-var deployment_version=<context.deployment_version>`.
- **Grenze (dokumentiert):** State-Output ist keine unabhängige Bestätigung des
  laufenden Lambda-Codes; bestehende Stacks erhalten ihn erst beim nächsten Apply.
- Keine zusätzliche AWS-Ressource.

---

## 6. Legacy-Verhalten

| Szenario | Verhalten |
|---|---|
| A — Neuinstallation (kein State) | `sourceVersion=null`, `versionStatus=UNVERIFIED`, `versionSource=no_remote_state` |
| B — Installierte Version verifiziert | `VERIFIED` + `sourceVersion`; bei Apply Abgleich mit dem State |
| C — State ohne Versionskennung | `LEGACY_UNKNOWN`; Apply nur mit `--allow-legacy-source`; **keine** Versionsannahme |
| D — State nicht lesbar | `UPGRADE_STATE_UNREADABLE`, Abbruch (keine Neuinstallations-Annahme) |
| E — Manifest-Version ≠ installiert | `UPGRADE_VERSION_BINDING_MISMATCH` vor Apply |
| F — Commit zwischen Plan/Apply geändert | `UPGRADE_VERSION_BINDING_MISMATCH` vor Apply |
| G — Legacy-Manifest (v1) | Deploy blockiert (`UPGRADE_VERSION_BINDING_MISSING`), Destroy erlaubt |

---

## 7. Plan-/Apply-Sicherheitsprüfungen

```text
plan --remote
  → Source-Preflight (Commit vorhanden, nicht dirty oder --allow-dirty-source)
  → terraform plan
  → P0A-Safety-Gate (DELETE/REPLACE)
  → detect_installed_version (UNREADABLE ⇒ Abbruch)
  → Manifest v2 schreiben (source/target/commit/dirty/status)
  → Hinweis: "Installed version: …"

deploy --plan
  → Manifest vorhanden (sonst UPGRADE_VERSION_BINDING_MISSING)
  → Manifest-Struktur/Checksumme (bestehend)
  → Version-Binding: target, commit, dirty, source version, legacy, State lesbar
  → P0A-Safety-Gate
  → Apply
```

Neue Fehlerkennungen: `UPGRADE_VERSION_BINDING_MISSING`,
`UPGRADE_VERSION_BINDING_MISMATCH`, `UPGRADE_SOURCE_DIRTY`,
`UPGRADE_SOURCE_UNVERIFIED`, `UPGRADE_LEGACY_SOURCE_UNKNOWN`,
`UPGRADE_STATE_UNREADABLE`.

**Grenze:** Das Manifest ist nicht signiert; es schützt vor Verwechslung/
Fehlbedienung, nicht vor lokalem Austausch von Plan **und** Manifest.

---

## 8. Testergebnisse

| Suite | Ergebnis |
|---|---|
| `installer/tests/test_version_binding.py` (neu) | **28 PASS** |
| `installer/tests/test_upgrade_gate_cli.py` (erweitert) | **14 PASS** |
| `installer/tests/test_upgrade_safety.py` (P0A) | **32 PASS** |
| **Installer gesamt (21 Module)** | **347 PASS** |
| Builder / Lambda | unverändert, nicht betroffen |
| `terraform fmt -check` / `terraform validate` | PASS / PASS |

Abgedeckt: realer Commit, detached HEAD, dirty, fehlende Git-Metadaten,
ungültige SHA, Neuinstallation, verifizierte Version, Legacy ohne Version,
unlesbarer State, Zielversions-/Commit-/Dirty-/Quellversions-Mismatch,
Legacy ohne/mit Freigabe, v1-Manifest (Deploy blockiert/Destroy erlaubt),
P0A-DELETE/REPLACE-Blockade, Destroy-Lifecycle, „Apply bei Blockade nicht
aufgerufen".

---

## 9. Git-Commits

| Commit | Inhalt |
|---|---|
| `feb0a7e` | `feat(installer)`: Source-Identity + Installationsversion + Bindungslogik (28 Tests) |
| `1dabd04` | `feat(installer)`: Manifest v2, CLI-Gates, Terraform-Output (Tests, 347 gesamt) |
| (folgt) | `docs(installer)`: Doku, Migrationsfahrplan, Auditlog, dieser Report |

Kein Push, kein Merge nach `main`.

---

## 10. Bekannte Einschränkungen

| ID | Einschränkung |
|---|---|
| L-01 | Manifest nicht signiert (Integrität/Identität, keine Authentizität) |
| L-02 | `sourceVersion` bestehender Stacks erst nach nächstem Apply verfügbar (Legacy bleibt `LEGACY_UNKNOWN`) |
| L-03 | Keine automatische Kompatibilitätsprüfung (`DevelopmentState.compare` ungenutzt) |
| L-04 | Keine Datenmigration, kein Rollback/Resume |
| L-05 | Zielversion ist die Deployment-Version (`--deployment-version`), keine Versionsmatrix |
| L-06 | Deploy verlangt jetzt ein Manifest (v1/kein Manifest blockiert) — Legacy-Pläne müssen neu geplant werden |

---

## 11. Aktualisierter Migrationsfahrplan

`docs/reports/MO-BUILDER-INSTALLER-UPGRADE-MIGRATION-PLAN.md` (10 Phasen) —
Kurzstatus:

| Phase | Status |
|---|---|
| 1 Identifikation | PARTIALLY |
| 2 Versionsstatus | **IMPLEMENTED** |
| 3 Inventur | PLANNED |
| 4 Zielversion/Kompatibilität | PARTIALLY |
| 5 Upgrade-Plan | **IMPLEMENTED** |
| 6 Klassifikation | PARTIALLY |
| 7 Migrationsvorbereitung | PARTIALLY |
| 8 Kontrollierter Apply | **IMPLEMENTED** |
| 9 Verifikation | PARTIALLY |
| 10 Nachweise | PARTIALLY |

---

## 12. Empfehlungen für P0C

1. `plan --upgrade --from/--to` mit `DevelopmentState.compare` (hartes STOP bei
   `MIGRATION_REQUIRED`/`INCOMPATIBLE`) und Versionsmatrix.
2. Automatisierte Inventur (Phase 3) und No-op-/Datenintegritäts-Verifikation (Phase 9).
3. Vollständige Change-Klassifikation (`safe`/`review`/`critical`) inkl. IAM.
4. Upgrade-Report/Changelog-Artefakt als Abschlussnachweis.
5. Optional: Manifest-Signatur/Attestation (Grenze L-01).

---

## 13. Status

```text
P0B COMPLETE — VERSION BINDING VERIFIED
```

Implementierung und Tests erfolgreich; P0A-Schutz unverändert aktiv.
Kein AWS-Zugriff, kein Apply/Destroy, kein Push. **STOP.**
