# Technical Requirements — May's Orders

## 1. Systemkontext

Serverloses Order-Management-System auf AWS-Basis:

```text
Client → API Gateway → Lambda → DynamoDB → CloudWatch
```

## 2. Technische Anforderungen

### 2.1 API

| ID | Anforderung |
|----|-------------|
| TR-01 | REST-API mit den Endpunkten `POST /orders`, `GET /orders/{orderId}`, `GET /orders`, `PATCH /orders/{orderId}/status` |
| TR-02 | Request-Validierung (Pflichtfelder, Formate) |
| TR-03 | Konsistente Fehlerantworten (HTTP-Statuscodes, Fehlercodes) |
| TR-04 | Pagination für `GET /orders` |

### 2.2 Compute (Lambda)

| ID | Anforderung |
|----|-------------|
| TR-05 | Lambda-Funktionen als Kern-Compute (Node.js/TypeScript, Entscheidung dokumentiert) |
| TR-06 | Idempotente und fehlerfreie Handler |
| TR-07 | CloudWatch Logging |

### 2.3 Datenhaltung (DynamoDB)

| ID | Anforderung |
|----|-------------|
| TR-08 | Single-Table-Design (Entscheidung im Datenmodell begründet) |
| TR-09 | Effiziente Access Patterns ohne unnötige Scans |
| TR-10 | Conditional Writes für Statusübergänge und Konkurrenzschutz |
| TR-11 | Pagination über LastEvaluatedKey |

### 2.4 Sicherheit / Auth

| ID | Anforderung |
|----|-------------|
| TR-12 | Authentifizierung über Cognito User Pool (JWT) — Entscheidung dokumentiert |
| TR-13 | Trennung: Authentication (Benutzeridentität) vs. IAM (Service-Berechtigungen) |
| TR-14 | IAM Least Privilege für Lambda Execution Roles |
| TR-15 | Keine IAM Access Keys als Benutzer-Login |
| TR-16 | Keine Secrets im Source Code / Logs / README |

### 2.5 Infrastruktur / IaC

| ID | Anforderung |
|----|-------------|
| TR-17 | Terraform als IaC für API Gateway, Lambda, DynamoDB, IAM, Cognito (falls final entschieden) |
| TR-18 | Reproduzierbare Umgebung (Terraform State) |

### 2.6 Monitoring / Reliability

| ID | Anforderung |
|----|-------------|
| TR-19 | CloudWatch: API-Requests, API-Errors, Lambda-Errors, Lambda-Duration, DynamoDB-Aktivität |
| TR-20 | Sinnvolle CloudWatch Alarms (sofern angemessen, kostenbewusst) |

## 3. Nicht-funktionale technische Anforderungen

| ID | Anforderung |
|----|-------------|
| TNFR-01 | Antwortzeiten im Serverless-Normalfall (einzelne Hunderte ms) |
| TNFR-02 | Skalierung bis 100.000 Orders/Tag bewerten (Lambda, API GW, DynamoDB, Hot Partitions) |
| TNFR-03 | Kostenanalyse: API Gateway, Lambda, DynamoDB, CloudWatch, Cognito |
| TNFR-04 | AWS Well-Architected Review (5 Säulen) |

## 4. Abgrenzung / Nicht-Ziele (Scope)

| Punkt | Begründung |
|-------|------------|
| Kein VPC / NAT Gateway / Subnets | Nicht erforderlich; Lambda+DynamoDB sind verwaltete Services, kein Netzwerkzugriff auf private Ressourcen nötig. Zusätzliche Services nur mit begründeter ADC. |
| Kein SQS | Kein Message-Pattern gefordert; Synchroner Request/Response reicht für das aktuelle Feature-Set. |
| Kein RDS / EC2 | Kein relationales Modell/Verwaltung erforderlich; Serverless-Kosten und -Skalierung bevorzugt. |
| Kein Step Functions | State Machine ist im Domain-Layer implementiert (geringe Komplexität, 6 Zustände). ADC dokumentiert. |
| Kein Frontend | Projekt fokussiert auf Backend-API + Infrastruktur. Browser-Verifikation ggf. via HTTP-Test. |
