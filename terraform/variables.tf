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

# MO-P0B: dokumentierte Zielversion der Bereitstellung. Wird als
# Terraform-Output `mo_version` im Remote-State abgelegt (State-Output, kein
# unabhaengiger Nachweis des laufenden Lambda-Codes).
variable "deployment_version" {
  description = "Semantische Version dieser Bereitstellung (major.minor.patch); wird als Output mo_version dokumentiert."
  type        = string
  default     = "0.1.0"

  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+$", var.deployment_version))
    error_message = "deployment_version muss dem Format major.minor.patch entsprechen (z. B. 0.1.0)."
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

variable "notification_email" {
  description = "Optional email address for Cognito backup SNS notifications. If not set, no SNS subscription is created."
  type        = string
  default     = "nowakbewerbung@gmail.com"
}

# Cognito-Backup-Module sind opt-in deaktivierbar (Standard: aktiviert).
# Bestehende Installationen bleiben unverändert ( moved-Blöcke in main.tf
# erhalten den State beim Wechsel auf count-basierte Module).
variable "enable_cognito_backup" {
  description = "Erstellt den Cognito-Backup-S3-Bucket. false deaktiviert das Backup-Modul (z. B. isolierte Testprojekte)."
  type        = bool
  default     = true
}

variable "enable_cognito_backup_automation" {
  description = "Erstellt die Cognito-Backup-Automatisierung (Lambda, Scheduler, SNS). Nur wirksam wenn enable_cognito_backup = true."
  type        = bool
  default     = true
}

variable "lambda_execution_boundary" {
  description = "Optional IAM permissions boundary ARN for the SQS worker Lambda role. If null, no permissions boundary is set."
  type        = string
  default     = null

  validation {
    condition     = var.lambda_execution_boundary == null || can(regex("^arn:aws:iam::[0-9]{12}:policy/", var.lambda_execution_boundary))
    error_message = "lambda_execution_boundary must be null or a valid IAM policy ARN (arn:aws:iam::<12-digit-account-id>:policy/<name>)."
  }
}
# MO-RC4-P02C: SQS-Zuverlaessigkeit. Fehlgeschlagene Auftraege landen in einer DLQ
# statt stillschweigend zu verschwinden; Ablaufzeiten sind konfigurierbar.
variable "sqs_message_retention_seconds" {
  description = "Aufbewahrung der Order-Queue in Sekunden (60..1209600). Default 4 Tage."
  type        = number
  default     = 345600
}

variable "sqs_dlq_message_retention_seconds" {
  description = "Aufbewahrung der Dead-Letter-Queue in Sekunden (60..1209600). Default 14 Tage."
  type        = number
  default     = 1209600
}

variable "sqs_visibility_timeout_seconds" {
  description = "Visibility Timeout der Order-Queue in Sekunden (0..43200). Sollte >= 6x Worker-Lambda-Timeout sein (Default 60 s bei 10 s Timeout)."
  type        = number
  default     = 60
}

variable "sqs_max_receive_count" {
  description = "Zustellversuche bis zur DLQ (1..1000). Default 1: erster Fehlversuch fuehrt beim naechsten Empfang in die DLQ."
  type        = number
  default     = 1
}

# MO-RC4-P02F: PENDING-Recovery (opt-in). Der Scheduler ruft den bestehenden
# Order-Handler regelmaessig auf; ohne Aktivierung entstehen keine Ressourcen.
variable "recovery_enabled" {
  description = "Aktiviert den Recovery-Scheduler (EventBridge Scheduler -> bestehender Handler). Default false."
  type        = bool
  default     = false
}

variable "recovery_schedule_expression" {
  description = "Schedule-Ausdruck fuer den Recovery-Lauf (Default: rate(5 minutes))."
  type        = string
  default     = "rate(5 minutes)"
}

variable "recovery_window_minutes" {
  description = "Recovery-Zeitfenster in Minuten (GSI1-Range-Query). Muss groesser als das Schedule-Intervall sein."
  type        = number
  default     = 60
}

variable "recovery_min_age_seconds" {
  description = "Mindestalter einer PENDING-Order, bevor Recovery sie erneut zustellt."
  type        = number
  default     = 60
}

variable "recovery_limit" {
  description = "Maximale Kandidaten pro Recovery-Lauf (Schutz vor Massenlauf)."
  type        = number
  default     = 50
}

variable "recovery_lease_seconds" {
  description = "Lease-Dauer fuer den Recovery-Claim (Schutz vor parallelen Laeufen)."
  type        = number
  default     = 300
}

# MO-RC4-P02I-B2: automatische Processing-Recovery (abgelaufene Claims).
# Standardmaessig AUS; unabhaengig von recovery_enabled (P02F).
variable "processing_recovery_enabled" {
  description = "Aktiviert die automatische Processing-Recovery (abgelaufene Processing-Claims). Default false."
  type        = bool
  default     = false
}

variable "processing_recovery_schedule_expression" {
  description = "Schedule-Ausdruck der Processing-Recovery (Default: rate(5 minutes))."
  type        = string
  default     = "rate(5 minutes)"
}

variable "processing_recovery_limit" {
  description = "Maximale Kandidaten pro Processing-Recovery-Lauf."
  type        = number
  default     = 20
}

variable "processing_recovery_safety_margin_seconds" {
  description = "Sicherheitsabstand zur Processing-Lease (Default 60 s)."
  type        = number
  default     = 60
}
