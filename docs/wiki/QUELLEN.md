# Quellen, Status und Pflege

## Referenzstand

- Repository: `maynowak/mays-order-aws`
- Dokumentationsbasis vor diesem Wiki-Commit: `main` `543ef7501d9f41f254871f21657fda3f7350b043` (24.11.2026)
- Erstellung/Überarbeitung dieser Wiki-Fassung: 25.11.2026
- GitHub-Pre-Release: [`v0.6.0-rc.1`](https://github.com/maynowak/mays-order-aws/releases/tag/v0.6.0-rc.1)
- Wiki-Ort: `docs/wiki/` (Teil des Repositorys, nicht ein separates Wiki-Repo)

## Dokumentationsportal

Die vollständige, verlinkte Übersicht der kanonischen Detaildokumente steht in
[`11-dokumentationsportal.md`](11-dokumentationsportal.md). Sie spiegelt die
Documentation-Liste der Root-`README.md` und ergänzt API-, Daten-, Security- und
Wiki-Nachweise.

## Autoritative Quellen im Repository

| Frage | Primärquelle |
|---|---|
| Was ist aktuell erledigt/blockiert? | `docs/PROJECT_STATUS.md`, `docs/roadmap/ROADMAP.md` |
| Was umfasst das veröffentlichte RC4? | `docs/RELEASE_NOTES.md`, `docs/release/RELEASE-v0.6.0-rc.1.md`, `docs/release/RC4-MODULE-RELEASE-CANDIDATE.md` |
| Welche API-Verträge gelten? | `api/endpoints.md`, `api/test-cases.md` |
| Wie ändern sich Order-Status? | `order-lifecycle/` |
| Wie sehen Schema und Zugriffsmuster aus? | `database/` und `docs/diagnostics/dynamodb/` |
| Wie ist die Infrastruktur entworfen? | `architecture/`, `terraform/`, `docs/architecture/` |
| Wie wird gebaut/installiert? | `docs/INSTALLER_GUIDE.md`, `docs/INSTALLER-LIFECYCLE.md`, `module_builder/`, `installer/` |
| Welche Tests/Evidence existieren? | `docs/reports/`, `tests/`, `docs/release/` |
| Was ist Datenschutz-/Security-Status? | `docs/security/`, `docs/reports/MAYS-ORDERS-DSGVO-*`, `docs/reports/MO-RC4-P00-*` |
| Was wurde wann geprüft? | `docs/AI_AUDITLOG.md` |

## Leseregeln

1. Aktuelle Statusseite, Release-Notizen und Roadmap gegen das Datum des Reports
   prüfen. Alte Reports bleiben gültige historische Evidenz, aber nicht
   automatisch aktueller Zustand.
2. Tag/Commitgrenze beachten. Dateien auf `main` können nach einem Release-Tag
   aktualisiert worden sein.
3. Lokale Tests, Artifact-Build, Terraform-Validierung, AWS-Live-Test und
   Produktion voneinander unterscheiden.
4. Bei Unsicherheit gilt die fachliche Single Source of Truth des jeweiligen
   Bereichs und der aktuelle ausführliche Nachweis.

## Pflege dieser Wiki (verbindlich)

Bei jeder Änderung an API, Architektur, Status, Release, Tests, Installer,
Module Builder oder Privacy:

1. **Betroffene Seite aktualisieren** (01–11) und neue Begriffe ins Glossar.
2. **`README.md`**: Status, „Neu seit dem RC4-Tag" und Einstiege prüfen.
3. **`QUELLEN.md`**: Basis-Commit/Datum und Quellenliste prüfen.
4. **`11-dokumentationsportal.md`**: neue/umbenannte Dokumente verlinken.
5. **Links/Bilder lokal prüfen**; keine toten Pfade.
6. **Dokumentations-Checkpoint**: `git status` → `git diff --check` →
   Secret-Audit → Commit → Push. Keine Pass-/Verified-Aussage ohne Evidence.

Die verbindliche Agenten-Regel steht in `AGENTS.md` (Root) und
`docs/AGENTS.md`: Wiki-Pflege ist Teil des Dokumentations-Checkpoints.

## Bilder und Quellen

- Titelbild: `docs/assets/mays-orders-aws-rc4-hero.png` (RC4-Release).
- Architektur: `architecture/architecture-diagram.svg` (früher Stand, Woche 1)
  und Mermaid-Diagramme in den Wiki-Seiten.
- Historische Release-Grafik: `docs/release/img/` (v0.4.0; nur mit
  Datums-/Statuskennzeichnung verwenden).

## Was diese Wiki nicht ist

- Keine Rechtsberatung und keine DSGVO-Konformitätserklärung.
- Keine Produktionsfreigabe und kein Deployment-Nachweis.
- Keine vollständige API-Referenz; diese bleibt `api/endpoints.md`.
- Keine fortlaufende Statusquelle; diese bleibt `docs/PROJECT_STATUS.md`.
