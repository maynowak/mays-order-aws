# Mays-Orders-AWS — Produktbeschreibung und Architektur

**Stand:** 11.10.2026 · **Release Candidate:** `v0.5.0-rc.1` · **Commit:** `f6e737b`  
**Produktive Privacy-Aktivierung:** **BLOCKED** (dauerhaftes Secret-Management und Rotation fehlen).

## 1. Produktidee

Mays-Orders-AWS ist ein eigenständiges, serverloses AWS-Backend zur Verwaltung von Bestellungen und Work Items. Es kombiniert eine JWT-geschützte HTTP-API, eine regelbasierte Statusmaschine, DynamoDB als Datenspeicher und asynchrone Verarbeitung über Amazon SQS. Ein projektbezogener Installer orchestriert den kontrollierten Terraform-Lebenszyklus.

Das System kann als technische Komponente anderer Anwendungen eingesetzt werden. **Mays-RIS ist ein separates Produkt**; ein Release von Mays-Orders-AWS aktualisiert RIS nicht automatisch.

## 2. Funktionsübersicht

| Funktion | Beschreibung | Nachweis |
|---|---|---|
| Order API | Erstellung, Abruf, Auflistung und Statusaktualisierung | Historische AWS-E2E-Regression 12/12 PASS |
| Statusmaschine | `PENDING → CONFIRMED → PROCESSING → SHIPPED → DELIVERED`; definierte `CANCELLED`-Pfade | Übergangsregeln und Fehlerfälle getestet |
| Asynchrone Verarbeitung | SQS-Queue und Worker-Lambda | Historisch live verifiziert |
| Persistenz | DynamoDB mit Indizes für Order- und Subject-Zugriffe | GSI1/GSI2 im Test verifiziert |
| Privacy | `inspect_subject`, `export_subject`, `erase_subject` | P-01 bis P-03 historisch live verifiziert; **nicht produktiv freigegeben** |
| Infrastruktur | Terraform-Module, isolierte Workspaces, Policy Gate | Installation und Destroy im Test verifiziert |
| Beobachtbarkeit | CloudWatch-Logs, Alarme/Dashboard, CloudTrail | Im isolierten Test nachgewiesen |
| Installer | Validierung, Plan, Deploy, Destroy, Kontext- und Artefaktprüfung | 81 Installer-Tests, 5 Integritätstests |

## 3. Systemarchitektur

```text
Client
  │
  ▼
API Gateway HTTP API v2 ── Cognito JWT Authorizer
  │
  ▼
Order API Lambda (Python 3.14)
  ├────────────────► DynamoDB (Orders, GSI1/GSI2)
  │
  └────────────────► SQS Queue ──► Worker Lambda ──► DynamoDB

Querschnitt: IAM Least Privilege | CloudWatch | CloudTrail
Lifecycle: Terraform | Installer | Policy Gate | Human Approval
```

**Cognito** authentifiziert API-Nutzer; **IAM** steuert Berechtigungen zwischen AWS-Diensten. **API Gateway** stellt die dokumentierten Order-Routen bereit. **Lambda** enthält die Geschäftslogik. **DynamoDB** speichert Orders und unterstützt indizierte Abfragen. **SQS** entkoppelt Verarbeitung von API-Aufrufen. **CloudWatch** dient operativer Beobachtung; **CloudTrail** dokumentiert AWS-API-Aktivitäten.

Die Architektur ist eine Übersicht; für exakte IAM-Aktionen, Ressourcen und API-Routen ist der versionierte Quellcode maßgeblich.

## 4. Order-Lifecycle

```text
PENDING → CONFIRMED → PROCESSING → SHIPPED → DELIVERED
          (CANCELLED nur über erlaubte Übergänge)
```

Die vollständigen Übergangsregeln stehen unter `order-lifecycle/`. Ungültige Übergänge werden zurückgewiesen. Die Verarbeitung über SQS und den Worker wurde in einer früheren AWS-Testinstallation live geprüft.

## 5. Interne Privacy-Funktionen

Die Funktionen dienen der subject-bezogenen Einsicht, dem Export und der Löschung:

- **`inspect_subject`:** Ermittelt subject-bezogene Datensätze; GSI2 und Isolation wurden geprüft.
- **`export_subject`:** Exportiert relevante Datensätze; JSON-/Decimal-Verarbeitung wurde geprüft.
- **`erase_subject`:** Löscht subject-bezogene Daten; anschließendes `NOT_FOUND` und wiederholte Aufrufe wurden geprüft.

Die Tests erfolgten über einen **internen Invoke-only-Dispatch**, ohne öffentliche Privacy-Route. Ein temporäres Secret wurde für den Test gesetzt und danach entfernt. Negativtests mit ungültigem Token, falschem Projekt und fehlendem Kontext wurden abgewiesen; der Pfad blieb nach Secret-Entfernung fail-closed.

**Wichtige Grenze:** Eine produktive Secret-Verwaltung mit Rotation ist **noch nicht implementiert**. Die Privacy-Funktionen sind daher **nicht zur produktiven Aktivierung freigegeben**. Ein erfolgreicher technischer Test ist keine pauschale datenschutzrechtliche Freigabe.

## 6. Infrastruktur und Sicherheit

Terraform definiert die Infrastruktur modular. Projektbezogene Workspaces trennen die State-Dateien innerhalb des verwendeten Backends. Der Installer überprüft AWS-Profil, Konto, Region, Projekt, Terraform-Kontext und Artefaktintegrität vor Mutationen.

Das **Terraform Policy Gate** prüft projektinterne Ressourcen- und Kostengrenzen. Ein PASS ersetzt weder AWS-IAM-Autorisierung noch menschliche Freigabe oder Kostenüberwachung. Die genauen Regeln stehen in `docs/TERRAFORM_POLICY_GATE.md` und `terraform/policy/resource-policy.json`.

Optionale Cognito-Backup-Komponenten lassen sich je nach Installationskontext konfigurieren. Für den isolierten Privacy-Test wurden sie deaktiviert, ohne bestehende produktive Installationen zu verändern.

## 7. Release und Evidence

| Prüfung | Ergebnis laut Release-Checkpoint |
|---|---|
| Release-Tag | `v0.5.0-rc.1` → `f6e737b`, gepusht |
| Lambda-Unit-Tests | 76 PASS |
| Installer-Unit-Tests | 81 PASS |
| Artifact-Integrity-Tests | 5 PASS |
| Terraform | `fmt -check` / `validate` PASS |
| AWS-Order-Regression | Historisch 12/12 PASS |
| Privacy-E2E | Historisch P-01/P-02/P-03 PASS |
| Testinstallation | 37 Ressourcen kontrolliert gelöscht; 0 projektspezifische Ressourcen verblieben |
| Lambda-ZIP SHA-256 | `b1018a3bd03455ede329ffaa3c66ca8115c6077741c8aad5282ee5f5fbd00e2b` |

**Historisch** heißt: Die Tests wurden in einer mittlerweile abgebauten AWS-Testinstallation durchgeführt; sie sind keine Behauptung eines aktuell laufenden Deployments.

## 8. Anwendungsfälle und Abgrenzung

Das Projekt eignet sich als Order-/Work-Processing-Backend, als Referenz für eventgetriebene AWS-Architekturen und als Testbett für kontrollierte Infrastructure-as-Code-Prozesse. Es ist **kein Recruiting-System**; Mays-RIS kann seine Fähigkeiten als gesondert versionierte Komponente nutzen.

## 9. Nächste Schritte

1. Produktives Secret-Management, Rotation, IAM-Grenzen und Runtime-Zugriff entwerfen.
2. Security- und AWS-E2E-Tests für diesen Produktionspfad durchführen.
3. Finale Release-Abnahme für `v0.2.0` separat durchführen.
4. Eine RIS-Integration nur nach eigener Freigabe und Integrationstests aktualisieren.

## 10. Quellen im Repository

- [`README.md`](../README.md)
- [`docs/INSTALLER_GUIDE.md`](INSTALLER_GUIDE.md)
- [`docs/RELEASE_NOTES.md`](RELEASE_NOTES.md)
- [`docs/TERRAFORM_POLICY_GATE.md`](TERRAFORM_POLICY_GATE.md)
- [`docs/reports/MAYS-ORDERS-RELEASE-CANDIDATE-HARDENING-01.md`](reports/MAYS-ORDERS-RELEASE-CANDIDATE-HARDENING-01.md)
- [`docs/reports/MAYS-ORDERS-PRIVACY-DESTROY-AND-RELEASE-01.md`](reports/MAYS-ORDERS-PRIVACY-DESTROY-AND-RELEASE-01.md)
