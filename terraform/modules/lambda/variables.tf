variable "project_name" {
  description = "Name des Projekts; wird als Prefix fuer Ressourcen-Namen verwendet."
  type        = string
}

variable "tags" {
  description = "Zusaetzliche Tags, die den Lambda-Ressourcen mitgegeben werden."
  type        = map(string)
  default     = {}
}

variable "iam_role_arn" {
  description = "ARN der IAM-Rolle fuer die Lambda-Funktion."
  type        = string
}

variable "dynamodb_table_name" {
  description = "Name der DynamoDB-Tabelle (wird als Environment Variable ORDERS_TABLE gesetzt)."
  type        = string
}

variable "handler" {
  description = "Lambda Handler Funktion."
  type        = string
  default     = "index.handler"
}

variable "runtime" {
  description = "Lambda Runtime."
  type        = string
  default     = "python3.11"
}

variable "timeout" {
  description = "Lambda Timeout in Sekunden."
  type        = number
  default     = 10
}

variable "filename" {
  description = "Pfad zum Lambda ZIP-Paket (relativ zum Repo-Root)."
  type        = string
}

variable "monitoring_enabled" {
  description = "Ob die Lambda-Log-Group mit Retention erstellt werden soll."
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "CloudWatch-Log-Retention der Lambda-Log-Group in Tagen."
  type        = number
  default     = 7
}

variable "queue_url" {
  description = "SQS queue URL for producer to send messages"
  type        = string
  default     = ""
}

variable "privacy_secret_enabled" {
  description = "Adds non-secret AWS_MANAGED provider/reference environment variables. Default false."
  type        = bool
  default     = false
}

variable "privacy_secret_id" {
  description = "Exact Secret ARN/name reference; required when privacy_secret_enabled=true."
  type        = string
  default     = ""
}

variable "privacy_kms_key_arn" {
  description = "Optional exact customer-managed KMS key ARN reference; never a secret value."
  type        = string
  default     = ""
}