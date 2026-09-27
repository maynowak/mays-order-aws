# COGNITO-BACKUP-02 MULTI-PROJECT USER-DATA BACKUP DESIGN

**Datum:** 2026-09-27  
**Projekt:** Mays-Orders-AWS  
**Scope:** Design Only – Keine Implementierung

## 1. Executive Summary

Design für Backup und Recovery von Cognito User-Daten für mays-orders und mays-order-par.

Bestehende Terraform Infrastruktur ist reproduzierbar. User-Daten sind nicht gesichert.

Design trennt strikt:
- Infrastructure Recovery via Terraform
- User Data Recovery via exportierbarer Backup-Struktur

Multi-Project Isolation wird über bestehende project_name/Workspace/Remote State Semantik sichergestellt.

Keine Infrastrukturänderungen in diesem Schritt.

## 2. Current State

### Terraform Struktur
- Modul: `terraform/modules/cognito/`
- Ressourcen:
  - `aws_cognito_user_pool.users` name = "${var.project_name}-users"
  - `aws_cognito_user_pool_client.app` name = "${var.project_name}-client"
  - `aws_cognito_user_group.staff` name = "staff"
- Outputs: user_pool_id, user_pool_arn, user_pool_endpoint, user_pool_client_id, user_pool_group_staff_name
- API Gateway JWT Authorizer nutzt Cognito Endpoint und Client ID

### Projektidentität
- project_name → Workspace → Remote State
- mays-orders → Workspace mays-orders → env:/mays-orders/terraform.tfstate
- mays-order-par → Workspace mays-order-par → env:/mays-order-par/terraform.tfstate
- Environment: Development
- Account: 240571105849
- Region: eu-central-1

### Naming / Tagging
- Tags: Project=var.project_name, Environment, Maker
- Keine zusätzlichen Cognito-spezifischen Tags erforderlich

## 3. Backup Scope

### A) Terraform / Infrastructure Configuration
- User Pool Konfiguration
- App Client Konfiguration
- Groups
- Pool Policies, MFA, Attribute
- Reproducible via Terraform

### B) Cognito User Data
- Username
- User attributes
- User Status, Enabled/Disabled
- Metadata
- Groups Membership
- Verification Status

### C) Nicht backupbar
- Passwörter
- Secrets
- Tokens

Trennung Infrastructure Recovery vs User Data Recovery wird ausdrücklich dokumentiert.

## 4. Multi-Project Backup Identität

Backup Identität:
<project_name>/<environment>/<backup-timestamp>

Beispiele:
- mays-orders/Development/2026-09-27T10:00:00Z
- mays-order-par/Development/2026-09-27T10:00:00Z

Project Identity:
- project_name
- environment
- account_id
- region
- source_user_pool_id
- source_user_pool_name

Cross-Project Restore muss technisch und durch Preflight Checks verhindert werden.

## 5. Backup Storage Design

Bewertung:

A) Bestehender Terraform-State-S3-Bucket
- Pro: existiert, versioniert, verschlüsselt
- Contra: Trennung Infrastructure vs User Data, Zugriffskontrolle, Compliance

B) Separater Backup-S3-Bucket
- Pro: klare Trennung, eigene Lifecycle, eigene Verschlüsselung, Zugriffskontrolle
- Contra: zusätzliche Infrastruktur

Designentscheidung:
Separater Backup-Bucket wird empfohlen, aber nicht implementiert in diesem Design Schritt.

Bewertungskriterien:
- Security
- Isolation
- Encryption
- Versionierung
- Lifecycle
- Retention
- Restore
- Multi-Project Trennung
- Kosten

## 6. Security / Encryption

Design:
- Encryption at Rest via S3 SSE-KMS
- Encryption in Transit via TLS
- IAM Least Privilege für Backup/Restore Rollen
- Zugriff nur für autorisierte Service Accounts/Pipelines
- Personenbezogene Daten: DSGVO relevant, Minimierung, Audit Logging
- Keine Passwörter im Backup

## 7. Backup Format

Versioniertes Format:

backup/
  manifest.json
  users/
  groups/
  metadata/

Manifest Inhalt:
- schema_version
- project_name
- environment
- account_id
- region
- source_user_pool_id
- source_user_pool_name
- backup_timestamp
- export_timestamp
- user_count
- group_count
- checksum
- backup_tool/version

Keine Passwörter.

## 8. User Export Design

Export Mechanismus:
- Cognito Admin APIs: AdminListUsers, AdminGetUser, AdminListGroups
- Pagination für große Mengen
- Rate Limits beachten
- Retry/Fehlerbehandlung
- Teilweise Exporte erkennen

Erfolgszustände:
- SUCCESS: alle User exportiert, Count match
- PARTIAL: Teilmenge exportiert
- FAILED: Export abgebrochen

Validierung via User Count Vergleich Quelle vs Export.

## 9. Backup Integrity

Integritätsprüfung:
- User Count
- Group Count
- Manifest vorhanden
- Checksums
- Backup Object Presence
- Schema Version
- Project Identity
- Source Pool Identity

Backup ist nur gültig wenn alle Checks bestehen.

## 10. Retention / Versioning / RPO/RTO

Retention Modell offen:
- Backup-Frequenz nicht definiert
- Retention Klassen offen
- RPO/RTO nicht festgelegt

Explizit dokumentiert:
RPO/RTO für Cognito ist noch nicht festgelegt.

S3 Versioning und Lifecycle können genutzt werden.

## 11. Restore Design

Restore Flow:
1. Backup Validation
2. Project/Environment Verification
3. Infrastructure Recovery via Terraform
4. Neuer User Pool via Terraform
5. App Client / Groups via Terraform
6. User Import via Admin APIs
7. Gruppenzuordnung
8. Password Reset / Invitation
9. API Gateway Authorizer Prüfung
10. Application Verification

Password Recovery:
Passwörter nicht exportierbar → kontrollierter Password Reset / Invitation Prozess erforderlich.

## 12. Cross-Project Protection

Preflight Checks:
- project_name match
- environment match
- account_id match
- region match
- source_user_pool_id match
- target project identity

Restore mays-orders Backup auf mays-order-par muss blockiert werden.

## 13. Failure Handling

Partielle Fehler:
- Export bricht ab → Backup als FAILED markieren
- S3 Upload teilweise → Integritätsprüfung fail
- User Import teilweise → PARTIAL
- Konflikte Username/Attribute → Loggen, Skip oder Error

Klare Unterscheidung FAILED / PARTIAL / SUCCESS.

## 14. Audit / Logging

Auditierbar:
- Zeitpunkt
- project_name
- environment
- source pool
- backup ID
- user count
- result
- errors
- operator identity

Keine personenbezogenen Userdaten in Logs.

## 15. DSGVO / Privacy

Cognito User Data kann personenbezogene Daten enthalten.

Technische Anforderungen:
- Verschlüsselung
- Zugriffskontrolle
- Retention
- Löschung
- Auditierbarkeit

Keine juristische Beratung.

## 16. Multi-Project Recovery Matrix

| Component | mays-orders | mays-order-par | Cross-Project |
|-----------|-------------|----------------|---------------|
| User Pool | Backup/Restore | Backup/Restore | BLOCK |
| Users | Backup/Restore | Backup/Restore | BLOCK |
| Groups | Backup/Restore | Backup/Restore | BLOCK |
| App Client | Terraform | Terraform | BLOCK |
| Backup | Project-spezifisch | Project-spezifisch | BLOCK |
| Restore | Project-spezifisch | Project-spezifisch | BLOCK |

## 17. Design Decisions

DD-01 Backup Storage: Separater Backup-Bucket empfohlen, nicht implementiert
DD-02 Encryption: SSE-KMS, TLS, IAM Least Privilege
DD-03 Backup Identity: <project_name>/<environment>/<timestamp>
DD-04 Backup Format: Manifest + users/groups/metadata, versioniert
DD-05 Versioning: S3 Versioning + Schema Version
DD-06 Retention: OPEN
DD-07 Export Mechanism: Cognito Admin APIs, Pagination, Retry
DD-08 Restore Mechanism: Terraform + Admin APIs + Password Reset
DD-09 Password Recovery: Reset/Invitation, keine Export
DD-10 Cross-Project Protection: Preflight Checks, Identity Matching
DD-11 Integrity Validation: Count, Checksum, Manifest, Identity
DD-12 Audit Logging: Zeit, Projekt, Pool, Result, Errors

Offene Entscheidungen:
- RPO/RTO
- Backup Frequenz
- Retention Dauer
- Backup Storage Bucket Name
- KMS Key Management

## 18. Implementation Boundary

COGNITO-BACKUP-02 implementiert NICHT:
- S3 Bucket
- Lambda
- IAM Policies
- EventBridge Scheduler
- Backup Job
- Restore Job
- User Export/Import

Dies ist reine Design Spezifikation.

## 19. Recommended Next Step

COGNITO-BACKUP-03 — IMPLEMENTATION

Voraussetzungen:
- RPO/RTO Definition
- Backup Storage Entscheidung
- Retention Policy
- Security Review

---

Design abgeschlossen, keine Infrastrukturänderungen vorgenommen.
