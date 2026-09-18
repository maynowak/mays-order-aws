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

variable "sqs_queue_arn" {
  description = "ARN der SQS Queue fuer SQS-Berechtigungen in der IAM-Policy."
  type        = string
  default     = ""
}