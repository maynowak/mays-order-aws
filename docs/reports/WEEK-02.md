# Weekly Report — Woche 2

**Datum:** 2026-08-18 (laufend)
**Projekt:** May's Orders — AWS Serverless Order Management
**Status:** 🔵 IN PROGRESS

## 1. Gesamtstatus

Woche 2 läuft. F011 (Terraform Infrastructure) in Arbeit; T011-01 (Terraform-Gerüst),
T011-02 (DynamoDB + GSI1), T011-03 (IAM), T011-04 (Lambda Order Handler + Zip-Build)
und T011-05 (Cognito: User Pool, Client, Gruppe `staff`) abgeschlossen und validiert.
Zusätzlich wurde der Lambda-Handler auf **Python 3.14** portiert (Branch
`feature/lambda-python-314`) und per `merge --no-ff` nach `main` integriert (Commit
`20bfb05`); die Node.js/TypeScript-Baseline (T011-04) wurde nach der Migration im
Cleanup (T011-04-CLEANUP, Branch `feature/lambda-python-cleanup`) aus dem aktiven
Lambda-Projekt entfernt und ist über Git-Historie (`449cdd7`) nachvollziehbar. Noch keine
AWS-Ressourcen erzeugt, kein `apply`.

## 2. Erledigte Features / Tasks

| Feature | Task | Status |
|---------|------|--------|
| F011 — Terraform Infrastructure | T011-01 Terraform-Gerüst (main/variables/outputs/README) | ✅ COMPLETE |
| F011 — Terraform Infrastructure | T011-02 DynamoDB-Tabelle + GSI1 (mays-orders, PK pk/sk, GSI1, On-Demand) | ✅ COMPLETE |
| F011 — Terraform Infrastructure | T011-03 IAM Lambda Execution Role + Least-Privilege Policy (DynamoDB+GSI1, Logs) | ✅ COMPLETE |
| F011 — Terraform Infrastructure | T011-04 Lambda Order Handler (TypeScript, nodejs22.x, Zip-Build, Execution Role T011-03, AP1..AP4) | ✅ COMPLETE |
| F011 — Terraform Infrastructure | T011-04-CLEANUP Node.js/TypeScript-Baseline entfernt (Python 3.14 aktiv) | ✅ COMPLETE |
| F011 — Terraform Infrastructure | LAMBDA-PY-314 Lambda-Handler auf Python 3.14 portiert (boto3, build_zip.py, unittest 49/49, runtime python3.14) | ✅ COMPLETE |
| F011 — Terraform Infrastructure | PY314-INTEGRATION Python-3.14-Stand nach `main` gemerged (Pflicht-Voraussetzung T011-05) | ✅ COMPLETE |
| F011 — Terraform Infrastructure | T011-05 Cognito (Pool `mays-orders-users`, Client `mays-orders-client` USER_PASSWORD_AUTH + Refresh, Gruppe `staff`) | ✅ COMPLETE |
| F002 — Cognito Authentication | T002-01…03 (User Pool, Client, Gruppe `staff`) via T011-05 | ✅ COMPLETE |
| F003 — API Gateway | T011-06 HTTP API + Routen + JWT Authorizer (via F011) | ✅ COMPLETE |
| F004 — Order Creation | … | ⏳ PLANNED |
| F005 — Order Retrieval | … | ⏳ PLANNED |
| F006 — Order Listing | … | ⏳ PLANNED |

## 3. Tests / Build / Validation

| Prüfung | Status |
|---------|--------|
| Python-Syntax (`python3 -m compileall`) | PASS |
| Python-Tests (unittest, 49 Test-Methoden) | PASS (state_machine 4, validation 19, orderService 12, index 14) |
| Python-ZIP-Build (`python3 build_zip.py`) | PASS (dist/lambda.zip, 6 Module, ~6,6 KB) |
| ZIP-Integrität + Handler-Import-Smoke | PASS |
| Terraform fmt | PASS |
| Terraform init | PASS (aws provider v6.60.0) |
| Terraform validate | PASS (ohne Warnungen; inkl. Cognito T011-05) |
| Recovery T011-06 (2026-08-18): `terraform fmt -check` / `terraform validate` / `git diff --check` / Secret-Audit | PASS (read-only, kein plan/apply) |
| Cleanup T011-04 (2026-08-18): `python3 build_zip.py` / `unzip -t` / `compileall` / unittest / `terraform fmt -check` / `init` / `validate` / `git diff --check` / Secret-Audit | PASS (kein plan/apply) |
| Terraform plan | NOT RUN (zu T011-07) |
| Terraform apply | NOT RUN (Freigabe erforderlich) |
| Live-API | NOT RUN |
| Node-Baseline (Vitest/tsc/npm) | REMOVED — Cleanup T011-04-CLEANUP; historisch via Git `449cdd7` |

## 4. AWS-Ressourcen

NONE — es wurden keine Ressourcen erzeugt (T011-02/T011-03/T011-04 sind reine
Terraform-Konfiguration; `apply` erst in T011-08 nach Freigabe).

## 5. Probleme / Risiken / Blocker

Keine. DynamoDB-, IAM- und Cognito-Konfiguration folgen exakt `database/dynamodb-design.md`,
`security/iam-design.md` bzw. `security/authentication-decision.md`; Least Privilege: nur
DynamoDB-Aktionen für Tabelle+GSI1 und Log-Rechte, kein Scan/DeleteItem/BatchWriteItem,
keine s3/sqs/iam-Rechte. Cognito: keine offene Registrierung (Admin-Create-User),
kein Secrets/App-Client-Secret, keine Access Keys.
Bekannte Randnotiz: `lambda/src/types.py` wurde bewusst als `order_types.py` benannt
(Stdlib-`types`-Kollision im Lambda-ZIP). Python-Tests laufen lokal unter 3.12.3
(System-Python); Ziel-Runtime `python3.14`.
T011-05-Technik-Hinweis: Provider 6.60.0 nutzt `aws_cognito_user_group` (Ressourcen-
Renaming, nicht `aws_cognito_user_pool_group`); `user_pool_domain` bewusst nicht umgesetzt
(USER_PASSWORD_AUTH braucht kein Hosted-UI).

## 6. Kosten

Keine AWS-Ressourcen erzeugt → keine Kosten. Weitere Bewertung in Woche 4
(`cost/cost-analysis.md`). On-Demand-Konfiguration vorbereitet (ADR-007).

## 7. Nächste Schritte

- T011-07 — terraform validate + plan (Review) (separater Task)

## 8. Zeitplan-Bewertung

F011/T011-01 bis T011-06 planmäßig; Lambda-Python-3.14-Migration als dokumentierter
Migrationsschritt abgeschlossen und nach `main` integriert. Terraform-Scope entspricht
dem Vier-Wochen-Plan (Woche 2).

## 9. Git Checkpoint

- Branch: `feature/http-api` (Feature-Branches bleiben erhalten; `feature/lambda-python-314` + `feature/cognito` + `feature/http-api` gepusht)
- Merge: `feature/lambda-python-314` → `main` (Commit `20bfb05`) — SUCCESS
- Merge: `feature/cognito` → `main` (Commit `dd9bb58`) · Push main: SUCCESS
- Commit: `9a332bf` (T011-06-Checkpoint) · Push: SUCCESS (`origin/feature/http-api`)
- Merge: `feature/http-api` → `main` (Commit `8a85b5e`) · Push main: SUCCESS
- Cleanup: Branch `feature/lambda-python-cleanup` (T011-04-CLEANUP) · Merge → `main` · Push: SUCCESS