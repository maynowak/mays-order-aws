# Weekly Report — Woche 2

**Datum:** 2026-08-17 (laufend)
**Projekt:** May's Orders — AWS Serverless Order Management
**Status:** 🔵 IN PROGRESS

## 1. Gesamtstatus

Woche 2 gestartet. F011 (Terraform Infrastructure) in Arbeit; T011-01 (Terraform-Gerüst)
abgeschlossen und validiert. Noch keine AWS-Ressourcen erzeugt, kein `apply`.

## 2. Erledigte Features / Tasks

| Feature | Task | Status |
|---------|------|--------|
| F011 — Terraform Infrastructure | T011-01 Terraform-Gerüst (main/variables/outputs/README) | ✅ COMPLETE |
| F011 — Terraform Infrastructure | T011-02 DynamoDB + GSI1 | ⏳ PLANNED |
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
| Terraform init | PASS (aws provider v5.100.0) |
| Terraform validate | PASS |
| Terraform plan | NOT RUN (zu T011-07) |
| Terraform apply | NOT RUN (Freigabe erforderlich) |
| Live-API | NOT RUN |

## 4. AWS-Ressourcen

NONE — es wurden keine Ressourcen erzeugt (T011-01 ist ein reines Datei-Gerüst).

## 5. Probleme / Risiken / Blocker

Keine.

## 6. Kosten

Keine AWS-Ressourcen erzeugt → keine Kosten. Weitere Bewertung in Woche 4
(`cost/cost-analysis.md`).

## 7. Nächste Schritte

- T011-02 — DynamoDB-Tabelle + GSI1

## 8. Zeitplan-Bewertung

F011/T011-01 planmäßig gestartet; Terraform-Scope entspricht dem Vier-Wochen-Plan (Woche 2).

## 9. Git Checkpoint

- Branch: `main`
- Commit: `67f02a3` (F011/T011-01 Terraform-Grundgerüst)
- Push: SUCCESS