# T011-11 — Monitoring-Outputs
output "dashboard_name" {
  description = "Name des CloudWatch-Dashboards (falls aktiviert)."
  value       = var.dashboard_enabled && var.monitoring_enabled ? aws_cloudwatch_dashboard.orders_overview[0].dashboard_name : null
}

output "dashboard_arn" {
  description = "ARN des CloudWatch-Dashboards (falls aktiviert)."
  value       = var.dashboard_enabled && var.monitoring_enabled ? aws_cloudwatch_dashboard.orders_overview[0].dashboard_arn : null
}

output "alarm_api_5xx_arn" {
  description = "ARN des API 5XX Alarms (falls aktiviert)."
  value       = var.monitoring_enabled ? aws_cloudwatch_metric_alarm.api_5xx[0].arn : null
}

output "alarm_api_4xx_arn" {
  description = "ARN des API 4XX Alarms (falls aktiviert)."
  value       = var.monitoring_enabled ? aws_cloudwatch_metric_alarm.api_4xx[0].arn : null
}

output "alarm_lambda_errors_arn" {
  description = "ARN des Lambda Errors Alarms (falls aktiviert)."
  value       = var.monitoring_enabled ? aws_cloudwatch_metric_alarm.lambda_errors[0].arn : null
}

output "alarm_lambda_duration_arn" {
  description = "ARN des Lambda Duration Alarms (falls aktiviert)."
  value       = var.monitoring_enabled ? aws_cloudwatch_metric_alarm.lambda_duration[0].arn : null
}

output "alarm_lambda_throttles_arn" {
  description = "ARN des Lambda Throttles Alarms (falls aktiviert)."
  value       = var.monitoring_enabled ? aws_cloudwatch_metric_alarm.lambda_throttles[0].arn : null
}

output "alarm_dynamodb_throttled_arn" {
  description = "ARN des DynamoDB Throttled Alarms (falls aktiviert)."
  value       = var.monitoring_enabled ? aws_cloudwatch_metric_alarm.dynamodb_throttled[0].arn : null
}