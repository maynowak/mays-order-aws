terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = merge({ "Project" = var.project_name }, var.tags)
  }
}

# T011-02 — DynamoDB-Tabelle + GSI1
# Fachquelle: database/dynamodb-design.md, database/access-patterns.md, ADR-002, ADR-007
resource "aws_dynamodb_table" "orders" {
  name         = var.project_name
  billing_mode = "PAY_PER_REQUEST" # ADR-007: On-Demand
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  attribute {
    name = "gsi1pk"
    type = "S"
  }

  attribute {
    name = "gsi1sk"
    type = "S"
  }

  global_secondary_index {
    name               = "gsi1"
    projection_type    = "INCLUDE"
    non_key_attributes = ["orderId", "status", "customer", "totalAmount", "createdAt", "updatedAt"]

    key_schema {
      attribute_name = "gsi1pk"
      key_type       = "HASH"
    }

    key_schema {
      attribute_name = "gsi1sk"
      key_type       = "RANGE"
    }
  }
}

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
      aws_dynamodb_table.orders.arn,
      "${aws_dynamodb_table.orders.arn}/index/gsi1",
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
}

resource "aws_iam_role_policy" "handler" {
  name   = "${var.project_name}-handler-policy"
  role   = aws_iam_role.handler.name
  policy = data.aws_iam_policy_document.handler.json
}

# T011-04 — Lambda: Order Handler (Zip-Build, Python 3.14)
# Fachquelle: ADR-001 (Serverless), api/endpoints.md, database/access-patterns.md (AP1..AP4)
# Execution Role: aws_iam_role.handler (T011-03). Zip-Build reproduzierbar via lambda/ (python3 build_zip.py).
# Migration: nodejs22.x → python3.14 (feature/lambda-python-314). Handler "index.handler" gilt für Python (index.py am ZIP-Root).
# API-GW→Lambda Invoke-Permission folgt in T011-06 (HTTP API + Routen + Authorizer).
resource "aws_lambda_function" "handler" {
  function_name    = "${var.project_name}-handler"
  role             = aws_iam_role.handler.arn
  handler          = "index.handler"
  runtime          = "python3.14"
  timeout          = 10 # Cold-Start + DynamoDB-Latenz (default 3s zu knapp)
  filename         = "${path.module}/../lambda/dist/lambda.zip"
  source_code_hash = filebase64sha256("${path.module}/../lambda/dist/lambda.zip")

  environment {
    variables = {
      ORDERS_TABLE = aws_dynamodb_table.orders.name
    }
  }
}

# T011-05 — Cognito: User Pool + App Client + Gruppe `staff`
# Fachquelle: security/authentication-decision.md (ADR-003), F002, security/iam-design.md
# Scope T011-05: nur Pool, Client, Gruppe. API Gateway / JWT-Authorizer / Lambda
# Invoke-Permission folgen in T011-06 (HTTP API + Routen + Authorizer).
# Kein user_pool_domain: Login via USER_PASSWORD_AUTH (kein Hosted-UI/OAuth-Redirect nötig,
# siehe terraform/README.md — Domain nur "falls nötig").
resource "aws_cognito_user_pool" "users" {
  name = "${var.project_name}-users"

  # Staff-Benutzer werden administrativ angelegt (T002-04 via AWS CLI); keine offene
  # Selbst-Registrierung (keine Signup-Anforderung im Repo dokumentiert, requirements/).
  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  # Passwortrichtlinie: Standardwerte (security/authentication-decision.md §6 — Verfeinerung nur falls gefordert)
  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_uppercase = true
    require_numbers   = true
    require_symbols   = true
  }

  # MFA optional — Standard (OFF), Verfeinerung nur falls gefordert (§6)
  mfa_configuration = "OFF"
}

resource "aws_cognito_user_pool_client" "app" {
  name         = "${var.project_name}-client"
  user_pool_id = aws_cognito_user_pool.users.id

  # Login via USER_PASSWORD_AUTH + Refresh (security/authentication-decision.md §3 JWT-Flow)
  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  # Public Client (kein Secret) — Voraussetzung fuer USER_PASSWORD_AUTH;
  # Benutzer-Login laeuft ueber Cognito/JWT, nie ueber IAM Access Keys (TR-15).
  generate_secret = false
}

resource "aws_cognito_user_group" "staff" {
  name         = "staff"
  user_pool_id = aws_cognito_user_pool.users.id

  # Claim `cognito:groups` im Access Token → Basis der Authorization (A-09, §5)
}
