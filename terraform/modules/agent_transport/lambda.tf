# L07 / W02 — Result consumer Lambda (module gate keeps it default-off).
# Handler: result_consumer.handler (same bundle as the HTTP handler).

variable "lambda_zip_path" {
  description = "Path to the May's Orders Lambda bundle."
  type        = string
  default     = ""
}

variable "lambda_runtime" {
  type    = string
  default = "python3.14"
}

variable "orders_table_name" {
  type = string
}

variable "orders_table_arn" {
  type = string
}

variable "result_batch_size" {
  type    = number
  default = 10
}

variable "result_batch_window_seconds" {
  type    = number
  default = 0
}

variable "result_secret_kms_key_arn" {
  description = "Optional customer-managed KMS key for the result secret."
  type        = string
  default     = ""
}

locals {
  consumer_name = "${var.project_name}-agent-result-consumer"
}

resource "aws_cloudwatch_log_group" "result_consumer" {
  name              = "/aws/lambda/${local.consumer_name}"
  retention_in_days = 14
  tags              = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_iam_role" "result_consumer" {
  name = local.consumer_name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_iam_role_policy" "result_consumer" {
  name = "${local.consumer_name}-policy"
  role = aws_iam_role.result_consumer.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "Logs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.result_consumer.arn}:*"
      },
      {
        Sid      = "OrdersTable"
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:UpdateItem"]
        Resource = var.orders_table_arn
      },
      {
        Sid      = "ReadResultSecret"
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.result_hmac.arn
      },
      {
        Sid    = "ConsumeResultQueue"
        Effect = "Allow"
        Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage",
        "sqs:GetQueueAttributes"]
        Resource = aws_sqs_queue.results.arn
      },
    ]
  })
}

# Only created when a customer-managed KMS key is actually configured.
resource "aws_iam_role_policy" "result_consumer_kms" {
  count = var.result_secret_kms_key_arn != "" ? 1 : 0

  name = "${local.consumer_name}-kms-policy"
  role = aws_iam_role.result_consumer.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "DecryptResultSecret"
      Effect   = "Allow"
      Action   = ["kms:Decrypt"]
      Resource = var.result_secret_kms_key_arn
    }]
  })
}

resource "aws_lambda_function" "result_consumer" {
  function_name = local.consumer_name
  role          = aws_iam_role.result_consumer.arn
  handler       = "result_consumer.handler"
  runtime       = var.lambda_runtime
  filename      = var.lambda_zip_path

  source_code_hash = (
    var.lambda_zip_path != "" ? filebase64sha256(var.lambda_zip_path) : null
  )

  timeout     = 30
  memory_size = 256

  environment {
    variables = {
      ORDERS_TABLE            = var.orders_table_name
      ORDER_RESULT_SECRET_ARN = aws_secretsmanager_secret.result_hmac.arn
    }
  }

  depends_on = [aws_cloudwatch_log_group.result_consumer]
  tags       = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_lambda_event_source_mapping" "results" {
  event_source_arn                   = aws_sqs_queue.results.arn
  function_name                      = aws_lambda_function.result_consumer.arn
  batch_size                         = var.result_batch_size
  maximum_batching_window_in_seconds = var.result_batch_window_seconds
  function_response_types            = ["ReportBatchItemFailures"]
  enabled                            = true
}

output "result_consumer_function_name" {
  value = aws_lambda_function.result_consumer.function_name
}
