# WIKI-CONSISTENCY-01 — DOKU-/WIKI-PRÜFUNG UND ERWEITERUNG — EXECUTION LOG

## 1. Status

- **Status:** `IMPLEMENTED / VERIFIED (DOKUMENTATION)` — **GREEN** für Inhalte,
  **YELLOW** für den dokumentierten CI/CD-Befund
- **Datum:** 2026-11-25
- **Repository:** `/home/dci-student/projects/Mays-Orders-AWS`
- **Branch:** `main`
- **Basis-HEAD vor diesem Task:** `543ef7501d9f41f254871f21657fda3f7350b043`
  (24.11.2026)
- **Scope:** `docs/wiki/**` auf Vollständigkeit prüfen, Behauptungen gegen Code,
  Tests, `docs/**` und `docs/reports/**` abgleichen, menschenlesbar erweitern,
  Release-Bilder einbinden, Agenten-Regel und Report ergänzen
- **Nicht im Scope:** Produktcode, AWS/Terraform-Mutation, RIS-Änderungen,
  Deployment, neue Fachfunktionen

## 2. Durchgeführte Abschnitte

1. **Inventur:** 12 Wiki-Dateien (README, 01–10, QUELLEN), 56 KB, untracked.
2. **Quellenabgleich:** `docs/PROJECT_STATUS.md`, `docs/RELEASE_NOTES.md`,
   `docs/roadmap/ROADMAP.md`, `docs/release/`, `api/`, `database/`,
   `order-lifecycle/`, `terraform/`, `installer/`, `module_builder/`,
   `docs/reports/`.
3. **Faktenprüfung:** Statusmaschine, API-Routen/Items, `orderDescription`,
   SKU-Leitlinie, Installer-/Builder-CLI, Testzahlen, Release-/RIS-Pin,
   CI/CD-Pipeline.
4. **Link-/Bildprüfung:** alle relativen Markdown-Links und Bilder automatisiert
   geprüft; anschließend 0 fehlende Ziele.
5. **Überarbeitung:** Seiten 01–12 inkl. neuem Dokumentationsportal (11) und
   FAQ (12); „Kurz erklärt"-Kästen, Beispiele, Tabellen, Bilder, Glossar.
6. **Governance:** Wiki-Pflege-Regel in `AGENTS.md`, `docs/AGENTS.md` und
   Playbook; Report + Auditlog; Status/Changelog.
7. **Checkpoint:** `git status`, `git diff --check`, Secret-Audit, Commit, Push
   (siehe §9).

## 3. Befunde und Korrekturen

| # | Befund | Bewertung | Maßnahme |
|---|---|---|---|
| W1 | Wiki war untracked und als „ZIP-Einfügung“ formuliert | Integrationslücke | Als `docs/wiki/` ins Repo übernommen; ZIP-/Einfüge-Wording ersetzt |
| W2 | Kein zentrales Dokumentationsportal; README-Liste nicht gespiegelt | Vollständigkeit | Seite 11 mit allen README-Dokumenten + API/Daten/Security/Wiki-Nachweisen |
| W3 | Keine menschenfreundliche FAQ/Erklärungen; viele Fachbegriffe | Lesbarkeit | Seite 12 (FAQ), „Kurz erklärt"-Kästen, Glossar stark erweitert |
| W4 | Testzahlen 674 vs. 81 nicht erklärt | Missverständnisrisiko | Kontext ergänzt: release-weite Suite vs. fokussiertes Modul; aktuelle Full-Läufe |
| W5 | CLI-/Pfadannahmen teils unsicher (`module_builder/README.md`, Upgrade) | Faktenrisiko | Gegen `--help`/`presets` verifiziert; genaue Build-/Upgrade-Beispiele; fehlende README entfernt |
| W6 | SKU-Leitlinie (MO-ORDER-DESCRIPTION-05) fehlte in der Wiki | Aktualität | In Orders-Seite, Privacy/Glossar und Dokumentationsportal ergänzt |
| W7 | Privacy-Grenzen zu pauschal | Genauigkeit | Datenkategorien-Tabelle inkl. ANONYMIZE/ERASE und Rest-Verknüpfung ergänzt |
| W8 | Keine Bilder außer Hero; Release-Bilder ungenutzt | Optik | RC4-Hero in README/07, Architektur-SVG in 02, historische v0.4-Grafik mit Datums-/Status-Caveat in 09 |
| W9 | D8-Source-Fail/CI-Lage nicht in der Wiki | Betriebstransparenz | Abschnitt in 07 mit Datum, Ursache, „kein Build/Plan/Deploy“ und Report-Links |
| W10 | Keine Wiki-Pflege-Regel für Agenten | Nachhaltigkeit | `AGENTS.md`, `docs/AGENTS.md`, Playbook ergänzt; QUELLEN-Pflegecheckliste |

## 4. Faktenprüfung (tatsächlich ausgeführt)

| Prüfung | Ergebnis |
|---|---|
| Release-Tag `v0.6.0-rc.1` | `5bc154e`; GitHub-Pre-Release veröffentlicht 2026-11-15 |
| AWS-Development-Lifecycle | 58 Create, 4/4 Live-E2E, 58 Destroy, State 0 (Release Notes) |
| RIS-Pin | Release Notes: `1dbb0cb` (RC3); keine RC4-Consumer-Abnahme |
| Lambda-Tests | **456/456 PASS** (Baseline 440; F012 +16) |
| Installer release-weit | **674 OK, 2 Skips** (aktueller Lauf); Release-Stand 674 PASS/1 Skip |
| Installer fokussiert | **81/81 PASS** (`installer.tests.test_installer`) |
| Policy Gate | **23 OK, 1 Skip** |
| E2E lokal | **36 OK, 5 Skips** |
| Module Builder | **129/129 PASS** |
| Seed | **28/28 PASS** |
| Lambda-ZIP | `sha256 117299c9…`, 47.552 B, 13 Module; Artefakt-Gate True |
| State Machine | `PENDING→CONFIRMED/CANCELLED`, `CONFIRMED→PROCESSING/CANCELLED`, `PROCESSING→SHIPPED`, `SHIPPED→DELIVERED`; sonst 409 |
| API-Routen | `POST /orders`, `GET /orders/{id}`, `GET /orders`, `PATCH /orders/{id}/status`; JWT |
| Items | `sku` (String, nicht leer), `quantity`/`unitPrice` (Integer ≥1); `lineTotal` serverseitig |
| `orderDescription` | optional, 1–1.024 Zeichen nach Trim; Privacy-Inspect/-Export/-Anonymize; nicht in `GET /orders` |
| SKU-Leitlinie | `api/endpoints.md` §2.1.1; `orderType` bleibt Routing; nicht normativ |
| Module Builder | Presets `complete`/`orders-service`; `orders-service` = 7 Module; `build --validate` read-only |
| Installer-CLI | `validate`, `plan`, `plan-destroy`, `deploy`, `destroy`, `backup`, `state`, `output`, `identity`, `gui`; `--guide` |
| D8/`directAWSGit` | D8: ManualApproval, aktuell Source-Fail (Bucket 404); Legacy `DetectChanges=false` |
| Link-/Bildprüfung | **0 fehlende Ziele** nach Erstellung dieses Reports |

## 5. Geänderte Dateien

- `docs/wiki/README.md` (Einstieg, Status, Neuigkeiten, Pflege, Bilder)
- `docs/wiki/01-produkt-und-rollen.md` (Kurz erklärt)
- `docs/wiki/02-architektur.md` (SVG, Terraform-Module, Kurz erklärt)
- `docs/wiki/03-orders-und-api.md` (Items, Fehler, SKU, Kurz erklärt)
- `docs/wiki/04-module-builder.md` (CLI, 7 Module, Grenzen, Quellen)
- `docs/wiki/05-installer.md` (Befehlstabelle, Grenzen, Kurz erklärt)
- `docs/wiki/06-sicherheit-und-datenschutz.md` (Datenkategorien, Restgrenzen)
- `docs/wiki/07-betrieb-und-release.md` (Hero, Zahlenkontext, CI/CD, Kurz erklärt)
- `docs/wiki/08-entwicklung-und-qualitaet.md` (Testbefehle, Wiki-Pflege)
- `docs/wiki/09-entwicklungschronik.md` (historische Grafik, F012/SKU/Wiki)
- `docs/wiki/10-glossar.md` (menschenlesbare Begriffe/Abkürzungen)
- `docs/wiki/11-dokumentationsportal.md` (neu)
- `docs/wiki/12-faq.md` (neu)
- `docs/wiki/QUELLEN.md` (Basis, Pflege, Portal, Bilder)
- `AGENTS.md`, `docs/AGENTS.md`, `docs/AI_AGENT_PLAYBOOK.md` (Wiki-Pflegeregel)
- `docs/PROJECT_STATUS.md`, `docs/CHANGELOG.md` (Status/Eintrag)
- `docs/AI_AUDITLOG.md` (Index + Eintrag)

## 6. Bilder

| Bild | Verwendung | Einordnung |
|---|---|---|
| `docs/assets/mays-orders-aws-rc4-hero.png` | README, Betrieb/Release | aktuelles RC4-Titelbild |
| `architecture/architecture-diagram.svg` | Architektur | früher Stand (Woche 1), ausdrücklich nicht vollständige RC4-Stückliste |
| `docs/release/img/ChatGPT Image …png` | Entwicklungschronik | historische v0.4.0-Grafik mit Datums-/Status-Caveat |

## 7. Klassifikation

- Wiki-Inhalt/Konsistenz: **GREEN**
- Links/Bilder/Pfade: **GREEN** (0 fehlend)
- Menschenslesbarkeit: **GREEN** (FAQ, Kurz erklärt, Glossar, Portal)
- CI/CD-Lage: **YELLOW** (D8 Source-Fail, kein Test-CI, `main` ungeschützt) —
  dokumentiert, nicht behoben
- Kein RED

## 8. Terraform / AWS

- Keine Terraform-/AWS-Operation ausgeführt; keine `.tf`- oder IAM-Änderung.
- Die CI/CD-Aussagen beruhen auf read-only `aws codepipeline`-Abfragen aus
  MO-ORDER-DESCRIPTION-02/03 (ManualApproval, Source-Fail, Legacy-Pipeline).
- Kein Deployment, kein Apply, keine RIS-Änderung.

## 9. Git

- Basis: `main`/`origin/main` `543ef75`; Worktree vor dem Task clean.
- `git diff --check`: PASS.
- Secret-Audit: keine Credentials/Secrets in Wiki, Bildern oder Reports.
- Commit/Push: dieser Doku-Commit; Remote-Verifikation im Abschlussbericht.
- Der Push löst erwartungsgemäß nur den bekannten D8-Source-Fail aus
  (kein Build/Plan/Deploy).

## 10. Offene Fragen / Risiken

- Die D8-Source-Störung (fehlender Bucket) bleibt offen; die Wiki beschreibt sie,
  behebt sie nicht.
- Die Wiki ist manuell zu pflegen; die AGENTS-Regel reduziert, aber verhindert
  Drift nicht automatisch.
- Die historische v0.4.0-Grafik ist optisch ansprechend, aber kein aktueller
  Status; sie ist entsprechend gekennzeichnet.
- Es gibt weiterhin kein Test-CI und keine Branch-Protection; lokale Tests und
  Reports bleiben die Evidenzbasis.

## 11. Nächste Schritte

1. Doku-Commit pushen und Remote-HEAD verifizieren.
2. Bei künftigen Features: Wiki-Seite + Portal + QUELLEN im selben Checkpoint
   aktualisieren (AGENTS-Regel).
3. Optional: CI-Artefakt-Bucket reparieren, damit die D8-Pipeline wieder
   Validate/Plan ausführen kann (separater Auftrag).

## 12. Resume Point

Wiki-Prüfung und -Erweiterung abgeschlossen. Nächster Schritt ist der
Doku-Checkpoint (Commit/Push) und danach die normale Weiterarbeit; keine
AWS-/Terraform-/RIS-Mutation.
