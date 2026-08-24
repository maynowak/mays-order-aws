# T011-03 — IAM: Lambda Execution Role (Least Privilege)
# Fachquelle: security/iam-design.md §2.1
# Kein dynamodb:Scan/DeleteItem/BatchWriteItem/CreateTable; keine s3/sqs/iam-Aktionen.

data "aws_iam_policy_document" "handler_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "handler" {
  statement {
    sid    = "DynamoDBOrders"
    effect = "Allow"
    actions = [
      "dynamodb:PutItem",
      "dynamodb:GetItem",
      "dynamodb:UpdateItem",
      "dynamodb:Query",
    ]
    resources = [
      var.dynamodb_table_arn,
      var.dynamodb_gsi1_arn,
    ]
  }

  statement {
    sid    = "Logs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["*"] # Log-Gruppen/-Streams entstehen erst zur Laufzeit (security/iam-design.md §2.1)
  }
}

resource "aws_iam_role" "handler" {
  name               = "${var.project_name}-handler-role"
  assume_role_policy = data.aws_iam_policy_document.handler_trust.json

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_iam_role_policy" "handler" {
  name   = "${var.project_name}-handler-policy"
  role   = aws_iam_role.handler.name
  policy = data.aws_iam_policy_document.handler.json
}