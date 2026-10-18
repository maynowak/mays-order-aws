# T011-03 — IAM: Lambda Execution Role (Least Privilege)
# Fachquelle: security/iam-design.md §2.1
# Bewusst NICHT erlaubt: dynamodb:Scan/BatchWriteItem/CreateTable, s3:*, iam:*.
# DeleteItem: beabsichtigt (Erasure-Funktion, MAYS-ORDERS-DSGVO-PRIVACY-ERASURE-01).
# SQS:SendMessage ist OPTIONAL und entsteht nur mit angebundener Queue
# (MAYS-ORDERS-MODULARIZATION-01-PHASE2): ohne var.sqs_queue_arn wird KEINE
# sqs-Berechtigung erzeugt (count-gated), siehe aws_iam_role_policy.sqs unten.

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

# Basis-Policy des Order-Handlers: DynamoDB (Table + GSI1/GSI2) und Logs.
# Das SQS-Statement ist bewusst NICHT Teil dieser Policy — es wird separat
# und nur bei angebundener Queue erzeugt (Least Privilege, s. o.).
data "aws_iam_policy_document" "handler" {
  statement {
    sid    = "DynamoDBTable"
    effect = "Allow"
    actions = [
      "dynamodb:PutItem",
      "dynamodb:GetItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
    ]
    resources = [
      var.dynamodb_table_arn,
    ]
  }

  statement {
    sid    = "DynamoDBGSI"
    effect = "Allow"
    actions = [
      "dynamodb:Query",
    ]
    resources = [
      var.dynamodb_gsi1_arn,
      var.dynamodb_gsi2_arn,
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

# Optionale SQS-Berechtigung (MAYS-ORDERS-MODULARIZATION-01-PHASE2):
# Nur wenn var.sqs_queue_arn gesetzt ist, entsteht eine eigene Inline-Policy
# mit sqs:SendMessage auf genau diese Queue. Ohne Queue-ARN wird KEINE
# sqs-Berechtigung erzeugt (count = 0) — der Handler läuft dann synchron
# (index.py skippt den Enqueue gracefull, siehe lambda/src/index.py).
data "aws_iam_policy_document" "sqs" {
  count = var.sqs_queue_arn != "" ? 1 : 0

  statement {
    sid    = "SQS"
    effect = "Allow"
    actions = [
      "sqs:SendMessage",
    ]
    resources = [var.sqs_queue_arn]
  }
}

resource "aws_iam_role_policy" "sqs" {
  count  = var.sqs_queue_arn != "" ? 1 : 0
  name   = "${var.project_name}-handler-sqs-policy"
  role   = aws_iam_role.handler.name
  policy = data.aws_iam_policy_document.sqs[0].json
}