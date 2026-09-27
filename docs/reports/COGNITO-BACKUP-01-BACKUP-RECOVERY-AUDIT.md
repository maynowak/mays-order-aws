# COGNITO-BACKUP-01 BACKUP / RECOVERY AUDIT

**Datum:** 2026-09-27  
**Projekt:** Mays-Orders-AWS  
**AWS Account:** 240571105849  
**Region:** eu-central-1  
**Profile:** mayaws

## 1. Executive Summary

Audit des Backup/Recovery-Fähigkeiten für Cognito User Pools in mays-orders und mays-order-par.

Ergebnis:
- Infrastructure & Configuration Recovery via Terraform möglich
- User Data Recovery nicht nativ durch AWS Backup abgedeckt
- Keine native AWS Backup Integration für Cognito User Pools
- User Export über Admin APIs möglich, Passwörter nicht exportierbar
- Multi-Project Trennung über project_name-Semantik gegeben
- RPO/RTO derzeit nicht definiert
- Produktionsfähiger Cognito Recovery Flow erfordert zusätzliche Implementierung

## 2. Current Cognito Architecture

Terraform Konfiguration:
- Modul: `terraform/modules/cognito/main.tf`
- Ressourcen:
  - `aws_cognito_user_pool.users` name = "${var.project_name}-users"
  - `aws_cognito_user_pool_client.app` name = "${var.project_name}-client"
  - `aws_cognito_user_group.staff` name = "staff"
- Outputs: user_pool_id, user_pool_arn, user_pool_endpoint, user_pool_client_id, user_pool_group_staff_name
- API Gateway JWT Authorizer nutzt Cognito Endpoint und Client ID

Project-Parameterisierung:
- project_name → ${project_name}-users / ${project_name}-client
- Tags: Project=var.project_name

Damit ist Infrastruktur reproduzierbar.

Terraform State ist kein Backup der Cognito Benutzerdaten.

## 3. Multi-Project Boundary

Projekttrennung:
- mays-orders → Workspace mays-orders → Remote State env:/mays-orders/terraform.tfstate
- mays-order-par → Workspace mays-order-par → Remote State env:/mays-order-par/terraform.tfstate

Backup Scope muss projektbezogen getrennt werden:
- Backup Identifier enthält project_name
- Storage muss projektgetrennt sein
- Restore darf nicht cross-project erfolgen

Bestehende Semantik ausreichend, keine neue ID nötig.

## 4. Backup Scope

### Was muss gesichert werden?

1. User Pool
   - Pool-Konfiguration, Policies, MFA, Attribute, Account Recovery, Lambda Triggers, Tags

2. Users
   - Username, User Status, Attribute, Gruppenmitgliedschaften, Verifikationsstatus, Metadaten
   - Passwörter nicht exportierbar

3. Groups
   - Gruppenname, Beschreibung, Precedence

4. App Clients
   - Client-ID, Auth Flows, Token-Konfiguration

5. Identity Provider
   - Aktuell nicht verwendet

6. Domains
   - Aktuell nicht verwendet

7. Secrets/Credentials
   - Nicht speichern, Passwörter nicht exportierbar

## 5. AWS-native Backup Möglichkeiten

AWS bietet keine native Backup Integration für Cognito User Pools.

| Mechanismus | Pool Config | Users | Groups | Clients | Restore | Multi-Project | Bemerkung |
|------------|-------------|-------|--------|---------|---------|---------------|-----------|
| AWS Backup | Nein | Nein | Nein | Nein | Nein | N/A | Cognito nicht unterstützt |
| Cognito Admin APIs Export | Ja via DescribeUserPool | Ja via AdminListUsers, ohne Passwörter | Ja via AdminListGroups | Ja via DescribeUserPoolClient | Manuell | Ja | Kein vollständiger Restore |
| Terraform | Ja | Nein | Ja | Ja | Ja für Config | Ja | Kein User Data |
| CloudFormation/Stack Export | Ja | Nein | Ja | Ja | Ja für Config | Ja | Kein User Data |

## 6. Terraform Recovery Boundary

Terraform kann Infrastruktur/Konfiguration reproduzieren:
- aws_cognito_user_pool.users
- aws_cognito_user_pool_client.app
- aws_cognito_user_group.staff

Terraform State ist kein Benutzer-Datenbackup.

Ein neu erzeugter User Pool besitzt nicht automatisch alte Benutzer.

## 7. Restore Szenario Konzept

Beispiel mays-orders Pool verloren:

1. Projekt identifizieren
2. Backup identifizieren
3. Pool-Konfiguration wiederherstellen via Terraform
4. Pool-ID/Endpoint neu, API Gateway Authorizer anpassen
5. App Client wiederherstellen
6. Gruppen wiederherstellen
7. Benutzer wiederherstellen via AdminCreateUser / Import
8. Attribute/Status wiederherstellen
9. API Gateway JWT Authorizer prüfen
10. Application Integration prüfen
11. Login/Test durchführen

Benutzer-Authentifizierung nach Restore nur möglich, wenn Benutzer mit verwalteten Passwörtern neu angelegt werden. Passwörter müssen zurückgesetzt werden.

## 8. Multi-Project Restore Isolation

Scenario A: Restore mays-orders
- Darf mays-order-par nicht beeinflussen
- Backup Identifier: project_name=mays-orders
- Pool Name: mays-orders-users
- Restore Target: Workspace mays-orders

Scenario B: Restore mays-order-par
- Darf mays-orders nicht beeinflussen
- Backup Identifier: project_name=mays-order-par

Trennung über project_name, Workspace und Remote State gewährleistet.

## 9. Backup Storage Evaluation

Bestehende Infrastruktur:
- S3 Bucket mays-orders-tfstate-central-240571105849 wird aktuell für Terraform State genutzt

Bewertung:
- Terraform State Bucket nicht für Cognito User Data verwenden
- Separater Backup Bucket mit Versionierung, Encryption, Lifecycle empfohlen
- Zugriffsschutz via IAM, Projekt-/Environment-Trennung
- Keine Infrastruktur implementiert im Rahmen dieses Audits

## 10. Security / Privacy

Cognito User Data kann personenbezogene Daten enthalten.

Aspekte:
- Verschlüsselung at rest in transit
- Zugriffskontrolle IAM
- Backup-Aufbewahrung, Löschung
- Kein Speichern von Passwörtern
- Audit Logging
- DSGVO: Datenminimierung, Löschfristen

Keine personenbezogenen Daten in Reports.

## 11. RPO / RTO Status

RPO/RTO für Cognito ist noch nicht festgelegt.

Technische Eigenschaften:
- Config Recovery via Terraform: schnell
- User Data Recovery: manuell, abhängig von Export-Frequenz

Explizit dokumentiert: RPO/RTO nicht definiert.

## 12. Backup / Recovery Matrix

| Bereich | Terraform | Backup nötig | Restore möglich | Multi-Project | Status |
|---------|-----------|--------------|-----------------|---------------|--------|
| Pool Config | Ja | Ja | Ja via Terraform | Ja | Konfiguriert |
| Users | Nein | Ja | Teilweise via API, Passwörter nein | Ja | Nicht gesichert |
| Groups | Ja | Nein | Ja via Terraform | Ja | Konfiguriert |
| App Clients | Ja | Nein | Ja via Terraform | Ja | Konfiguriert |
| IdP | Nein | Nein | N/A | Ja | Nicht vorhanden |
| Domain | Nein | Nein | N/A | Ja | Nicht vorhanden |
| Secrets | Nein | Nein | Nein | Ja | Nicht exportierbar |

## 13. Open Decisions

- Backup-Frequenz für User Data
- Backup Storage Ort und Verschlüsselung
- RPO/RTO Definition
- Verantwortlichkeit für User Data Export/Import
- Prozess für Passwort-Reset nach Restore

## 14. Recommended Next Implementation Step

Technisch:
- Definition von RPO/RTO
- Auswahl separaten Backup Storage
- Automatisierter Export von User Pool Konfiguration via Admin APIs
- Dokumentierter User Export/Import Prozess
- Test-Restore Verfahren

Keine unnötige Architektur.

## 15. Fazit

Infrastructure Recovery via Terraform vorhanden.
Configuration Recovery via Terraform vorhanden.
User Data Recovery nicht nativ abgedeckt, erfordert manuelle Prozesse.

Multi-Project Trennung über project_name-Semantik gegeben.

Produktionsfähiger Cognito Recovery Flow erfordert zusätzliche Implementierung.

---

Audit abgeschlossen, keine Infrastrukturänderungen vorgenommen.
