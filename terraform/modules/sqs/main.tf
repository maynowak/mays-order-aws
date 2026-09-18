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

resource "aws_sqs_queue" "orders" {
  name                       = var.queue_name != null ? var.queue_name : "${var.project_name}-orders-queue"
  visibility_timeout_seconds = 30
  message_retention_seconds  = 120

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_sqs_queue_policy" "orders" {
  queue_url = aws_sqs_queue.orders.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowAccessFromAccount"
        Effect    = "Allow"
        Principal = "*"
        Action    = ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource  = aws_sqs_queue.orders.arn
      }
    ]
  })
}

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