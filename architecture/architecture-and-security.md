# Architecture & Security Definition — May's Orders

> **Zweck:** Konsolidierte Architektur-/Sicherheits-Dokumentation auf Basis des IST-Zustands
> (verified gegen Terraform + Code). Dies ist die erste vollständige Ausführung der
> AWS Architecture + Security Definition. Kein Redesign — reine Bestandsaufnahme.
> Stand: 2026-08-31 · Branch `main` · HEAD `150f9d6` · **kein `terraform apply`** (alle
> Services CONFIGURED, NICHT CREATED).

---

## A. Architecture Overview

Reale Serverless-Kette (ADR-001), ohne VPC (ADR-006):

```text
Client
  │  login (USER_PASSWORD_AUTH) → JWT
  ▼
Cognito User Pool ──(JWT issuer)──┐
  │                               │ (Bearer JWT)
  ▼                               ▼
API Gateway (HTTP API V2, JWT-Autorisator)
  │  AWS_PROXY, Payload v2.0
  ▼
Lambda (Order Handler, python3.14, index.handler)
  │  IAM Execution Role (Least Privilege)
  ▼
DynamoDB (mays-orders, On-Demand, GSI1)
  │
  ├── CloudWatch (operational monitoring: Logs, Metriken, Alarme, Dashboard)
  └── CloudTrail → S3 (Account-weiter AWS-API-Audit-Trail; Management Events)
```

Module-Zuordnung (Terraform): `dynamodb`, `iam`, `lambda`, `cognito`, `api`, `monitoring`, `cloudtrail`.

## B. Network Topology

> Vollständige Gegenüberstellung (Ist-Serverless vs. Produktions-Ziel mit VPC/Subnetz/AZ/CIDR):
> `architecture/networking.md`.

- **Anzahl Kunden-VPCs: 0.** Keine VPC, keine Subnetze, keine Route Tables, kein
  Internet Gateway, kein NAT Gateway, keine VPC-Endpoints, keine Security Groups/NACLs, kein EC2.
- Lambda läuft in der **AWS-verwalteten Ausführungsumgebung** (KEINE Projekt-VPC; kein
  `vpc_config` in `aws_lambda_function.handler`).
- DynamoDB, Cognito, API Gateway, CloudWatch, CloudTrail, S3 sind **regionale AWS-managed
  Services** außerhalb jeder Kunden-VPC.
- Inter-Service-Zugriffe (Lambda→DynamoDB, API GW→Lambda) laufen über AWS-interne,
  TLS-gesicherte Endpunkte (SigV4/IAM), nicht über eine Kunden-VPC/Subnetz-Route.
- **Internet-Zugriff-Anforderung:** nur API-Gateway-Ingress (Client→API) und Cognito-Login
  sind öffentlich; alle weiteren Sprünge sind AWS-intern.

## C. Public / Private Classification

| Komponente | Public/Private | VPC | Subnetz | Internet-Zugriff | Grund |
|------------|----------------|-----|---------|------------------|-------|
| Cognito (Login) | Public (AWS-managed Edge) | – | – | Ja (Client-Login) | Authentifizierung |
| API Gateway (HTTP API) | Public (AWS-managed Edge) | – | – | Ja (Client-Requests) | App-Ingress |
| Lambda | Private (AWS-managed, kein Public-IP, nur Invoke via API GW) | AWS-managed | – | Nur AWS-intern | Kein direkter Client-Zugriff |
| DynamoDB | Private (AWS-managed regional) | – | – | Nein | Nur via IAM/SigV4 |
| CloudWatch | Private (AWS-managed) | – | – | Nein | Nur AWS-intern |
| CloudTrail S3 | Private (Bucket-Policy, Public-Access-Block) | – | – | Nein | Nur CloudTrail-Service |

> „Private" heißt hier: kein öffentlicher Endpunkt/keine Public-IP, Zugriff nur über
> AWS-IAM/SigV4 bzw. Bucket-Policy — NICHT „in einer Projekt-VPC".

## D. Component Inventory

| AWS-Service | Terraform-Ressource | Name | Region | AZ-Relevanz | Exposure | IAM |
|---|---|---|---|---|---|---|
| DynamoDB | `aws_dynamodb_table.orders` | `mays-orders` | eu-central-1 | AWS-managed multi-AZ | Private | Execution-Role (Put/Get/Update/Query) |
| IAM | `aws_iam_role.handler` + `aws_iam_role_policy.handler` | `mays-orders-handler-role` | global | – | – | – |
| Lambda | `aws_lambda_function.handler` | `mays-orders-handler` | eu-central-1 | AWS-managed (kein VPC) | Private | Role T011-03 |
| Cognito | `aws_cognito_user_pool.users` etc. | `mays-orders-users` | eu-central-1 | AWS-managed | Public-Login | – (Benutzer ≠ IAM) |
| API Gateway | `aws_apigatewayv2_api.orders` etc. | `mays-orders-api` | eu-central-1 | AWS-managed Edge | Public | JWT-Autorisator + Invoke-Permission |
| CloudWatch | `aws_cloudwatch_log_group.handler`, dashboard, 6 Alarme | `mays-orders-*` | eu-central-1 | – | Private | Execution-Role logs:* |
| CloudTrail | `aws_cloudtrail.trail` | `mays-orders-trail` | Account/all region | – | – | – (Service-Funktion) |
| S3 (CloudTrail-Logs) | `aws_s3_bucket.trail` + Policy | `mays-orders-cloudtrail-<acc>` | Account | – | Private | Bucket-Policy (CloudTrail) |

## E. Data Flow

| Verbindung | Protokoll | Sicherheitskontrolle |
|------------|-----------|----------------------|
| Client → Cognito | HTTPS/TLS | USER_PASSWORD_AUTH |
| Client → API Gateway | HTTP (App) | JWT Bearer (Cognito Issuer/Audience) |
| API Gateway → Lambda | AWS intern | `aws_lambda_permission` (Principal apigateway, source_arn) |
| Lambda → DynamoDB | TLS/SigV4 | IAM Execution Role (Least Privilege) |
| Lambda → CloudWatch Logs | AWS intern | `logs:*` |
| AWS-API-Aktivität → CloudTrail → S3 | AWS-managed | Bucket-Policy + SSE-S3 + Public-Access-Block |

> **Wichtige Trennung:** App-Protokoll HTTP (API Gateway `protocol_type = "HTTP"`, kein
> Custom-Domain/ACM) ist NICHT gleichbedeutend mit unverschlüsselter AWS-Kommunikation.
> Alle AWS-Service/API-Transportwege nutzen TLS-gesicherte AWS-Endpunkte.

## F. Security Boundaries

1. **Identity (Cognito)** vs **AWS-Berechtigung (IAM)** strikt getrennt (TR-15).
2. **Gateway-Ebene:** JWT-Autorisator validiert Signatur + Issuer + Audience.
3. **Service-Ebene:** Resource-Based-Policy begrenzt Lambda-Invoke auf die HTTP API.
4. **Daten-Ebene:** Least-Privilege-Rolle (kein `Scan`/`Delete`/`Batch`/`*`).
5. **Netz-Ebene:** keine Kunden-VPC; Isolierung über AWS-managed Service-Grenzen + IAM.
6. **Audit-Ebene:** CloudTrail liefert WHO/WHAT/WHEN/WHERE für Management-Events.

## G. Encryption Matrix

| Komponente | At Rest | In Transit | Verantwortlich | Status |
|------------|---------|------------|----------------|--------|
| DynamoDB | AWS-managed SSE (Default) | TLS/SigV4 | AWS | CURRENT (Default, ausreichend) |
| S3 (CloudTrail) | **explizit SSE-S3 AES256** | TLS | AWS | CURRENT (explizit) |
| CloudWatch Logs | AWS-managed SSE | TLS | AWS | CURRENT (Default) |
| Lambda (Code/Env) | AWS-managed (Deployment-Artefakt) | – | AWS | CURRENT |
| KMS (customer-managed) | – | – | – | **OPTIONAL/DEFERRED** |

> Anforderung erfüllt: **alle persistierten Projektdaten sind at rest verschlüsselt**
> (DynamoDB/S3/CloudWatch via AWS-managed bzw. explizites SSE-S3). Customer-managed KMS
> ist für den Prototyp NICHT nötig (Kostengrund) → optional/deferred.

## H. IAM / Access Matrix

| Subjekt | Ziel | Aktionen | Mechanismus |
|---------|------|----------|-------------|
| Cognito User | API | – | JWT (Authentication) |
| API Gateway | Lambda | `lambda:InvokeFunction` | Resource-Based Policy |
| Lambda Role | DynamoDB (Tabelle+GSI1) | `PutItem/GetItem/UpdateItem/Query` | Inline-Policy |
| Lambda Role | CloudWatch Logs | `CreateLogGroup/Stream`, `PutLogEvents` | Inline-Policy |
| CloudTrail Service | S3 Bucket | `s3:PutObject` (Prefix) | Bucket-Policy + SourceArn |

## I. Monitoring / Audit Matrix

| Zweck | System | Aktuell |
|-------|--------|---------|
| Operational monitoring | **CloudWatch** (Logs, Metriken, Dashboard, 6 Alarme) | IMPLEMENTED (IaC) |
| AWS-API-Audit-Trail | **CloudTrail** (Management Events RW, multi-region, global, Log-Validierung, S3) | IMPLEMENTED (IaC) |
| Data Events (DynamoDB-Objektebene) | CloudTrail | **OPTIONAL/DEFERRED** |
| Security-Eventing (SNS/EventBridge) | — | **OPTIONAL/DEFERRED** |

Trennung klar erhalten: CloudWatch = Betrieb, CloudTrail = Audit.

## J. Disaster Recovery

- **Zu schützende Daten:** Order-Items in DynamoDB (`mays-orders`).
- **Backup:** KEINE — kein PITR, keine Streams, keine Snapshots (Befund, nicht still behoben).
- **Recovery-Mechanismus:** Infrastruktur ist via Terraform reproduzierbar; **Datenwiederherstellung fehlt**.
- **Region:** eu-central-1 einzeln; keine Multi-Region-Replikation.
- **RPO/RTO:** nicht konfiguriert (kein Wiederherstellungsmechanismus eingerichtet).
- **Lambda-Failure:** synchroner Request/Response, kein Auto-Retry; Fehler → 500 (500 via CloudWatch alarmiert).
- **DynamoDB-Failure:** AWS-managed multi-AZ; On-Demand; Ausfall = regional.
- **Region-Failure:** nicht adressiert (single region). Für Prototyp akzeptabel; echtes DR = OPTIONAL.

> PITR/Backup = **FOLLOW-UP** (RECOMMENDED falls Datenwiederherstellung gefordert), derzeit DEFERRED.

## K. Scaling / Region / AZ

| Komponente | Was skaliert | Wo | Grenze | Security-Boundary |
|------------|--------------|----|--------|-------------------|
| Lambda | Invocations/Concurrency | Region eu-central-1 | Default-Concurrency (1000, unkonfiguriert) | Role (unverändert) |
| DynamoDB | On-Demand (`PAY_PER_REQUEST`) | Region | Hot-Partition auf GSI1 `gsi1pk="LIST"` | Role (unverändert) |
| API Gateway | Automatisch (HTTP API) | AWS-Edge | Default-Quotas (kein Throttling konfiguriert) | JWT-Autorisator |
| CloudTrail | Service-managed | Account (multi-region) | – | Bucket-Policy |

- **Region:** eu-central-1 (Default `var.aws_region`). Kein Multi-Region (nicht nötig, Prototyp).
- **AZ-Relevanz:** keine eigenen AZ-Ressourcen; AWS-managed Services sind multi-AZ.
- Multi-Region wird NICHT eingeführt (ADR-006, unnötige Komplexität).

## L. Terraform Mapping

| Terraform-Ressource | AWS | Security-Zweck | Netz-Position |
|---------------------|-----|----------------|---------------|
| `aws_dynamodb_table.orders` | DynamoDB | Datenhaltung, Conditional Writes | AWS-managed (kein VPC) |
| `aws_iam_role/policy.handler` | IAM | Least Privilege | – |
| `aws_lambda_function.handler` | Lambda | Business-Logik | AWS-managed (kein VPC) |
| `aws_lambda_permission.api_gateway` | Resource-Policy | Invoke auf API GW begrenzen | – |
| `aws_apigatewayv2_*` | API Gateway | JWT-Autorisierung, Routing | AWS-Edge |
| `aws_cognito_*` | Cognito | Authentication | AWS-managed |
| `aws_cloudwatch_*` | CloudWatch | Monitoring/Retention | AWS-managed |
| `aws_cloudtrail.trail` + S3-* | CloudTrail/S3 | Audit-Trail, at-rest & Bucket-Policy | AWS-managed |

---

## Final Security Checklist (Antworten)

- **VPCs:** 0
- **Public Subnets:** 0
- **Private Subnets:** 0
- **Komponente wo:** alle AWS-managed (keine in Projekt-VPC)
- **Öffentlich erreichbar:** Cognito (Login), API Gateway (HTTP API)
- **Privat:** Lambda, DynamoDB, S3 (CloudTrail), CloudWatch, CloudTrail
- **Lambda:** AWS-managed Umgebung (kein VPC)
- **DynamoDB:** AWS-managed regional (kein VPC)
- **Lambda → DynamoDB:** AWS SDK über TLS/SigV4 (kein VPC-Endpoint)
- **Externer Verkehr:** Client → API Gateway (HTTP, JWT) → Lambda
- **Region:** eu-central-1
- **AZs:** AWS-managed (keine eigenen)
- **Skalierung:** Lambda auto (Concurrency), DynamoDB On-Demand, API GW auto
- **Gespeicherte Daten:** Order-Items (DynamoDB), CloudTrail-Logs (S3), CloudWatch-Logs
- **Persistierte Daten at rest verschlüsselt:** JA (DynamoDB/CloudWatch AWS-managed; CloudTrail S3 explizit SSE-S3)
- **Data in transit:** JA wo gefordert (AWS-Service-TLS); App = HTTP (dokumentiert)
- **CloudTrail aktiviert:** JA (IaC, multi-region, Management Events RW)
- **API/Data-Events geloggt:** Management-Events JA; Data-Events NEIN (deferred)
- **Logging verschlüsselt:** JA (S3 SSE-S3)
- **Log-Integrität:** JA (`enable_log_file_validation = true`)
- **DynamoDB PITR:** NEIN (Befund, deferred)
- **Recovery-Prozedur:** Terraform-Reproduktion; Daten-Recovery fehlt
- **RPO/RTO:** nicht definiert (kein Mechanismus)
- **Screenshot-Evidenz:** NICHT VERFÜGBAR (kein `apply`; alle Services NOT CREATED) → später
- **Architektur-Doku:** dieses Dokument + `architecture/architecture-decisions.md` +
  `architecture/request-flow.md` + `security/` (iam/authentication/cloudtrail)