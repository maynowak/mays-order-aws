# F003 — API Gateway (HTTP API)

| Feld | Wert |
|------|------|
| **ID** | F003 |
| **Name** | API Gateway (HTTP API) |
| **Status** | 🟡 DESIGNED — NOT IMPLEMENTED |
| **Week** | 2 |
| **Abhängigkeiten** | F001 |
| **Fachquelle** | `architecture/architecture-decisions.md` (ADR-004), `api/endpoints.md` |

## Beschreibung

HTTP API (API Gateway V2) mit Cognito-JWT-Autorisator und Lambda-Integration für die
Endpunkte `POST /orders`, `GET /orders/{orderId}`, `GET /orders`, `PATCH /orders/{orderId}/status`.

## Tasks

| ID | Task | Status |
|----|------|--------|
| T003-01 | HTTP API + Integration + Route `POST /orders` | ✅ COMPLETE |
| T003-02 | Route `GET /orders/{orderId}` | ✅ COMPLETE |
| T003-03 | Route `GET /orders` | ✅ COMPLETE |
| T003-04 | Route `PATCH /orders/{orderId}/status` | ✅ COMPLETE |
| T003-05 | JWT-Autorisator (Cognito) anbinden | ✅ COMPLETE |
| T003-06 | Lambda-Invoke-Permission (Resource-Based Policy) | ✅ COMPLETE |
| T003-07 | Live-Test: alle Routen mit Token | ⏳ PLANNED |

> T003-01…T003-06 sind im Rahmen von **F011/T011-06** (Branch `feature/http-api`) per
> Terraform implementiert: `aws_apigatewayv2_api.orders`, `aws_apigatewayv2_stage.default`,
> `aws_apigatewayv2_authorizer.jwt`, `aws_apigatewayv2_integration.lambda`
> (AWS_PROXY, Payload 2.0), vier `aws_apigatewayv2_route.*` (alle JWT-geschützt),
> `aws_lambda_permission.api_gateway`. Kein `apply` — Ressourcen erst nach Freigabe erzeugt.

## Testnachweise

| Prüfung | Status |
|---------|--------|
| Terraform fmt/init/validate | PASS (T011-06, Provider 6.60.0) |
| Terraform plan | NOT RUN (zu T011-07) |
| Live: Routen erreichbar (200) | NOT RUN (kein apply) |
| Live: 401 ohne Token | NOT RUN (kein apply) |

## Git Checkpoint

- Branch: `feature/http-api` · Commit: offen · Push: offen (Checkpoint-Task)

## Next Step

T003-07 (Live-Test: alle Routen mit Token) — nach `apply` und Freigabe (F011/T011-08).