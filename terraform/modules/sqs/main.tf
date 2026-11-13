# SQS-Queue + Dead-Letter-Queue (MO-RC4-P02C)
# Fachquelle: reliability/consistency-and-failure-handling.md, ADR-006
#
# Fehlgeschlagene Nachrichten duerfen nicht stillschweigend verschwinden:
# - Hauptqueue mit Redrive-Policy auf eine DLQ (maxReceiveCount konfigurierbar)
# - Retention fuer Hauptqueue und DLQ getrennt konfigurierbar (Default: DLQ deutlich laenger)
# - Visibility Timeout >= 6x Lambda-Timeout (AWS-Empfehlung fuer SQS-Event-Source-Mappings)
#
# Bewusst NICHT gesetzt: Resource-Policy mit Wildcard-Principal (F-03). Zugriff
# ausschliesslich ueber IAM-Identitaets-Policies (Least Privilege).

variable "project_name" {
  description = "Name des Projekts"
  type        = string
}

variable "tags" {
  description = "Tags für Ressourcen"
  type        = map(string)
  default     = {}
}

variable "queue_name" {
  description = "Name der SQS Queue"
  type        = string
  default     = null
}

variable "visibility_timeout_seconds" {
  description = <<-EOT
    Visibility Timeout der Hauptqueue. Muss zur Worker-Lambda passen: AWS empfiehlt
    mindestens das 6-fache des Lambda-Timeouts (Worker-Timeout 10 s => 60 s).
    Zu kurz => Nachrichten werden waehrend der Verarbeitung erneut zugestellt.
  EOT
  type        = number
  default     = 60

  validation {
    condition     = var.visibility_timeout_seconds >= 0 && var.visibility_timeout_seconds <= 43200
    error_message = "visibility_timeout_seconds muss zwischen 0 und 43200 liegen."
  }
}

variable "message_retention_seconds" {
  description = <<-EOT
    Aufbewahrung der Hauptqueue in Sekunden (Default 4 Tage, AWS-Maximum 14 Tage).
    Vorher 120 s: Nachrichten verschwanden nach zwei Minuten unbemerkt.
  EOT
  type        = number
  default     = 345600

  validation {
    condition     = var.message_retention_seconds >= 60 && var.message_retention_seconds <= 1209600
    error_message = "message_retention_seconds muss zwischen 60 und 1209600 liegen."
  }
}

variable "dlq_message_retention_seconds" {
  description = <<-EOT
    Aufbewahrung der Dead-Letter-Queue (Default 14 Tage = AWS-Maximum), damit
    fehlgeschlagene Auftraege untersucht und kontrolliert erneut verarbeitet werden koennen.
  EOT
  type        = number
  default     = 1209600

  validation {
    condition     = var.dlq_message_retention_seconds >= 60 && var.dlq_message_retention_seconds <= 1209600
    error_message = "dlq_message_retention_seconds muss zwischen 60 und 1209600 liegen."
  }
}

variable "max_receive_count" {
  description = <<-EOT
    Anzahl Zustellversuche, nach denen eine Nachricht in die DLQ wandert.
    Default 1: Nach dem ersten fehlgeschlagenen Verarbeitungsversuch wird die
    Nachricht beim naechsten Empfangsversuch in die DLQ ueberfuehrt.
    (Keine Exactly-once-Garantie; SQS ist at-least-once.)
  EOT
  type        = number
  default     = 1

  validation {
    condition     = var.max_receive_count >= 1 && var.max_receive_count <= 1000
    error_message = "max_receive_count muss zwischen 1 und 1000 liegen."
  }
}

variable "dlq_name" {
  description = "Name der Dead-Letter-Queue (Default: <queue_name>-dlq)"
  type        = string
  default     = null
}

locals {
  main_queue_name = var.queue_name != null ? var.queue_name : "${var.project_name}-orders-queue"
  dlq_name        = var.dlq_name != null ? var.dlq_name : "${local.main_queue_name}-dlq"
}

resource "aws_sqs_queue" "dlq" {
  name                      = local.dlq_name
  message_retention_seconds = var.dlq_message_retention_seconds

  tags = merge({ "Project" = var.project_name, "Purpose" = "dead-letter" }, var.tags)
}

resource "aws_sqs_queue" "orders" {
  name                       = local.main_queue_name
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = var.message_retention_seconds

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.max_receive_count
  })

  tags = merge({ "Project" = var.project_name }, var.tags)
}

# Resource Policy bewusst nicht gesetzt
# Zugriff wird ausschließlich über IAM-Identitäts-Policies gesteuert.
# Dadurch wird ein Wildcard-Principal vermieden und Least Privilege eingehalten.


output "queue_url" {
  description = "URL of the SQS queue"
  value       = aws_sqs_queue.orders.id
}

output "queue_arn" {
  description = "ARN of the SQS queue"
  value       = aws_sqs_queue.orders.arn
}

output "queue_name" {
  description = "Name of the SQS queue"
  value       = aws_sqs_queue.orders.name
}

output "dlq_url" {
  description = "URL of the dead-letter queue"
  value       = aws_sqs_queue.dlq.id
}

output "dlq_arn" {
  description = "ARN of the dead-letter queue"
  value       = aws_sqs_queue.dlq.arn
}

output "dlq_name" {
  description = "Name of the dead-letter queue"
  value       = aws_sqs_queue.dlq.name
}
