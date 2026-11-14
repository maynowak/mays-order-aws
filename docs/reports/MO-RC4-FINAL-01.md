# MO-RC4-FINAL-01 — RC4 Local Release Candidate

**Status:** `RESULT B — RC4 READY WITH DEPLOYMENT GATES`
**Datum:** 2026-11-14

> **Nachtrag 2026-11-14:** Der kontrollierte AWS-Development-Lebenszyklus
> wurde nach diesem lokalen Abschluss separat ausgeführt. Siehe
> `docs/reports/MO-RC4-AWS-LIFECYCLE-FINAL-01.md`:
> `mays-orders-rc4` wurde deployed, live getestet und vollständig zerstört.
> Die Aussage „keine AWS-Mutation“ in diesem Dokument gilt nur für den
> ursprünglichen lokalen Auftrag, nicht für den anschließenden Lifecycle-Lauf.
**Integration-Branch:** `release/rc4-integration`
**Merge-Commit:** `0620044779dc92a87c5554e782e13817407a0b0d`
**Terraform plan/apply:** nicht ausgeführt
**AWS-Live-Aufrufe/Deployment:** keine
**Push/Main-Merge:** nicht ausgeführt

## 1. Ausgangslage

- Basis: `release/rc4-integration` @ `51df73665be9738017505352c18c9420603827d9`.
- Feature: `feature/mo-rc4-final-01`.
- Alle Worktrees waren clean; keine fremden Änderungen wurden überschrieben.
- Keine Subagenten in diesem Auftrag; alle Prüfungen und Commits wurden
  serialisiert über den Hauptagenten ausgeführt.
- Bestehende P00-B/C/D/E-Module und Orchestrierung wurden wiederverwendet.

## 2. Implementierte Funktionen

### A — Installer stabilisiert

- Hardcodierte Pfade
  `/home/dci-student/projects/Mays-Orders-AWS` aus den Installer-Tests
  entfernt; Tests verwenden `REPO_ROOT`.
- Dependency-Detector akzeptiert jetzt ein explizites Repository-Root und
  hängt nicht mehr vom aktuellen Arbeitsverzeichnis ab.
- Deterministische Detector-Tests mit offline Fixture statt Registry-Netzwerk.
- AWS-Live-Profil-Test ist standardmäßig **SKIPPED**; Aktivierung nur mit
  `MO_AWS_LIVE_PROFILE_TEST=1` und separater Read-Only-Freigabe.
- Ergebnis: vollständige Installer-Suite **674 Tests OK, 1 Skipped**.

### B — P00-F Rotation/Revocation für APP_MANAGED

- Bestehender HMAC-Vertrag unverändert.
- Maximal ein vorheriger Schlüssel innerhalb eines expliziten Fensters:
  - `PRIVACY_APP_PREVIOUS_KEY_ID`
  - `PRIVACY_APP_PREVIOUS_KEY_VERSION`
  - `PRIVACY_APP_ROTATION_STARTED_AT`
  - `PRIVACY_APP_ROTATION_UNTIL`
- Fenster max. 24 Stunden; unvollständige, gleiche oder überlange Konfiguration
  wird fail-closed abgelehnt.
- Vorheriges Schlüsselmaterial wird ausschließlich über den bestehenden lokalen
  Loader injiziert; kein AWS-KMS, keine neue Verschlüsselung, kein Hot-Reload.
- `revoke()` sperrt den Provider sofort; eine neue Konfiguration erfordert
  einen kontrollierten Environment-Recycle.
- APP_MANAGED bleibt default-off und wird nicht als Bearer-Token-Provider
  aktiviert.
- Kein neuer KMS-Schlüssel, keine Terraform-Ressource.

### C — P00-G Retention

**Sicher deaktiviert / BLOCKED BY OWNER DECISION.**

- Keine `retentionUntil`-/TTL-Felder implementiert.
- Keine automatische Löschung, kein Backfill, keine Frist erfunden.
- Offene Entscheidungen: Q-05 (`tenantId`), Q-06 (Fristen),
  Q-07 (Cancel-Anonymisierung), Q-14 (Bestandsdaten).
- Details: `docs/reports/MO-RC4-P00-G-RETENTION-DISABLED-01.md`.
- ERASE/ANONYMIZE/RETAIN-Verhalten bleibt unverändert.

### D — Installer / Builder

- `complete`-Preset enthält das optionale `privacy_secret`-Modul.
- Neuer Builder-Test sichert die P00-E-Integration im generierten Projekt.
- Zwei vollständige Builder-Läufe erzeugen byte-identische Dateibäume
  (ausgenommen das Manifest mit Laufzeit-Metadaten).
- Das generierte Projekt besteht `terraform fmt -check`, `init -backend=false`
  und `validate`.
- Keine parallele Installer-Architektur, keine neuen Pflicht-Flags.

### E — RC4-Verifikation

| Prüfung | Ergebnis |
|---|---|
| Lambda | **440/440 PASS** |
| Installer | **674 PASS, 1 Skipped** (AWS live profile deferred) |
| Module Builder | **129/129 PASS** |
| Policy Gate | **23/23 PASS** |
| Lokale E2E | **36 PASS, 5 Skipped** |
| Seed | **28/28 PASS** |
| Terraform `fmt -check` | **PASS** |
| Terraform `init -backend=false` | **PASS** |
| Terraform `validate` | **PASS** |
| `git diff --check` | **PASS** |

Keine bekannten Fehler als PASS deklariert. Der Live-Test ist ausdrücklich
Skipped; es gibt keine offenen lokalen Testfehler.

## 3. Release-Artefakte

| Artefakt | Wert |
|---|---|
| `lambda/dist/lambda.zip` | 46.929 Bytes |
| SHA-256 | `20f4bab5766529e3340273cfde3b35c601a389122759051f2aef801337b76377` |
| Lambda-Module | 13 |
| ZIP-Reproduzierbarkeit | zwei Builds byte-identisch |
| Builder-Preset | `complete`, zwei Läufe byte-identisch (ohne Manifest) |
| Generiertes Terraform | fmt/init/validate PASS |
| Module-Builder-Version | 0.1.0 |

Es wurde kein Release-Tag erzeugt. Die Release-Bezeichnung bleibt Q-12.

## 4. Commits

```text
7a72c46 fix(installer): stabilize dependency detector and live-profile tests
dad5b16 feat(privacy): add explicit app-managed rotation and revocation
ed17c12 build(lambda): refresh artifact for app-managed rotation
cc6ab71 test(builder): cover privacy secret in complete preset
85ef5fb fix(installer): remove remaining primary-worktree test dependency
0620044 merge: complete rc4 local release candidate
```

## 5. Tatsächlich betroffene Ressourcen

Es wurden **keine AWS-Ressourcen erzeugt, geändert oder gelöscht** und kein
Terraform-Plan/Apply ausgeführt. Die Änderungen betreffen ausschließlich
Lambda-Quellcode/-Tests, Installer-/Builder-Tests, den Dependency-Detector und
das versionierte Lambda-Artefakt sowie Dokumentation.

## 6. Offene Freigaben

1. **Q-05/Q-06/Q-07/Q-14:** Tenant-/Retention-/Cancel-/Legacy-Entscheidungen;
   P00-G bleibt deshalb deaktiviert.
2. **Q-11 P00-F Rest:** operative Aktivierung, Revocation in warmen
   Environments und Behandlung bestehender Signaturen.
3. **Terraform-Plan** (separate Freigabe).
4. **Terraform-Apply / AWS-Live-Verifikation** (separate Freigabe).
5. Secret-Value-Provisionierung out-of-band und ggf. CMK-Key-Policy.
6. **Q-12 Release-Label** und **Q-13 AWS-Testkonto**.
7. Deployment, Push und Main-Merge.

**Ergebnis B:** Lokale Entwicklung und Regression sind abgeschlossen; es fehlen
ausschließlich Live-, Deployment- und Owner-Freigaben.
