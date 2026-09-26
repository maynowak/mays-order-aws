# BACKUP-02 — Recovery Strategy & Resource Classification

**Datum:** 2026-09-26  
**Ausgangspunkt:** BACKUP-01 Commit 36a6957  
**Scope:** Analyse + Klassifikation Recovery-Strategie, keine Implementierung

---

## 1. Scope

Auf Basis BACKUP-01 belastbare Recovery-Strategie definieren.
Trennung CODE / CONFIG / STATE / PERSISTENT DATA / AUDIT DATA / TRANSIENT DATA.
Recovery-Methoden klassifizieren, Abhängigkeiten, Reihenfolge, Gaps, AWS Backup Bewertung.

Keine Terraform Apply, keine Infrastrukturänderung.

---

## 2. Git Basis

- `git rev-parse --show-toplevel`: `/home/dci-student/projects/Mays-Orders-AWS`
- Branch: `main`
- HEAD: `36a6957022ffb697adc69418f61ae9567deb44d7`
- `git status --short`: clean
- BACKUP-01 abgeschlossen: `36a6957`

---

## 3. Recovery Principles

- Reprovisioning via Terraform ist ausreichend für reine Konfigurationsressourcen.
- Persistente Daten erfordern Backup/Restore, nicht nur Reprovisioning.
- Audit-Daten sind unverzichtbar, benötigen mindestens Versionierung/Sicherung.
- State ist kritische Infrastruktur, erfordert eigenes Recovery-Konzept.
- Keine RPO/RTO Werte im Repository definiert → NOT DEFINED.

---

## 4. Resource Recovery Matrix

### 4.1 DynamoDB

1. RESOURCE: `aws_dynamodb_table.orders`
2. BUSINESS / SYSTEM IMPORTANCE: Hoch — Kern-Bestelldaten
3. WHAT MUST SURVIVE?: Schema + Daten
4. BACKUP REQUIREMENT: Ja
5. RECOVERY METHOD: B / C
6. REPROVISIONING METHOD: A — Reprovision via Terraform
7. DATA RESTORE REQUIRED?: Ja
8. CONFIG RESTORE REQUIRED?: Ja
9. DEPENDENCIES: Lambda Env ORDERS_TABLE, IAM Policy, SQS Worker
10. RESTORE ORDER: Phase 3
11. RESTORE VALIDATION: NOT VERIFIED
12. CURRENT STATE: Kein PITR, kein Backup
13. TARGET STATE: PITR aktiv, Backup vorhanden
14. GAP: PITR fehlt, Restore-Verfahren nicht dokumentiert
15. PRIORITY: Hoch

### 4.2 S3 / CloudTrail Bucket

1. RESOURCE: `aws_s3_bucket.trail`
2. IMPORTANCE: Mittel — Audit Nachvollziehbarkeit
3. WHAT MUST SURVIVE?: Konfiguration + Audit-Logs
4. BACKUP REQUIREMENT: Ja für Logs
5. RECOVERY METHOD: A + B
6. REPROVISIONING METHOD: A
7. DATA RESTORE REQUIRED?: Ja für Logs
8. CONFIG RESTORE REQUIRED?: Ja
9. DEPENDENCIES: CloudTrail Trail
10. RESTORE ORDER: Phase 8
11. RESTORE VALIDATION: NOT VERIFIED
12. CURRENT STATE: SSE-S3, keine Versionierung, kein Lifecycle
13. TARGET STATE: Versionierung, Lifecycle, ggf. Replikation
14. GAP: Keine Versionierung, kein Backup
15. PRIORITY: Mittel

### 4.3 Cognito User Pool

1. RESOURCE: `aws_cognito_user_pool.users`
2. IMPORTANCE: Hoch — Authentifizierung
3. WHAT MUST SURVIVE?: Konfiguration + Benutzerbestand
4. BACKUP REQUIREMENT: Ja für Benutzerdaten
5. RECOVERY METHOD: A für Config, F für User Data
6. REPROVISIONING METHOD: A
7. DATA RESTORE REQUIRED?: Ja für User Data
8. CONFIG RESTORE REQUIRED?: Ja
9. DEPENDENCIES: API Gateway Authorizer
10. RESTORE ORDER: Phase 4
11. RESTORE VALIDATION: NOT VERIFIED
12. CURRENT STATE: Konfiguration reproduzierbar, User Data kein Backup
13. TARGET STATE: Konfig reproduzierbar + User Export/Backup Strategie
14. GAP: Kein User Backup, kein Recovery-Verfahren
15. PRIORITY: Hoch

### 4.4 API Gateway HTTP API

1. RESOURCE: `aws_apigatewayv2_api`
2. IMPORTANCE: Hoch
3. WHAT MUST SURVIVE?: Konfiguration
4. BACKUP REQUIREMENT: Nein
5. RECOVERY METHOD: A
6. REPROVISIONING METHOD: A
7. DATA RESTORE REQUIRED?: Nein
8. CONFIG RESTORE REQUIRED?: Ja
9. DEPENDENCIES: Lambda, Cognito Authorizer
10. RESTORE ORDER: Phase 7
11. RESTORE VALIDATION: NOT VERIFIED
12. CURRENT STATE: Terraform reproduzierbar
13. TARGET STATE: Unverändert
14. GAP: Keine
15. PRIORITY: Niedrig

### 4.5 SQS

1. RESOURCE: `aws_sqs_queue.orders`
2. IMPORTANCE: Mittel
3. WHAT MUST SURVIVE?: Konfiguration, ggf. ausstehende Nachrichten
4. BACKUP REQUIREMENT: Nein für Daten, Retention reicht
5. RECOVERY METHOD: A, G für Nachrichten
6. REPROVISIONING METHOD: A
7. DATA RESTORE REQUIRED?: Nein, transient
8. CONFIG RESTORE REQUIRED?: Ja
9. DEPENDENCIES: Lambda Consumer
10. RESTORE ORDER: Phase 5
11. RESTORE VALIDATION: NOT VERIFIED
12. CURRENT STATE: Retention 120s, keine DLQ
13. TARGET STATE: DLQ empfohlen
14. GAP: Keine DLQ, kurze Retention
15. PRIORITY: Mittel

### 4.6 Lambda

1. RESOURCE: `aws_lambda_function.handler`, `sqs_worker`
2. IMPORTANCE: Hoch
3. WHAT MUST SURVIVE?: Code + Konfiguration
4. BACKUP REQUIREMENT: Code in Git
5. RECOVERY METHOD: A, D
6. REPROVISIONING METHOD: A
7. DATA RESTORE REQUIRED?: Nein
8. CONFIG RESTORE REQUIRED?: Ja
9. DEPENDENCIES: IAM Role, DynamoDB, SQS
10. RESTORE ORDER: Phase 6
11. RESTORE VALIDATION: NOT VERIFIED
12. CURRENT STATE: Code in Repo, Log Retention 7d
13. TARGET STATE: Unverändert
14. GAP: Log Retention Limit, kein Log Export
15. PRIORITY: Niedrig

### 4.7 IAM

1. RESOURCE: `aws_iam_role` Lambda Execution
2. IMPORTANCE: Hoch
3. WHAT MUST SURVIVE?: Konfiguration
4. BACKUP REQUIREMENT: Nein
5. RECOVERY METHOD: A
6. REPROVISIONING METHOD: A
7. DATA RESTORE REQUIRED?: Nein
8. CONFIG RESTORE REQUIRED?: Ja
9. DEPENDENCIES: Lambda
10. RESTORE ORDER: Phase 2
11. RESTORE VALIDATION: NOT VERIFIED
12. CURRENT STATE: Terraform reproduzierbar
13. TARGET STATE: Unverändert
14. GAP: Keine
15. PRIORITY: Niedrig

### 4.8 Terraform State

1. RESOURCE: `terraform/terraform.tfstate` lokal
2. IMPORTANCE: Kritisch
3. WHAT MUST SURVIVE?: State Datei
4. BACKUP REQUIREMENT: Ja
5. RECOVERY METHOD: B
6. REPROVISIONING METHOD: D
7. DATA RESTORE REQUIRED?: Ja
8. CONFIG RESTORE REQUIRED?: Ja
9. DEPENDENCIES: Alle Ressourcen
10. RESTORE ORDER: Phase 1
11. RESTORE VALIDATION: NOT VERIFIED
12. CURRENT STATE: Lokal, leer, kein Backup, kein Locking
13. TARGET STATE: Remote Backend S3+DynamoDB Lock, Versionierung
14. GAP: Kein Remote Backend, kein Backup, kein Locking
15. PRIORITY: Kritisch

### 4.9 CloudWatch Logs

1. RESOURCE: Log Group `/aws/lambda/...`
2. IMPORTANCE: Mittel
3. WHAT MUST SURVIVE?: Historische Betriebsdaten
4. BACKUP REQUIREMENT: Optional
5. RECOVERY METHOD: G
6. REPROVISIONING METHOD: A
7. DATA RESTORE REQUIRED?: Nein
8. CONFIG RESTORE REQUIRED?: Ja
9. DEPENDENCIES: Lambda
10. RESTORE ORDER: Phase 9
11. RESTORE VALIDATION: NOT VERIFIED
12. CURRENT STATE: Retention 7 Tage
13. TARGET STATE: Unverändert
14. GAP: Kurze Retention, kein Export
15. PRIORITY: Niedrig

### 4.10 CloudTrail

1. RESOURCE: `aws_cloudtrail.trail`
2. IMPORTANCE: Hoch — Audit
3. WHAT MUST SURVIVE?: Konfiguration + Logs
4. BACKUP REQUIREMENT: Ja für Logs
5. RECOVERY METHOD: A + B
6. REPROVISIONING METHOD: A
7. DATA RESTORE REQUIRED?: Ja
8. CONFIG RESTORE REQUIRED?: Ja
9. DEPENDENCIES: S3 Bucket
10. RESTORE ORDER: Phase 8
11. RESTORE VALIDATION: NOT VERIFIED
12. CURRENT STATE: Multi-Region, Management Events, Logs in S3 ohne Versionierung
13. TARGET STATE: Unverändert + S3 Versionierung
14. GAP: Keine S3 Versionierung
15. PRIORITY: Mittel

---

## 5. Data / Config / Code / State Classification

**DynamoDB**
- Configuration: Table Schema via Terraform
- Persistent Data: Orders
- Code: n/a
- State: n/a

**S3 CloudTrail**
- Configuration: Bucket Policy, Encryption via Terraform
- Audit Data: CloudTrail Logs
- Persistent Data: Ja

**Cognito**
- Configuration: User Pool Schema via Terraform
- Persistent Data: User Accounts, Passwörter
- Code: n/a

**API Gateway**
- Configuration: Api, Routes, Authorizer via Terraform
- Code: n/a

**SQS**
- Configuration: Queue Params via Terraform
- Transient Data: Nachrichten 120s

**Lambda**
- Code: Python Source in Git
- Configuration: Runtime, Env, Role via Terraform
- State: n/a

**IAM**
- Configuration: Role & Policy via Terraform

**Terraform State**
- State: Terraform State File
- Configuration: Backend Config fehlt

**CloudWatch Logs**
- Configuration: Retention via Terraform
- Audit Data: Logs

**CloudTrail**
- Configuration: Trail Config via Terraform
- Audit Data: Trail Logs

---

## 6. Recovery Methods

A — REPROVISION: IAM, API Gateway, Lambda Config, Cognito Config, SQS Config
B — BACKUP / RESTORE: DynamoDB, S3 CloudTrail Logs, Terraform State
C — POINT-IN-TIME RECOVERY: DynamoDB Ziel
D — REBUILD: Lambda Code aus Git
E — RECONCILE: Nach Restore ID/ARN Versuche
F — MANUAL RECOVERY: Cognito User Data
G — NOT REQUIRED: SQS Nachrichten transient, CloudWatch Logs

---

## 7. Recovery Dependencies

Terraform State → IAM → DynamoDB → Cognito → SQS → Lambda → API Gateway → CloudTrail/S3 → Validation

Abhängigkeiten nach Repository:
- Lambda braucht IAM Role, DynamoDB Table Name, SQS Queue URL
- API Gateway braucht Lambda Invoke ARN, Cognito User Pool Endpoint/Client ID
- CloudTrail braucht S3 Bucket Name
- Cognito Authorizer referenziert User Pool

---

## 8. Proposed Recovery Order

PHASE 1 — State / Basis
Terraform State wiederherstellen / Remote Backend etablieren

PHASE 2 — IAM / Security
IAM Roles replizieren

PHASE 3 — Persistente Daten
DynamoDB Restore / PITR

PHASE 4 — Identity
Cognito User Pool Config, User Data Recovery falls verfügbar

PHASE 5 — Messaging
SQS Queue Reprovision

PHASE 6 — Compute
Lambda Deploy aus Git

PHASE 7 — API
API Gateway Reprovision

PHASE 8 — Audit
CloudTrail + S3 Bucket

PHASE 9 — Verification
Restore Validation, Smoke Tests

Reihenfolge basiert auf tatsächlichen Terraform Abhängigkeiten. NOT VERIFIED für Restore-Tests.

---

## 9. RPO/RTO Status

NOT DEFINED
Keine RPO/RTO Werte im Repository definiert.

Datenverlust tolerierbar? NOT DEFINED
Wiederaufbau ausreichend? Für Config Ja, für Daten Nein.

---

## 10. Current Gaps

aus BACKUP-01 bestätigt:

**DynamoDB**
- PITR fehlt → WHY MATTERS: Datenverlustrisiko
- Target: PITR aktiv
- Required: PITR Enable
- Not Required: AWS Backup für Config

**Cognito**
- User Data Backup fehlt
- Target: Export/Backup Strategie
- Required: Dokumentierte User Recovery
- Not Required: sofortige Implementierung

**Terraform State**
- Lokal, kein Backend
- Target: Remote Backend S3+DynamoDB Lock
- Required: Backend Config
- Priority: Kritisch

**S3 / CloudTrail**
- Versionierung fehlt
- Target: Versionierung + Lifecycle
- Required: S3 Versioning

**SQS**
- Keine DLQ
- Target: DLQ für Fehlermanagement
- Open Decision

**Restore-Prozeduren**
- Nicht dokumentiert
- Target: Runbooks

**Restore-Tests**
- Nicht nachgewiesen
- Target: Test-Strategie

---

## 11. Target State

- DynamoDB PITR + Backups
- S3 Versionierung CloudTrail Bucket
- Terraform Remote Backend mit Locking
- Cognito User Export Dokumentation
- SQS DLQ
- Dokumentierte Restore-Prozeduren
- Restore-Test Plan

---

## 12. AWS Backup Evaluation

**DynamoDB**
- AWS Backup: OPTIONAL, native PITR ausreichend

**S3**
- AWS Backup: NOT REQUIRED, native Versionierung ausreichend

**Cognito**
- AWS Backup: NOT REQUIRED, kein Support, eigenes Export nötig

**Terraform State**
- AWS Backup: NOT REQUIRED, S3 Versionierung ausreichend

**Lambda / IAM / API Gateway**
- AWS Backup: NOT REQUIRED, Terraform Reprovision ausreichend

Gesamtbewertung: Kein pauschaler AWS Backup Bedarf, native Funktionen bevorzugen.

---

## 13. Restore Test Strategy

Aktuell NOT VERIFIED.
Empfohlener nächster Schritt: Restore-Test Plan definieren, nicht implementieren.

---

## 14. Migration / Transformation Boundary

BACKUP / RECOVERY → Wiederherstellung bestehender Zustände

MIGRATION / TRANSFORMATION → Schemaänderungen, Datenmigration

Offene Follow-Ups:
- Falls Restore DynamoDB PITR in neues Schema → Transformation nötig → OPEN FOLLOW-UP
- Cognito User Migrieren → OPEN FOLLOW-UP

Keine Transformation im Rahmen B2.

---

## 15. Recommended Next Steps

1. Dokumentation Restore-Runbooks
2. Terraform State Remote Backend evaluieren
3. DynamoDB PITR Entscheid
4. S3 Versionierung Entscheid
5. Restore-Test Strategie definieren

---

**Ende BACKUP-02**
