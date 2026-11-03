# MO-BUILDER-INSTALLER-UPGRADE-MIGRATION-PLAN

**Migrationsfahrplan für bestehende MO-Installationen**

**Stand:** 2026-11-03 (P0A + P0B + P0C + P1 + P2 umgesetzt)
**Charakter:** Entwicklungs- und Betriebsvorlage — **autorisiert keine AWS-Änderungen**
**Bezug:** `docs/reports/MO-BUILDER-INSTALLER-UPGRADE-READINESS-01.md`,
`docs/reports/MO-INSTALLER-UPGRADE-SAFETY-P0A-01.md`,
`docs/reports/MO-INSTALLER-UPGRADE-VERSIONING-P0B-01.md`,
`docs/reports/MO-INSTALLER-UPGRADE-DRIFT-SAFETY-P0C-01.md`,
`docs/reports/MO-INSTALLER-UPGRADE-ORCHESTRATION-P1-01.md`,
`docs/reports/MO-BUILDER-UPGRADE-P2-01.md`

Legende: **IMPLEMENTED** · **PARTIALLY** · **PLANNED** · **BLOCKED**

---

| # | Phase | Ziel | Status | Was vorhanden ist | Was fehlt |
|---|---|---|---|---|---|
| 1 | Identifikation | Vorhandene Installation und State identifizieren | **PARTIALLY** | `validate` (Backend-Heuristik, Namenskollisionen), `plan --remote` liest den State, Manifest bindet Workspace/Backend; **P0C: State-Baseline (Serial/Lineage/Fingerprint)** | Explizite Ressourcen-Inventur vor dem Plan; State-Zugehörigkeit nur über Terraform |
| 2 | Versionsstatus | Installierte Version verifizieren oder Legacy feststellen | **IMPLEMENTED** | `mo_version`-Output, `detect_installed_version` (`VERIFIED`/`LEGACY_UNKNOWN`/`UNVERIFIED`/`UNREADABLE`) | Bestehende Stacks haben den Output erst nach dem nächsten Apply |
| 3 | Inventur | Konfiguration und Datenressourcen erfassen | **PLANNED** | Plan zeigt Ressourcen; P0A kennt geschützte Typen | Automatisierte Inventur/Report (Kandidat P1) |
| 4 | Zielversion/Kompatibilität | Ziel festlegen, Kompatibilität prüfen | **PARTIALLY** | `target_version` gebunden; **P1: SemVer-Regeln (COMPATIBLE/REVIEW/MIGRATION/INCOMPATIBLE/UNKNOWN) blockieren** | Kompatibilitätsmatrix/Evidenz für Minor-Upgrades fehlt (Minor = REVIEW) |
| 5 | Upgrade-Plan | Geschützten Plan erzeugen | **IMPLEMENTED** | `plan --remote` + Manifest (v2) + P0A-Safety-Gate + **P0C Drift-/No-op-Bericht** | Kein eigener `--upgrade`-Modus |
| 6 | Klassifikation | Kritische Änderungen klassifizieren | **IMPLEMENTED** | **P1: SAFE/REVIEW/CRITICAL** aus P0A, Drift, geplanten Änderungen und Kompatibilität; Gesamt = Maximum | Feinere fachliche Regeln (IAM-Diff, Datenmodell) bleiben Ausbaustufe |
| 7 | Migrationsvorbereitung | Migrationsstrategie und Vorbedingungen | **PARTIALLY** | `upgrade-migration-plan.json/.md` bei Blockade (Strategien A–D, Vorbedingungen) | Keine Ausführung, keine Backup-Verifikation, kein Freigabe-Workflow |
| 8 | Kontrollierter Apply | Gespeicherten Plan anwenden | **IMPLEMENTED** | `deploy --plan` mit Manifest-, Versions-, **State-Baseline-**, Safety- und Policy-Prüfung | Kein Resume/Rollback (Kandidat P3) |
| 9 | Verifikation | Installation und Datenintegrität prüfen | **PARTIALLY** | Post-Apply-State-Zugriff, Destroy-Residual-Audit; **P0C: No-op-Klassifikation und Drift-Bericht als Verifikationsgrundlage** | Automatisierte Datenintegritätsprüfung (P1) |
| 10 | Nachweise | Version und Abschluss dokumentieren | **PARTIALLY** | Manifest + `mo_version`; **P1: `upgrade-readiness.json/.md`**; P0C-Driftbericht | Abschluss-/Changelog-Artefakt, signierte Nachweise |

---

## Sicherheitsregeln (gelten für jede Phase)

1. Keine automatische Datenmigration; jede Migration ist ein eigener,
   freigegebener Vorgang.
2. Ein gültiger Plan-Hash ersetzt keine Versions-/Safety-Prüfung.
3. `LEGACY_UNKNOWN` wird nie durch eine geratene Version ersetzt.
4. Destroy bleibt ein separater, explizit freigegebener Lifecycle.
5. RIS- und Shared-Infrastruktur (State-Bucket, Lock-Tabelle) bleiben unberührt.

## P2 — umgesetzt (2026-11-03)

- Builder-Manifest Schema 2 mit Datei-Fingerprints; Projektstatus
  NEW/MANAGED/LEGACY/UNVERIFIED/CONFLICTED.
- `module_builder upgrade --dry-run|--apply`: Diff (ADD/UPDATE_SAFE/
  USER_MODIFIED/USER_OWNED/REMOVE_CANDIDATE/CONFLICT), Konfigurationserhalt
  (tfvars/.env), Parameter-Vorschläge, Bericht, Staging-Apply, Manifest-Update.
- Keine Löschung, kein Überschreiben von Benutzerdateien, Legacy nur mit Review.
- Übergabe: Builder liefert Dateien; Installer bleibt für
  `plan --remote --upgrade` und Infrastruktur verantwortlich.

## Nächste Schritte (P3)

- Automatisierte Inventur (Phase 3) und Datenintegritätsprüfung (Phase 9).
- `DevelopmentState.compare` verdrahten (Phase 4).
- Vollständige Change-Klassifikation (Phase 6).
- Upgrade-Abschlussreport/Attestation (Phase 10).
- Builder-Upgrade-Modus (separater Strang).

## P1 — umgesetzt (2026-11-03)

- Expliziter Modus `plan --remote --upgrade` (kein zweiter Apply-Pfad).
- Voraussetzungen: bestehende Installation, Remote-State; Legacy bleibt
  `UNKNOWN` und blockiert.
- Versionskompatibilität mit SemVer-Regeln; Major/Downgrade/unbekannt blockieren,
  Minor verlangt Review (bzw. Evidenz).
- Change-Klassifikation SAFE/REVIEW/CRITICAL (Maximum).
- `upgrade-readiness.json/.md`; Apply prüft Kompatibilität/Readiness erneut,
  `REVIEW_REQUIRED` nur mit `--accept-upgrade-review`.
- Grenzen: keine Migration, kein Rollback, keine Kompatibilitätsmatrix.

## P0C — umgesetzt (2026-11-03)

- State-Baseline (Serial/Lineage/Fingerprint) im Manifest und Apply-Gate
  (`UPGRADE_STATE_BASELINE_MISMATCH` / `_MISSING`).
- Drift-Erkennung aus `resource_drift` mit fail-closed
  (`UPGRADE_DRIFT_UNVERIFIED`) und Blockade bei Drift geschützter Typen.
- No-op-Klassifikation (`NO_OP_VERIFIED`/`CHANGES_PLANNED`/`NO_OP_UNVERIFIED`).
- `upgrade-drift-report.json/.md` im Run-Verzeichnis.
- Grenze: TOCTOU und State-Fingerprint ersetzen keine Datenintegritätsprüfung.
