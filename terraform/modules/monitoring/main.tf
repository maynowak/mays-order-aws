# T011-11 — CloudWatch Monitoring as Code
# Fachquelle: monitoring/monitoring-design.md (Source of Truth für Anforderungen),
#             cost/cost-analysis.md §2 (kostenbewusst: 7-Tage-Retention, minimaler
#             Alarm-Umfang, kein SNS-Topic in dieser Aufgabe).
#
# Ziel: Dashboard + Alarme + Log-Retention vollständig per Terraform beschrieben,
# damit sie später reproduzierbar in AWS erzeugt werden können (kein apply in
# T011-11). Verwendete Metriken sind ausschließlich echte AWS-Namespaces:
#   AWS/ApiGateway (Count, 4XXError, 5XXError)        — HTTP API (ApiId, Stage)
#   AWS/Lambda     (Invocations, Errors, Duration,     — FunctionName
#                   Throttles, ConcurrentExecutions)
#   AWS/DynamoDB   (ThrottledRequests,                 — TableName
#                   ConditionalCheckFailedRequests)
#
# Business-Metriken (Orders Created / Orders by Status / Order Success Rate)
# sind BEWUSST NICHT als Custom Metrics implementiert (GAP, siehe
# docs/reports/T011-11-CLOUDWATCH-MONITORING.md): sie stünden als
# "FUTURE APPLICATION METRIC" auf Datenquelle DynamoDB/Order-Daten
# (createdAt, updatedAt, status). Keine erfundenen Metric Names.

locals {
  # gemeinsame Metric-Serien (ein Widget kann mehrere Serien kombinieren)
  m_api_requests      = ["AWS/ApiGateway", "Count", "ApiId", var.api_id, "Stage", var.api_stage_name, { stat = "Sum", period = 300, label = "Requests" }]
  m_api_4xx           = ["AWS/ApiGateway", "4XXError", "ApiId", var.api_id, "Stage", var.api_stage_name, { stat = "Sum", period = 300, label = "4XX" }]
  m_api_5xx           = ["AWS/ApiGateway", "5XXError", "ApiId", var.api_id, "Stage", var.api_stage_name, { stat = "Sum", period = 300, label = "5XX" }]
  m_lambda_invokes    = ["AWS/Lambda", "Invocations", "FunctionName", var.lambda_function_name, { stat = "Sum", period = 300, label = "Invocations" }]
  m_lambda_errors     = ["AWS/Lambda", "Errors", "FunctionName", var.lambda_function_name, { stat = "Sum", period = 300, label = "Errors" }]
  m_lambda_duration   = ["AWS/Lambda", "Duration", "FunctionName", var.lambda_function_name, { stat = "p95", period = 300, label = "Duration p95 (ms)" }]
  m_lambda_throttles  = ["AWS/Lambda", "Throttles", "FunctionName", var.lambda_function_name, { stat = "Sum", period = 300, label = "Throttles" }]
  m_lambda_concurrent = ["AWS/Lambda", "ConcurrentExecutions", "FunctionName", var.lambda_function_name, { stat = "Maximum", period = 300, label = "Concurrent" }]
  m_ddb_throttled     = ["AWS/DynamoDB", "ThrottledRequests", "TableName", var.dynamodb_table_name, { stat = "Sum", period = 300, label = "ThrottledRequests" }]
  m_ddb_cond_failed   = ["AWS/DynamoDB", "ConditionalCheckFailedRequests", "TableName", var.dynamodb_table_name, { stat = "Sum", period = 300, label = "ConditionalCheckFailed" }]

  order_ops_markdown = <<-EOT
    ## Order Operations — BUSINESS METRICS (GAP / PLANNED)

    Orders Created · Orders by Status · Order Success Rate sind **noch keine
    CloudWatch-Metriken** (keine Custom Metrics in dieser Aufgabe, keine
    erfundenen Metric Names).

    **STATUS = PLANNED / FUTURE APPLICATION METRIC**

    Datenquelle später: DynamoDB/Order-Daten via Lambda oder DynamoDB
    (`createdAt`, `updatedAt`, `status`, `totalAmount`). Erste Auswertung als
    Query auf GSI1 (`gsi1pk=LIST`, `gsi1sk=createdAt`) oder ein Lambda-
    Metric-Logger, der CloudWatch Custom Metrics (Namespace `MaySOrders`)
    emittiert. Siehe monitoring/monitoring-design.md §9 + Report T011-11.
  EOT

  monitoring_dashboard_widgets = [
    # ---- SYSTEM HEALTH ------------------------------------------------------
    { type = "text", width = 24, height = 1, properties = { markdown = "## System Health" } },
    { type = "metric", width = 8, height = 6, properties = { metrics = [local.m_api_requests], view = "timeSeries", region = var.aws_region, title = "API Requests" } },
    { type = "metric", width = 8, height = 6, properties = { metrics = [local.m_api_4xx], view = "timeSeries", region = var.aws_region, title = "API 4XX Errors" } },
    { type = "metric", width = 8, height = 6, properties = { metrics = [local.m_api_5xx], view = "timeSeries", region = var.aws_region, title = "API 5XX Errors" } },
    { type = "metric", width = 8, height = 6, properties = { metrics = [local.m_lambda_invokes], view = "timeSeries", region = var.aws_region, title = "Lambda Invocations" } },
    { type = "metric", width = 8, height = 6, properties = { metrics = [local.m_lambda_errors], view = "timeSeries", region = var.aws_region, title = "Lambda Errors" } },
    { type = "metric", width = 8, height = 6, properties = { metrics = [local.m_lambda_duration], view = "timeSeries", region = var.aws_region, title = "Lambda Duration" } },
    { type = "metric", width = 8, height = 6, properties = { metrics = [local.m_lambda_throttles], view = "timeSeries", region = var.aws_region, title = "Lambda Throttles" } },
    { type = "metric", width = 8, height = 6, properties = { metrics = [local.m_lambda_concurrent], view = "timeSeries", region = var.aws_region, title = "Concurrent Executions" } },
    { type = "metric", width = 8, height = 6, properties = { metrics = [local.m_ddb_throttled], view = "timeSeries", region = var.aws_region, title = "DynamoDB Throttled Requests" } },
    # ---- ORDER OPERATIONS (Business-Metriken: GAP/PLANNED, kein Fake) --------
    { type = "text", width = 24, height = 1, properties = { markdown = "## Order Operations" } },
    { type = "text", width = 24, height = 6, properties = { markdown = local.order_ops_markdown } },
    # ---- ERROR ANALYSIS ------------------------------------------------------
    { type = "text", width = 24, height = 1, properties = { markdown = "## Error Analysis" } },
    { type = "metric", width = 8, height = 6, properties = { metrics = [local.m_api_4xx, local.m_api_5xx], view = "timeSeries", region = var.aws_region, title = "API Errors (4XX / 5XX)" } },
    { type = "metric", width = 8, height = 6, properties = { metrics = [local.m_lambda_errors], view = "timeSeries", region = var.aws_region, title = "Lambda Errors" } },
    { type = "metric", width = 8, height = 6, properties = { metrics = [local.m_ddb_throttled, local.m_ddb_cond_failed], view = "timeSeries", region = var.aws_region, title = "DynamoDB Throttling" } },
  ]

  monitoring_dashboard_body = {
    start   = "-PT6H"
    widgets = local.monitoring_dashboard_widgets
  }
}

# --- 1. Dashboard: May's Orders — Order Management Overview ------------------
resource "aws_cloudwatch_dashboard" "orders_overview" {
  count          = var.monitoring_enabled && var.dashboard_enabled ? 1 : 0
  dashboard_name = "${var.project_name}-overview"
  dashboard_body = jsonencode(local.monitoring_dashboard_body)
}

# --- 2. Alarme (monitoring-design.md §4, kostenbewusst) ----------------------
# Kein SNS-Topic/Aktions in T011-11 (kostenbewusst; SNS optional später).
# Schwellwerte = konfigurierbare Variablen ("Initial threshold / starting value —
# requires calibration with real AWS metrics."). treat_missing_data="notBreaching"
# verhindert Fehlalarme bei fehlenden Daten (kein Traffic) und hält den Alarm
# bei ausbleibenden Messwerten auf OK.

resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  count             = var.monitoring_enabled ? 1 : 0
  alarm_name        = "${var.project_name}-api-5xx"
  alarm_description = "High API 5XX errors (HTTP API). Threshold: initial value, requires calibration with real AWS metrics."
  namespace         = "AWS/ApiGateway"
  metric_name       = "5XXError"
  dimensions = {
    ApiId = var.api_id
    Stage = var.api_stage_name
  }
  statistic           = "Sum"
  period              = var.alarm_period_seconds
  evaluation_periods  = var.alarm_evaluation_periods
  threshold           = var.api_5xx_threshold
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "api_4xx" {
  count             = var.monitoring_enabled ? 1 : 0
  alarm_name        = "${var.project_name}-api-4xx"
  alarm_description = "High API 4XX errors (HTTP API). Threshold: initial value, requires calibration with real AWS metrics."
  namespace         = "AWS/ApiGateway"
  metric_name       = "4XXError"
  dimensions = {
    ApiId = var.api_id
    Stage = var.api_stage_name
  }
  statistic           = "Sum"
  period              = var.alarm_period_seconds
  evaluation_periods  = var.alarm_evaluation_periods
  threshold           = var.api_4xx_threshold
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  count             = var.monitoring_enabled ? 1 : 0
  alarm_name        = "${var.project_name}-lambda-errors"
  alarm_description = "High Lambda errors (order handler). Threshold: initial value, requires calibration with real AWS metrics."
  namespace         = "AWS/Lambda"
  metric_name       = "Errors"
  dimensions = {
    FunctionName = var.lambda_function_name
  }
  statistic           = "Sum"
  period              = var.alarm_period_seconds
  evaluation_periods  = var.alarm_evaluation_periods
  threshold           = var.lambda_error_threshold
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  count             = var.monitoring_enabled ? 1 : 0
  alarm_name        = "${var.project_name}-lambda-duration"
  alarm_description = "High Lambda duration (order handler, ms). Threshold: initial value, requires calibration with real AWS metrics."
  namespace         = "AWS/Lambda"
  metric_name       = "Duration"
  dimensions = {
    FunctionName = var.lambda_function_name
  }
  statistic           = "Average"
  period              = var.alarm_period_seconds
  evaluation_periods  = var.alarm_evaluation_periods
  threshold           = var.lambda_duration_threshold_ms
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  count             = var.monitoring_enabled ? 1 : 0
  alarm_name        = "${var.project_name}-lambda-throttles"
  alarm_description = "High Lambda throttles (order handler). Threshold: initial value, requires calibration with real AWS metrics."
  namespace         = "AWS/Lambda"
  metric_name       = "Throttles"
  dimensions = {
    FunctionName = var.lambda_function_name
  }
  statistic           = "Sum"
  period              = var.alarm_period_seconds
  evaluation_periods  = var.alarm_evaluation_periods
  threshold           = var.lambda_throttle_threshold
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "dynamodb_throttled" {
  count             = var.monitoring_enabled ? 1 : 0
  alarm_name        = "${var.project_name}-dynamodb-throttled"
  alarm_description = "High DynamoDB throttled requests (orders table). Threshold: initial value, requires calibration with real AWS metrics."
  namespace         = "AWS/DynamoDB"
  metric_name       = "ThrottledRequests"
  dimensions = {
    TableName = var.dynamodb_table_name
  }
  statistic           = "Sum"
  period              = var.alarm_period_seconds
  evaluation_periods  = var.alarm_evaluation_periods
  threshold           = var.dynamodb_throttled_threshold
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}