# MO-RC4-POST-MERGE-DOC-SYNC-01 — Release- und Roadmap-Sync

**Status:** `RESULT A — DOC SYNC & ROADMAP COMPLETE`
**Datum:** 2026-11-15
**Repository:** `maynowak/mays-order-aws`
**Branch:** `main`
**Release:** `v0.6.0-rc.1`

## 1. Tatsächlicher Git-Ausgangsstand

- Erwarteter lokaler Main-HEAD: `ece8b1e`
- Tatsächlicher lokaler Main-HEAD: `ece8b1e`
- Remote-Main-HEAD: **`7724c43`**
- Abweichung: lokaler `main` war **2 Commits hinter** Remote
- Ursache: autorisierte manuelle Release-Dokumente der Projektinhaberin:
  - `b6bf339 Release notes pdf and md`
  - `7724c43 add realese image`
- Nach Freigabe: **Fast-Forward** auf `7724c43`, keine lokalen Commits überschrieben
- Release-Tag `v0.6.0-rc.1` unverändert auf
  `5bc154e079b4d7ee9eedbbf5b45b1ecca5c35420`
- Working Tree vor Änderungen: clean

## 2. Aktualisierte Dokumente

| Dokument | Änderung |
|---|---|
| `docs/PROJECT_STATUS.md` | RC4-Release, Tag, GitHub-Pre-Release, Main-Merge, Main-Push, README/PDF und Non-Production-Status synchronisiert |
| `docs/CHANGELOG.md` | Post-Merge-Doc-Sync und abgeschlossener Main-Merge ergänzt |
| `docs/RELEASE_NOTES.md` | Kanonische Release-Dateien, Post-Merge-Status und GitHub-Asset-Hinweis ergänzt |
| `docs/release/RC4-INTEGRATION-MANIFEST.md` | Release Readiness auf „Main merged + pushed“ aktualisiert |
| `README.md` | Offizielle Release-Dokumente/PDF und Roadmap verlinkt |
| `docs/release/RELEASE-v0.6.0-rc.1.md` | Post-Merge-Addendum und aktuelle Tag-/Main-Angaben ergänzt; Release-Body erhalten |
| `docs/release/RELEASE-v0.6.0-rc.1.pdf` | Addendum-Seite vorangestellt; ursprünglicher 4-Seiten-Body erhalten |
| `docs/roadmap/future-extensions.md` | Als historischer Ideenkatalog markiert; kanonische Roadmap verlinkt |

Keine Produktcode-, Tag-, Versions- oder AWS-Änderung.

## 3. Release-Artefakte im Vergleich

| Artefakt | Umfang | SHA-256 |
|---|---|---|
| `docs/release/RELEASE-v0.6.0-rc.1.md` | offizielles Release-Dokument + Post-Merge-Addendum | — |
| `docs/release/RELEASE-v0.6.0-rc.1.pdf` | 5 Seiten (1 Addendum + ursprünglicher 4-Seiten-Body) | `165bf8b3bd69632e1b601c104a95c66b65b368ba339557d4b7dbed853b046ae7` |
| `docs/RELEASE_NOTES.md` | aggregierte Post-Merge-Release-Notes | — |
| `docs/release/MAYS-ORDERS-AWS-v0.6.0-rc.1.pdf` | 7-seitiges detailliertes Release-Paket | `968a9276617f681e1534f60855de19c6a51889a3346c02907392df2a945438da` |

Erkenntnisse:

- Das offizielle Release-Dokument enthält den Release-Body und eine klare
  Post-Merge-Abgrenzung.
- Das detaillierte PDF enthält zusätzlich Architektur, ausführlichere
  Security-/Testabschnitte und die vollständige Paketbeschreibung.
- Der ursprüngliche 4-Seiten-Body wurde nicht gelöscht; das Addendum wurde
  vorangestellt.
- **GitHub-Release-Asset bleibt unverändert**:
  `MAYS-ORDERS-AWS-v0.6.0-rc.1.pdf`. Ein Austausch gegen das kanonische PDF
  benötigt eine separate Freigabe.

## 4. Roadmap

Kanonische Datei:

```text
docs/roadmap/ROADMAP.md
```

`docs/roadmap/future-extensions.md` bleibt als historischer Ideenkatalog
erhalten und verweist auf die kanonische Roadmap. Es gibt keine parallele
Status-Roadmap.

Roadmap-Bereiche:

- RC4 — `DONE`
- Module Builder — überwiegend `DONE`, Modulvertrag `IN PROGRESS`
- Installer — `DONE`
- Security — Mechanismen `DONE`; Produktionsaktivierung `BLOCKED`
- Privacy — interne Funktionen `DONE`; Retention/DSGVO-Betrieb `BLOCKED`
- RIS-Integration — `PLANNED`
- CI/CD — Security-Workflows `IN PROGRESS`; vollständige Pipeline `PLANNED`
- Production Readiness — `IN PROGRESS`/`BLOCKED`
- Nächster Release — `PLANNED`, keine Versionsnummer festgelegt

## 5. Offene Entscheidungen

- **Q-05:** `tenantId` — `READY_FOR_OWNER`
- **Q-06:** Retention-Fristen — `BLOCKED_BY_EXTERNAL_DECISION`
- **Q-07:** Cancel-Anonymisierung — `READY_FOR_OWNER`
- **Q-14:** Bestandsdaten ohne Retention — `READY_FOR_OWNER`
- **Q-11 P00-F:** operative Rotation/Revocation, Warm-Environment und
  bestehende Signaturen — offen
- **Produktive Privacy-Secret-Aktivierung** — `BLOCKED`
- **KMS-Key-Policy bei externem CMK** — `BLOCKED`
- **Production-Deployment-Freigabe** — `BLOCKED`
- **Q-12:** `APPROVED — v0.6.0-rc.1` — bleibt geschlossen

## 6. Prüfergebnisse

- Relative Dokumentationslinks: **keine fehlenden Ziele**
- Release-Versionen: `v0.6.0-rc.1`, Builder `0.1.0`, Installer `0.1.0`,
  Deployment/Teststack `0.2.0`
- Tag-Ziel: unverändert `5bc154e`
- Main-Merge: `82f7ae1`; Main-Push: abgeschlossen
- Produktivdeployment: nicht durchgeführt
- Keine AWS-Aufrufe, keine Terraform-Operation, kein neuer Worktree
- `git diff --check`: PASS

## 7. Git

- Dokumentationsänderungen: dieser Commit
- Vorheriger Main-Baseline: `7724c43`
- Remote-Main wird nach diesem Commit aktualisiert
- Auditlog: aktualisiert
- Working Tree nach Commit: clean

**Ergebnis A:** Release-Dokumentation, kanonische Referenzen und Roadmap sind
synchronisiert; `main` wird regulär gepusht. Kein Produktions- oder
AWS-Deployment.
