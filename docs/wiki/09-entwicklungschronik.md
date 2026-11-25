# 09 · Entwicklungschronik

Diese Chronik fasst Meilensteine zusammen. Sie ersetzt nicht die verlinkten
Reports: Details zu Commits, Ressourcenzahlen und Testläufen sind im jeweiligen
Checkpoint dokumentiert.

![Historische Projektgrafik v0.4.0 (Sept. 2026)](<../release/img/ChatGPT Image 14. Sept. 2026, 15_54_35.png>)

*Historische Release-Grafik aus dem Repository (`v0.4.0`, 14.09.2026). Sie zeigt
den damaligen Stand und ist **kein** aktueller Status- oder Produktionsnachweis;
maßgeblich sind `PROJECT_STATUS.md`, Release Notes und die aktuellen Reports.*

| Etappe | Entwicklung | Beleg / Einordnung |
|---|---|---|
| Frühe Wochen | Anforderungen, API, Statusmaschine, DynamoDB-Zugriff, Authentifizierung und erste Tests ausgearbeitet; frühe Laufzeitstände wurden später auf Python 3.14 umgestellt. | `docs/initialweekcontest/`, `docs/features/`, `docs/reports/WEEK-*.md`; frühe Stände sind historisch |
| Order-Core | Cognito-JWT, HTTP API, Lambda, DynamoDB, Monitoring und Terraform-Infrastruktur zum vollständigen Order-Lebenszyklus zusammengeführt. | `docs/PRODUCT_OVERVIEW.md`, Architektur- und T011-Berichte |
| Recovery & Cognito-Backup | Backup, Wiederherstellung, Monitoring/Benachrichtigung und Multi-Projekt-/Remote-State-Schutz schrittweise erarbeitet. | `docs/reports/BACKUP-*`, `COGNITO-BACKUP-*` |
| Installer-Ausbau | Projekt-/AWS-Kontext, Remote State, Plan-/Destroy-Schutz, Kollisions-Preflight, Artefaktintegrität, Policy Gate und Upgrade-Sicherheit ergänzt. | Installer-H1/H2/D8, Collision- und MO-Installer-Berichte |
| Privacy / DSGVO-Arbeiten | Inspect/Export/Erase-Fähigkeiten, interne Privacy-Grenze, Identitäts-/Berechtigungsprüfungen, Secret-Provider- und KMS-Optionen untersucht bzw. implementiert; Retention und produktive Aktivierung blieben separat begrenzt. | `docs/reports/MAYS-ORDERS-DSGVO-*`, `MO-RC4-P00-*`; keine pauschale Rechtskonformitäts- oder Produktionsfreigabe |
| Modulbau & RC3-Vorbereitung | Deterministischer Module Builder mit `complete`, `orders-service` und expliziter Modulauswahl; generierte Projekte übernehmen Policy Gate und Artefakte. RIS-Konsumentenprüfung wurde für den RC3-Stand belegt. | `docs/reports/MAYS-ORDERS-MODULE-BUILDER-*`, `MO-RC3-P03…P08`; `v0.5.0-rc.3` war laut Status ein Doku-Stand, kein Tag |
| RC4-Teststack | Owner-/Consumer-Isolation, SQS-Worker, DLQ, GSI3/Recovery und internes Privacy-Verhalten im abgegrenzten RC4-Modulstand entwickelt und lokal sowie in einem isolierten AWS-Development-Zyklus geprüft. | RC4-Berichte, `RELEASE_NOTES.md`; Development-Stack wurde danach vollständig entfernt |
| RC4 Release | Release-Owner gab `v0.6.0-rc.1` frei; annotierter Tag, GitHub-Pre-Release und Main-Merge wurden dokumentiert. | `docs/release/RELEASE-v0.6.0-rc.1.md`, `docs/PROJECT_STATUS.md` |
| Nach Release: F012 | Optionales `orderDescription`-Feld inkl. Validierung, Speicherung und Privacy-Auswertung ergänzt, lokal getestet und in `main` integriert. Kein AWS-Deployment. | `docs/features/F012-order-description.md`, Reports `MO-ORDER-DESCRIPTION-01…03`, `docs/CHANGELOG.md` |
| SKU-Leitlinie | Dokumentiert, dass `sku` frei/nicht kataloggeprüft ist und eigene Konventionen als informativer Order-Art-Hinweis möglich sind — ohne `orderType` zu ersetzen. | `api/endpoints.md` §2.1.1, `MO-ORDER-DESCRIPTION-05-SKU-GUIDANCE.md` |
| Doku-Konsolidierung | Status, API-Testfälle, Changelog, Roadmap und Schema-Doku auf F012 nachgezogen; zuletzt am 24.11.2026 laut Projektstatus. | `MO-ORDER-DESCRIPTION-04-DOC-SYNC.md`, `docs/roadmap/ROADMAP.md` |
| Wiki-Konsistenz | Diese Wiki gegen Code, Tests und Reports geprüft; Bilder, Dokumentationsportal, Glossar und Pflege-Regeln ergänzt. | `docs/wiki/`, `WIKI-CONSISTENCY-01-EXECUTION_LOG.md` |

## Warum es mehrere Versionsnummern gibt

- `v0.5.0-rc.1`/`rc.2` waren frühere Release Candidates.
- `v0.5.0-rc.3` wurde dokumentiert und vorbereitet, laut aktuellem
  `PROJECT_STATUS.md` aber **nicht getaggt**.
- `v0.6.0-rc.1` ist das freigegebene RC4-Release-Label.
- `0.1.0` sind die einzelnen Komponenten-Versionen von Module Builder und
  Installer.
- `0.2.0` war die Deployment-/Teststack-Version.

Release-, Komponent- und Deployment-Versionen bezeichnen unterschiedliche
Grenzen. Der Git-Tag bindet einen konkreten Code-Commit; spätere Doku-Commits
auf `main` ändern den Inhalt des Tags nicht.

## Offene Themen im dokumentierten Status

- Produktionsdeployment und produktive Privacy-/Secret-Aktivierung;
- fachlich/rechtlich entschiedene Retention- und Löschfristen;
- Consumer-Acceptance für ein neueres RC4-Modul in RIS;
- weitere Produktions-/Multi-Account-Nachweise;
- full CI/CD Build-/Plan-/Deployment-Gates; Pipeline-Befunde in Status/Roadmap
  prüfen.

Die aktuelle kanonische Roadmap ist `docs/roadmap/ROADMAP.md`; ältere
„Future Extensions“-Dokumente sind Ideensammlungen, kein aktueller Beschluss.
