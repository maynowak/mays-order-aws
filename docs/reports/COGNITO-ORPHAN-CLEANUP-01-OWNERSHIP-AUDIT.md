# COGNITO-ORPHAN-CLEANUP-01 OWNERSHIP AUDIT

**Datum:** 2026-09-27  
**Projekt:** Mays-Orders-AWS  
**AWS Account:** 240571105849  
**Region:** eu-central-1  
**Profile:** mayaws  
**Repository:** maysnowak/mays-order-aws

## 1. Ausgangslage

Nach Abschluss von B8.6 FINAL-CONSISTENCY-RECOVERY-AUDIT-AND-DOCUMENTATION-01 wurden drei Cognito User Pools mit Tag `Project=mays-orders` identifiziert, die nicht im aktuellen Terraform Remote State enthalten sind.

Pool IDs:
- eu-central-1_BKXksSwJI
- eu-central-1_CwDJAbTiS
- eu-central-1_QOJoc7nfZ

Ziel: Ownership/Dependency-Audit ohne Änderung der Terraform/Remote-State-Architektur.

## 2. Untersuchte Cognito Pools

### Pool 1: eu-central-1_BKXksSwJI
- Pool Name: mays-orders-users
- Status: Active
- CreationDate: 2026-09-25T18:46:01.492000+02:00
- LastModifiedDate: 2026-09-25T18:46:01.492000+02:00
- Tags: Environment=Development, Maker=Maymilly Nowak, Project=mays-orders
- Users: 0
- App Clients: mays-orders-client
- Lambda Triggers: {}
- Identity Providers: None
- MFA Configuration: OFF

### Pool 2: eu-central-1_CwDJAbTiS
- Pool Name: mays-orders-users
- Status: Active
- CreationDate: 2026-09-25T18:17:35.897000+02:00
- LastModifiedDate: 2026-09-25T18:17:35.897000+02:00
- Tags: Environment=Development, Maker=Maymilly Nowak, Project=mays-orders
- Users: 0
- App Clients: mays-orders-client
- Lambda Triggers: {}
- Identity Providers: None
- MFA Configuration: OFF

### Pool 3: eu-central-1_QOJoc7nfZ
- Pool Name: mays-orders-users
- Status: Active
- CreationDate: 2026-09-25T18:29:59.577000+02:00
- LastModifiedDate: 2026-09-25T18:29:59.577000+02:00
- Tags: Environment=Development, Maker=Maymilly Nowak, Project=mays-orders
- Users: 0
- App Clients: mays-orders-client
- Lambda Triggers: {}
- Identity Providers: None
- MFA Configuration: OFF

## 3. Terraform State Prüfung

Remote State geprüft für:
- env:/mays-orders/terraform.tfstate
- env:/mays-order-par/terraform.tfstate

Ergebnis: Keine der drei Pool IDs ist im aktuellen Remote State enthalten.

State ist nach B8.5 Destroy leer, Ressourcenanzahl 0.

## 4. Configuration Prüfung

Terraform Module `modules/cognito/main.tf` definiert `aws_cognito_user_pool.users` ohne hardcodierte IDs.

Keine Referenz auf die drei Pool IDs in aktueller Git-Konfiguration gefunden.

## 5. Dependency Prüfung

AWS-Abfragen:
- API Gateway APIs: keine vorhanden
- Lambda Functions: keine vorhanden
- Cognito App Clients existieren pro Pool, aber keine aktiven Authorizer/Integrationen gefunden
- CloudFormation Stacks: keine relevanten Referenzen

Ergebnis: Keine aktive Abhängigkeit festgestellt.

## 6. User / App Client Prüfung

- User count pro Pool: 0
- App Client pro Pool: 1 x mays-orders-client
- App Client Creation Dates entsprechen Pool Creation Dates
- Keine Nutzer, keine Sign-In Activity nachweisbar

## 7. Historische Herkunft

Creation Dates liegen vom 25.09.2026. Git History zeigt in diesem Zeitraum:
- Installer Parallel Deployment Tests
- Workspace/Parallel Project Änderungen

Wahrscheinlich Herkunft aus Installer-Testläufen vor/nach Migration, Pools wurden erstellt aber nie in Remote State übernommen bzw. nach Destroy nicht bereinigt.

Kennzeichnung als historische Erkenntnis, keine Nachträgliche Umschreibung alter Reports.

## 8. Entscheidung pro Pool

| Pool ID | Name | Users | App Clients | Terraform State | Active Dependency | Historical Origin | Decision |
|---------|------|-------|-------------|-----------------|-------------------|------------------|----------|
| eu-central-1_BKXksSwJI | mays-orders-users | 0 | 1 | nicht enthalten | keine festgestellt | Installer Test 25.09.2026 | REQUIRES_MANUAL_DECISION |
| eu-central-1_CwDJAbTiS | mays-orders-users | 0 | 1 | nicht enthalten | keine festgestellt | Installer Test 25.09.2026 | REQUIRES_MANUAL_DECISION |
| eu-central-1_QOJoc7nfZ | mays-orders-users | 0 | 1 | nicht enthalten | keine festgestellt | Installer Test 25.09.2026 | REQUIRES_MANUAL_DECISION |

Begründung: Pools sind nicht im aktuellen Terraform State und haben keine aktiven AWS-Abhängigkeiten oder Nutzer. Allerdings existieren App Clients, was eine aktive Konfiguration suggeriert. Nach den definierten Kriterien für SAFE_TO_DELETE müssen keine relevanten App Clients vorhanden sein. Da App Clients existieren, wird konservativ REQUIRES_MANUAL_DECISION gewählt.

## 9. Cleanup Empfehlung

Keine Löschung im Rahmen dieses Audits.

SAFE_TO_DELETE wurde nicht erreicht.

Empfehlung: Separate Freigabeentscheidung nach expliziter Prüfung.

Falls Cleanup gewünscht:
- Vorab manuelle Prüfung auf versteckte Referenzen
- Dokumentation des Cleanup-Vorgangs
- Getrennter Schritt nach expliziter Freigabe

## 10. Risiken / offene Unsicherheiten

- App Clients existieren pro Pool, obwohl keine Nutzer vorhanden sind
- Historische Herkunft nicht 100% belegt, aber plausibel als Testartefakte
- Keine aktive Nutzung nachweisbar, aber vollständige Abhängigkeitsanalyse über AWS CLI ist limitiert
- Keine Löschung durchgeführt

## 11. Explizite Aussage

Löschung wurde in diesem Audit **nicht** durchgeführt.

Terraform State, Remote State und AWS Infrastructure blieben unverändert.

---

**Nächster Schritt:** Separater Cleanup-Schritt nach expliziter Prüfung des Audit-Ergebnisses, falls gewünscht.
