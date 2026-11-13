# Agent Transport — result queue (Mays-Orders side).
#
# Owned by the consumer side (Orders reads it). Created only when
# `enable_agent_transport = true`.

variable "project_name" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "ris_result_producer_role_arns" {
  description = "IAM role ARNs in RIS allowed to enqueue result messages."
  type        = list(string)
  default     = []
}

variable "visibility_timeout_seconds" {
  type    = number
  default = 60
}

variable "message_retention_seconds" {
  type    = number
  default = 345600
}

variable "dlq_message_retention_seconds" {
  type    = number
  default = 1209600
}

variable "max_receive_count" {
  type    = number
  default = 3
}

resource "aws_sqs_queue" "results_dlq" {
  name                      = "${var.project_name}-agent-results-dlq"
  message_retention_seconds = var.dlq_message_retention_seconds
  sqs_managed_sse_enabled   = true
  tags                      = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_sqs_queue" "results" {
  name                       = "${var.project_name}-agent-results"
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = var.message_retention_seconds
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.results_dlq.arn
    maxReceiveCount     = var.max_receive_count
  })

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_sqs_queue_policy" "results" {
  queue_url = aws_sqs_queue.results.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowRisResultProducerSendMessage"
        Effect    = "Allow"
        Principal = { AWS = var.ris_result_producer_role_arns }
        Action    = ["sqs:SendMessage"]
        Resource  = aws_sqs_queue.results.arn
      },
    ]
  })
}

output "results_queue_url" {
  value = aws_sqs_queue.results.id
}

output "results_queue_arn" {
  value = aws_sqs_queue.results.arn
}

output "results_dlq_arn" {
  value = aws_sqs_queue.results_dlq.arn
}

# ---------------------------------------------------------------------------
# Result HMAC secret (R03). Container only: the value is set out-of-band and
# never appears in Terraform state, Git, reports, logs or tests.
# ---------------------------------------------------------------------------
resource "aws_secretsmanager_secret" "result_hmac" {
  name        = "${var.project_name}-agent-result-hmac"
  description = "HMAC key for RIS -> Orders agent result messages"
  tags        = merge({ "Project" = var.project_name }, var.tags)
}

# Read access is granted only to the explicitly supplied RIS producer roles.
# An empty list leaves the secret without any cross-role grant.
resource "aws_secretsmanager_secret_policy" "result_hmac" {
  secret_arn = aws_secretsmanager_secret.result_hmac.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowRisProducerReadSecret"
        Effect    = "Allow"
        Principal = { AWS = var.ris_result_producer_role_arns }
        Action    = ["secretsmanager:GetSecretValue"]
        Resource  = aws_secretsmanager_secret.result_hmac.arn
      },
    ]
  })
}

output "result_hmac_secret_arn" {
  value = aws_secretsmanager_secret.result_hmac.arn
}
