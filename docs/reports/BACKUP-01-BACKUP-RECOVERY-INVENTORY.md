# BACKUP-01 — BACKUP / RECOVERY INVENTORY & CURRENT-STATE AUDIT

**Audit Datum:** 2026-09-26  
**Scope:** Ist-Analyse Backup-/Recovery-Stand Repository, READ-ONLY  
**Agent:** OpenCode  
**Git Basis:** siehe Abschnitt 2

---

## 1. Scope

Erstellung einer belastbaren Ist-Analyse des aktuell implementierten Backup-/Recovery-Stands im Repository.
Keine Implementierung, kein Terraform Apply, keine Ressourcenänderung.

Fokus Ressourcen:
DynamoDB, S3, CloudTrail, Cognito, API Gateway, SQS / DLQ, Lambda, IAM, Terraform State, CloudWatch/Logs, sonstige persistente Ressourcen.

Trennung:
- **BACKUP** → Kopie / Schutz vorhandener Daten
- **RECOVERY** → Wiederherstellung nach Verlust / Beschädigung
- **REPROVISIONING** → Wiederaufbau aus Terraform / Konfiguration
- **RESTORE TEST** → tatsächlich durchgeführter Wiederherstellungstest

---

## 2. Git/Repository-Basis

- `git rev-parse --show-toplevel`: `/home/dci-student/projects/Mays-Orders-AWS`
- Branch: `main`
- HEAD: `447960f8fdc5f1d4d435d08d1bf416349531a2d2`
- `git status`: clean
- Letzte Commits:
  - `447960f` docs: audit CI/CD source auth, document CodeConnections usage
  - `d87c494` test: parametrize E2E tests for PROJECT_NAME
  - `48cb0a6` docs: consolidate parallel project mechanism documentation
  - `c67baa0` docs: add consolidated CI/CD installer parallel reports

Repository-Identität bestätigt.

---

## 3. Ressource-Inventar

### 3.1 DynamoDB

**A) Ressource**
`aws_dynamodb_table.orders` — `terraform/modules/dynamodb/main.tf`
- Name = `var.project_name`
- PAY_PER_REQUEST, hash_key pk, range_key sk
- GSI1 mit INCLUDE projection
- Keine explizite SSE-Konfiguration → AWS-managed default

**B) aktueller Schutzmechanismus**
- AWS-managed SSE default
- Keine `point_in_time_recovery` in Terraform
- Keine `backup` Ressource
- Keine DynamoDB Streams

**C) Backup vorhanden?**
Nein. PITR nicht konfiguriert. NOT DOCUMENTED sonstige Backups.

**D) Recovery / Restore Mechanismus vorhanden?**
Nein. Kein Restore-Verfahren im Repo dokumentiert.

**E) Terraform-reproduzierbar?**
Ja, Tabellen-Schema reproduzierbar.

**F) Daten selbst müssen wiederhergestellt werden?**
Ja.

**G) Konfiguration muss wiederhergestellt werden?**
Ja, via Terraform.

**H) Abhängigkeiten beim Restore**
Lambda Env `ORDERS_TABLE`, SQS Worker, IAM Policy, API Gateway keine direkte Abhängigkeit. Bei Restore ändert sich Table ARN/Name → Env Var und IAM müssten angepasst werden.

**I) dokumentiertes Verfahren vorhanden?**
NOT DOCUMENTED

**J) tatsächlicher Restore-Test vorhanden?**
Nein.

**K) Status**
RED für Daten-Backup / Recovery. YELLOW für Reprovisioning.

---

### 3.2 S3 — CloudTrail Bucket

**A) Ressource**
`aws_s3_bucket.trail` — `terraform/modules/cloudtrail/main.tf`
- Bucket = `${var.project_name}-cloudtrail-${account_id}`
- SSE-S3 AES256, Public Access Block, Bucket Policy für CloudTrail

**B) aktueller Schutzmechanismus**
- Server-Side Encryption AES256
- Public Access Block
- `force_destroy = true`
- **Keine Versionierung**
- **Kein Lifecycle**

**C) Backup vorhanden?**
Nein. Keine Versionierung, keine Replikation.

**D) Recovery / Restore Mechanismus vorhanden?**
Nein.

**E) Terraform-reproduzierbar?**
Ja.

**F) Daten selbst müssen wiederhergestellt werden?**
Ja, CloudTrail Logs sind Audit-Daten.

**G) Konfiguration muss wiederhergestellt werden?**
Ja.

**H) Abhängigkeiten**
CloudTrail Trail referenziert Bucket-Name. Änderung des Bucket-Namens erfordert Trail-Update.

**I) dokumentiertes Verfahren vorhanden?**
NOT DOCUMENTED

**J) tatsächlicher Restore-Test vorhanden?**
Nein.

**K) Status**
YELLOW — Konfiguration reproduzierbar, Daten ohne Versionierung.

---

### 3.3 Cognito User Pool

**A) Ressource**
`aws_cognito_user_pool.users` — `terraform/modules/cognito/main.tf`
- admin_create_user_only = true
- password policy, MFA OFF
- App Client `USER_PASSWORD_AUTH`

**B) aktueller Schutzmechanismus**
Kein Backup-Mechanismus dokumentiert.

**C) Backup vorhanden?**
Nein für Benutzerdaten/Passwörter.

**D) Recovery / Restore Mechanismus vorhanden?**
Nein.

**E) Terraform-reproduzierbar?**
Konfiguration ja, Benutzerdaten nein.

**F) Daten selbst müssen wiederhergestellt werden?**
Benutzerdaten ≠ Konfiguration.

**G) Konfiguration muss wiederhergestellt werden?**
Ja via Terraform.

**H) Abhängigkeiten**
API Gateway JWT Authorizer referenziert User Pool Endpoint/Client ID.

**I) dokumentiertes Verfahren vorhanden?**
NOT DOCUMENTED

**J) tatsächlicher Restore-Test vorhanden?**
Nein.

**K) Status**
RED für Benutzerdaten, GREEN für Konfigurations-Reprovisioning.

---

### 3.4 API Gateway HTTP API

**A) Ressource**
`aws_apigatewayv2_api` über `terraform/modules/api`

**B) Schutzmechanismus**
Keine Datenpersistenz.

**C) Backup vorhanden?**
N/A

**D) Recovery**
Reprovisioning via Terraform.

**E) Terraform-reproduzierbar?**
Ja.

**K) Status**
GREEN für Reprovisioning.

---

### 3.5 SQS

**A) Ressource**
`aws_sqs_queue.orders` — `terraform/modules/sqs/main.tf`
- visibility_timeout_seconds = 30
- message_retention_seconds = 120
- Keine DLQ konfiguriert

**B) Schutzmechanismus**
Kein Backup.

**C) Backup vorhanden?**
Nein.

**D) Recovery**
Keine Persistenz über Retention hinaus.

**E) Terraform-reproduzierbar?**
Ja.

**K) Status**
YELLOW — Queue reproduzierbar, Nachrichten nicht gesichert.

---

### 3.6 Lambda

**A) Ressource**
`aws_lambda_function.handler` + `sqs_worker`
Code im Repo `lambda/src/`, Build via `lambda/build_zip.py`

**B) Schutzmechanismus**
Code in Git, Log Group mit Retention 7 Tage

**C) Backup vorhanden?**
Code-Backup via Git ja, Log-Backup nein.

**D) Recovery**
Reprovisioning via Terraform + Git.

**E) Terraform-reproduzierbar?**
Ja.

**K) Status**
GREEN für Code, YELLOW für Logs.

---

### 3.7 IAM

**A) Ressource**
`aws_iam_role` via `terraform/modules/iam`

**B) Backup**
Keine, Reprovisioning via Terraform.

**K) Status**
GREEN

---

### 3.8 Terraform State

**A) Ressource**
Lokaler State `terraform/terraform.tfstate`
- Kein Backend-Block
- Resources leer, serial 3072

**B) Schutzmechanismus**
Keiner. Kein S3 Backend, kein Locking.

**C) Backup vorhanden?**
Nein.

**D) Recovery**
Manuelles State-Backup nicht dokumentiert.

**E) Terraform-reproduzierbar?**
Ja, Konfiguration vorhanden.

**K) Status**
RED

---

### 3.9 CloudWatch / Logs

**A) Ressource**
Log Group `/aws/lambda/<function>` mit retention_in_days, Dashboard, Alarme

**B) Schutzmechanismus**
Retention 7 Tage, kein Export.

**C) Backup vorhanden?**
Nein.

**K) Status**
YELLOW

---

### 3.10 CloudTrail

**A) Ressource**
`aws_cloudtrail.trail` multi-region, Management Events Read+Write, Log File Validation

**B) Schutzmechanismus**
Logs in S3 Bucket siehe 3.2

**C) Backup**
Keine Versionierung.

**K) Status**
YELLOW

---

## 4. Backup-Status

Keine der untersuchten persistenten Datenquellen verfügt über ein explizites Backup:
- DynamoDB PITR fehlt
- S3 Versionierung fehlt
- Cognito User Data Backup fehlt
- SQS Nachrichten Retention nur 120s, keine DLQ
- Terraform State lokal ohne Backup

Evidenz: `CURRENT-INFRA-AUDIT-EXECUTION-LOG.md` bestätigt `no PITR/backups/streams`. `PROJECT-OVERVIEW.md` Status NOT IMPLEMENTED für Backup/Disaster Recovery. Roadmap `future-extensions.md` listet PITR/Backups als DEFERRED.

---

## 5. Recovery-Status

Kein dokumentiertes Restore-Verfahren gefunden. Kein Restore-Test nachweisbar.
Reprovisioning via Terraform ist für Infrastruktur-Ressourcen vorhanden, reicht jedoch nicht für Datenverlust.

---

## 6. Terraform-Reprovisioning

Vollständig aus Terraform rekonstruierbar:
- DynamoDB Schema
- IAM Role/Policy
- Lambda Konfiguration
- Cognito Pool/Client/Group Konfiguration
- API Gateway
- SQS Queue
- CloudTrail + S3 Bucket
- Monitoring

Nicht aus Terraform rekonstruierbar:
- DynamoDB Daten
- Cognito Benutzer/Passwörter
- SQS Nachrichten
- CloudTrail Logs Historie
- CloudWatch Logs Historie
- Terraform State

---

## 7. Restore-Test-Status

NOT DOCUMENTED / NOT VERIFIED
Kein Nachweis für durchgeführten Restore-Test im Repository.

---

## 8. Recovery-Abhängigkeiten

DynamoDB
  ↓ Lambda Env ORDERS_TABLE
  ↓ SQS Worker
  ↓ IAM Policy auf Table/GSI
  ↓ API Gateway via Lambda

Cognito User Pool
  ↓ API Gateway JWT Authorizer

SQS Queue
  ↓ Lambda Event Source Mapping

CloudTrail
  ↓ S3 Bucket Policy / Name

IDs/ARNs ändern sich bei Neu-Provisioning → Umgebungsvariablen, Policies, Authorizer Config müssen synchron bleiben.

---

## 9. Gaps

- DynamoDB PITR / Backups nicht konfiguriert
- S3 Versionierung / Lifecycle nicht konfiguriert
- Cognito User Export/Backup nicht vorhanden
- SQS DLQ nicht konfiguriert
- Terraform State ohne Remote Backend / Locking / Backup
- Keine dokumentierten Restore-Prozeduren
- Keine Restore-Tests
- CloudWatch Logs kein Export/Backup
- Keine Disaster Recovery Strategie dokumentiert

---

## 10. Empfehlungen / nächste Schritte

**RECOMMENDATION / OPEN DECISION:**
- Evaluierung DynamoDB PITR und On-Demand Backups
- Evaluierung S3 Versionierung für CloudTrail Bucket
- Terraform State Remote Backend mit S3+DynamoDB Lock
- Dokumentation Restore-Runbooks
- Restore-Tests planen

Keine Implementierung im Rahmen BACKUP-01.

---

## 11. Abgrenzung

Dieser Audit erfasst nur den Ist-Zustand. Geplante Datenmigrationen/Transformationen werden nicht implementiert, lediglich festgehalten wo ein Recovery-Szenario Transformationen erfordern könnte.

---

**Ende BACKUP-01 Audit**
