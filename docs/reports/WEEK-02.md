# Weekly Report — Woche 2

**Datum:** 2026-08-17 (laufend)
**Projekt:** May's Orders — AWS Serverless Order Management
**Status:** 🔵 IN PROGRESS

## 1. Gesamtstatus

Woche 2 läuft. F011 (Terraform Infrastructure) in Arbeit; T011-01 (Terraform-Gerüst),
T011-02 (DynamoDB + GSI1), T011-03 (IAM) und T011-04 (Lambda Order Handler + Zip-Build)
abgeschlossen und validiert. Noch keine AWS-Ressourcen erzeugt, kein `apply`.

## 2. Erledigte Features / Tasks

| Feature | Task | Status |
|---------|------|--------|
| F011 — Terraform Infrastructure | T011-01 Terraform-Gerüst (main/variables/outputs/README) | ✅ COMPLETE |
| F011 — Terraform Infrastructure | T011-02 DynamoDB-Tabelle + GSI1 (mays-orders, PK pk/sk, GSI1, On-Demand) | ✅ COMPLETE |
| F011 — Terraform Infrastructure | T011-03 IAM Lambda Execution Role + Least-Privilege Policy (DynamoDB+GSI1, Logs) | ✅ COMPLETE |
| F011 — Terraform Infrastructure | T011-04 Lambda Order Handler (TypeScript, nodejs22.x, Zip-Build, Execution Role T011-03, AP1..AP4) | ✅ COMPLETE |
| F011 — Terraform Infrastructure | T011-05 Cognito (Pool, Client, Gruppe) | ⏳ PLANNED |
| F002 — Cognito Authentication | … | ⏳ PLANNED |
| F003 — API Gateway | … | ⏳ PLANNED |
| F004 — Order Creation | … | ⏳ PLANNED |
| F005 — Order Retrieval | … | ⏳ PLANNED |
| F006 — Order Listing | … | ⏳ PLANNED |

## 3. Tests / Build / Validation

| Prüfung | Status |
|---------|--------|
| TypeScript-Build (`npm run build`, tsc --noEmit + esbuild) | PASS (Lambda T011-04) |
| Unit-Tests (Vitest `npm test`) | PASS (45/45: stateMachine 14, validation 19, orderService 12) |
| Lambda-Zip (`npm run package`) | PASS (dist/lambda.zip, nur index.js, ~156 KB) |
| npm audit | PASS (0 vulnerabilities) |
| Terraform init | PASS (aws provider v6.60.0) |
| Terraform validate | PASS (ohne Warnungen) |
| Terraform plan | NOT RUN (zu T011-07) |
| Terraform apply | NOT RUN (Freigabe erforderlich) |
| Live-API | NOT RUN |

## 4. AWS-Ressourcen

NONE — es wurden keine Ressourcen erzeugt (T011-02/T011-03 sind reine Terraform-
Konfiguration; `apply` erst in T011-08 nach Freigabe).

## 5. Probleme / Risiken / Blocker

Keine. DynamoDB- und IAM-Konfiguration folgen exakt `database/dynamodb-design.md` bzw.
`security/iam-design.md`; Least Privilege: nur DynamoDB-Aktionen für Tabelle+GSI1 und
Log-Rechte, kein Scan/DeleteItem/BatchWriteItem, keine s3/sqs/iam-Rechte.

## 6. Kosten

Keine AWS-Ressourcen erzeugt → keine Kosten. Weitere Bewertung in Woche 4
(`cost/cost-analysis.md`). On-Demand-Konfiguration vorbereitet (ADR-007).

## 7. Nächste Schritte

- T011-05 — Cognito (Pool, Client, Gruppe) (separater Task)

## 8. Zeitplan-Bewertung

F011/T011-01 bis T011-03 planmäßig; Terraform-Scope entspricht dem Vier-Wochen-Plan (Woche 2).

## 9. Git Checkpoint

- Branch: `main`
- Commit: `449cdd7` (F011/T011-04 Lambda Order Handler + Zip-Build)
- Push: SUCCESS