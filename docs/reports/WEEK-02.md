# Weekly Report — Woche 2

**Datum:** 2026-08-18 (laufend)
**Projekt:** May's Orders — AWS Serverless Order Management
**Status:** 🔵 IN PROGRESS

## 1. Gesamtstatus

Woche 2 läuft. F011 (Terraform Infrastructure) in Arbeit; T011-01 (Terraform-Gerüst),
T011-02 (DynamoDB + GSI1), T011-03 (IAM) und T011-04 (Lambda Order Handler + Zip-Build)
abgeschlossen und validiert. Zusätzlich wurde der Lambda-Handler auf **Python 3.14**
portiert (Branch `feature/lambda-python-314`); die Node.js/TypeScript-Variante bleibt
als historische Baseline. Noch keine AWS-Ressourcen erzeugt, kein `apply`.

## 2. Erledigte Features / Tasks

| Feature | Task | Status |
|---------|------|--------|
| F011 — Terraform Infrastructure | T011-01 Terraform-Gerüst (main/variables/outputs/README) | ✅ COMPLETE |
| F011 — Terraform Infrastructure | T011-02 DynamoDB-Tabelle + GSI1 (mays-orders, PK pk/sk, GSI1, On-Demand) | ✅ COMPLETE |
| F011 — Terraform Infrastructure | T011-03 IAM Lambda Execution Role + Least-Privilege Policy (DynamoDB+GSI1, Logs) | ✅ COMPLETE |
| F011 — Terraform Infrastructure | T011-04 Lambda Order Handler (TypeScript, nodejs22.x, Zip-Build, Execution Role T011-03, AP1..AP4) | ✅ COMPLETE |
| F011 — Terraform Infrastructure | LAMBDA-PY-314 Lambda-Handler auf Python 3.14 portiert (boto3, build_zip.py, unittest 49/49, runtime python3.14) | ✅ COMPLETE |
| F011 — Terraform Infrastructure | T011-05 Cognito (Pool, Client, Gruppe) | ⏳ PLANNED |
| F002 — Cognito Authentication | … | ⏳ PLANNED |
| F003 — API Gateway | … | ⏳ PLANNED |
| F004 — Order Creation | … | ⏳ PLANNED |
| F005 — Order Retrieval | … | ⏳ PLANNED |
| F006 — Order Listing | … | ⏳ PLANNED |

## 3. Tests / Build / Validation

| Prüfung | Status |
|---------|--------|
| TypeScript-Build (`npm run build`, tsc --noEmit + esbuild) | PASS (Baseline T011-04) |
| Unit-Tests Baseline (Vitest `npm test`) | PASS (45/45: stateMachine 14, validation 19, orderService 12) |
| Python-Syntax (`python3 -m compileall`) | PASS |
| Python-Tests (unittest, 49 Test-Methoden) | PASS (state_machine 4, validation 19, orderService 12, index 14) |
| Python-ZIP-Build (`python3 build_zip.py`) | PASS (dist/lambda.zip, 6 Module, ~6,6 KB) |
| ZIP-Integrität + Handler-Import-Smoke | PASS |
| npm audit | PASS (0 vulnerabilities, Baseline) |
| Terraform fmt | PASS |
| Terraform init | PASS (aws provider v6.60.0) |
| Terraform validate | PASS (ohne Warnungen) |
| Terraform plan | NOT RUN (zu T011-07) |
| Terraform apply | NOT RUN (Freigabe erforderlich) |
| Live-API | NOT RUN |

## 4. AWS-Ressourcen

NONE — es wurden keine Ressourcen erzeugt (T011-02/T011-03/T011-04 sind reine
Terraform-Konfiguration; `apply` erst in T011-08 nach Freigabe).

## 5. Probleme / Risiken / Blocker

Keine. DynamoDB- und IAM-Konfiguration folgen exakt `database/dynamodb-design.md` bzw.
`security/iam-design.md`; Least Privilege: nur DynamoDB-Aktionen für Tabelle+GSI1 und
Log-Rechte, kein Scan/DeleteItem/BatchWriteItem, keine s3/sqs/iam-Rechte.
Bekannte Randnotiz: `lambda/src/types.py` wurde bewusst als `order_types.py` benannt
(Stdlib-`types`-Kollision im Lambda-ZIP). Python-Tests laufen lokal unter 3.12.3
(System-Python); Ziel-Runtime `python3.14`.

## 6. Kosten

Keine AWS-Ressourcen erzeugt → keine Kosten. Weitere Bewertung in Woche 4
(`cost/cost-analysis.md`). On-Demand-Konfiguration vorbereitet (ADR-007).

## 7. Nächste Schritte

- T011-05 — Cognito (Pool, Client, Gruppe) (separater Task)

## 8. Zeitplan-Bewertung

F011/T011-01 bis T011-04 planmäßig; Lambda-Python-3.14-Migration als dokumentierter
Migrationsschritt abgeschlossen. Terraform-Scope entspricht dem Vier-Wochen-Plan (Woche 2).

## 9. Git Checkpoint

- Branch: `feature/lambda-python-314` (Feature-Branch bleibt erhalten)
- Commit: `64130a9` (F011 — Lambda-Handler auf Python 3.14 portiert)
- Push: wird nach dem Docs-Nachzug ausgeführt