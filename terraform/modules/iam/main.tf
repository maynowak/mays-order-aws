# T011-03 — IAM: Lambda Execution Role (Least Privilege)
# Fachquelle: security/iam-design.md §2.1
# Bewusst NICHT erlaubt: dynamodb:Scan/BatchWriteItem/CreateTable, s3:*, iam:*.
# DeleteItem: beabsichtigt (Erasure-Funktion, MAYS-ORDERS-DSGVO-PRIVACY-ERASURE-01).
# SQS:SendMessage ist OPTIONAL und entsteht nur bei aktivem Gate
# (MAYS-ORDERS-MODULARIZATION-01-PHASE2, GAP-06-FIX): ohne
# var.sqs_enabled = true wird KEINE sqs-Berechtigung erzeugt (count-gated),
# siehe aws_iam_role_policy.sqs unten. Das Gate ist plan-bekannt; der
# Queue-ARN bleibt Policy-Resource.

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

# Optionale SQS-Berechtigung (MAYS-ORDERS-MODULARIZATION-01-PHASE2,
# GAP-06-FIX): Das Gate ist der plan-bekannte boolesche Vertrag
# var.sqs_enabled. Die Ressourcenanzahl hängt AUSSCHLIESSLICH davon ab —
# nicht vom Inhalt oder der Plan-Bekanntheit des berechneten Queue-ARNs
# (der ARN ist beim Fresh-Plan der Queue noch unbekannt). Der ARN bleibt
# Resource der Policy (keine Wildcard). Ohne Gate entsteht KEINE
# sqs-Berechtigung (count = 0) — der Handler läuft dann synchron
# (index.py skippt den Enqueue gracefull, siehe lambda/src/index.py).
#
# Vertragsprüfung (Precondition, ab Terraform 1.2 / deklariert >= 1.5.0):
#   - Gate an + bekannter leerer/Whitespace-ARN → harter Fehler (Plan/Apply).
#   - Gate aus + leerer ARN → keine Instanz, keine Prüfung, keine Ressource.
#   - Gate an + unbekannter ARN (Queue entsteht im selben Plan) → Prüfung
#     wird auf apply vertagt; der count bleibt plan-bekannt.
# Bewusst KEIN check-Block (nur Warnung) und keine variable-validation mit
# Fremdvariablen-Referenz (erst ab Terraform 1.9).
data "aws_iam_policy_document" "sqs" {
  count = var.sqs_enabled ? 1 : 0

  statement {
    sid    = "SQS"
    effect = "Allow"
    actions = [
      "sqs:SendMessage",
    ]
    resources = [var.sqs_queue_arn]
  }

  lifecycle {
    precondition {
      condition     = trimspace(var.sqs_queue_arn) != ""
      error_message = "sqs_enabled = true erfordert einen nicht leeren sqs_queue_arn. Ohne angebundene Queue muss sqs_enabled = false gesetzt sein (dann entsteht keine SQS-IAM-Ressource)."
    }
  }
}

resource "aws_iam_role_policy" "sqs" {
  count  = var.sqs_enabled ? 1 : 0
  name   = "${var.project_name}-handler-sqs-policy"
  role   = aws_iam_role.handler.name
  policy = data.aws_iam_policy_document.sqs[0].json
}
