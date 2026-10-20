# May's Orders — AWS Serverless Order & Work Processing

**Release:** `v0.5.0-rc.2` · **Status:** geprüfter Release Candidate · **Production Privacy Activation:** **BLOCKED**

Mays-Orders-AWS ist ein eigenständiges serverloses AWS-Backend für Bestellungen und Work Items. Die Plattform verbindet eine JWT-geschützte HTTP-API mit einer regelbasierten Statusmaschine, DynamoDB, SQS-Worker-Verarbeitung und einem kontrollierten Terraform-Installer.

## Kernfunktionen

- **Order-Lifecycle:** `PENDING → CONFIRMED → PROCESSING → SHIPPED → DELIVERED` mit definierten Cancellation-Pfaden.
- **Authentifizierung:** Cognito/JWT über API Gateway HTTP API v2.
- **Verarbeitung:** Python-3.14-Lambda, DynamoDB, SQS und Worker-Lambda.
- **Privacy intern:** `inspect_subject`, `export_subject`, `erase_subject` — getestet, **nicht produktiv aktiviert**.
- **Infrastruktur:** Terraform-Module, Workspace-Isolation, Policy Gate, Installer mit Plan/Deploy/Destroy.
- **Betrieb:** CloudWatch-Monitoring und CloudTrail-Auditierung.

## Architektur

```text
Client → API Gateway (JWT/Cognito) → Order Lambda → DynamoDB
                                          │
                                          └→ SQS → Worker Lambda → DynamoDB

Terraform + Installer + Policy Gate | IAM | CloudWatch | CloudTrail
```

## Release-Nachweise

| Bereich | Ergebnis |
|---|---|
| Tag / Commit | `v0.5.0-rc.2` / Release-Commit dieses Tags (Basline `adddca8`) |
| Lambda-Unit-Tests | 76 PASS |
| Installer-Unit-Tests | 81 PASS |
| Artifact-Integrity-Tests | 5 PASS |
| Terraform fmt / validate | PASS |
| Order AWS-E2E | Historisch 12/12 PASS |
| Privacy AWS-E2E | Historisch P-01/P-02/P-03 PASS |
| Isolierter Test-Destroy | 37 Ressourcen entfernt; 0 projektspezifische Reste |

**Hinweis:** Historische E2E-Nachweise beziehen sich auf eine inzwischen vollständig abgebaute Testinstallation. Ein finaler Release `v0.2.0` ist noch nicht veröffentlicht.

## Dokumentation

- [Ausführliche Produktbeschreibung](docs/PRODUCT_OVERVIEW.md)
- [Installer-Handbuch](docs/INSTALLER_GUIDE.md)
- [Release Notes](docs/RELEASE_NOTES.md)
- [Terraform Policy Gate](docs/TERRAFORM_POLICY_GATE.md)
- [Release-Candidate-Report](docs/reports/MAYS-ORDERS-RELEASE-CANDIDATE-HARDENING-01.md)
- [Destroy-Nachweis](docs/reports/MAYS-ORDERS-PRIVACY-DESTROY-AND-RELEASE-01.md)
- [Orders-Service-Modul-Vertrag](docs/reports/MAYS-ORDERS-MODULE-CONTRACT-01.md)
- [Modul-Integrations- & Testleitfaden](docs/MAYS_ORDERS_TERRAFORM_MODUL_INTEGRATION_TEST_GUIDE_2026-10-19.md)

## Einstieg ohne Deployment

```bash
git clone https://github.com/maynowak/mays-order-aws.git
cd mays-order-aws
git checkout v0.5.0-rc.2
./Mays-Order-AWS-installer --help
./Mays-Order-AWS-installer validate
```

**Kein AWS-Deployment ohne Freigabe.** Konto, Region, Profil, Workspace, Plan und Policy Gate vor jeder Mutation prüfen. Details im [Installer-Handbuch](docs/INSTALLER_GUIDE.md).

## Module Builder — Terraform-Bereitstellung generieren

```bash
# 1) Vollständiger Stack als eigenständiges Projekt:
python -m module_builder build --target ./generated/my-orders   --project-name my-orders --preset complete --validate

# 2) Wiederverwendbares Orders-Service-Terraform-Modul (MANAGED/EXTERNAL Cognito):
python -m module_builder build --preset orders-service   --target ./module/Mays-Order-AWS --project-name my-orders --validate

# 3) Freie Modulauswahl (Pflicht-Deps explizit; --with-deps ergänzt transitiv):
python -m module_builder build --target ./generated/custom   --project-name custom --modules dynamodb,sqs,iam,lambda --with-deps

python -m module_builder presets    # verfügbare Presets listen
```

Details: [Modul-Integrations- & Testleitfaden](docs/MAYS_ORDERS_TERRAFORM_MODUL_INTEGRATION_TEST_GUIDE_2026-10-19.md) · [Orders-Service-Modul-Vertrag](docs/reports/MAYS-ORDERS-MODULE-CONTRACT-01.md) · `python -m module_builder --help`

## Projektabgrenzung

Mays-Orders-AWS ist eine eigenständige Order-/Work-Processing-Komponente. Mays-RIS ist ein separates System und wird durch einen Tag dieses Repositories nicht automatisch aktualisiert.

## Sicherheitsstatus und Roadmap

Der Release Candidate enthält interne Privacy-Funktionen, aber **keine produktionsfähige dauerhafte Secret-Verwaltung und Rotation**. Ihre produktive Aktivierung bleibt bis zur separaten Implementierung und Security-/AWS-E2E-Abnahme **BLOCKED**. Das Terraform Policy Gate ersetzt weder IAM noch menschliche Freigabe oder Kostenkontrolle.
