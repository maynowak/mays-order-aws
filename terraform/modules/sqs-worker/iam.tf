data "aws_iam_policy_document" "worker_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "worker_policy" {
  statement {
    sid    = "DynamoDBRead"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:UpdateItem",
    ]
    resources = [var.dynamodb_table_arn]
  }

  statement {
    sid    = "SQS"
    effect = "Allow"
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
    ]
    resources = [var.sqs_queue_arn]
  }

  statement {
    sid    = "Logs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["*"]
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

resource "aws_iam_role" "worker" {
  name                 = "${var.project_name}-sqs-worker-role"
  assume_role_policy   = data.aws_iam_policy_document.worker_trust.json
  permissions_boundary = var.lambda_execution_boundary

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_iam_role_policy" "worker" {
  name   = "${var.project_name}-sqs-worker-policy"
  role   = aws_iam_role.worker.name
  policy = data.aws_iam_policy_document.worker_policy.json
}

output "role_arn" {
  value = aws_iam_role.worker.arn
}