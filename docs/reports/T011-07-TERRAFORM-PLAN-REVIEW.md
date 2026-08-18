# T011-07 Terraform Validate + Plan Review

> Read-only Infrastructure Review. `terraform plan` ist ausdrücklich erlaubt und
> Bestandteil dieses Tasks. `terraform apply` wurde **nicht** ausgeführt. Git bleibt
> Source of Truth.

## Summary

T011-07 — Terraform Validate + Plan Review abgeschlossen. Ergebnis:

- `terraform fmt -check`: PASS
- `terraform init`: PASS (AWS-Provider 6.60.0, Lockfile wiederverwendet)
- `terraform validate`: PASS
- `terraform plan`: RUN — **16 to add, 0 to change, 0 to destroy**
- Plan-Klassifikation: **A) EXPECTED / CLEAN** — keine Discrepancies, keine
  unerwarteten Änderungen, kein `destroy`, kein `replace`, kein Node.js-Runtime.

Der Plan erzeugt ausschließlich die in T011-02…T011-06 dokumentierten Ressourcen
(alle als `create`, da `AWS Resources: NONE` — kein State, kein bisheriger Apply).

## Git Checkpoint

```text
Branch:       main (= origin/main) → HEAD 1c48669
Review-Branch: feature/t011-07-plan-review
Branches:     main, feature/lambda-python-314, feature/cognito, feature/http-api,
              feature/lambda-python-cleanup (alle erhalten)
Arbeitsbaum:  sauber (nur docs.zip unversioniert, kein Projektinhalt)
```

## Terraform Version

`Terraform v1.15.8` (linux_amd64) — unverändert zum Projektstand.

## AWS Provider

`terraform providers`: `provider[registry.terraform.io/hashicorp/aws] ~> 6.0`
→ installiert **v6.60.0** (Lockfile). Kein Downgrade auf 5.x, keine Versionsänderung.

## Format Validation

`terraform fmt -check -recursive .` → **PASS** (Exit 0, keine Ausgabe).

## Terraform Init

`terraform init` → **PASS**.

- Backend: lokal (Default; kein S3-Backend — Entscheidung T011-09 offen)
- Provider: `hashicorp/aws v6.60.0` wiederverwendet aus Lockfile/Installation
  („Reusing previous version … from the dependency lock file")

## Terraform Validate

`terraform validate` → **PASS** — „The configuration is valid."

## Terraform Plan

`terraform plan` → ausgeführt, READ-ONLY, ohne `-out` (keine Notwendigkeit).

## Plan Summary

```text
Plan: 16 to add, 0 to change, 0 to destroy.
```

Alle 16 Ressourcen sind Neu-Erstellungen (`+ create`). Das ist erwartet: bisher
keine AWS-Ressourcen (`AWS Resources: NONE`), kein Terraform-State/Apply erfolgt.
2 Data-Sources werden während apply gelesen (`data.aws_iam_policy_document.handler_trust`,
`data.aws_iam_policy_document.handler`).

## Resource-by-Resource Review

| Aktion | Ressource | Warum? | Erwartet? |
|--------|-----------|--------|-----------|
| + create | `aws_dynamodb_table.orders` | T011-02 DynamoDB-Tabelle | ✅ |
| + create | `aws_iam_role.handler` | T011-03 Execution Role | ✅ |
| + create | `aws_iam_role_policy.handler` | T011-03 Inline-Policy | ✅ |
| + create | `aws_lambda_function.handler` | T011-04 Lambda (Python 3.14) | ✅ |
| + create | `aws_cognito_user_pool.users` | T011-05 User Pool | ✅ |
| + create | `aws_cognito_user_pool_client.app` | T011-05 App Client | ✅ |
| + create | `aws_cognito_user_group.staff` | T011-05 Gruppe staff | ✅ |
| + create | `aws_apigatewayv2_api.orders` | T011-06 HTTP API | ✅ |
| + create | `aws_apigatewayv2_stage.default` | T011-06 $default-Stage | ✅ |
| + create | `aws_apigatewayv2_authorizer.jwt` | T011-06 JWT-Authorizer | ✅ |
| + create | `aws_apigatewayv2_integration.lambda` | T011-06 Lambda-Integration | ✅ |
| + create | `aws_apigatewayv2_route.create_order` | T011-06 POST /orders | ✅ |
| + create | `aws_apigatewayv2_route.get_order` | T011-06 GET /orders/{orderId} | ✅ |
| + create | `aws_apigatewayv2_route.list_orders` | T011-06 GET /orders | ✅ |
| + create | `aws_apigatewayv2_route.update_order_status` | T011-06 PATCH /orders/{orderId}/status | ✅ |
| + create | `aws_lambda_permission.api_gateway` | T011-06 Invoke-Permission | ✅ |
| <= read | `data.aws_iam_policy_document.handler_trust` | IAM Trust (bereits validiert) | ✅ |
| <= read | `data.aws_iam_policy_document.handler` | IAM Policy (dynamodb+logs) | ✅ |

## DynamoDB Review

`aws_dynamodb_table.orders` (Plan):

- Name `mays-orders`, `billing_mode = PAY_PER_REQUEST` (ADR-007, On-Demand) ✅
- `hash_key = "pk"`, `range_key = "sk"` (Single-Table-Design) ✅
- GSI1: `name = "gsi1"`, `key_schema` HASH `gsi1pk` / RANGE `gsi1sk`,
  `projection_type = INCLUDE` mit `non_key_attributes = [orderId, status, customer,
  totalAmount, createdAt, updatedAt]` — exakt Access Pattern AP3 ✅
- Keine Änderung/kein Replace, keine Löschung. ✅

## IAM Review

`aws_iam_role.handler` (Plan):

- Trust: `sts:AssumeRole` mit Principal `lambda.amazonaws.com` (Service) ✅
- `aws_iam_role_policy.handler`: Least Privilege —
  - Statement `DynamoDBOrders`: `dynamodb:PutItem/GetItem/UpdateItem/Query` auf
    Tabelle + GSI1 (kein Scan/DeleteItem/BatchWriteItem) ✅
  - Statement `Logs`: `logs:CreateLogGroup/CreateLogStream/PutLogEvents` auf `*`
    (Log-Ressourcen entstehen zur Laufzeit) — dokumentierte, bewusste Ausnahme ✅
- Keine IAM User, keine Access Keys, keine Secrets im Plan. ✅

## Lambda Review

`aws_lambda_function.handler` (Plan):

- `runtime = "python3.14"` (aktiver Stand, kein `nodejs22.x`) ✅
- `handler = "index.handler"`, `package_type = "Zip"`,
  `filename = "./../lambda/dist/lambda.zip"` (Python-Build) ✅
- `timeout = 10`, `memory_size = 128` (Default), `environment.ORDERS_TABLE =
  "mays-orders"` ✅
- Rolle: `aws_iam_role.handler` (T011-03) ✅

## Cognito Review

- `aws_cognito_user_pool.users`: Name `mays-orders-users`,
  `admin_create_user_config.allow_admin_create_user_only = true` (keine offene
  Registrierung), Passwortrichtlinie Standardwerte, `mfa_configuration = OFF` ✅
- `aws_cognito_user_pool_client.app`: `mays-orders-client`,
  `explicit_auth_flows = [ALLOW_USER_PASSWORD_AUTH, ALLOW_REFRESH_TOKEN_AUTH]`,
  `generate_secret = false` (Public Client) ✅
- `aws_cognito_user_group.staff`: Gruppe `staff` (Claim `cognito:groups`) ✅
- Kein `user_pool_domain` (bewusst, USER_PASSWORD_AUTH) ✅

## API Gateway Review

- `aws_apigatewayv2_api.orders`: `mays-orders-api`, `protocol_type = HTTP`,
  Description „vier Order-Routen" (ADR-004) ✅
- `aws_apigatewayv2_stage.default`: `$default`, `auto_deploy = true` ✅
- `aws_apigatewayv2_authorizer.jwt`: `JWT`, `identity_sources =
  ["$request.header.Authorization"]`; Issuer/Audience abgeleitet aus Cognito
  (im Plan `known after apply`, da Ressourcenreferenzen) ✅
- `aws_apigatewayv2_integration.lambda`: `AWS_PROXY`, `payload_format_version =
  "2.0"`, `connection_type = INTERNET` ✅
- 4 Routen — exakt die dokumentierten:
  - `POST /orders` ✅
  - `GET /orders/{orderId}` ✅
  - `GET /orders` ✅
  - `PATCH /orders/{orderId}/status` ✅
  - alle `authorization_type = "JWT"` + `authorizer_id` ✅
- `aws_lambda_permission.api_gateway`: `lambda:InvokeFunction`, Principal
  `apigateway.amazonaws.com`, `source_arn` aus `execution_arn` (known after
  apply) — eng begrenzt auf diese HTTP API ✅

## Security Review

- IAM Least Privilege: nur DynamoDB-Operationen auf Tabelle+GSI1 + Logs ✅
- Keine Access Keys, keine Secrets, kein App-Client-Secret (Public Client) ✅
- Cognito Auth + JWT-Authorizer (Issuer/Audience aus Ressourcen, nicht hardcodiert) ✅
- Lambda-Invoke-Permission nur für `apigateway.amazonaws.com`, source_arn-begrenzt ✅
- Keine offene Registrierung (Admin-Create-User) ✅
- Keine Security-Architektur-Änderung durch den Plan. ✅

## Cost Impact

Nur tatsächlich erkennbare Kostenrelevanz aus dem Plan:

- Alle 16 Ressourcen werden erst bei `apply` erzeugt — ohne `apply` keine Kosten.
- Kostenrelevante Ressourcen im Plan: DynamoDB (PAY_PER_REQUEST), Lambda,
  API Gateway (HTTP), Cognito (User Pool).
- Konkrete Kostenbeträge: **nicht aus dem Plan bestimmt** (keine Kostenangaben
  im Plan; Bewertung in `cost/cost-analysis.md` / Woche 4).

## Unexpected Changes

**Keine.** Plan zeigt ausschließlich die 16 dokumentierten Neu-Erstellungen.
Kein `destroy`, kein `change`, kein `replace`:

- DynamoDB Keys / GSI: unverändert geplant (neu)
- IAM Permissions: nur dokumentierte Least-Privilege-Statements
- Lambda Runtime: `python3.14` (kein `nodejs22.x`)
- Cognito-Konfiguration: dokumentiert
- JWT Authorizer / Routes / Lambda Permission: dokumentiert

## Discrepancies

**Keine.** Der Plan stimmt mit der dokumentierten May's-Orders-Architektur und
den Task-Reports T011-02…T011-06 überein.

## Terraform Apply

```text
terraform apply: NOT RUN — FREIGABE ERFORDERLICH (T011-08)
```

## AWS Resources

NONE — es wurden keine AWS-Ressourcen erzeugt (nur `terraform plan`, read-only).

## Validation

| Prüfung | Ergebnis |
|---------|----------|
| `terraform version` | v1.15.8 |
| `terraform providers` | aws ~> 6.0 (6.60.0) |
| `terraform fmt -check` | PASS |
| `terraform init` | PASS |
| `terraform validate` | PASS |
| `terraform plan` | RUN — 16 to add, 0 to change, 0 to destroy |
| `git diff --check` | PASS |
| Secret-Audit | PASS |
| `terraform apply` | NOT RUN (Freigabe erforderlich) |

## Known Limitations

- Plan basiert auf lokalem State (kein Backend-State vorhanden; S3-Backend-
  Entscheidung T011-09 offen).
- Issuer/Audience, source_arn und weitere Attribute erscheinen im Plan als
  `known after apply` — das ist normal (Ressourcenreferenzen), kein Fehler.
- Kein Live-Test möglich, bevor `apply` (T011-08) durchgeführt wurde.
- Erwartete Werte der Outputs erst nach `apply` verfügbar.

## Current Project Status

- T011-01…06 + T011-04-CLEANUP COMPLETE · **T011-07 COMPLETE** · T011-08 NEXT
  (`terraform apply`, nur nach menschlicher Freigabe)
- Plan-Klassifikation: A) EXPECTED / CLEAN
- AWS Resources: NONE · `terraform apply`: NOT RUN
- Week 2 IN PROGRESS · F011 IN PROGRESS

## Next Step

T011-08 — `terraform apply` (nach expliziter menschlicher Freigabe) + Outputs
dokumentieren. STOP — keine weiteren Schritte in diesem Task.