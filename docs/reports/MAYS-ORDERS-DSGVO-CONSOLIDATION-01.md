# MAYS-ORDERS-DSGVO-CONSOLIDATION-01
## Datenschutzanalyse Mays-Orders-AWS

**Datum:** 2026-10-10  
**Branch:** main  
**HEAD:** 0b689ee22273c172bfd8b11d9950428506042e7d  
**Status:** ANALYSIS COMPLETE – READ ONLY

---

## 1. Executive Summary

Mays-Orders-AWS ist ein serverloses Order-Management System. Technische Datenschutz-Eigenschaften sind teilweise vorhanden, jedoch fehlen zentrale DSGVO-unterstützende Funktionen wie Retention, Löschung, Betroffenenrechte, objektbezogene Autorisierung und Privacy by Design Konfiguration.

Die Software bietet technische Funktionen, die Betreiberpflichten unterstützen können. Rechtsgrundlagen, Verarbeitungszwecke und Löschfristen werden nicht von der Software vorgegeben und bleiben Betreiberverantwortung.

Keine AWS Mutationen durchgeführt.

---

## 2. Repository Baseline

- OpenCode Orchestration vorhanden: Commander, Architect, Developer, Tester, Reviewer
- Governance Docs gelesen: AGENTS.md, docs/AGENTS.md, docs/AI_AGENT_PLAYBOOK.md, docs/PROJECT_STATUS.md, docs/AI_AUDITLOG.md
- Working Tree clean, untracked terraform/tfplan
- Terraform Provider AWS v6.65.0
- Region eu-central-1, project_name default mays-orders

---

## 3. Data Inventory – technisch bestätigt

### Order Data
DATA CATEGORY: Order Master Data
SOURCE: API POST /orders
PURPOSE: Bestellverwaltung
PERSONAL DATA: Ja – customer.name, customer.email
STORAGE LOCATION: DynamoDB Table project_name
PROCESSING COMPONENT: Lambda order_service.create_order
ACCESS: Cognito authentifiziert, aktuell keine Objektprüfung
RETENTION: Unbegrenzt, kein TTL
DELETION: Keine Delete API, manueller DynamoDB Delete möglich
EXPORT: Keine Export Funktion
ENCRYPTION: DynamoDB Server-Side Encryption default
EVIDENCE: database/dynamodb-design.md:32-33, api/endpoints.md:22-24
STATUS: CONFIRMED

### Customer Data
DATA CATEGORY: Customer Contact
SOURCE: API Input
PURPOSE: Bestellzuordnung
PERSONAL DATA: Ja – Name, Email
STORAGE LOCATION: DynamoDB Order Item Map customer
PROCESSING COMPONENT: Lambda validation + order_service
ACCESS: Authentifizierter Staff
RETENTION: Unbegrenzt
DELETION: Nicht automatisiert
EXPORT: Nein
ENCRYPTION: DynamoDB SSE
EVIDENCE: database/dynamodb-design.md:32-33
STATUS: CONFIRMED

### Cognito User Identity
DATA CATEGORY: Benutzeridentität
SOURCE: Cognito User Pool
PURPOSE: Authentication
PERSONAL DATA: Ja – sub, email, username, groups
STORAGE LOCATION: Cognito User Pool eu-central-1
PROCESSING COMPONENT: API Gateway Cognito Authorizer
ACCESS: Cognito Admin APIs
RETENTION: Cognito User Lifecycle, Betreiberverantwortung
DELETION: Via Cognito Admin API
EXPORT: Admin API Export möglich
ENCRYPTION: AWS Managed
EVIDENCE: security/authentication-decision.md:27-32
STATUS: CONFIRMED

### JWT Claims
DATA CATEGORY: Auth Token
SOURCE: Cognito Access Token
PURPOSE: Authorization
PERSONAL DATA: Ja – sub, cognito:username, cognito:groups
STORAGE LOCATION: In Transit
PROCESSING COMPONENT: API Gateway, Lambda
ACCESS: Authentifizierter Client
RETENTION: Token Lifetime ~1h
DELETION: Token Ablauf
EXPORT: Nein
ENCRYPTION: Signed JWT
EVIDENCE: security/authentication-decision.md:34-36
STATUS: CONFIRMED

### SQS Nachrichten
DATA CATEGORY: Order Event
SOURCE: Lambda _send_to_sqs
PURPOSE: Async Verarbeitung
PERSONAL DATA: Indirekt – orderId referenziert personenbezogene Order
STORAGE LOCATION: SQS Queue
PROCESSING COMPONENT: Lambda Handler, Worker
ACCESS: SQS IAM Role
RETENTION: SQS Standard 4 Tage
DELETION: Nachrichten Delete nach Konsum
EXPORT: Nein
ENCRYPTION: SQS Server-Side Encryption optional
EVIDENCE: lambda/src/index.py:34-48
STATUS: CONFIRMED

### CloudWatch Logs
DATA CATEGORY: Logs
SOURCE: Lambda Execution
PURPOSE: Observability
PERSONAL DATA: Möglich – orderId, customer Daten in Logs
STORAGE LOCATION: CloudWatch Logs /aws/lambda/*
PROCESSING COMPONENT: Lambda
ACCESS: IAM
RETENTION: Konfigurierbar via var.log_retention_days
DELETION: Log Group Deletion
EXPORT: Log Export möglich
ENCRYPTION: CloudWatch KMS optional
EVIDENCE: terraform/modules/lambda/main.tf
STATUS: CONFIRMED

### CloudTrail Events
DATA CATEGORY: Audit Log
SOURCE: AWS API Calls
PURPOSE: Audit
PERSONAL DATA: Nein – API Events
STORAGE LOCATION: S3 Bucket project_name-cloudtrail-accountid
PROCESSING COMPONENT: CloudTrail
ACCESS: S3 IAM
RETENTION: Unbegrenzt, Lifecycle fehlend
DELETION: S3 Delete
EXPORT: S3 Access
ENCRYPTION: S3 SSE
EVIDENCE: terraform/modules/cloudtrail/main.tf
STATUS: CONFIRMED

### Terraform State
DATA CATEGORY: Infrastructure State
SOURCE: Terraform
PURPOSE: IaC
PERSONAL DATA: Nein
STORAGE LOCATION: S3 mays-orders-tfstate-central-240571105849
PROCESSING COMPONENT: Terraform
ACCESS: IAM
RETENTION: Unbegrenzt
DELETION: Manuell
EXPORT: Nein
ENCRYPTION: SSE
EVIDENCE: terraform/backend.tf
STATUS: CONFIRMED

---

## 4. Data Flow Analysis

Client → Cognito Auth → API Gateway HTTP API → Lambda Handler → DynamoDB
                                      ↘ SQS → Worker → DynamoDB

Zusätzliche Flüsse:
Lambda → CloudWatch Logs
AWS Services → CloudTrail → S3
Terraform → S3 State + DynamoDB Lock

Daten entstehen im API Request, werden in Lambda validiert, in DynamoDB persistiert, über SQS asynchron weiterverarbeitet. Logs und Audit Trails erhalten Metadaten. Keine Datenkopien in S3 außer CloudTrail.

---

## 5. GDPR Requirements Mapping – technisch

Art. 5 Grundsätze: Datenminimierung teilweise – customer.name/email Pflicht. Zweckbindung nicht technisch erzwungen. Rechtmäßigkeit: Betreiberverantwortung.

Art. 6 Rechtmäßigkeit: Software neutral, keine Rechtsgrundlage fest.

Art. 12-15 Transparenz/Auskunft: Keine technische Auskunftsfunktion vorhanden.

Art. 16 Berichtigung: Update Order Status möglich, Edit Order nicht vorgesehen.

Art. 17 Löschung: Keine Delete API, keine kaskadierende Löschung.

Art. 18 Einschränkung: Nicht implementiert.

Art. 20 Datenübertragbarkeit: Kein Export.

Art. 25 Datenschutz durch Technik: Verschlüsselung default, keine Pseudonymisierung, keine Objekt-Autorisierung.

Art. 28 Auftragsverarbeitung: AWS als Prozessor, Verträge Betreiberverantwortung.

Art. 30 Verzeichnis: Nicht automatisch erstellt.

Art. 32 Sicherheit: Cognito JWT, IAM Least Privilege, SSE, CloudTrail vorhanden.

Art. 33-34 Datenschutzverletzung: CloudTrail vorhanden, Benachrichtigung nicht automatisiert.

Art. 44 ff Internationale Übermittlung: Region eu-central-1 konfigurierbar.

---

## 6. Privacy by Design

Vorhanden: Encryption at Rest/Transit, Least Privilege IAM, Cognito Auth, CloudTrail Audit, Projektisolation via project_name.

Fehlend: Datenminimierung erweiterbar, Pseudonymisierung, Objektbezogene Autorisierung, Logging-Minimierung, TTL/Retention, Löscharchitektur.

Verbesserungspotenzial: Next Token statt Order ID in Pagination, Log Masking, Tagging Strategie.

---

## 7. Security Assessment

Authentication: Cognito User Pool + JWT via API Gateway – bestätigt.

Authorization: Nur Authentifizierung geprüft, keine Objektprüfung. Ein authentisierter Staff kann aktuell theoretisch alle Orders lesen/ändern. Keine Tenant Isolation auf Datenebene.

IAM: Lambda Execution Role least privilege, DynamoDB Zugriff auf Tabelle.

Verschlüsselung: AWS Default SSE aktiv.

Projektisolation: Über project_name und workspaces, kein Multi-Tenant.

---

## 8. Retention and Erasure

DynamoDB: Kein TTL konfiguriert, unbegrenzte Aufbewahrung.

SQS: Standard Retention 4 Tage.

CloudWatch Logs: Retention via var.log_retention_days konfigurierbar.

CloudTrail: Unbegrenzt, kein Lifecycle.

S3 CloudTrail Bucket: Kein Lifecycle.

Backup: DynamoDB Point-in-Time Recovery aktiv konfigurierbar, Cognito Backup separat.

Löschung: Keine technische Lösch-API, keine kaskadierende Löschung.

Vorschlag: Konfigurierbare Retention Policy via Installer Variablen: log_retention_days, cloudtrail_retention_days, dynamodb_ttl_enabled, dynamodb_ttl_attribute.

---

## 9. Data Subject Rights

Auskunft: Nicht technisch unterstützt.

Berichtigung: Status Update möglich, Order Edit nicht vorgesehen.

Löschung: Nicht unterstützt.

Einschränkung: Nicht unterstützt.

Export/Datenübertragbarkeit: Nicht unterstützt.

Empfehlung: Administrative Schutzfunktion mit starker Autorisierung, keine öffentlichen Endpunkte.

---

## 10. Privacy Assessment Capability

Konzept für optionale Prüfung:

A. Statisch aus Terraform: Region, Verschlüsselung, Log Retention, IAM Roles, Public Access Block
B. Lokale Tests: Konfiguration, Validierung
C. AWS Read-only: Ressourcenliste, Tagging
D. Betreiberangaben: Rechtsgrundlage, Zwecke, Löschfristen

Ergebnisformat: CHECK, REQUIREMENT, EXPECTED, ACTUAL, EVIDENCE, STATUS, RISK, RECOMMENDATION

Keine rechtliche Konformitätsbescheinigung.

---

## 11. Installer Integration Options

Mögliche Optionen:
- AWS Region
- Log Retention
- CloudTrail Retention
- DynamoDB TTL Enable/Disable
- Encryption Settings
- Privacy Assessment Report Export

Beibehalten: Terraform Workspaces, Projektisolation.

---

## 12. Operator Responsibilities

Betreiber muss definieren:
- Verarbeitungszwecke und Rechtsgrundlagen
- Datenaufbewahrungsfristen
- Löschfristen
- Betroffenenrechte Prozesse
- Auftragsverarbeiter Verträge
- Datenschutzinformationen

Software unterstützt technisch, entscheidet nicht rechtlich.

---

## 13. Gap Analysis – priorisiert

GAP-01: Objektbezogene Autorisierung
CATEGORY: Security
CURRENT: Authentifizierung nur
EXPECTED: Prüfung order ownership / RBAC
PRIORITY: P0

GAP-02: Löschfunktion
CATEGORY: GDPR Art.17
CURRENT: Keine Delete API
EXPECTED: Löschen Order + abhängige Daten
PRIORITY: P0

GAP-03: Retention Policy
CATEGORY: Retention
CURRENT: Keine TTL / Lifecycle
EXPECTED: Konfigurierbare Retention
PRIORITY: P1

GAP-04: Data Subject Rights Support
CATEGORY: GDPR
CURRENT: Keine Export/Auskunft
EXPECTED: Admin Export/Auskunft
PRIORITY: P1

GAP-05: Logging Minimierung
CATEGORY: Privacy by Design
CURRENT: Ungefilterte Logs
EXPECTED: PII Masking
PRIORITY: P2

---

## 14. Implementation Roadmap

1. Dateninventar – DONE
2. Datenflussanalyse – DONE
3. Sicherheitsprüfung – DONE
4. Retention Konzept – offen
5. Betroffenenrechte Konzept – offen
6. Privacy Configuration – offen
7. Privacy Assessment – offen
8. Installer Unterstützung – offen
9. Dokumentation – in Arbeit
10. Verifikation – offen

---

## 15. Evidence

Evidenzbasierte Aussagen mit Datei-Referenzen siehe oben. Keine unbelegten Behauptungen.

---

## 16. Open Questions

- Gibt es bestehende Datenschutz-Dokumentation?
- Ist Multi-Tenant geplant?
- Welche Löschfristen sind rechtlich gefordert?

---

## 17. Final Recommendation

Analyse abgeschlossen. Software bietet solide Basis für datenschutzkonforme Installation, erfordert jedoch Betreiberentscheidungen und zusätzliche technische Maßnahmen für vollständige DSGVO-Unterstützung.

Keine AWS Mutationen durchgeführt. Bericht fertig.

---

CHECKPOINT: MAYS-ORDERS-DSGVO-CONSOLIDATION-01  
STATUS: YELLOW  
AWS MUTATIONS: NONE  
FILES CHANGED: docs/reports/MAYS-ORDERS-DSGVO-CONSOLIDATION-01.md, docs/reports/MAYS-ORDERS-DSGVO-CONSOLIDATION-01-EXECUTION_LOG.md
