# MO-BUILDER-INSTALLER-UPGRADE-MIGRATION-PLAN

**Migrationsfahrplan für bestehende MO-Installationen**

**Stand:** 2026-11-03 (P0A + P0B umgesetzt)
**Charakter:** Entwicklungs- und Betriebsvorlage — **autorisiert keine AWS-Änderungen**
**Bezug:** `docs/reports/MO-BUILDER-INSTALLER-UPGRADE-READINESS-01.md`,
`docs/reports/MO-INSTALLER-UPGRADE-SAFETY-P0A-01.md`,
`docs/reports/MO-INSTALLER-UPGRADE-VERSIONING-P0B-01.md`

Legende: **IMPLEMENTED** · **PARTIALLY** · **PLANNED** · **BLOCKED**

---

| # | Phase | Ziel | Status | Was vorhanden ist | Was fehlt |
|---|---|---|---|---|---|
| 1 | Identifikation | Vorhandene Installation und State identifizieren | **PARTIALLY** | `validate` (Backend-Heuristik, Namenskollisionen), `plan --remote` liest den State, Manifest bindet Workspace/Backend | Explizite Ressourcen-Inventur vor dem Plan; State-Zugehörigkeit nur über Terraform |
| 2 | Versionsstatus | Installierte Version verifizieren oder Legacy feststellen | **IMPLEMENTED** | `mo_version`-Output, `detect_installed_version` (`VERIFIED`/`LEGACY_UNKNOWN`/`UNVERIFIED`/`UNREADABLE`) | Bestehende Stacks haben den Output erst nach dem nächsten Apply |
| 3 | Inventur | Konfiguration und Datenressourcen erfassen | **PLANNED** | Plan zeigt Ressourcen; P0A kennt geschützte Typen | Automatisierte Inventur/Report (Kandidat P0C) |
| 4 | Zielversion/Kompatibilität | Ziel festlegen, Kompatibilität prüfen | **PARTIALLY** | `target_version` gebunden (`--deployment-version`), Commit-/Dirty-Bindung | `DevelopmentState.compare` ist ungenutzt; keine Versionsmatrix/Kompatibilitätsregeln |
| 5 | Upgrade-Plan | Geschützten Plan erzeugen | **IMPLEMENTED** | `plan --remote` + Manifest (v2) + P0A-Safety-Gate | Kein eigener `--upgrade`-Modus |
| 6 | Klassifikation | Kritische Änderungen klassifizieren | **PARTIALLY** | P0A blockt DELETE/REPLACE geschützter Typen; Safety blockt Destroys | Vollständige Klassifikation `safe/review/critical` inkl. IAM/Datenmodell |
| 7 | Migrationsvorbereitung | Migrationsstrategie und Vorbedingungen | **PARTIALLY** | `upgrade-migration-plan.json/.md` bei Blockade (Strategien A–D, Vorbedingungen) | Keine Ausführung, keine Backup-Verifikation, kein Freigabe-Workflow |
| 8 | Kontrollierter Apply | Gespeicherten Plan anwenden | **IMPLEMENTED** | `deploy --plan` mit Manifest-, Versions-, Safety- und Policy-Prüfung | Kein Resume/Rollback (Kandidat P3) |
| 9 | Verifikation | Installation und Datenintegrität prüfen | **PARTIALLY** | Post-Apply-State-Zugriff, Destroy-Residual-Audit | Automatisierte Datenintegritäts-/No-op-Verifikation (P0C) |
| 10 | Nachweise | Version und Abschluss dokumentieren | **PARTIALLY** | Manifest + State-Output `mo_version` | Upgrade-Report/Changelog-Artefakt, signierte Nachweise |

---

## Sicherheitsregeln (gelten für jede Phase)

1. Keine automatische Datenmigration; jede Migration ist ein eigener,
   freigegebener Vorgang.
2. Ein gültiger Plan-Hash ersetzt keine Versions-/Safety-Prüfung.
3. `LEGACY_UNKNOWN` wird nie durch eine geratene Version ersetzt.
4. Destroy bleibt ein separater, explizit freigegebener Lifecycle.
5. RIS- und Shared-Infrastruktur (State-Bucket, Lock-Tabelle) bleiben unberührt.

## Nächste Schritte (P0C)

- Automatisierte Inventur (Phase 3) und No-op-Verifikation (Phase 9).
- `DevelopmentState.compare` verdrahten (Phase 4).
- Vollständige Change-Klassifikation (Phase 6).
- Builder-Upgrade-Modus (separater Strang).
