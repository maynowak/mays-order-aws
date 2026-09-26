# BACKUP-04 — Multi-Project DynamoDB Protection

**Datum:** 2026-09-26  
**Scope:** Aktivierung DynamoDB Point-in-Time Recovery im Multi-Project Kontext  
**Keine Apply, nur Konfiguration**

---

## 1. Scope

Implementierung des ersten produktiven Backup-Schutzmechanismus:
DynamoDB Point-in-Time Recovery (PITR) für alle Projekte, die die
gemeinsame Terraform Ressource verwenden.

Anforderung: Multi-Project kompatibel, keine Hardcodes.

---

## 2. Ausgangszustand

BACKUP-01: Kein PITR konfiguriert
BACKUP-02: Recovery Strategie definiert
BACKUP-03: Multi-Project Foundation definiert

DynamoDB Terraform Ressource:
`terraform/modules/dynamodb/main.tf`
- `resource "aws_dynamodb_table" "orders"`
- Name = `var.project_name`
- Billing PAY_PER_REQUEST
- GSI1 vorhanden
- Tags mit `Project = var.project_name`
- Kein PITR

---

## 3. DynamoDB Resource

- Terraform Resource: `aws_dynamodb_table.orders`
- Tabellenname: `var.project_name`
- Workspace-abhängig: Ja
- Tags: Project
- GSI: gsi1
- Encryption: AWS-managed default
- Backup: Nein

Multi-Project Mechanismus:
`project_name` → Terraform Workspace → isolierter State → projektbezogene Tabelle

---

## 4. Multi-Project Mechanismus

Validiert in BACKUP-03:
- `project_name` aus InstallationContext
- Terraform Workspace = `project_name`
- Resource Naming enthält `project_name`
- Project Tag in allen Ressourcen

Jede Projektinstanz erhält eigene Tabelle mit eigenem Namen.

---

## 5. PITR Implementation

Änderung:
`terraform/modules/dynamodb/main.tf`

Hinzugefügt:
```hcl
point_in_time_recovery {
  enabled = true
}
```

Minimalste Änderung, keine bestehenden Parameter verändert.

Kein Hardcoding auf `mays-orders`. Gilt für alle Projekte via `var.project_name`.

---

## 6. Warum die Implementierung projektübergreifend funktioniert

- PITR Block ist Teil der gemeinsamen Terraform Ressource
- Ressource wird pro Workspace mit unterschiedlichem `project_name` instanziiert
- DynamoDB Table Name = `var.project_name` → eindeutig pro Projekt
- Keine Bedingungen oder if project_name == ...
- Terraform Plan mit `project_name=mays-orders` → Tabelle `mays-orders`, PITR enabled
- Terraform Plan mit `project_name=mays-order-par` → Tabelle `mays-order-par`, PITR enabled

Multi-Project Nachweis durch Plan Output.

---

## 7. Validation

**terraform fmt -check -recursive**
Ergebnis: PASS

**terraform validate**
Ergebnis: Success! The configuration is valid.

**terraform plan**
Ergebnis: Konfiguration generiert Plan mit PITR enabled
Beispiel `project_name=mays-order-par`:
- `module.dynamodb.aws_dynamodb_table.orders` name = `mays-order-par`
- `point_in_time_recovery { enabled = true }` vorhanden

Multi-Project Validierung erfolgreich.

AWS Apply:
**NICHT AUSGEFÜHRT**
Plan verified, Apply nicht erforderlich für B4 Dokumentation.
Apply wäre erforderlich für produktive Aktivierung, wird separat freigegeben.

---

## 8. AWS Apply Status

PLAN VERIFIED
APPLY REQUIRED BUT NOT EXECUTED

Gründe:
- Keine unbeabsichtigte produktive Änderung
- Apply benötigt AWS Credentials, spezifischen Workspace, Projektkontext
- B4 ist Konfigurations-Analyse, kein Deploy

---

## 9. Recovery Implications

PITR aktiviert:
- Datenverlustfenster reduziert auf Sekunden
- Restore auf beliebigen Zeitpunkt innerhalb der Retention
- Konfiguration schützt Daten, keine Migration/Transformation
- Restore-Test noch nicht durchgeführt

PITR schützt Daten vor Verlust, ersetzt keine Schema-Migration.

---

## 10. Remaining Gaps

- Restore-Test nicht durchgeführt
- PITR Retention Period nicht explizit gesetzt, AWS Default gilt
- Terraform State Remote Backend weiterhin offen
- Dokumentierter Restore-Runbook fehlt

---

## 11. Next Step

B5: Restore-Test Strategie und Dokumentation

---

**U P G R A D E   N O T E**

⚠️ UPGRADE NOTE — DATA TRANSFORMATION REQUIRED

Änderungen an bestehendem DynamoDB Datenmodell, Schema,
Partition-/Sort-Key-Struktur oder inkompatiblen Attributmodellen
können eine versionierte Datenmigration/Transformation erfordern.

PITR/Backup schützt Daten vor Verlust, ersetzt aber keine
Schema-/Datenmigration.

Keine Migration implementiert.

---

Ende BACKUP-04
