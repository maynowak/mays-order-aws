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
    sid     = "DynamoDBOrders"
    effect  = "Allow"
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
    sid     = "Logs"
    effect  = "Allow"
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
