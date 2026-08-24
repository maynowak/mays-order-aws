variable "project_name" {
  description = "Name des Projekts; wird als Prefix fuer Ressourcen-Namen verwendet."
  type        = string
}

variable "tags" {
  description = "Zusaetzliche Tags, die den Monitoring-Ressourcen mitgegeben werden."
  type        = map(string)
  default     = {}
}

variable "monitoring_enabled" {
  description = "Erstellt CloudWatch-Dashboard, -Alarme und die Lambda-Log-Group (Retention)."
  type        = bool
  default     = true
}

variable "dashboard_enabled" {
  description = "Erstellt das CloudWatch-Uebersichts-Dashboard (Teil des Monitorings)."
  type        = bool
  default     = true
}

variable "aws_region" {
  description = "AWS-Region, in der die Infrastruktur erzeugt wird."
  type        = string
  default     = "eu-central-1"
}

variable "alarm_period_seconds" {
  description = "Auswertungsperiode der Alarme in Sekunden (300 = 5 Minuten)."
  type        = number
  default     = 300
}

variable "alarm_evaluation_periods" {
  description = "Anzahl aufeinanderfolgender Perioden, bis ein Alarm ausloest."
  type        = number
  default     = 1
}

variable "api_5xx_threshold" {
  description = "API-5XX-Schwellwert (Summe / Auswertungsperiode). Initial threshold / starting value — requires calibration with real AWS metrics."
  type        = number
  default     = 5
}

variable "api_4xx_threshold" {
  description = "API-4XX-Schwellwert (Summe / Auswertungsperiode). Initial threshold / starting value — requires calibration with real AWS metrics."
  type        = number
  default     = 20
}

variable "lambda_error_threshold" {
  description = "Lambda-Errors-Schwellwert (Summe / Auswertungsperiode). Initial threshold / starting value — requires calibration with real AWS metrics."
  type        = number
  default     = 1
}

variable "lambda_duration_threshold_ms" {
  description = "Lambda-Duration-Schwellwert in Millisekunden (Average / Auswertungsperiode; Lambda-Timeout = 10000 ms). Initial threshold / starting value — requires calibration with real AWS metrics."
  type        = number
  default     = 8000
}

variable "lambda_throttle_threshold" {
  description = "Lambda-Throttles-Schwellwert (Summe / Auswertungsperiode). Initial threshold / starting value — requires calibration with real AWS metrics."
  type        = number
  default     = 1
}

variable "dynamodb_throttled_threshold" {
  description = "DynamoDB-ThrottledRequests-Schwellwert (Summe / Auswertungsperiode). Initial threshold / starting value — requires calibration with real AWS metrics."
  type        = number
  default     = 1
}

# Dependencies from other modules
variable "lambda_function_name" {
  description = "Name der Lambda-Funktion (fuer Lambda-Metriken)."
  type        = string
}

variable "api_id" {
  description = "ID der HTTP API (fuer API-Gateway-Metriken)."
  type        = string
}

variable "api_stage_name" {
  description = "Name der API Stage (fuer API-Gateway-Metriken)."
  type        = string
}

variable "dynamodb_table_name" {
  description = "Name der DynamoDB-Tabelle (fuer DynamoDB-Metriken)."
  type        = string
}