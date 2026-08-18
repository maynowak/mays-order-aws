# T011-06 HTTP API REPORT

> Task-Report: F011/T011-06 — API Gateway HTTP API + vier Routen + JWT Authorizer +
> Lambda-Integration + Invoke-Permission, als Terraform-Konfiguration. Git bleibt
> Source of Truth.

## Summary

Im Rahmen von F011 (Terraform Infrastructure) wurde die dokumentierte HTTP API
(API Gateway V2, ADR-004) über Terraform implementiert: HTTP API (`aws_apigatewayv2_api`),
`$default`-Stage mit Auto-Deploy, JWT-Authorizer (Cognito), eine Lambda-Integration
(AWS_PROXY, Payload Format 2.0) auf die bestehende Python-3.14-Lambda, vier
dokumentierte Order-Routen (alle JWT-geschützt) sowie die Lambda-Invoke-Permission
(nur API Gateway als Principal). Kein REST API, kein `apply`, keine AWS-Ressourcen erzeugt.

Der Python-Lambda-Handler (`lambda/src/index.py`) wurde **nicht** verändert: Er
routet bereits exakt über den HTTP-API-v2-Event-Contract (`routeKey`,
`pathParameters`, `queryStringParameters`, `body`, `isBase64Encoded`; v2-Proxy-Response) —
identisch zu den vier dokumentierten Routen. Keine blinde Annahme: Der Contract wurde
vor Implementierung aus dem tatsächlichen Handler-Code verifiziert (Abschnitt 5 der
Vorgabe).

## Existing Architecture

| Komponente | Stand | Quelle |
|------------|-------|--------|
| DynamoDB | `aws_dynamodb_table.orders` + GSI1 (T011-02) — unverändert | `database/` |
| IAM | `aws_iam_role.handler` Execution Role (T011-03) — unverändert | `security/iam-design.md` |
| Lambda | `aws_lambda_function.handler`, Python 3.14, `index.handler` (T011-04 + Migration) | `lambda/src/index.py` |
| Cognito | `aws_cognito_user_pool.users`, `aws_cognito_user_pool_client.app`, `aws_cognito_user_group.staff` (T011-05) | `security/authentication-decision.md`, F002 |
| API Gateway | `aws_apigatewayv2_api.orders` (T011-06, neu) | `architecture/architecture-decisions.md` (ADR-004) |

## Changed Files

| Datei | Art | Zweck |
|-------|-----|-------|
| `terraform/main.tf` | geändert | HTTP API (V2), Stage, JWT-Authorizer, Integration, 4 Routen, Lambda-Invoke-Permission |
| `terraform/outputs.tf` | geändert | `api_gateway_endpoint`, `api_gateway_id`, `api_gateway_authorizer_id` |
| `terraform/README.md` | geändert | §2.5 HTTP API (Ressourcentabelle, Routen, Entscheidungen), Ressourcentabelle §3 |
| `docs/features/F003-api-gateway.md` | geändert | T003-01…06 COMPLETE, Testnachweise, Next Step |
| `docs/features/F011-terraform-infrastructure.md` | geändert | T011-06 IN PROGRESS→COMPLETE, Progress/Changes/Known Issues |
| `docs/PROJECT_STATUS.md` | geändert | Status, Phase-Level, Feature-Status |
| `docs/reports/WEEK-02.md` | geändert | Wochenreport (T011-06, Validation) |
| `docs/CHANGELOG.md` | geändert | Changelog-Eintrag T011-06 |
| `docs/reports/T011-06-HTTP-API.md` | neu | dieser Report |

## HTTP API

| Eigenschaft | Wert |
|-------------|------|
| Ressource | `aws_apigatewayv2_api.orders` |
| Name | `${var.project_name}-api` (= `mays-orders-api`) |
| Protocol | `HTTP` (ADR-004 — bewusst kein REST API / `aws_api_gateway_*`) |
| Stage | `aws_apigatewayv2_stage.default`, Name `$default`, `auto_deploy = true` |
| Tags | Provider-Default-Tags (Project + `var.tags`), wie bei allen Ressourcen |
| Output | `api_gateway_endpoint` → `aws_apigatewayv2_api.orders.api_endpoint` (Invoke-URL) |

## Routes

Vier dokumentierte Routen (`api/endpoints.md`, `api/api-documentation.md`) — keine
zusätzlichen/öffentlichen Routen:

| Method | Path | Lambda Operation | Auth |
|--------|------|------------------|------|
| POST | `/orders` | AP1 Create (`create_order`) | JWT (Cognito) |
| GET | `/orders/{orderId}` | AP2 Get by ID (`get_order`) | JWT (Cognito) |
| GET | `/orders` | AP3 Listing (`list_orders`) | JWT (Cognito) |
| PATCH | `/orders/{orderId}/status` | AP4 Status-Update (`update_order_status`) | JWT (Cognito) |

Alle Routen: `authorization_type = "JWT"` + `authorizer_id =
aws_apigatewayv2_authorizer.jwt.id`; `target = "integrations/${...integration.id}"`.

## Lambda Integration

| Eigenschaft | Wert |
|-------------|------|
| Ressource | `aws_apigatewayv2_integration.lambda` |
| Integration Type | `AWS_PROXY` |
| Integration URI | `aws_lambda_function.handler.invoke_arn` (bestehende Python-3.14-Lambda, keine zweite Lambda) |
| Payload Format | `2.0` — exakt der Event-Contract von `lambda/src/index.py` (verifiziert) |
| Timeout | Provider-Default (HTTP API Lambda-Integration; keine Abweichung nötig) |

## JWT Authorizer

| Eigenschaft | Wert |
|-------------|------|
| Ressource | `aws_apigatewayv2_authorizer.jwt` |
| Type | `JWT` |
| Identity Source | `$request.header.Authorization` |
| Issuer | `https://${aws_cognito_user_pool.users.endpoint}` (= `https://cognito-idp.<region>.amazonaws.com/<pool-id>`) — **keine** hardcodierte Region/ID |
| Audience | `[aws_cognito_user_pool_client.app.id]` — **keine** hardcodierte Client-ID |

## Cognito Integration

- User Pool Resource: `aws_cognito_user_pool.users` (T011-05, unverändert)
- App Client: `aws_cognito_user_pool_client.app` — Public Client, kein Secret,
  `ALLOW_USER_PASSWORD_AUTH` + `ALLOW_REFRESH_TOKEN_AUTH` (T011-05, unverändert)
- Gruppe: `aws_cognito_user_group.staff` (T011-05, unverändert)
- Authorization Claim: `cognito:groups` (A-09) — siehe "Security": wird in T011-06
  noch nicht im Lambda ausgewertet (JWT-Authorizer prüft Issuer + Audience).

## Lambda Invoke Permission

| Eigenschaft | Wert |
|-------------|------|
| Ressource | `aws_lambda_permission.api_gateway` |
| Action | `lambda:InvokeFunction` |
| Principal | `apigateway.amazonaws.com` (nur API Gateway) |
| Function | `aws_lambda_function.handler.function_name` |
| Source ARN | `${aws_apigatewayv2_api.orders.execution_arn}/*/*` (eng begrenzt auf diese HTTP API) |

Berechtigungsrichtungen sauber getrennt: API GW → Lambda (Resource-Based Policy,
T011-06) ≠ Lambda → DynamoDB (IAM Execution Role, T011-03). IAM-Rolle unverändert.

## Security

- Alle vier Routen JWT-geschützt (keine öffentlichen Routen).
- JWT-Authorizer validiert Signatur + Ablauf + Issuer (Cognito User Pool) + Audience
  (App Client) am Gateway — kein Custom-Authorizer-Code (ADR-003).
- `cognito:groups`-Authorization (A-09) bleibt in T011-06 bewusst offen: Der Handler
  wertet Gruppen noch nicht aus; das Gruppenscoping gehört zu den Security-Features
  (Woche 3, F009). Die Gruppe `staff` existiert bereits (T011-05) und wird später
  über den Claim ausgewertet.
- Keine Secrets, keine IAM Access Keys, kein App-Client-Secret (Public Client).
- Keine offene Registrierung (Admin-Create-User, T011-05).

## Validation

- `terraform fmt` — PASS
- `terraform init` (AWS-Provider ~> 6.0 / 6.60.0, Lock-File wiederverwendet) — PASS
- `terraform validate` — PASS (ohne Warnungen)
- `git diff --check` — PASS
- Secret-Audit — PASS (grep auf AKIA/Access-Key/Secret/Private-Key-Muster über das
  gesamte Repo inkl. terraform/: keine Treffer)
- Python-Validierung (compile/unittest/ZIP/Smoke): **NOT RUN — nicht erforderlich**,
  da `lambda/src/index.py` nicht verändert wurde (Event-Contract passt exakt; Abschnitt
  5 der Vorgabe). Der bestehende Nachweis (49/49 unittest, compileall, ZIP-Build,
  Integrity, Smoke) aus der Python-3.14-Migration bleibt gültig.

## Terraform Plan

NOT RUN — gehört laut Projektplan zu **T011-07** (Review), nicht vorgezogen.

## Terraform Apply

NOT RUN — keine AWS-Ressourcen erzeugen; menschliche Freigabe erforderlich (T011-08).

## AWS Resources

NONE — reine Terraform-Konfiguration; nichts erzeugt, keine Kosten.

## Cost Impact

- HTTP API (V2): ~70 % günstiger als REST API (ADR-004) — kostenrelevant bei Live-Betrieb.
- JWT-Authorizer: keine separaten Kosten.
- Keine laufenden Kosten ohne `apply` (T011-08).

## Known Limitations

- Kein Live-Test (Routen erreichbar / 401 ohne Token) — erst nach `apply` (T011-08),
  dann T003-07/T002-05.
- `cognito:groups`-Authorization wird im Lambda noch nicht ausgewertet (A-09) —
  Gruppenscoping folgt in Woche 3 (F009).
- `identity_sources` ausschließlich `Authorization`-Header (Standard); andere Quellen
  (z. B. Cookie) sind nicht konfiguriert und nicht gefordert.
- Kein Rate Limiting / WAF (nicht Teil der dokumentierten Architektur).

## Git Checkpoint

- Branch: `feature/http-api` (Feature-Branches werden **nicht** gelöscht)
- Baseline: `main` = `9c1a7b6` (Merge-Nachzug T011-05)
- Commit: `9a332bf` (T011-06-Checkpoint) · Push: SUCCESS (`origin/feature/http-api`)
- Danach: `git merge --no-ff feature/http-api` nach `main` + Push

## Feature Branch

`feature/http-api` — wird nach Abschluss NICHT gelöscht (bleibt neben
`feature/lambda-python-314` und `feature/cognito` erhalten).

## Merge to main

`feature/http-api` → `main` per `git merge --no-ff` (Commit `8a85b5e`) · Push main: SUCCESS.

## Push Status

Push feature/http-api: SUCCESS (Commits `9a332bf` + Docs-Nachzug `44ef829`,
`origin/feature/http-api`).

## Current Project Status

- API Gateway: **CONFIGURED** (Terraform T011-06) — NOT CREATED (kein apply)
- AWS Resources: NONE
- F011 IN PROGRESS · T011-01…06 COMPLETE · T011-07 NEXT (plan + validate Review)
- F003: T003-01…06 COMPLETE (Terraform) · T003-07 PLANNED (Live, nach apply)

## Next Step

T011-07 — terraform validate + plan (Review) — separater Task / Prompt. STOP.