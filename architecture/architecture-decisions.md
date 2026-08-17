# Architecture Decisions — May's Orders

## ADR-001: Serverless-Kernarchitektur (API Gateway + Lambda + DynamoDB)

**Status:** ACCEPTED

### Problem

Ein Order-Management-System mit vier Endpunkten und klaren State-Transitions soll
kostengünstig, skalierbar und wartbar betrieben werden.

### Alternativen

| Option | Bewertung |
|--------|-----------|
| **A) Serverless: HTTP API + Lambda + DynamoDB** | Pay-per-use, automatisch skalierend, kein Server-Management. **GEWÄHLT** |
| B) EC2 (verwalteter Server) | Server-Patching, feste Kosten, manuelles Auto-Scaling, Overkill für 100–100k Orders/Tag |
| C) RDS (relational) | Kosten + Wartung; benötigt VPC/Subnets; kein relationales Modell gefordert |
| D) Fargate (Container) | Mehr Komplexität (Image-Build, ECS), kein Vorteil gegenüber Lambda hier |

### Entscheidung

Option A. Lambda-Funktion + DynamoDB sind vollständig verwaltete Services, skalieren
automatisch, sind kostenbewusst (Pay-per-Use, Free-Tier) und erfordern **keine VPC,
Subnets oder NAT Gateway**.

### Trade-offs

- Cold Starts: akzeptabel für Bestell-Backoffice-Latenz (erste Request einiger 100 ms).
- Lambda-Zeitlimit/Invocations sind begrenzt, für diese Workload irrelevant.
- Kein dauerhaft gehaltener Prozess → Zustand lebt ausschließlich in DynamoDB (stateless,
  gute Skalierung).

## ADR-002: DynamoDB Single-Table + GSI für Listing

**Status:** ACCEPTED (Begründung: `database/dynamodb-design.md`, `database/access-patterns.md`)

- Eine Tabelle `mays-orders`, Punktzugriffe über `pk`, Listing über GSI1 (`LIST` → `createdAt`).
- **Kein Scan** für irgendein Pattern.

## ADR-003: Cognito User Pool als Authentication

**Status:** ACCEPTED (Begründung: `security/authentication-decision.md`)

- Benutzeridentität via Cognito User Pool; JWT wird vom API Gateway `COGNITO_USER_POOLS`-Autorisator validiert.
- Kostenlos bis 50.000 MAU.
- Kein Custom-Authorizer, kein IAM für Benutzer.

## ADR-004: HTTP API (API Gateway V2) statt REST API

**Status:** ACCEPTED

- Native JWT-Autorisierung, ~70 % günstiger pro Request, ausreichendes Feature-Set.

## ADR-005: State Machine im Code statt Step Functions

**Status:** ACCEPTED (Woche 1)

| Kriterium | Step Functions | Code (Domain-Layer) |
|-----------|----------------|---------------------|
| Sichtbarkeit des Zustands | Als Ressource sichtbar | Im Code als Tabelle |
| Kosten | 4.000 State-Transitions kostenlos, danach 0,025 $/1.000 | 0 |
| Komplexität | Neuer Service, ASL-Definition, zusätzliches IAM | Eine Modul-Funktion, unit-testbar |
| Geeignet | Komplexe, langlaufende Prozesse | 6 Zustände, ein Request/Response |

6 Zustände, 6 gültige Übergänge, synchron — ein zusätzlicher AWS-Service wäre hier
**unnötige Komplexität** (Requirements C-03). Die State Machine wird als pure, unit-getestete
Funktion implementiert; DynamoDB Conditional Writes garantieren die atomare Durchsetzung.

**Wenn später nötig** (z. B. langlaufende Versand-Integration): Step Functions als
Migration dokumentiert.

## ADR-006: Keine zusätzlichen Services (SQS, EventBridge, VPC, NAT)

**Status:** ACCEPTED

- Kein Bedarf an asynchronem Messaging (synchroner Request/Response).
- Kein VPC: Lambda → DynamoDB läuft ohne VPC.
- Kein zusätzlicher Service wird ohne neue Architecture Decision ergänzt.

## ADR-007: On-Demand Capacity (vorläufig)

**Status:** PROPOSED (Entscheidung in Woche 4 mit Kosten-Daten finalisiert)

- On-Demand für schwankenden Test-/Demo-Verkehr; Quantifizierung Provisioned vs. On-Demand
  in `cost/cost-analysis.md`.

## Zusammenfassung Architektur

```text
Client
  │  Bearer JWT
  ▼
Cognito User Pool ──(JWT-Ausstellung)──┐
  ▲                                   │
  │ login/refresh                     ▼
  └────────────────── API Gateway (HTTP API, JWT-Autorisator)
                              │
                              ▼
                      Lambda (Order Handler)
                              │  IAM Execution Role (Least Privilege)
                              ▼
                        DynamoDB (mays-orders)
                              │
                              ▼
                          CloudWatch (Logs, Metriken, Alarme)
```