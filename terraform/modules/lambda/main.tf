# T011-04 — Lambda: Order Handler (Zip-Build, Python 3.14)
# Fachquelle: ADR-001 (Serverless), api/endpoints.md, database/access-patterns.md (AP1..AP4)
# Execution Role: module.iam.role_arn. Zip-Build reproduzierbar via lambda/ (python3 build_zip.py).
# Migration: nodejs22.x → python3.14 (feature/lambda-python-314). Handler "index.handler" gilt für Python (index.py am ZIP-Root).
# API-GW→Lambda Invoke-Permission folgt in T011-06 (HTTP API + Routen + Authorizer).

resource "aws_lambda_function" "handler" {
  function_name    = "${var.project_name}-handler"
  role             = var.iam_role_arn
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

# T011-11 — Lambda Log Group with Retention
# Lambda erzeugt die Log-Group automatisch, aber ohne Retention ("Never expire").
# Die explizite Terraform-Log-Group ist KEINE Duplizierung, sondern die IaC-
# Steuerung der Retention (7 Tage, kostenbewusst): die Lambda nutzt sie mit.
resource "aws_cloudwatch_log_group" "handler" {
  count             = var.monitoring_enabled ? 1 : 0
  name              = "/aws/lambda/${aws_lambda_function.handler.function_name}"
  retention_in_days = var.log_retention_days
  tags              = merge({ "Project" = var.project_name }, var.tags)
}