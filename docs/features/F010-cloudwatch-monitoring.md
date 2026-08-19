# F010 — CloudWatch Monitoring

| Feld | Wert |
|------|------|
| **ID** | F010 |
| **Name** | CloudWatch Monitoring |
| **Status** | 🔵 IN PROGRESS (IaC T011-11 fertig; Live-Test offen) |
| **Week** | 3–4 |
| **Abhängigkeiten** | F003, F011 |
| **Fachquelle** | `monitoring/monitoring-design.md` |

## Beschreibung

Metriken (API 4xx/5xx, Lambda Errors/Duration/Throttles, DynamoDB Throttling),
CloudWatch-Dashboard als Gesamtübersicht, minimale Alarme (kostenbewusst),
Log-Retention 7 Tage — vollständig als **Terraform/IaC** beschrieben
(T011-11, `terraform/monitoring.tf`). **Kein AWS Apply** in T011-11.

## Tasks

| ID | Task | Status |
|----|------|--------|
| T010-01 | JSON-Logging in Lambda | 🟡 IMPLEMENTED (IaC-Retention; strukturiertes Logging im Handler-Code) |
| T010-02 | Log-Retention setzen (7 Tage) | ✅ COMPLETE (T011-11: `aws_cloudwatch_log_group`, `log_retention_days=7`) |
| T010-03 | Metriken definieren + Alarme (falls angemessen) | ✅ COMPLETE (IaC: Dashboard + 6 Alarme, konfigurierbare Schwellwerte) |
| T010-04 | Fehler-Szenarien auslösen und in Logs nachweisen | ⏳ PLANNED (nach AWS-Live-Test, übernächste Woche) |
| T010-05 | Skalierungs-/Kosten-Messung (Woche 4) | ⏳ PLANNED |
| T010-06 | Business-Metriken (Orders Created / by Status / Success Rate) | ⏳ PLANNED (GAP dokumentiert, siehe monitoring-design.md §9) |
| T010-07 | Alarm-Schwellwerte an realen Daten kalibrieren | ⏳ PLANNED (nach AWS-Live-Test) |

## Testnachweise

| Prüfung | Status |
|---------|--------|
| Terraform fmt / init / validate | PASS (T011-11) |
| Terraform plan (default) | PASS — 24 to add, 0 change, 0 destroy (T011-11) |
| Logging verifiziert | NOT RUN (kein apply) |
| Alarme konfiguriert | PASS (IaC) — live: NOT RUN |
| Dashboard live | NOT RUN |
| Messung (Duration/Cost) | NOT RUN |

## Git Checkpoint

- Branch: `feature/t011-11-cloudwatch-monitoring` · Commit: siehe T011-11 · Push: offen

## Next Step

AWS-Live-Test (übernächste Woche): Dashboard/Metriken/Alarme/Logs verifizieren,
Thresholds kalibrieren.
