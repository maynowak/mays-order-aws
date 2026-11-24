# MO-ORDER-DESCRIPTION-04 — DOCUMENTATION CONSISTENCY SYNC

**Status:** `IMPLEMENTED / VERIFIED (DOKUMENTATION)` · **Datum:** 2026-11-24
**Basis:** `main` / `origin/main` `0fc8972` (MO-ORDER-DESCRIPTION-03 integriert)
**Scope:** Abgleich aller aktuellen Doku-Quellen gegen den integrierten Stand;
keine Produkt-, AWS-, Terraform- oder RIS-Änderung.

## 1. Anlass

Nach der Main-Integration von `orderDescription` (MO-ORDER-DESCRIPTION-01…03)
wurde geprüft, ob alle aktuellen Dokumentationsquellen den neuen Vertrag und den
Integrationsstand widerspiegeln. Historische Wochen-/Release-/Report-Dokumente
werden nicht rückwirkend umgeschrieben.

## 2. Gefundene Lücken

| # | Datei | Befund |
|---|---|---|
| D1 | `docs/PROJECT_STATUS.md` | „Current Task/Checkpoint" sagte noch „Merge Review offen" und `main` `1eaa14e` |
| D2 | `docs/features/F012-order-description.md` | Status/Pending/Checkpoint noch vor Integration |
| D3 | `docs/CHANGELOG.md` | Boundaries sagten „kein Merge, Merge Review ausstehend" |
| D4 | `architecture/architecture-decisions.md` | D-1: „API-Body bleibt unverändert" ohne additiven Nachtrag |
| D5 | `docs/phase1-order-message-status-model.md` | Public-API-Feldtabelle ohne `orderType`/`orderDescription` (Phase-1-Snapshot) |
| D6 | `docs/diagnostics/dynamodb/schema-reference.md` | Stand-Datum unverändert (2026-11-03) |
| D7 | `tests/test-results.md` | Kein Eintrag für die 456/456-Verifikation (nur Woche 1/2) |
| D8 | `api/test-cases.md` | Keine Testfälle für das neue Feld |
| D9 | `docs/roadmap/ROADMAP.md` | `Current main`/`Updated` veraltet, kein Feature-Eintrag |

## 3. Durchgeführte Änderungen

- **D1:** PROJECT_STATUS auf `main` `0fc8972`, Integration (Fast-Forward,
  Cherry-Pick, Evidence) und „kein Deployment" aktualisiert; Application Code
  als „in main integriert, nicht deployed" gekennzeichnet.
- **D2:** F012 auf „in `main` integriert" gesetzt; Completed Tasks um Review und
  Integration ergänzt; Pending nur noch Deployment.
- **D3:** Changelog-Boundaries auf Integration/Push und bekannten D8-Source-Fail
  aktualisiert.
- **D4:** Dated Nachtrag in ADR D-1: optionales `orderDescription`, keine neuen
  Pflichtfelder/Identitäts-/Routing-/Preisänderungen.
- **D5:** Phase-1-Snapshot mit datiertem Hinweis und den zwei additiven API-Feldern
  ergänzt; aktueller Vertrag bleibt `api/endpoints.md`.
- **D6:** Schema-Referenz-Stand auf 2026-11-24 gesetzt.
- **D7:** Neuer Test-Results-Abschnitt 2026-11-23/24 mit 456/456, 16/16,
  Installer 81/81, Builder 129/129, Seed 28/28, ZIP/Artefakt-Gate; Live-API
  ausdrücklich NOT RUN.
- **D8:** API-Testfälle T-17…T-20 als Unit-/Service-verifiziert ergänzt; HTTP-E2E
  nicht ausgeführt.
- **D9:** Roadmap `Updated`/`Current main` aktualisiert und ORD-01 (DONE, kein
  Deployment) ergänzt.

## 4. Verifikation

- Systematischer Abgleich: alle aktuellen `.md`-Dateien mit `orderType` enthalten
  nun auch `orderDescription` (ohne Historie/Reports/Release).
- `git diff --check`: PASS; keine Code-, Terraform-, CI- oder RIS-Datei geändert.
- Keine Tests erforderlich (reine Dokumentation); die zitierten Testergebnisse
  stammen aus den tatsächlich ausgeführten Läufen vom 2026-11-23.
- Keine AWS-/Terraform-/RIS-Mutation, kein Deployment.

## 5. Grenzen

- Historische Dokumente (`docs/reports/`, `docs/release/`, `docs/initialweekcontest/`,
  Wochen-Feature-Dokus) bleiben unverändert; sie beschreiben ihren jeweiligen
  Zeitpunkt.
- Die D8-Source-Störung (fehlender CI-Artefakt-Bucket) bleibt als bekannter
  operativer Befund offen und wurde nicht behoben.
- Ein Deployment von `orderDescription` ist weiterhin separat freizugeben.
