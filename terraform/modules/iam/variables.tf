variable "project_name" {
  description = "Name des Projekts; wird als Prefix fuer Ressourcen-Namen verwendet."
  type        = string
}

variable "tags" {
  description = "Zusaetzliche Tags, die den IAM-Ressourcen mitgegeben werden."
  type        = map(string)
  default     = {}
}

variable "dynamodb_table_arn" {
  description = "ARN der DynamoDB-Tabelle fuer DynamoDB-Berechtigungen in der IAM-Policy."
  type        = string
}

variable "dynamodb_gsi1_arn" {
  description = "ARN des GSI1-Index fuer DynamoDB-Berechtigungen in der IAM-Policy."
  type        = string
}

variable "dynamodb_gsi2_arn" {
  description = "ARN des GSI2-Index fuer DynamoDB-Berechtigungen in der IAM-Policy."
  type        = string
}

variable "sqs_queue_arn" {
  description = "ARN der SQS Queue fuer SQS-Berechtigungen in der IAM-Policy."
  type        = string
  default     = ""
}

variable "sqs_enabled" {
  description = <<-EOT
    Plan-bekanntes Gate fuer die SQS-IAM-Berechtigung (GAP-06).
    true  = Handler-Policy mit sqs:SendMessage auf sqs_queue_arn wird erzeugt;
            ein leerer sqs_queue_arn ist dann ein harter Fehler (Precondition).
    false = keine SQS-bezogenen IAM-Ressourcen (Standard, z. B. synchroner Betrieb).
    Der Wert muss vor der Queue-Erstellung bekannt sein; er darf NICHT vom
    berechneten Queue-ARN abgeleitet werden.
  EOT
  type        = bool
  default     = false
}
