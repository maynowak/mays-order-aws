variable "project_name" {
  description = "Name des Projekts; wird als Prefix fuer Ressourcen-Namen verwendet."
  type        = string
  default     = "mays-orders"

  # Naming-Safety (T013): ein vorhersagbarer, kompatibel nutzbarer Installationsname.
  # Kleinschreibung + Bindestrich ist über alle verwendeten Ressourcen hinweg gültig
  # (DynamoDB-Tabelle == project_name → min. 3 Zeichen; S3-Bucket ist kleinschreibungs-
  # pflichtig). Kein leading/trailing Bindestrich. Siehe terraform/README.md §9.
  validation {
    condition     = length(var.project_name) >= 3 && can(regex("^[a-z0-9][a-z0-9-]*$", var.project_name))
    error_message = "project_name muss mind. 3 Zeichen lang sein und darf nur Kleinbuchstaben, Ziffern und Bindestriche enthalten (kein fuehrender/trailender Bindestrich)."
  }
}

variable "aws_region" {
  description = "AWS-Region, in der die Infrastruktur erzeugt wird."
  type        = string
  default     = "eu-central-1"
}

variable "tags" {
  description = "Zusaetzliche Tags, die allen Ressourcen mitgegeben werden."
  type        = map(string)
  default     = {}
}

# DynamoDB-Beispiel-Daten-Seed (opt-in, standardmäßig DEAKTIVIERT):
# nur mit bewusstem `terraform apply -var="seed_example_data=true"` werden die
# 50 Demo-Orders (database/seed/orders_seed_demo_50.json) in die Tabelle geladen.
# Siehe docs/reports/DYNAMODB-SEED-DEMO-50.md.
variable "seed_example_data" {
  description = "Importiert die bereitgestellten Beispiel-Orders in DynamoDB."
  type        = bool
  default     = false
}

variable "seed_file_path" {
  description = "Pfad zur Demo-Seed-Datei (JSON) relativ zum Repo-Root."
  type        = string
  default     = "database/seed/orders_seed_demo_50.json"
}

# T011-11 — CloudWatch Monitoring (Dashboard, Alarme, Logs)
# Fachquelle: monitoring/monitoring-design.md, cost/cost-analysis.md §2 CloudWatch.
# monitoring_enabled=false erzeugt KEINE Monitoring-Ressourcen (kostenbewusst);
# Standard ist aktiv, aber ohne unnötige Zusatzressourcen (kein SNS-Topic, keine
# Custom Metrics — siehe docs/reports/T011-11-CLOUDWATCH-MONITORING.md).
variable "monitoring_enabled" {
  description = "Erstellt CloudWatch-Dashboard, -Alarme und die Lambda-Log-Group (Retention)."
  type        = bool
  default     = true
}

variable "dashboard_enabled" {
  description = "Erstellt das CloudWatch-Übersichts-Dashboard (Teil des Monitorings)."
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "CloudWatch-Log-Retention der Lambda-Log-Group in Tagen (kostenbewusst, monitoring-design.md §3)."
  type        = number
  default     = 7
}

variable "alarm_period_seconds" {
  description = "Auswertungsperiode der Alarme in Sekunden (300 = 5 Minuten)."
  type        = number
  default     = 300
}

variable "alarm_evaluation_periods" {
  description = "Anzahl aufeinanderfolgender Perioden, bis ein Alarm auslöst."
  type        = number
  default     = 1
}

# Schwellwerte — "Initial threshold / starting value — requires calibration with
# real AWS metrics." Keine Produktionswerte behaupten (T011-11-Auftrag §8).
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