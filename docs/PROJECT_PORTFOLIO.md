# Project Portfolio — May's Orders

> Übergeordnete Projektdokumentation: vollständiger Projektweg von Business Problem bis
> Finale Präsentation. **Nur tatsächlich erreichte Abschnitte sind als COMPLETE markiert.**
> Statuskonvention siehe `docs/PROJECT_STATUS.md`.

## Projekt

- **Name:** May's Orders
- **Händler:** OrderFlow GmbH (fiktiv)
- **Typ:** AWS Serverless Order-Management-System (Backend + IaC)
- **Kernfrage:** Welches Business-Problem wird gelöst? → Ein Bestell-Backoffice, das den
  kompletten Lebenszyklus einer Bestellung nachvollziehbar, sicher und kostengünstig abbildet.

## Projektweg

```text
Business Problem      ✅ COMPLETE  (requirements/business-requirements.md)
      ↓
Requirements          ✅ COMPLETE  (requirements/)
      ↓
Architecture          ✅ COMPLETE  (architecture/, ADR-001…007)
      ↓
API Design            ✅ COMPLETE  (api/endpoints.md)
      ↓
Data Model            ✅ COMPLETE  (database/dynamodb-design.md, access-patterns.md)
      ↓
Authentication        ✅ COMPLETE  (security/authentication-decision.md) — Design
      ↓
Implementation        ⏳ PLANNED   (Woche 2, docs/features/F003…F006)
      ↓
Testing               ⏳ PLANNED   (api/test-cases.md, docs/reports/test-strategy.md)
      ↓
Security              ✅ COMPLETE  (Design) / ⏳ PLANNED (Umsetzung W2/3)
      ↓
Monitoring            ✅ COMPLETE  (Design) / ⏳ PLANNED (Umsetzung W3/4)
      ↓
Scalability           ⏳ PLANNED   (Woche 4)
      ↓
Cost Optimization     ⏳ PLANNED   (Woche 4, Messung)
      ↓
Terraform             ⏳ PLANNED   (Woche 2, terraform/)
      ↓
Final Validation      ⏳ PLANNED   (Woche 4)
      ↓
Final Presentation    ⏳ PLANNED   (Woche 4, presentation/)
```

## Leitfragen (Präsentationsziele)

| Frage | Antwort-Ort |
|-------|-------------|
| Welches Business-Problem wird gelöst? | `requirements/business-requirements.md` |
| Warum Serverless? | `architecture/architecture-decisions.md` (ADR-001) |
| Warum API Gateway? | ADR-003/004 |
| Warum Lambda? | ADR-001 |
| Warum DynamoDB? | `database/dynamodb-design.md` |
| Warum nicht EC2 / RDS? | ADR-001 (Alternativen) |
| Wie werden Orders effizient abgefragt? | `database/access-patterns.md` |
| Wie wird der Lifecycle modelliert? | `order-lifecycle/state-machine.md` |
| Wie werden ungültige Übergänge verhindert? | `order-lifecycle/transition-rules.md` |
| Wie werden konkurrierende Updates behandelt? | `reliability/consistency-and-failure-handling.md` |
| Wie funktioniert Auth/Authz? | `security/authentication-decision.md`, `security/iam-design.md` |
| Wie wird überwacht? | `monitoring/monitoring-design.md` |
| Wie skaliert es / was kostet es? | `cost/cost-analysis.md` (Woche 4-Messung geplant) |
| Wie wird Infrastruktur verwaltet? | `terraform/README.md` |
| Well-Architected? | Woche 4 (geplant) |

## Status-Zusammenfassung

| Phase | Status |
|-------|--------|
| Woche 1 — Analyse & Architektur | ✅ COMPLETE |
| Woche 2 — Core Implementation | ⏳ PLANNED |
| Woche 3 — Business Rules, Reliability, Security | ⏳ PLANNED |
| Woche 4 — Professionalization | ⏳ PLANNED |

## Recovery

Der aktuelle Stand ist jederzeit über `docs/PROJECT_STATUS.md` abrufbar.