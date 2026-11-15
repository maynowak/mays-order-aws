# MO-RC4-RELEASE-01 — v0.6.0-rc.1 veröffentlicht / Main-Merge vorbereitet

**Status:** `RESULT A — RELEASE PUBLISHED / MAIN MERGE PREPARED`
**Datum:** 2026-11-14

## 1. Release-Entscheidung

- **Q-12:** `APPROVED — v0.6.0-rc.1`
- **Release-Version:** `v0.6.0-rc.1`
- **Deployment-/Teststack-Version:** `0.2.0` (unverändert)
- **Installer:** `0.1.0` (unverändert)
- **Module Builder:** `0.1.0` (unverändert)
- **Retention:** P00-G deaktiviert
- **APP_MANAGED:** default-off

## 2. Release-Commit und Tag

| Feld | Wert |
|---|---|
| Release-Commit | `5bc154e079b4d7ee9eedbbf5b45b1ecca5c35420` |
| Commit-Subject | `docs(release): approve rc4 v0.6.0-rc.1` |
| Tag | `v0.6.0-rc.1` (annotiert) |
| Tag-Objekt | `79628819717e4609d828581dff53055f2b32f8ec` |
| Tag-Ziel | `5bc154e079b4d7ee9eedbbf5b45b1ecca5c35420` |
| Remote-Branch | `origin/release/rc4-integration` |
| Remote-Tag | `v0.6.0-rc.1` → Tag-Objekt geprüft |

Der Tag liegt exakt auf dem freigegebenen Versions-Commit.
Nach dem Tag werden nur noch Audit-/Report-Dokumente auf dem Branch ergänzt;
der Tag bleibt unverändert.

## 3. Dokumentationsupdate

Aktualisiert:

- `docs/RELEASE_NOTES.md`
- `docs/release/RC4-MODULE-RELEASE-CANDIDATE.md`
- `docs/release/MO-RC4-P00-DECISION-REGISTER.md`
- `docs/PROJECT_STATUS.md`
- `docs/CHANGELOG.md`
- `docs/release/RC4-INTEGRATION-MANIFEST.md`

Die Komponentenversionen wurden **nicht** geändert. Die frühere Bezeichnung
`v0.5.0-rc.4` bleibt nur als verworfene Alternative dokumentiert.
`v0.5.0-rc.3` ist als historischer Doku-Stand ohne Git-Tag gekennzeichnet.

## 4. Veröffentlichung

- Branch gepusht: `368ac59..5bc154e`
- Tag separat gepusht: `v0.6.0-rc.1`
- Kein Force-Push
- Remote-Tag und Remote-Branch verifiziert
- Annotierter Tag mit Message:
  `Mays Orders RC4 v0.6.0-rc.1 — approved release candidate`

## 5. Main-Merge-Vorprüfung

| Prüfung | Ergebnis |
|---|---|
| `main` | `f597d1486292f7bd8bcaa7ac3e96276f091f9a07` |
| Release-Branch | `5bc154e` |
| Abstand | **192 Commits voraus, 0 dahinter** |
| Merge-Base | `f597d14` |
| `main` ist Ancestor | **JA** |
| `git merge-tree --write-tree --name-only main HEAD` | **PASS**, keine Konflikte |
| `git diff --check main...HEAD` | **PASS** |
| Main verändert | **NEIN** |
| Merge ausgeführt | **NEIN** |

Der reguläre Main-Merge ist technisch konfliktfrei vorbereitet. Er bleibt
eine separate Freigabe.

## 6. Verifikation des Releases

Der Release-Commit enthält ausschließlich Dokumentation auf Basis des bereits
getesteten und veröffentlichten RC4-Stands:

- Lambda 440/440 PASS
- Installer 674 PASS, 1 Skipped
- Module Builder 129/129 PASS
- Policy Gate 23/23 PASS
- E2E lokal 36 PASS, 5 Skipped; Live-E2E 4/4 PASS
- Seed 28/28 PASS
- Terraform fmt/init/validate PASS
- AWS Development Lifecycle: 58 create, Live-E2E, 58 destroy, State 0

Es wurden keine AWS-Aufrufe, kein Terraform Apply, kein Deployment und kein
Main-Merge in diesem Auftrag ausgeführt.

## 7. Offene Grenzen

- Produktive Aktivierung bleibt BLOCKED.
- P00-G Retention bleibt deaktiviert.
- Produktive Secret-/KMS-Aktivierung und P00-F-Betriebsaktivierung bleiben
  separate Owner-Gates.
- RIS-Integration bleibt NO-GO.
- Main-Merge bleibt separat freizugeben.

**Ergebnis A:** Release `v0.6.0-rc.1` veröffentlicht; Main-Merge vorbereitet,
nicht ausgeführt.
