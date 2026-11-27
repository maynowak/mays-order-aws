# 11 · Dokumentationsportal

Die Root-`README.md` und dieses Repository enthalten die kanonischen
Detaildokumente. Diese Seite ist der **Einstieg in die Tiefe**: Sie bündelt die
wichtigsten Quellen, damit Wiki und Detaildoku nicht auseinanderlaufen.
Historische Reports bleiben Nachweise ihres Zeitpunkts; für den aktuellen Stand
gelten `docs/PROJECT_STATUS.md` und `docs/roadmap/ROADMAP.md`.

## Release, Status und Nachweise

| Dokument | Inhalt | Pfad |
|---|---|---|
| Release Notes | RC4-Release, Versionen, Testzahlen, Grenzen | [`docs/RELEASE_NOTES.md`](../RELEASE_NOTES.md) |
| Official Release Document | kanonisches RC4-Dossier (Markdown) | [`RELEASE-v0.6.0-rc.1.md`](../release/RELEASE-v0.6.0-rc.1.md) |
| Official Release PDF | kanonisches RC4-Dossier (PDF) | [`RELEASE-v0.6.0-rc.1.pdf`](../release/RELEASE-v0.6.0-rc.1.pdf) |
| Detailed Release Package PDF | ausführliches Release-Paket | [`MAYS-ORDERS-AWS-v0.6.0-rc.1.pdf`](../release/MAYS-ORDERS-AWS-v0.6.0-rc.1.pdf) |
| RC4 Module Release Candidate | Modul-/Builder-Release-Kandidat | [`RC4-MODULE-RELEASE-CANDIDATE.md`](../release/RC4-MODULE-RELEASE-CANDIDATE.md) |
| RC4 Final Report | Abschluss und Grenzen des RC4-Modulscopes | [`MO-RC4-FINAL-01.md`](../reports/MO-RC4-FINAL-01.md) |
| AWS Development Lifecycle Report | 58-Create/Live-E2E/58-Destroy-Nachweis | [`MO-RC4-AWS-LIFECYCLE-FINAL-01.md`](../reports/MO-RC4-AWS-LIFECYCLE-FINAL-01.md) |
| RC4 Release Report | Release-Paketierung und Entscheidungen | [`MO-RC4-RELEASE-01.md`](../reports/MO-RC4-RELEASE-01.md) |
| Projektstatus | aktueller Stand, Checkpoints, Blocker | [`docs/PROJECT_STATUS.md`](../PROJECT_STATUS.md) |
| RC4/RIS-Kompatibilitätskandidat | laufender Stand, lokale QA und offene Gates | [`MO-RC4-RIS-COMPATIBILITY-FIX-01.md`](../features/MO-RC4-RIS-COMPATIBILITY-FIX-01.md) |
| Roadmap | kanonische Entwicklungsplanung | [`docs/roadmap/ROADMAP.md`](../roadmap/ROADMAP.md) |
| Auditlog | Prüfungen, Reports, Entscheidungen | [`docs/AI_AUDITLOG.md`](../AI_AUDITLOG.md) |

## Architektur und Produkt

| Dokument | Inhalt | Pfad |
|---|---|---|
| Architecture | Architektur, Komponenten, Sicherheitsgrenzen | [`MAYS-ORDERS-ARCHITECTURE.md`](../architecture/MAYS-ORDERS-ARCHITECTURE.md) |
| Architektur-Entscheidungen | ADRs und additive Nachträge | [`architecture-decisions.md`](../../architecture/architecture-decisions.md) |
| Architecture & Security | technische Sicherheits- und Betriebssicht | [`architecture-and-security.md`](../../architecture/architecture-and-security.md) |
| Product Overview | Produkt-, Rollen- und Fähigkeitssicht | [`PRODUCT_OVERVIEW.md`](../PRODUCT_OVERVIEW.md) |
| Request Flow | Weg eines API-Aufrufs | [`request-flow.md`](../../architecture/request-flow.md) |
| Networking | Netz-/VPC-Grenzen | [`networking.md`](../../architecture/networking.md) |
| Backend/State | S3-Backend, Lock, Workspaces | [`MAYS-ORDERS-BACKEND-STATE.md`](../architecture/MAYS-ORDERS-BACKEND-STATE.md) |

## API, Daten und Diagnose

| Dokument | Inhalt | Pfad |
|---|---|---|
| API-Vertrag | Routen, Felder, Validierung, Fehler | [`api/endpoints.md`](../../api/endpoints.md) |
| API-Testfälle | T-01…T-20 inkl. `orderDescription` | [`api/test-cases.md`](../../api/test-cases.md) |
| API-Dokumentation | Schemas und Konsistenzregeln | [`api/api-documentation.md`](../../api/api-documentation.md) |
| DynamoDB-Design | Item-Modell, Schlüssel, Indizes | [`database/dynamodb-design.md`](../../database/dynamodb-design.md) |
| Schema-Referenz | code-verifizierter Ist-Stand | [`schema-reference.md`](../diagnostics/dynamodb/schema-reference.md) |
| Security & IAM (Diagnose) | Zugriff, PII, Anonymisierung | [`security-and-iam.md`](../diagnostics/dynamodb/security-and-iam.md) |
| State Machine | Übergangsmatrix | [`transition-rules.md`](../../order-lifecycle/transition-rules.md) |

## Installer und Terraform

| Dokument | Inhalt | Pfad |
|---|---|---|
| Installer Guide | Bedienung, Flags, Sicherheitsgates | [`docs/INSTALLER_GUIDE.md`](../INSTALLER_GUIDE.md) |
| Installer Lifecycle | Validate → Plan → Approval → Deploy → Verify → Destroy | [`docs/INSTALLER-LIFECYCLE.md`](../INSTALLER-LIFECYCLE.md) |
| Terraform Policy Gate | Plan-Regeln und Ressourcen-Policy | [`docs/TERRAFORM_POLICY_GATE.md`](../TERRAFORM_POLICY_GATE.md) |
| Terraform-Root | Root-Modul, Kern- und optionale Child-Module | [`terraform/`](../../terraform/) |
| Bootstrap | State-Bucket/Lock-Infrastruktur | [`terraform/bootstrap/`](../../terraform/bootstrap/) |

## Module Builder

| Dokument | Inhalt | Pfad |
|---|---|---|
| Module Builder Foundation | Presets, Generator, Grenzen | [`MAYS-ORDERS-MODULE-BUILDER-FOUNDATION-01.md`](../reports/MAYS-ORDERS-MODULE-BUILDER-FOUNDATION-01.md) |
| Module Builder Hardening | deterministische Artefakte, Policy Gate | [`MAYS-ORDERS-MODULE-BUILDER-HARDENING-01.md`](../reports/MAYS-ORDERS-MODULE-BUILDER-HARDENING-01.md) |
| Module Builder Options | Modulauswahl, Bewertungen, Optionen | [`MAYS-ORDERS-MODULE-BUILDER-OPTIONS-01.md`](../reports/MAYS-ORDERS-MODULE-BUILDER-OPTIONS-01.md) |
| Orders-Service Module Contract | feste Orders-Service-Komposition inkl. optionalem Result-Transport | [`MAYS-ORDERS-MODULE-CONTRACT-01.md`](../reports/MAYS-ORDERS-MODULE-CONTRACT-01.md) |
| Module Integration & Test Guide | Test-/Integrationsleitfaden für Modulnutzer | [`MAYS_ORDERS_TERRAFORM_MODUL_INTEGRATION_TEST_GUIDE_2026-10-19.md`](../MAYS_ORDERS_TERRAFORM_MODUL_INTEGRATION_TEST_GUIDE_2026-10-19.md) |
| Builder-CLI | `build`, `upgrade`, `presets` | [`module_builder/`](../../module_builder/) |

## Security und Privacy

| Dokument | Inhalt | Pfad |
|---|---|---|
| Security & Privacy Contract | interner Privacy-Vertrag und Trust Boundary | [`MO-RC4-P00-IMPLEMENTATION-CONTRACT.md`](../contracts/MO-RC4-P00-IMPLEMENTATION-CONTRACT.md) |
| APP_MANAGED HMAC Contract | HMAC-Payload-/Schlüsselvertrag | [`MO-RC4-P00-D-HMAC-PAYLOAD-CONTRACT.md`](../contracts/MO-RC4-P00-D-HMAC-PAYLOAD-CONTRACT.md) |
| IAM-Design | Least Privilege, Rollen, Grenzen | [`security/iam-design.md`](../../security/iam-design.md) |
| DSGVO-/Privacy-Reports | Erasure, Retention, Restore-Gates | [`docs/security/`](../security/) |
| Datenschutz-Entscheidungen | Erasure/Retention/Backup-Gates | [`ORDER-ERASURE-RETENTION-DECISIONS.md`](../security/ORDER-ERASURE-RETENTION-DECISIONS.md) |

## Wiki-spezifische Nachweise

| Dokument | Inhalt |
|---|---|
| [`12-faq.md`](12-faq.md) | häufige Fragen in einfacher Sprache |
| [`MO-ORDER-DESCRIPTION-04-DOC-SYNC.md`](../reports/MO-ORDER-DESCRIPTION-04-DOC-SYNC.md) | Doku-Konsistenz nach F012 |
| [`MO-ORDER-DESCRIPTION-05-SKU-GUIDANCE.md`](../reports/MO-ORDER-DESCRIPTION-05-SKU-GUIDANCE.md) | SKU-Konventionen als Order-Art-Hinweis |
| [`WIKI-CONSISTENCY-01-EXECUTION_LOG.md`](../reports/WIKI-CONSISTENCY-01-EXECUTION_LOG.md) | Prüfung/Ergänzung dieser Wiki |
| [`CI-CODQL-SARIF-DEPENDENCY-AUDIT-01.md`](../reports/CI-CODQL-SARIF-DEPENDENCY-AUDIT-01.md) | CodeQL/SARIF-Upload und Dependency-Scanner-Befund |

## Pflege

- Neue Feature-/API-/Release-Änderungen zuerst in den kanonischen Dokumenten
  belegen, dann die betroffene Wiki-Seite und diese Übersicht aktualisieren.
- Keine Pass-/Verified-Aussage ohne konkreten Evidence-Pfad.
- Historische Reports nicht rückwirkend umschreiben; Datum und Kontext nennen.
- Die Root-`README.md` bleibt die Projekt-Einstiegsseite; diese Wiki ist die
  geführte Lesereise mit Verweisen in die Tiefe.
