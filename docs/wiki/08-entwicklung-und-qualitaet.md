# 08 · Entwicklung und Qualität

## Repository-Karte

| Pfad | Zweck |
|---|---|
| `lambda/` | Python-Laufzeitcode, Handler, Builder der Deploy-Artefakte und Lambda-Tests |
| `terraform/` | Root-Infrastruktur, Child-Module und Plan-Policy |
| `module_builder/` | Presets, Katalog, Generator, Upgrade und Tests |
| `installer/` | CLI, Kontext-/Plan-/State-/Artefakt-Schutz und Tests |
| `api/`, `database/`, `order-lifecycle/`, `security/` | fachliche Verträge / Single Sources of Truth |
| `architecture/` | Diagramme, Architekturentscheidungen und Installationskonzept |
| `docs/features/` | Feature-Status und Belege |
| `docs/reports/` | ausführliche Arbeits- und Verifikationsberichte |
| `docs/release/` | Releases, RC-Dossiers und Gates |
| `docs/runbooks/` | operative Abläufe |

## Fachliche Quellen vor einer Änderung

Lies zuerst `docs/AGENTS.md`, `docs/PROJECT_STATUS.md` und das relevante
Fachgebiet. Für API-Änderungen gilt `api/endpoints.md`, für Modell/Indices
`database/`, für Übergänge `order-lifecycle/`, für IAM `security/`, für
Architekturentscheidungen `architecture/architecture-decisions.md`.

Der Status in `PROJECT_STATUS.md` kann gegenüber Code und jüngsten Berichten
verzögert sein. Prüfe Zeitstempel, Git-Verlauf, Feature-Bericht und konkrete
Nachweise gegeneinander und dokumentiere die Grenze transparent.

## Prüfebenen

| Ebene | Was sie zeigt | Was sie allein nicht zeigt |
|---|---|---|
| Unit-Tests mit Fakes/Mocks | lokale Handler-/Regellogik | AWS-Service-Verhalten |
| Build und Hash | reproduzierbares/identisches ZIP | dass genau dieses ZIP live läuft |
| Terraform `validate` | Konfiguration ist syntaktisch/konsistent | Kosten, Ownership, erfolgreiche Bereitstellung |
| Terraform Plan + Policy Gate | geplante Änderungen und Regelprüfung | menschliche Freigabe oder Live-Erfolg |
| AWS-Live-E2E | tatsächlich getestete AWS-Pfade im genannten Testkontext | Produktion oder andere Konten/Regionen |
| Production Evidence | nur den nachgewiesenen Produktionsumfang | nicht getestete Pfade oder Zukunftszustände |

RC4-Tests enthalten viele lokale Fakes. Die konsolidierte Testsuite ist daher
kein Ersatz für authentifizierte Live-Tests zu DLQ/Retry, GSI3, Recovery,
Cleanup und Consumer-Verhalten. Siehe insbesondere
`docs/reports/MO-RC4-TESTSUITE-CONSOLIDATION-13A.md` und späteren Live-/Release-
Nachweis. Historische Testberichte nicht als gerade eben erneut ausgeführte
Tests beschreiben.

## Lokale Prüfbefehle

Beispiele anhand der Repository-Anweisungen; Voraussetzungen und exakte
Versionen im aktuellen Checkout prüfen:

```bash
# Lambda
cd lambda
python3 -m compileall -q src tests
PYTHONPATH=src python3 -m unittest discover -s tests
python3 build_zip.py

# Installer: release-weite Suite (aktuell 691 Tests, 2 Skips)
python3 -m unittest discover -s installer/tests
# Fokussiertes Installer-Modul (aktuell 98 Tests)
python3 -m unittest installer.tests.test_installer
# Dependency Detector + SARIF Adapter (offline, 33 Tests)
python3 -m unittest installer.tests.test_installer.TestDependencyDetector installer.tests.test_installer.TestSarifAdapter
# Policy Gate (aktuell 23 Tests)
python3 -m unittest installer.tests.test_policy_gate

# E2E-Harness (lokal; 36 Tests, einige Live-Skips)
python3 -m unittest discover -s tests

# Terraform (passendes Modul/Root)
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
```

> **Für Einsteiger:** Die Zahlen sind keine Note, sondern eine Landkarte:
> 691 Installer-Tests bedeuten „viele Schutzfälle geprüft“, 98 fokussierte Tests
> bedeuten „das gerade geänderte Installer-Modul geprüft“. Keine dieser Zahlen
> ist ein AWS-Live- oder Produktionsnachweis.

AWS-Live-Tests sind gesondert vorzubereiten und benötigen passende Identität,
Testdaten, Cleanup-Konzept und Freigabe. `plan` ist kein `apply`, und
`validate` ist kein Live-E2E.

## Dokumentations- und Git-Checkpoint

Das Projekt verlangt nachvollziehbare Evidenz: Report, tatsächlich gelaufene
Prüfungen, Build/Validierung, Git-Status, `git diff --check`, Secret-Audit,
Commit und Push. Feature-Doku und `PROJECT_STATUS.md` werden fortlaufend
aktualisiert. Statuswerte wie `IMPLEMENTED`, `TESTED`, `VERIFIED`, `BLOCKED`
oder `NOT TESTED` verwenden und nicht überdehnen.

## Wiki pflegen

Diese Wiki ist **Teil des Repositorys** (`docs/wiki/`) und wird wie Code
behandelt. Bei Änderungen an API, Architektur, Status, Release, Tests, Installer,
Module Builder oder Privacy:

1. betroffene Wiki-Seite (01–11) aktualisieren,
2. `README.md`, `QUELLEN.md` und `11-dokumentationsportal.md` prüfen,
3. neue Fachbegriffe ins Glossar aufnehmen,
4. Links/Bilder lokal kontrollieren,
5. den normalen Dokumentations-Checkpoint ausführen.

Die verbindliche Regel steht in `AGENTS.md` und `docs/AGENTS.md`. Die Wiki
richtet sich bewusst an **Menschen** (Einstieg, Erklärung, Beispiele); die
kanonische Tiefe bleibt in den verlinkten Fachdokumenten.
