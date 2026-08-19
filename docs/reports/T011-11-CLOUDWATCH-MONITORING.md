# T011-11 — CloudWatch Monitoring as Code — Report

> **Task:** CloudWatch-Monitoring vollständig per Terraform (IaC) — Dashboard(s),
> Alarme, zugehörige Monitoring-Konfiguration. **Kein AWS-Apply, kein Live-Test.**
> **Basis:** Branch `feature/t011-11-cloudwatch-monitoring` (Merge nach `main` nach Checkpoint).
> **Datum:** 2026-08-19

## 1. Ziel

Das Monitoring von May's Orders soll reproduzierbar als Infrastructure as Code
beschrieben werden: ein zentrales CloudWatch-Dashboard, sinnvolle CloudWatch-Alarme
und die Log-Konfiguration (Retention). Später werden diese Ressourcen per
`terraform apply` in AWS erzeugt. AWS ist in dieser Aufgabe **nicht** praktisch
testbar → kein `apply`, kein Live-Test, kein manuelles AWS-Setup.

## 2. Ausgangszustand

- Terraform-Stand: DynamoDB (T011-02), IAM (T011-03), Lambda (T011-04, Python 3.14),
  Cognito (T011-05), HTTP API V2 (T011-06), Demo-Seed opt-in (T011-10).
- **Keine CloudWatch-Ressourcen** in Terraform vorhanden (`aws_cloudwatch_*` = 0).
- Plan-Stand vor T011-11: **16 to add, 0 to change, 0 to destroy** (T011-07/T011-10).

## 3. Vorhandenes Monitoring (Ist)

- `monitoring/monitoring-design.md` (Source of Truth): Metriken API 4xx/5xx,
  Lambda Errors/Duration/Throttles, DynamoDB Throttling; Log-Retention 7 Tage;
  Alarme minimal (kostenbewusst), Dashboard geplant.
- `cost/cost-analysis.md` §2: Log-Retention 7 Tage; 3 Alarme ≈ 0,30 $/Monat;
  SNS optional (sehr gering).
- **Kein** AWS-CloudWatch-Betrieb bisher (kein apply) → keine Live-Metriken vorhanden.

## 4. Neue Terraform-Ressourcen (T011-11)

| Ressource | Typ | Name | Zweck |
|-----------|-----|------|-------|
| Dashboard | `aws_cloudwatch_dashboard` | `mays-orders-overview` | Zentrale Gesamtübersicht |
| Alarm ×6 | `aws_cloudwatch_metric_alarm` | `mays-orders-api-5xx`, `-api-4xx`, `-lambda-errors`, `-lambda-duration`, `-lambda-throttles`, `-dynamodb-throttled` | Fehler-/Latenz-/Throttling-Überwachung |
| Log-Group | `aws_cloudwatch_log_group` | `/aws/lambda/mays-orders-handler` | IaC-Retention (7 Tage) |

Alle Monitoring-Ressourcen sind über `count = var.monitoring_enabled` steuerbar
(`false` → 0 Monitoring-Ressourcen im Plan). Bestehende Infrastruktur wird **nicht**
verändert (keine Lambda-Runtime-, Cognito-, API-GW-, DynamoDB-Änderungen).

## 5. Dashboard „May's Orders — Order Management Overview"

Ein zentrales Dashboard (`mays-orders-overview`) mit drei Bereichen:

**A. SYSTEM HEALTH** — 9 Metric-Widgets:

| Widget | Metrik | Statistik |
|--------|--------|-----------|
| API Requests | `AWS/ApiGateway Count` | Sum |
| API 4XX Errors | `AWS/ApiGateway 4XXError` | Sum |
| API 5XX Errors | `AWS/ApiGateway 5XXError` | Sum |
| Lambda Invocations | `AWS/Lambda Invocations` | Sum |
| Lambda Errors | `AWS/Lambda Errors` | Sum |
| Lambda Duration | `AWS/Lambda Duration` | p95 |
| Lambda Throttles | `AWS/Lambda Throttles` | Sum |
| Concurrent Executions | `AWS/Lambda ConcurrentExecutions` | Maximum |
| DynamoDB Throttled Requests | `AWS/DynamoDB ThrottledRequests` | Sum |

**B. ORDER OPERATIONS** — Markdown-Widget: Orders Created / Orders by Status /
Order Success Rate sind **GAP / PLANNED** (keine Custom Metrics; keine erfundenen
Metric Names). Datenquelle später: DynamoDB/Order-Daten (`createdAt`, `updatedAt`,
`status`). Siehe §8.

**C. ERROR ANALYSIS** — 3 Widgets: API Errors (4XX+5XX), Lambda Errors,
DynamoDB Throttling (ThrottledRequests + ConditionalCheckFailedRequests).

Widget-Struktur ist eine sinnvolle **Widget-Sammlung innerhalb eines Dashboards**
(keine 10 separaten Dashboards — kostenbewusst). Alle Dimensionen referenzieren die
bestehenden Terraform-Ressourcen (ApiId, Stage `$default`, FunctionName, TableName) —
keine hartkodierten IDs.

## 6. Metriken

Nur echte AWS-Namespaces (keine erfundenen Namen):

| Kategorie | Namespace | Metriken | Dimension |
|-----------|-----------|----------|-----------|
| API | `AWS/ApiGateway` | `Count`, `4XXError`, `5XXError` | `ApiId`, `Stage` |
| Lambda | `AWS/Lambda` | `Invocations`, `Errors`, `Duration`, `Throttles`, `ConcurrentExecutions` | `FunctionName` |
| DynamoDB | `AWS/DynamoDB` | `ThrottledRequests`, `ConditionalCheckFailedRequests` | `TableName` |

## 7. Alarme

| Alarm | Metrik | Statistik | Schwellwert (Initial) | Periode |
|-------|--------|-----------|-----------------------|---------|
| `api-5xx` | `AWS/ApiGateway 5XXError` | Sum | 5 | 300 s (5 min) |
| `api-4xx` | `AWS/ApiGateway 4XXError` | Sum | 20 | 300 s |
| `lambda-errors` | `AWS/Lambda Errors` | Sum | 1 | 300 s |
| `lambda-duration` | `AWS/Lambda Duration` | Average | 8000 ms | 300 s |
| `lambda-throttles` | `AWS/Lambda Throttles` | Sum | 1 | 300 s |
| `dynamodb-throttled` | `AWS/DynamoDB ThrottledRequests` | Sum | 1 | 300 s |

- `treat_missing_data = "notBreaching"` → bei fehlenden Daten kein Fehlalarm.
- **Kein SNS-Topic** (kostenbewusst; `cost/cost-analysis.md` §5: SNS optional).
- Schwellwerte sind konfigurierbare Variablen („Initial threshold / starting value —
  requires calibration with real AWS metrics.").

## 8. Order Business Metrics

| Metrik | Typ | Status | Datenquelle (später) |
|--------|-----|--------|----------------------|
| Orders Created | C) abgeleitet | PLANNED / FUTURE APPLICATION METRIC | GSI1 (`gsi1pk=LIST`, `gsi1sk=createdAt`) oder Lambda-Metric-Logger |
| Orders by Status | C) abgeleitet | PLANNED / FUTURE APPLICATION METRIC | DynamoDB `status`-Feld |
| Order Success Rate | C) abgeleitet | PLANNED / FUTURE APPLICATION METRIC | `status`-Verteilung (`DELIVERED` vs. `CANCELLED`) |

Nicht in T011-11 implementiert (kein neuer Lambda-Code, keine erfundenen Metriken).

## 9. Order-Datum/Zeit: createdAt / updatedAt

- `createdAt` = Zeitpunkt der Order-Erstellung; `updatedAt` = letzte Änderung
  (beide ISO-8601 UTC, im Order-Modell und in den Seed-Daten vorhanden).
- CloudWatch-Metriken haben **eigene Timestamps** (Erhebungszeitpunkte) — diese
  beiden Zeitkonzepte werden nicht vermischt.
- Beispiel-/Dokumentationszeitraum (kein echter CloudWatch-Betrieb):
  **16.05.2025 – 22.05.2025** — reine Beispieldaten.

## 10. CloudWatch Logging

- Lambda-Log-Group `/aws/lambda/mays-orders-handler` explizit via Terraform mit
  `retention_in_days = 7` (IaC-Steuerung; Lambda erzeugt die Group sonst ohne Retention).
- Strukturiertes JSON-Logging im Handler; keine Secrets/PII.
- API-Gateway-Access-Logs: optional, **nicht** aktiviert (kostenbewusst, keine
  Änderung an der Stage).

## 11. Kostenbewusstsein

- 1 Dashboard statt mehrerer; 6 Alarme (≈ 0,60 $/Monat; Planungsbasis
  cost-analysis.md §2: CloudWatch ~0,30–1,00 $/Monat).
- Log-Retention 7 Tage; keine Custom Metrics; keine High-Cardinality-Dimensionen;
  kein SNS-Topic.

## 12. Tests / Lokale Validierung

| Prüfung | Ergebnis |
|---------|----------|
| `terraform fmt` / `fmt -check` | PASS |
| `terraform init -input=false -backend=false` | PASS |
| `terraform validate` | PASS |
| `terraform plan` (default) | PASS — **24 to add, 0 to change, 0 to destroy** |
| `terraform plan -var="monitoring_enabled=false"` | PASS — **16 to add** |
| `terraform plan -var="dashboard_enabled=false"` | PASS — **23 to add** |
| Dashboard-JSON (Widget-Schema) | PASS (`terraform console`, jsondecode) |
| Python-Tests | PASS (Lambda 51/51, Seed 28/28) |
| `git diff --check` | PASS |
| Secret-Audit | PASS |
| `terraform apply` | **NOT RUN** |

Plan-Analyse: ausschließlich `create`-Aktionen (24), kein `update`, kein `delete`,
kein `replace`; bestehende Order-Infrastruktur (Lambda Runtime, Cognito, API Gateway,
DynamoDB-Schema) unverändert.

## 13. Alarm-Status (OK / ALARM / INSUFFICIENT_DATA)

- Mögliche Zustände: `OK` / `ALARM` / `INSUFFICIENT_DATA` (CloudWatch-Standard).
- `treat_missing_data = "notBreaching"`: fehlende Daten werden als „nicht breaching"
  gewertet → Zustand bleibt `OK` (kein Fehlalarm bei fehlendem Traffic).
- **Alarm configuration = PLAN VERIFIED.** Der lokale Terraform-Plan kann den
  tatsächlichen späteren Alarm-Zustand **nicht** beweisen.
- **Actual alarm state = NOT RUN** — keine Behauptung einer echten AWS-Alarmierung.

## 14. AWS Live Status

| Prüfung | Status |
|---------|--------|
| Terraform implementation | COMPLETE / PASS |
| Terraform validation | PASS |
| Terraform plan | PASS |
| AWS apply | NOT RUN |
| CloudWatch Dashboard live | NOT RUN |
| CloudWatch Alarms live | NOT RUN |
| Real AWS metric verification | NOT RUN |
| Threshold calibration | PLANNED |

Grund: AWS-Live-Test erst übernächste Woche möglich.

## 15. Offene Punkte / Nächste Schritte

- T011-08: `terraform apply` nach menschlicher Freigabe.
- AWS-Live-Test (übernächste Woche): Dashboard erscheint, Widgets zeigen echte Daten,
  Metrics liefern Werte, Alarms wechseln korrekt zwischen OK/ALARM/INSUFFICIENT_DATA,
  Logs erscheinen, Thresholds anhand realer Daten kalibrieren.
- Optional: Business-Metriken als Application Metrics (Lambda-Metric-Logger), SNS-Topic
  für Alarm-Benachrichtigung, API-GW-Access-Logs, `Low Order Success Rate`-Alarm.

## 16. Finaler Status

| Kriterium | Status |
|-----------|--------|
| Monitoring IaC | PASS |
| Dashboard Terraform | PASS |
| Alarm Terraform | PASS |
| Metrics | PARTIAL (Infra-Metriken PASS; Business-Metriken PLANNED) |
| Business Metrics | PLANNED |
| Terraform fmt | PASS |
| Terraform validate | PASS |
| Terraform plan | PASS |
| AWS Apply | NOT RUN |
| AWS CloudWatch Verification | NOT RUN |
| Documentation | PASS |
| Git | PASS |

## 17. Referenzen

- `monitoring/monitoring-design.md` (aktualisiert)
- `docs/features/F010-cloudwatch-monitoring.md` (aktualisiert)
- `docs/features/F011-terraform-infrastructure.md` (aktualisiert)
- `terraform/monitoring.tf` / `terraform/variables.tf`
- `docs/reports/T011-11-CLOUDWATCH-MONITORING-EXECUTION-LOG.md`