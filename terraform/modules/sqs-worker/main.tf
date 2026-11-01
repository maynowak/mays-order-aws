resource "aws_lambda_function" "worker" {
  function_name    = "${var.project_name}-sqs-worker"
  role             = aws_iam_role.worker.arn
  handler          = var.handler
  runtime          = var.runtime
  timeout          = var.timeout
  filename         = var.filename
  source_code_hash = filebase64sha256(var.filename)

  environment {
    variables = {
      ORDERS_TABLE = var.dynamodb_table_name
    }
  }

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_cloudwatch_log_group" "worker" {
  count             = var.monitoring_enabled ? 1 : 0
  name              = "/aws/lambda/${aws_lambda_function.worker.function_name}"
  retention_in_days = var.log_retention_days
  tags              = merge({ "Project" = var.project_name }, var.tags)

}

resource "aws_lambda_event_source_mapping" "sqs_worker" {
  event_source_arn = var.sqs_queue_arn
  function_name    = aws_lambda_function.worker.arn
  batch_size       = 5
  enabled          = true

  # MO-RC4-P02C: Der Handler meldet fehlgeschlagene Nachrichten einzeln
  # (batchItemFailures), damit erfolgreiche Nachrichten eines Batches nicht
  # erneut zugestellt werden. Fehlgeschlagene Nachrichten werden bis
  # maxReceiveCount erneut zugestellt und danach in die DLQ ueberfuehrt.
  function_response_types = ["ReportBatchItemFailures"]
}

output "function_name" {
  value = aws_lambda_function.worker.function_name
}

output "function_arn" {
  value = aws_lambda_function.worker.arn
}

output "log_group_name" {
  value = var.monitoring_enabled ? aws_cloudwatch_log_group.worker[0].name : ""
}