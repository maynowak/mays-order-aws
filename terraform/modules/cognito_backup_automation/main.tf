locals {
  name = "${var.project_name}-cognito-backup"
}

data "aws_iam_policy_document" "assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "backup_lambda" {
  name               = "${local.name}-role"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
  tags               = var.tags
}

data "aws_iam_policy_document" "backup_policy" {
  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = ["arn:aws:logs:${var.aws_region}:*:log-group:/aws/lambda/*"]
  }

  statement {
    effect = "Allow"
    actions = [
      "cognito-idp:ListUsers",
      "cognito-idp:ListGroups",
      "cognito-idp:AdminListGroupsForUser"
    ]
    resources = ["*"]
  }

  statement {
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:GetObject",
      "s3:ListBucket"
    ]
    resources = [
      "arn:aws:s3:::${var.bucket_name}",
      "arn:aws:s3:::${var.bucket_name}/*"
    ]
  }
}

resource "aws_iam_policy" "backup_policy" {
  name   = "${local.name}-policy"
  policy = data.aws_iam_policy_document.backup_policy.json
}

resource "aws_iam_role_policy_attachment" "backup_attach" {
  role       = aws_iam_role.backup_lambda.name
  policy_arn = aws_iam_policy.backup_policy.arn
}

resource "aws_lambda_function" "backup" {
  function_name = "${local.name}-lambda"
  role          = aws_iam_role.backup_lambda.arn
  handler       = "cognito_backup_handler.handler"
  runtime       = "python3.11"
  filename      = "${path.root}/../lambda/dist/cognito_backup.zip"
  source_code_hash = filebase64sha256("${path.root}/../lambda/dist/cognito_backup.zip")
  timeout       = 300

  environment {
    variables = {
      PROJECT_NAME    = var.project_name
      ENVIRONMENT     = var.environment
      AWS_ACCOUNT_ID  = data.aws_caller_identity.current.account_id
      MY_AWS_REGION   = var.aws_region
      USER_POOL_ID    = var.user_pool_id
      USER_POOL_NAME  = var.user_pool_name
      BUCKET_NAME     = var.bucket_name
    }
  }

  tags = var.tags
}

data "aws_caller_identity" "current" {}

resource "aws_scheduler_schedule" "backup_schedule" {
  name       = "${local.name}-schedule"
  schedule_expression = var.backup_schedule
  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.backup.arn
    role_arn = aws_iam_role.scheduler_role.arn
  }
}

data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler_role" {
  name               = "${local.name}-scheduler-role"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

data "aws_iam_policy_document" "scheduler_policy" {
  statement {
    effect = "Allow"
    actions = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.backup.arn]
  }
}

resource "aws_iam_policy" "scheduler_policy" {
  name   = "${local.name}-scheduler-policy"
  policy = data.aws_iam_policy_document.scheduler_policy.json
}

resource "aws_iam_role_policy_attachment" "scheduler_attach" {
  role       = aws_iam_role.scheduler_role.name
  policy_arn = aws_iam_policy.scheduler_policy.arn
}

resource "aws_lambda_permission" "allow_scheduler" {
  statement_id  = "AllowSchedulerInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.backup.function_name
  principal     = "scheduler.amazonaws.com"
  source_arn    = aws_scheduler_schedule.backup_schedule.arn
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${local.name}-lambda-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Cognito Backup Lambda errors"
  dimensions = {
    FunctionName = aws_lambda_function.backup.function_name
  }
  treat_missing_data = "notBreaching"
  alarm_actions       = [aws_sns_topic.notifications.arn]
}

resource "aws_cloudwatch_metric_alarm" "lambda_invocations" {
  alarm_name          = "${local.name}-invocations-failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Invocations"
  namespace           = "AWS/Lambda"
  period              = 86400
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Cognito Backup Lambda invocations monitoring"
  dimensions = {
    FunctionName = aws_lambda_function.backup.function_name
  }
  treat_missing_data = "missing"
  alarm_actions       = []
}

resource "aws_sns_topic" "notifications" {
  name = "${local.name}-notifications"
  tags = var.tags
}

resource "aws_sns_topic_policy" "notifications" {
  arn = aws_sns_topic.notifications.arn
  policy = data.aws_iam_policy_document.sns_policy.json
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.notifications.arn
  protocol  = "email"
  endpoint  = "nowakbewerbung@gmail.com"
}

data "aws_iam_policy_document" "sns_policy" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudwatch.amazonaws.com"]
    }
    actions   = ["SNS:Publish"]
    resources = [aws_sns_topic.notifications.arn]
  }
}
