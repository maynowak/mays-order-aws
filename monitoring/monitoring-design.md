# Monitoring Design — May's Orders

> **Source of Truth** für die Monitoring-Anforderungen (F010, T011-11).
> Stand T011-11: Monitoring wird vollständig per **Terraform** (IaC) beschrieben —
> Dashboard, Alarme, Log-Retention. **Kein AWS Apply/Test** in T011-11.

## 1. Monitoring-Ziel

- Betriebszustand der API jederzeit erkennbar.
- Fehler schnell lokalisierbar (welcher Endpoint, welche Lambda, welches DynamoDB-Pattern).
- Kostenkontrolle (CloudWatch-Logs nicht unkontrolliert wachsen lassen).
- Reproduzierbar: Monitoring wird als Infrastructure as Code (Terraform) abgebildet,
  damit Dashboard und Alarme später in AWS nachvollziehbar erstellt werden können.

## 2. CloudWatch Logs

- Lambda-Log-Group: `/aws/lambda/mays-orders-handler`.
  - Lambda erzeugt die Group automatisch, aber ohne Retention (`Never expire`).
  - Terraform definiert die Log-Group **explizit** mit **Retention 7 Tage**
    (`var.log_retention_days`, Default `7`) — keine Duplizierung, sondern IaC-
    Steuerung der Retention (kostenbewusst, siehe §12).
- **Strukturiertes JSON-Logging** in der Lambda (korrelierte Request-ID).
- **Keine** Secrets/Tokens/Kunden-PII ungefiltert (Anonymisierung/Pruning Woche 3).
- API-Gateway-Access-Logs: **optional** (Log-Format klein halten). In T011-11
  bewusst NICHT aktiviert (kostenbewusst; keine Änderung an der bestehenden Stage).

## 3. CloudWatch Metrics

Nur **echte AWS-Metriken** (keine erfundenen Metric Names), bezogen auf die
vorhandenen Ressourcen:

| Metrik | Namespace | Dimension |
|--------|-----------|-----------|
| API-Requests (Count) | `AWS/ApiGateway` | `ApiId`, `Stage` |
| API-4xx (`4XXError`) | `AWS/ApiGateway` | `ApiId`, `Stage` |
| API-5xx (`5XXError`) | `AWS/ApiGateway` | `ApiId`, `Stage` |
| Lambda-Invocations | `AWS/Lambda` | `FunctionName` |
| Lambda-Errors | `AWS/Lambda` | `FunctionName` |
| Lambda-Duration (p95) | `AWS/Lambda` | `FunctionName` |
| Lambda-Throttles | `AWS/Lambda` | `FunctionName` |
| Concurrent Executions | `AWS/Lambda` | `FunctionName` |
| DynamoDB-ThrottledRequests | `AWS/DynamoDB` | `TableName` |
| DynamoDB-ConditionalCheckFailed | `AWS/DynamoDB` | `TableName` |

## 4. Dashboard

**Ein** zentrales CloudWatch-Dashboard: `mays-orders-overview` (Terraform
`aws_cloudwatch_dashboard`).

> „May's Orders — Order Management Overview"

Bereiche:
- **SYSTEM HEALTH** — API Requests, API 4XX, API 5XX, Lambda Invocations,
  Lambda Errors, Lambda Duration, Lambda Throttles, Concurrent Executions,
  DynamoDB Throttled Requests (je ein Widget).
- **ORDER OPERATIONS** — Orders Created / Orders by Status / Order Success Rate:
  als **Markdown-Widget** als **GAP / PLANNED** ausgewiesen (siehe §9 — noch
  keine Custom Metrics; keine erfundenen Werte im Dashboard).
- **ERROR ANALYSIS** — API Errors (4XX+5XX), Lambda Errors, DynamoDB Throttling
  (ThrottledRequests + ConditionalCheckFailedRequests).

Einzelmetriken (API Requests, API Errors, Lambda Duration/Errors/Invocations/
Throttles, Concurrent Executions, DynamoDB Throttled, Order Status Distribution,
Order Success Rate) werden durch diese Widget-Struktur abgedeckt — nicht als
separate Dashboards (kostenbewusst).

## 5. Alarms

Terraform-`aws_cloudwatch_metric_alarm` (alle `count = var.monitoring_enabled ? 1 : 0`):

| Alarm | Metrik | Statistik | Schwellwert (Initial) |
|-------|--------|-----------|------------------------|
| `api-5xx` | `AWS/ApiGateway 5XXError` | Sum | 5 / Periode |
| `api-4xx` | `AWS/ApiGateway 4XXError` | Sum | 20 / Periode |
| `lambda-errors` | `AWS/Lambda Errors` | Sum | 1 / Periode |
| `lambda-duration` | `AWS/Lambda Duration` | Average | 8000 ms |
| `lambda-throttles` | `AWS/Lambda Throttles` | Sum | 1 / Periode |
| `dynamodb-throttled` | `AWS/DynamoDB ThrottledRequests` | Sum | 1 / Periode |

- Periode: `var.alarm_period_seconds` (Default 300 = 5 min), Evaluation:
  `var.alarm_evaluation_periods` (Default 1).
- `treat_missing_data = "notBreaching"`: bei fehlenden Daten (kein Traffic)
  kein Fehlalarm — Zustand bleibt `OK`.
- **Kein SNS-Topic/Aktion** in T011-11 (kostenbewusst; SNS optional später,
  siehe `cost/cost-analysis.md` §5).
- Optional (später): `Low Order Success Rate` — **nur** als Business-Metrik
  möglich, siehe §9.

## 6. API Metrics

HTTP API V2 (`mays-orders-api`) → `AWS/ApiGateway`:
- `Count` (Anzahl Requests), `4XXError`, `5XXError` — Dimension `ApiId` + `Stage`
  (`$default`).
- Im Dashboard als API Requests, API 4XX/5XX Errors und Error-Analysis abgebildet.
- Access-Logging der Stage: optional (nicht aktiviert, kostenbewusst).

## 7. Lambda Metrics

Order Handler (`mays-orders-handler`, Python 3.14) → `AWS/Lambda`:
- `Invocations`, `Errors`, `Duration` (p95 im Dashboard, Average im Alarm),
  `Throttles`, `ConcurrentExecutions` — Dimension `FunctionName`.
- Lambda-Log-Group mit 7-Tage-Retention (siehe §2).

## 8. DynamoDB Metrics

Tabelle `mays-orders` (On-Demand) → `AWS/DynamoDB`:
- `ThrottledRequests` (Alarm + Dashboard), `ConditionalCheckFailedRequests`
  (Dashboard Error-Analysis) — Dimension `TableName`.
- `ConsumedRead/WriteCapacity` (optional, Kosten-Diagnose) — nicht im T011-11-Scope.

## 9. Order Business Metrics

| Metrik | Kategorie | Status | Datenquelle (später) |
|--------|-----------|--------|----------------------|
| Orders Created | aus Order-Daten abgeleitet | **PLANNED / FUTURE APPLICATION METRIC** | DynamoDB GSI1 (`gsi1pk=LIST`, `gsi1sk=createdAt`) oder Lambda-Metric-Logger |
| Orders by Status | aus Order-Daten abgeleitet | **PLANNED / FUTURE APPLICATION METRIC** | DynamoDB `status`-Feld, Query/Scan (Auswertung) |
| Order Success Rate | aus Order-Daten abgeleitet | **PLANNED / FUTURE APPLICATION METRIC** | DynamoDB `status`-Verteilung (`DELIVERED` vs. `CANCELLED`) |

- Diese Metriken sind in T011-11 **NICHT** als CloudWatch Custom Metrics
  implementiert (kein neuer Lambda-Code, keine erfundenen Metric Names).
- Umsetzung erst, wenn sie als echte CloudWatch-Metriken verfügbar sein können
  (Application Metrics; Namespace z. B. `MaySOrders`).
- A) direkt von AWS bereitgestellte Metriken → §3 (API/Lambda/DynamoDB).
  B) Application Metrics → PLANNED (Lambda-Metric-Logger).
  C) aus DynamoDB/Order-Daten abgeleitete Business-Metriken → PLANNED.

## 10. createdAt / updatedAt

Order-Modell (DynamoDB, Seed-Daten):

- **`createdAt`** = Zeitpunkt der Order-Erstellung (ISO-8601 UTC).
- **`updatedAt`** = Zeitpunkt der letzten Änderung (z. B. Status-Update, ISO-8601 UTC).
- `gsi1sk = createdAt` (GSI1-Key, Listing „neueste zuerst").

**Nicht vermischen:** CloudWatch-Metriken besitzen **eigene Timestamps**
(Zeitpunkt der Metrik-Erhebung, z. B. 5-Minuten-Perioden). `createdAt`/`updatedAt`
sind **Domain-Felder der Order**. Beispiel-/Dokumentationszeitraum (kein echter
AWS-CloudWatch-Betrieb): `16.05.2025 – 22.05.2025` — reine Beispieldaten, keine
Behauptung eines laufenden Systems.

## 11. Alarm Thresholds

- Schwellwerte sind **konfigurierbare Terraform-Variablen** (`terraform/variables.tf`).
- Alle Werte sind „**Initial threshold / starting value — requires calibration
  with real AWS metrics.**" — keine Produktionswerte.
- Kalibrierung erfolgt erst nach AWS-Live-Test (übernächste Woche) anhand echter
  Metrikdaten (Traffic, Fehlerraten, Latenz).

## 12. Kostenbewusstsein

- **1 Dashboard** statt mehrerer; **6 Alarme** (≈ 0,60 $/Monat bei 0,10 $/Alarm);
  Planungsbasis `cost/cost-analysis.md` §2 (~0,30–1,00 $/Monat CloudWatch).
- **Log-Retention 7 Tage** — verhindert unbegrenztes Log-Wachstum.
- **Keine Custom Metrics**, nur um Dashboards „voller" aussehen zu lassen.
- **Kein SNS-Topic** in T011-11 (optional später, sehr geringe Kosten).
- Keine High-Cardinality-Metriken (nur feste Dimensionen: ApiId/Stage,
  FunctionName, TableName).

## 13. Terraform / IaC

- Datei: `terraform/monitoring.tf` (T011-11).
- Ressourcen: `aws_cloudwatch_dashboard`, `aws_cloudwatch_metric_alarm` (×6),
  `aws_cloudwatch_log_group` (Retention).
- Variablen: `monitoring_enabled`, `dashboard_enabled`, `log_retention_days`,
  `alarm_period_seconds`, `alarm_evaluation_periods`, 6 Schwellwerte
  (siehe §11).
- `monitoring_enabled=false` → **keine** Monitoring-Ressourcen im Plan.
- Referenzen auf bestehende Ressourcen (API-ID, Stage, FunctionName, TableName)
  werden per Terraform-Attribut aufgelöst — keine hartkodierten IDs.

## 14. Lokaler Validierungsstand (T011-11)

| Prüfung | Ergebnis |
|---------|----------|
| `terraform fmt` / `fmt -check` | PASS |
| `terraform init` | PASS |
| `terraform validate` | PASS |
| `terraform plan` (default) | **24 to add, 0 to change, 0 to destroy** (16 + 8 Monitoring) |
| `plan -var="monitoring_enabled=false"` | 16 to add (Monitoring aus) |
| `plan -var="dashboard_enabled=false"` | 23 to add (Dashboard aus) |
| Dashboard-JSON (Widget-Schema) | PASS (terraform console, jsondecode) |
| `git diff --check` · Secret-Audit · Python-Tests | PASS (Lambda 51/51, Seed 28/28) |
| `terraform apply` | **NOT RUN** (Freigabe erforderlich) |

## 15. AWS-Test später (übernächste Woche)

Nach Freigabe und `apply` werden live geprüft:

- Dashboard erscheint, Widgets zeigen echte Daten.
- Metrics liefern Werte; Alarms wechseln korrekt zwischen OK / ALARM /
  INSUFFICIENT_DATA.
- Logs erscheinen (7-Tage-Retention greift).
- Thresholds werden anhand realer Daten kalibriert.
- Fehler-Szenarien (401, 409, 500) auslösen und in CloudWatch-Logs nachweisen.

**Alarm-Konfiguration = PLAN VERIFIED. Tatsächlicher Alarm-Zustand = NOT RUN.**
