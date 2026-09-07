# Week 3 — Business Rules, Reliability & Security

> **Offizieller Fokus:** Business Rules, Reliability & Security.
> **Status:** ⏳ NOT STARTED (geplant)
> **Go-to-Dokument:** `docs/reports/WEEK-03.md` · `docs/reports/four-week-plan.md` §Woche 3

Diese Woche ist im Vier-Wochen-Plan vorgesehen, aber noch nicht durchgeführt. Die
zugehörigen Fachquellen aus Woche 1 existieren bereits und sind hier verlinkt.

## Geplante Deliverables (Vier-Wochen-Plan)

| # | Feature | Status |
|---|---------|--------|
| 1 | State Machine als Domain-Modul + Unit-Tests (18 Fälle) | ⏳ PLANNED |
| 2 | Conditional-Write-Integration + Konkurrenztest (R-01, R-02) | ⏳ PLANNED |
| 3 | Idempotenz-Semantik + Test | ⏳ PLANNED |
| 4 | Security: Auth-/Authorization-Logik, Group-Checks, kein PII im Log | ⏳ PLANNED |
| 5 | CloudWatch-Alarme/Dashboard (kostenbewusst) | ⏳ PLANNED |
| 6 | Negativ-Tests (401/403) | ⏳ PLANNED |
| 7 | Doku-Update aller Security-/Reliability-Entscheidungen | ⏳ PLANNED |

## Fachquellen (bereits vorhanden, aus Woche 1/2)

| Thema | Ort |
|-------|-----|
| State Machine / Transitions | [`order-lifecycle/state-machine.md`](../order-lifecycle/state-machine.md) · [`lambda/src/state_machine.py`](../lambda/src/state_machine.py) |
| Validation | [`lambda/src/validation.py`](../lambda/src/validation.py) |
| Konsistenz & Fehlerbehandlung | [`reliability/consistency-and-failure-handling.md`](../reliability/consistency-and-failure-handling.md) |
| IAM-Design | [`security/iam-design.md`](../security/iam-design.md) |
| Monitoring | [`monitoring/monitoring-design.md`](../monitoring/monitoring-design.md) |

## Wöchentlicher Nachweis

- [Weekly Report Woche 3](../docs/reports/WEEK-03.md) (Notiz: NOT STARTED)