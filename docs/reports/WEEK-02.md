# Weekly Report — Woche 2

**Datum:** 2026-08-17 (laufend)
**Projekt:** May's Orders — AWS Serverless Order Management
**Status:** 🔵 IN PROGRESS

## 1. Gesamtstatus

Woche 2 läuft. F011 (Terraform Infrastructure) in Arbeit; T011-01 (Terraform-Gerüst) und
T011-02 (DynamoDB-Tabelle + GSI1) abgeschlossen und validiert. Noch keine AWS-Ressourcen
erzeugt, kein `apply`.

## 2. Erledigte Features / Tasks

| Feature | Task | Status |
|---------|------|--------|
| F011 — Terraform Infrastructure | T011-01 Terraform-Gerüst (main/variables/outputs/README) | ✅ COMPLETE |
| F011 — Terraform Infrastructure | T011-02 DynamoDB-Tabelle + GSI1 (mays-orders, PK pk/sk, GSI1, On-Demand) | ✅ COMPLETE |
| F011 — Terraform Infrastructure | T011-03 IAM-Rolle + Policy | ⏳ PLANNED |
| F002 — Cognito Authentication | … | ⏳ PLANNED |
| F003 — API Gateway | … | ⏳ PLANNED |
| F004 — Order Creation | … | ⏳ PLANNED |
| F005 — Order Retrieval | … | ⏳ PLANNED |
| F006 — Order Listing | … | ⏳ PLANNED |

## 3. Tests / Build / Validation

| Prüfung | Status |
|---------|--------|
| TypeScript-Build | NOT APPLICABLE (kein App-Code) |
| Unit-Tests | NOT RUN |
| Terraform init | PASS (aws provider v6.60.0) |
| Terraform validate | PASS (ohne Warnungen) |
| Terraform plan | NOT RUN (zu T011-07) |
| Terraform apply | NOT RUN (Freigabe erforderlich) |
| Live-API | NOT RUN |

## 4. AWS-Ressourcen

NONE — es wurden keine Ressourcen erzeugt (T011-02 ist reine Terraform-Konfiguration;
`apply` erst in T011-08 nach Freigabe).

## 5. Probleme / Risiken / Blocker

Keine. DynamoDB-Konfiguration folgt exakt `database/dynamodb-design.md` (PK, GSI1,
Projection, On-Demand); kein Scan-Pattern (ADR-002). AWS-Provider auf `~> 6.0`
(6.60.0) gehoben; GSI1 nutzt die neue `key_schema`-Syntax (≥ 6.29.0).

## 6. Kosten

Keine AWS-Ressourcen erzeugt → keine Kosten. Weitere Bewertung in Woche 4
(`cost/cost-analysis.md`). On-Demand-Konfiguration vorbereitet (ADR-007).

## 7. Nächste Schritte

- T011-03 — IAM-Rolle + Policy (separater Task)

## 8. Zeitplan-Bewertung

F011/T011-01 und T011-02 planmäßig; Terraform-Scope entspricht dem Vier-Wochen-Plan (Woche 2).

## 9. Git Checkpoint

- Branch: `main`
- Commit: `fc89aef` (F011 Provider-Upgrade `~> 6.0` / 6.60.0, GSI1 `key_schema`)
- Push: SUCCESS