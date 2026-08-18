# T011-06 Recovery & Status Verification

> Recovery nach VS-Code-/Agent-Absturz. Evidenzbasierte Verifikation des tatsächlichen
> Stands von T011-06 — HTTP API + Routen + Authorizer. Keine neue Implementierung,
> kein `terraform plan`, kein `terraform apply`. Jede Aussage ist aus Git-/Code-Stand belegbar.

## Anlass

Nach einem Absturz gab es widersprüchliche Statusangaben in der Projektdokumentation
(u. a. F011-Task-Tabelle `T011-06 = PLANNED` vs. Checkpoint-Angaben `COMPLETE`/gemergt).
Ziel: eindeutige Feststellung des tatsächlichen Stands anhand von Git und Code.

## Git Status

```text
Branch:  main
HEAD:    daba5ef04b7b482af78d5c773e49d27fcd4e0a5e
Remote:  origin (https://github.com/maynowak/mays-order-aws.git)
Branch-vv:
  feature/cognito           c2727be [origin/feature/cognito]
  feature/http-api          44ef829 [origin/feature/http-api]
  feature/lambda-python-314 d64f583 [origin/feature/lambda-python-314]
* main                      daba5ef [origin/main]
```

- Arbeitsbaum: sauber; einzige unversionierte Datei `docs.zip` (kein Projektinhalt).
- `git fetch origin`: keine neuen Commits.
- `main` == `origin/main` (`daba5ef`) → main ist gepusht.

## Feature Branch

```text
feature/http-api:  44ef829 == origin/feature/http-api
Log:
  44ef829 docs: Push-Status feature/http-api (SUCCESS, Commit 9a332bf) + T011-06 COMPLETE …
  9a332bf feat: F011/T011-06 HTTP API V2 mit vier Order-Routen, JWT-Authorizer (Cognito),
          Lambda-Integration (Payload 2.0) und Invoke-Permission + Outputs + Doku
```

- Dokumentierter Commit `9a332bf` **existiert** (`git cat-file -t 9a332bf` → `commit`).
- Feature-Branch ist gepusht und synchron (`feature/http-api` == `origin/feature/http-api`).

## Main Branch

```text
main:
  daba5ef docs: Merge-Nachzug feature/http-api -> main (Commit 8a85b5e) …
  8a85b5e Merge feature/http-api: F011/T011-06 HTTP API V2 …
```

- Dokumentierter Merge-Commit `8a85b5e` **existiert** (`git cat-file -t 8a85b5e` → `commit`).
- Merge-Eltern: `9c1a7b6` (main-Stand) + `44ef829` (feature/http-api).
- Der Merge-Stat umfasst genau die T011-06-Artefakte:
  `terraform/main.tf` (+89), `terraform/outputs.tf` (+16), `terraform/README.md`,
  `docs/CHANGELOG.md`, `docs/PROJECT_STATUS.md`, `docs/features/F003-*`,
  `docs/features/F011-*`, `docs/reports/T011-06-HTTP-API.md`, `docs/reports/WEEK-02.md`.

## Merge Verification

```text
git merge-base --is-ancestor 9a332bf main  → TRUE (Exit 0)
```

- `9a332bf` ist ein Vorfahre von `main` → T011-06-Code ist in `main` enthalten.
- Merge `8a85b5e` ist Teil der ersten Parent-Linie von `main` (`daba5ef` direkt darüber).

## Terraform Resources

Alle T011-06-Ressourcen in `terraform/main.tf` (Stand: gemergter main-Code):

| Ressource | Name (main.tf) | Zweck |
|-----------|----------------|-------|
| `aws_apigatewayv2_api` | `orders` | HTTP API `mays-orders-api`, `protocol_type = "HTTP"` (ADR-004) |
| `aws_apigatewayv2_stage` | `default` | `$default`-Stage mit `auto_deploy = true` |
| `aws_apigatewayv2_authorizer` | `jwt` | JWT-Authorizer (Cognito) |
| `aws_apigatewayv2_integration` | `lambda` | AWS_PROXY, Payload 2.0 → `aws_lambda_function.handler.invoke_arn` |
| `aws_apigatewayv2_route` | `create_order` | `POST /orders` |
| `aws_apigatewayv2_route` | `get_order` | `GET /orders/{orderId}` |
| `aws_apigatewayv2_route` | `list_orders` | `GET /orders` |
| `aws_apigatewayv2_route` | `update_order_status` | `PATCH /orders/{orderId}/status` |
| `aws_lambda_permission` | `api_gateway` | Invoke-Permission für API Gateway |

Terraform-Stand: Provider `~> 6.0` (6.60.0), `required_version >= 1.5.0`. Kein REST API (`aws_api_gateway_*`).

## HTTP Routes

| Method | Path | Target / Integration | Authorization |
|--------|------|----------------------|---------------|
| POST | `/orders` | `integrations/${aws_apigatewayv2_integration.lambda.id}` | JWT (`authorizer_id`) |
| GET | `/orders/{orderId}` | `integrations/${aws_apigatewayv2_integration.lambda.id}` | JWT |
| GET | `/orders` | `integrations/${aws_apigatewayv2_integration.lambda.id}` | JWT |
| PATCH | `/orders/{orderId}/status` | `integrations/${aws_apigatewayv2_integration.lambda.id}` | JWT |

Alle vier Routen in `terraform/main.tf:237–267` mit `authorization_type = "JWT"` +
`authorizer_id = aws_apigatewayv2_authorizer.jwt.id`. Identisch zu `api/endpoints.md`
und `api/api-documentation.md`. Keine zusätzlichen/öffentlichen Routen.

## JWT Authorizer

`terraform/main.tf:213–223` (`aws_apigatewayv2_authorizer.jwt`):

- Type: `JWT`
- Identity Source: `["$request.header.Authorization"]`
- Issuer: `https://${aws_cognito_user_pool.users.endpoint}` (kein Hardcode; abgeleitet aus User Pool)
- Audience: `[aws_cognito_user_pool_client.app.id]` (kein Hardcode)
- Verknüpfung: alle vier Routen verweisen auf `authorizer_id` dieses Authorizers.

Cognito-Basis (T011-05, gemergt): `aws_cognito_user_pool.users`,
`aws_cognito_user_pool_client.app` (USER_PASSWORD_AUTH, Public Client),
`aws_cognito_user_group.staff`.

## Lambda Integration

`terraform/main.tf:228–233` (`aws_apigatewayv2_integration.lambda`):

- Integration Type: `AWS_PROXY`
- Integration URI: `aws_lambda_function.handler.invoke_arn` (bestehende Python-3.14-Lambda, keine zweite Funktion)
- Payload Format Version: `2.0`
- Lambda Runtime: `python3.14` (`terraform/main.tf:129`), Handler `index.handler`

## Lambda Invoke Permission

`terraform/main.tf:273–277` (`aws_lambda_permission.api_gateway`):

- Action: `lambda:InvokeFunction`
- Principal: `apigateway.amazonaws.com`
- Function: `aws_lambda_function.handler.function_name`
- Source ARN: `${aws_apigatewayv2_api.orders.execution_arn}/*/*` (eng auf diese HTTP API begrenzt)

## Lambda Event Contract

`lambda/src/index.py` (unverändert, gemergt) verarbeitet das HTTP-API-v2-Eventformat:

- Routing über `routeKey` (`index.py:56–62`) — exakt `POST /orders`, `GET /orders`,
  `GET /orders/{orderId}`, `PATCH /orders/{orderId}/status` (`index.py:75–95`)
- `pathParameters` (`orderId`), `queryStringParameters`, `body`, `isBase64Encoded` → v2-Contract kompatibel
- v2-Proxy-Response `{statusCode, headers, body}` (`index.py:32–37`)

Befund: Code und Payload-Format **passen zusammen**. Kein offenes Problem am Event-Contract.

## Validation

Tatsächlich erneut ausgeführt (read-only; kein plan/apply):

| Prüfung | Ergebnis |
|---------|----------|
| `terraform fmt -check` (terraform/) | PASS |
| `terraform validate` (terraform/) | PASS — "The configuration is valid." |
| `git diff --check` | PASS |
| Secret-Audit (AKIA/Access-Key/Secret/Private-Key-Muster) | PASS (nur Doku-Erwähnungen des Musters, keine Secrets) |
| `terraform plan` | NOT RUN (gehört zu T011-07) |
| `terraform apply` | NOT RUN (Freigabe erforderlich) |

Python-Validierung: Lambda-Code in T011-06 unverändert → bestehender Nachweis
(compileall, 49/49 unittest, ZIP-Build/-Integrität, Smoke) aus der Python-3.14-Migration
bleibt gültig (belegt in `docs/reports/LAMBDA-PYTHON-3.14-MIGRATION.md`).

## Documentation Consistency

Widersprüche festgestellt und anhand des tatsächlichen Stands aufgelöst (Doku korrigiert,
Code unverändert):

| Datei | Vorher (falsch) | Nachher (korrigiert) |
|-------|-----------------|----------------------|
| `docs/features/F011-terraform-infrastructure.md` | Task-Tabelle `T011-06 = ⏳ PLANNED`; Progress-Block "IN PROGRESS" | `T011-06 = ✅ COMPLETE`; Current Task `T011-07` |
| `docs/PROJECT_STATUS.md` | "API GW (T011-06) in Arbeit"; Terraform-Zeile "T011-05 konfiguriert" | API GW konfiguriert; Terraform "T011-06 konfiguriert, T011-07 next" |
| `docs/reports/WEEK-02.md` | `T011-06 = 🔵 IN PROGRESS`; Next Step "T011-06 (separater Task)" | `T011-06 = ✅ COMPLETE`; Next Step `T011-07` |
| `docs/features/F003-api-gateway.md` | "DESIGNED — NOT IMPLEMENTED"; "Commit offen" | Terraform konfiguriert (T003-01…06 COMPLETE); Commit `9a332bf`/Merge `8a85b5e` |

Bereits korrekt: `docs/reports/T011-06-HTTP-API.md` (Report), `docs/CHANGELOG.md` (T011-06-Eintrag),
Checkpoint-Tabelle in `docs/PROJECT_STATUS.md`.

## Tatsächlicher Status

```text
T011-06 = COMPLETE
```

Alle Nachweise erfüllt:

- [x] Code vorhanden (terraform/main.tf, outputs.tf — gemergt in main)
- [x] vier Routen vorhanden (POST /orders, GET /orders/{orderId}, GET /orders, PATCH /orders/{orderId}/status)
- [x] JWT Authorizer vorhanden (Cognito Issuer/Audience)
- [x] Lambda Integration vorhanden (AWS_PROXY, Payload 2.0)
- [x] Lambda Invoke Permission vorhanden (apigateway.amazonaws.com, source_arn begrenzt)
- [x] Validation erfolgreich (fmt/validate/diff-check/Secret-Audit PASS)
- [x] Feature Commit vorhanden (`9a332bf`)
- [x] Feature Branch gepusht (`origin/feature/http-api` = `44ef829`)
- [x] Merge nach main vorhanden (`8a85b5e`)
- [x] main gepusht (`origin/main` = `daba5ef`)

## Offene Punkte

- `terraform plan` — bewusst NOT RUN, gehört zu T011-07 (Review) laut Projektplan.
- `terraform apply` — bewusst NOT RUN, nur nach menschlicher Freigabe (T011-08).
- Live-Test der Routen (200 mit Token, 401 ohne Token) — erst nach apply (F003/T003-07).
- `cognito:groups`-Authorization (A-09) wird im Lambda noch nicht ausgewertet — Woche 3 (F009).
- `docs.zip` (unversionierte Datei im Arbeitsbaum) — kein Projektinhalt, nicht committet.

## Next Step

T011-07 — `terraform validate` + `plan` (Review) als separater Task nach menschlicher Freigabe.
STOP — keine weitere Implementierung in dieser Recovery.