# D8 CI/CD IAM Roles
#
# This module creates the IAM roles for CodePipeline and CodeBuild
# with least-privilege permissions per stage.

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.0"
    }
  }
}

# ============================================================
# Variables
# ============================================================

variable "project_name" {
  type        = string
  default     = "mays-orders"
  description = "Project name for resource naming"
}

variable "environment" {
  type        = string
  default     = "development"
  description = "Environment name"
}

variable "aws_region" {
  type        = string
  default     = "eu-central-1"
  description = "AWS region"
}

variable "artifact_bucket_name" {
  type        = string
  description = "S3 bucket for pipeline artifacts"
}

variable "kms_key_arn" {
  type        = string
  description = "KMS key ARN for encryption (optional)"
  default     = ""
}

# ============================================================
# Data Sources
# ============================================================

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

data "aws_iam_policy_document" "pipeline_assume_role" {
  statement {
    sid    = "AllowCodePipelineServicePrincipal"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["codepipeline.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

data "aws_iam_policy_document" "codebuild_assume_role" {
  statement {
    sid    = "AllowCodeBuildServicePrincipal"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["codebuild.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

# ============================================================
# CodePipeline Role
# ============================================================
resource "aws_iam_role" "pipeline" {
  name               = "${var.project_name}-${var.environment}-ci-cd-pipeline-role"
  description        = "IAM role for CodePipeline"
  assume_role_policy = data.aws_iam_policy_document.pipeline_assume_role.json

  tags = {
    Project     = var.project_name
    Environment = var.environment
    Component   = "ci-cd"
    ManagedBy   = "mays-installer"
  }
}

resource "aws_iam_role_policy" "pipeline_policy" {
  name = "${var.project_name}-${var.environment}-ci-cd-pipeline-policy"
  role = aws_iam_role.pipeline.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # S3 artifact bucket access
      {
        Sid    = "AllowS3ArtifactBucketAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:PutObject",
          "s3:PutObjectAcl",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.artifact_bucket_name}",
          "arn:aws:s3:::${var.artifact_bucket_name}/*"
        ]
      },
      # CodeBuild project access
      {
        Sid    = "AllowCodeBuildAccess"
        Effect = "Allow"
        Action = [
          "codebuild:StartBuild",
          "codebuild:BatchGetBuilds",
          "codebuild:BatchGetProjects"
        ]
        Resource = [
          "arn:aws:codebuild:${var.aws_region}:${data.aws_caller_identity.current.account_id}:project/${var.project_name}-${var.environment}-ci-*"
        ]
      },
      # CloudWatch Logs for pipeline
      {
        Sid    = "AllowCloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = [
          "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/codepipeline/${var.project_name}-${var.environment}-ci-cd*"
        ]
      },
      # CodeStar Connections for GitHub source (CodeStarSourceConnection)
      {
        Sid    = "AllowCodeStarConnections"
        Effect = "Allow"
        Action = [
          "codestar-connections:UseConnection",
          "codeconnections:UseConnection"
        ]
        Resource = [
          "arn:aws:codeconnections:eu-central-1:240571105849:connection/b0fa25d8-874f-4639-8e91-3ed87b2bb59b"
        ]
      },
      # KMS decryption for artifact encryption
      {
        Sid    = "AllowKMSDecrypt"
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = var.kms_key_arn != "" ? [var.kms_key_arn] : ["*"]
        Condition = {
          StringEquals = {
            "kms:ViaService" = "s3.${var.aws_region}.amazonaws.com"
          }
        }
      }
    ]
  })
}

# ============================================================
# CodeBuild Role
# ============================================================
resource "aws_iam_role" "codebuild" {
  name               = "${var.project_name}-${var.environment}-ci-codebuild-role"
  description        = "IAM role for CodeBuild projects (shared across stages)"
  assume_role_policy = data.aws_iam_policy_document.codebuild_assume_role.json

  tags = {
    Project     = var.project_name
    Environment = var.environment
    Component   = "ci-cd"
    ManagedBy   = "mays-installer"
  }
}

resource "aws_iam_role_policy" "codebuild_base" {
  name = "${var.project_name}-${var.environment}-ci-codebuild-base"
  role = aws_iam_role.codebuild.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # CloudWatch Logs
      {
        Sid    = "AllowCloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = [
          "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/codebuild/${var.project_name}-${var.environment}-ci-*"
        ]
      },
      # S3 artifact bucket access
      {
        Sid    = "AllowS3ArtifactBucketAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:PutObject",
          "s3:PutObjectAcl",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.artifact_bucket_name}",
          "arn:aws:s3:::${var.artifact_bucket_name}/*"
        ]
      },
      # CodeBuild artifact access
      {
        Sid    = "AllowCodeBuildArtifactAccess"
        Effect = "Allow"
        Action = [
          "codebuild:BatchGetBuilds",
          "codebuild:BatchGetProjects"
        ]
        Resource = [
          "arn:aws:codebuild:${var.aws_region}:${data.aws_caller_identity.current.account_id}:project/${var.project_name}-${var.environment}-ci-*"
        ]
      },
      # Secrets Manager for profile/credentials
      {
        Sid    = "AllowSecretsManagerRead"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:/mays-installer/ci/*"
        ]
      },
      # STS for cross-account (if needed)
      {
        Sid    = "AllowSTSAssumeRole"
        Effect = "Allow"
        Action = [
          "sts:AssumeRole"
        ]
        Resource = [
          "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.project_name}-${var.environment}-*"
        ]
      },
      # KMS for artifact encryption
      {
        Sid    = "AllowKMSEncryptDecrypt"
        Effect = "Allow"
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Condition = {
          StringEquals = {
            "kms:ViaService" = [
              "s3.${var.aws_region}.amazonaws.com",
              "codebuild.${var.aws_region}.amazonaws.com"
            ]
          }
        }
        Effect = "Allow"
        Resource = [
          "*"
        ]
      },
      # CodePipeline artifact access for CODEPIPELINE source type
      {
        Sid    = "AllowCodePipelineArtifactAccess"
        Effect = "Allow"
        Action = [
          "codepipeline:GetPipelineExecution",
          "codepipeline:GetPipelineState",
          "codepipeline:GetPipeline",
          "codepipeline:ListPipelineExecutions"
        ]
        Resource = [
          "arn:aws:codepipeline:eu-central-1:240571105849:mays-orders-development-ci-cd"
        ]
      },
      # SSM Parameter Store for buildspec parameter-store
      {
        Sid    = "AllowSSMParameterStoreRead"
        Effect = "Allow"
        Action = [
          "ssm:GetParameters",
          "ssm:GetParametersByPath"
        ]
        Resource = [
          "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/mays-installer/ci/*"
        ]
      }
    ]
  })
}

# DEPLOY stage - mutation
resource "aws_iam_role_policy" "codebuild_deploy" {
  name = "${var.project_name}-${var.environment}-ci-codebuild-deploy"
  role = aws_iam_role.codebuild.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Full Terraform apply permissions - explicit service ARNs
      {
        Sid    = "AllowTerraformApply"
        Effect = "Allow"
        Action = [
          "ec2:*",
          "iam:*",
          "lambda:*",
          "dynamodb:*",
          "apigateway:*",
          "sqs:*",
          "s3:*",
          "cloudwatch:*",
          "logs:*",
          "cloudtrail:*",
          "kms:*",
          "ssm:*",
          "secretsmanager:*",
          "cognito-idp:*",
          "cognito-identity:*"
        ]
        Resource = [
          "arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:${var.project_name}-${var.environment}-*",
          "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.project_name}-${var.environment}-*",
          "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/${var.project_name}-${var.environment}-*",
          "arn:aws:iam::${data.aws_caller_identity.current.account_id}:instance-profile/${var.project_name}-${var.environment}-*",
          "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:${var.project_name}-${var.environment}-*",
          "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/${var.project_name}-${var.environment}-*",
          "arn:aws:apigateway:${var.aws_region}::/restapis/*",
          "arn:aws:apigateway:${var.aws_region}::/tags/*",
          "arn:aws:sqs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:${var.project_name}-${var.environment}-*",
          "arn:aws:s3:::${var.project_name}-${var.environment}-*",
          "arn:aws:s3:::*",
          "arn:aws:cloudwatch:${var.aws_region}:${data.aws_caller_identity.current.account_id}:alarm:${var.project_name}-${var.environment}-*",
          "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.project_name}-${var.environment}-*",
          "arn:aws:cloudtrail:${var.aws_region}:${data.aws_caller_identity.current.account_id}:trail/${var.project_name}-${var.environment}-*",
          "arn:aws:kms:${var.aws_region}:${data.aws_caller_identity.current.account_id}:key/*",
          "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}-${var.environment}-*",
          "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}-${var.environment}-*",
          "arn:aws:cognito-idp:${var.aws_region}:${data.aws_caller_identity.current.account_id}:userpool/*",
          "arn:aws:cognito-identity:${var.aws_region}:${data.aws_caller_identity.current.account_id}:identitypool/*"
        ]
      }
    ]
  })
}

# VERIFY stage - read-only
resource "aws_iam_role_policy" "codebuild_verify" {
  name = "${var.project_name}-${var.environment}-ci-codebuild-verify"
  role = aws_iam_role.codebuild.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowTerraformVerifyRead"
        Effect = "Allow"
        Action = [
          "ec2:Describe*",
          "iam:GetRole",
          "iam:ListRolePolicies",
          "iam:GetRolePolicy",
          "lambda:ListFunctions",
          "lambda:GetFunction",
          "lambda:GetFunctionConfiguration",
          "dynamodb:DescribeTable",
          "dynamodb:ListTables",
          "apigateway:GET",
          "sqs:ListQueues",
          "sqs:GetQueueAttributes",
          "cloudwatch:DescribeAlarms",
          "cloudwatch:ListMetrics",
          "logs:DescribeLogGroups",
          "s3:ListBuckets",
          "s3:GetBucketLocation",
          "cloudtrail:DescribeTrails",
          "kms:DescribeKey",
          "sts:GetCallerIdentity"
        ]
        Effect = "Allow"
        Resource = [
          "*"
        ]
      }
    ]
  })
}

# PLAN stage - read-only
resource "aws_iam_role_policy" "codebuild_plan" {
  name = "${var.project_name}-${var.environment}-ci-codebuild-plan"
  role = aws_iam_role.codebuild.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowTerraformPlanRead"
        Effect = "Allow"
        Action = [
          "ec2:Describe*",
          "iam:GetRole",
          "iam:GetRolePolicy",
          "iam:ListRolePolicies",
          "iam:ListAttachedRolePolicies",
          "lambda:ListFunctions",
          "lambda:GetFunction",
          "lambda:GetFunctionConfiguration",
          "dynamodb:DescribeTable",
          "dynamodb:ListTables",
          "apigateway:GET",
          "sqs:ListQueues",
          "sqs:GetQueueAttributes",
          "cloudwatch:DescribeAlarms",
          "cloudwatch:ListMetrics",
          "logs:DescribeLogGroups",
          "s3:ListBuckets",
          "s3:GetBucketLocation",
          "s3:GetBucketVersioning",
          "s3:GetBucketEncryption",
          "s3:GetBucketPublicAccessBlock",
          "cloudtrail:DescribeTrails",
          "cloudtrail:GetTrailStatus",
          "kms:DescribeKey",
          "kms:ListAliases"
        ]
        Effect = "Allow"
        Resource = [
          "*"
        ]
      }
    ]
  })
}

# DESTROY stage - mutation
resource "aws_iam_role_policy" "codebuild_destroy" {
  name = "${var.project_name}-${var.environment}-ci-codebuild-destroy"
  role = aws_iam_role.codebuild.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowTerraformDestroy"
        Effect = "Allow"
        Action = [
          "ec2:*",
          "iam:*",
          "lambda:*",
          "dynamodb:*",
          "apigateway:*",
          "sqs:*",
          "s3:*",
          "cloudwatch:*",
          "logs:*",
          "cloudtrail:*",
          "kms:*",
          "ssm:*",
          "secretsmanager:*",
          "cognito-idp:*",
          "cognito-identity:*"
        ]
        Resource = [
          "arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:${var.project_name}-${var.environment}-*",
          "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.project_name}-${var.environment}-*",
          "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/${var.project_name}-${var.environment}-*",
          "arn:aws:iam::${data.aws_caller_identity.current.account_id}:instance-profile/${var.project_name}-${var.environment}-*",
          "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:${var.project_name}-${var.environment}-*",
          "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/${var.project_name}-${var.environment}-*",
          "arn:aws:apigateway:${var.aws_region}::/restapis/*",
          "arn:aws:sqs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:${var.project_name}-${var.environment}-*",
          "arn:aws:s3:::${var.project_name}-${var.environment}-*",
          "arn:aws:cloudwatch:${var.aws_region}:${data.aws_caller_identity.current.account_id}:alarm:${var.project_name}-${var.environment}-*",
          "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.project_name}-${var.environment}-*",
          "arn:aws:cloudtrail:${var.aws_region}:${data.aws_caller_identity.current.account_id}:trail/${var.project_name}-${var.environment}-*",
          "arn:aws:kms:${var.aws_region}:${data.aws_caller_identity.current.account_id}:key/*",
          "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}-${var.environment}-*",
          "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}-${var.environment}-*",
          "arn:aws:cognito-idp:${var.aws_region}:${data.aws_caller_identity.current.account_id}:userpool/*",
          "arn:aws:cognito-identity:${var.aws_region}:${data.aws_caller_identity.current.account_id}:identitypool/*"
        ]
      }
    ]
  })
}

# DESTROY PLAN stage - read-only
resource "aws_iam_role_policy" "codebuild_destroy_plan" {
  name = "${var.project_name}-${var.environment}-ci-codebuild-destroy-plan"
  role = aws_iam_role.codebuild.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowTerraformDestroyPlanRead"
        Effect = "Allow"
        Action = [
          "ec2:Describe*",
          "iam:GetRole",
          "iam:GetRolePolicy",
          "iam:ListRolePolicies",
          "lambda:ListFunctions",
          "lambda:GetFunction",
          "lambda:GetFunctionConfiguration",
          "dynamodb:DescribeTable",
          "dynamodb:ListTables",
          "apigateway:GET",
          "sqs:ListQueues",
          "sqs:GetQueueAttributes",
          "cloudwatch:DescribeAlarms",
          "cloudwatch:ListMetrics",
          "logs:DescribeLogGroups",
          "s3:ListBuckets",
          "s3:GetBucketLocation",
          "cloudtrail:DescribeTrails",
          "kms:DescribeKey",
          "sts:GetCallerIdentity"
        ]
        Effect = "Allow"
        Resource = [
          "*"
        ]
      }
    ]
  })
}

# VALIDATE stage - read-only
resource "aws_iam_role_policy" "codebuild_validate" {
  name = "${var.project_name}-${var.environment}-ci-codebuild-validate"
  role = aws_iam_role.codebuild.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowSTSGetCallerIdentity"
        Effect = "Allow"
        Action = [
          "sts:GetCallerIdentity"
        ]
        Effect = "Allow"
        Resource = [
          "*"
        ]
        Sid = "AllowSTSGetCallerIdentity"
      },
      {
        Sid    = "AllowIAMReadOnly"
        Effect = "Allow"
        Action = [
          "iam:GetRole",
          "iam:GetRolePolicy",
          "iam:ListRolePolicies",
          "iam:GetPolicy",
          "iam:GetPolicyVersion",
          "iam:ListPolicyVersions"
        ]
        Effect = "Allow"
        Resource = [
          "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.project_name}-${var.environment}-*"
        ]
      },
      {
        Sid    = "AllowTerraformProviderRead"
        Effect = "Allow"
        Action = [
          "ec2:DescribeRegions",
          "ec2:DescribeAvailabilityZones",
          "sts:GetCallerIdentity"
        ]
        Effect = "Allow"
        Resource = [
          "*"
        ]
        Sid = "AllowTerraformProviderRead"
      }
    ]
  })
}

# ============================================================
# Outputs
# ============================================================

output "codebuild_role_arn" {
  value = aws_iam_role.codebuild.arn
}

output "codebuild_role_name" {
  value = aws_iam_role.codebuild.name
}

output "pipeline_role_arn" {
  value = aws_iam_role.pipeline.arn
}

output "pipeline_role_name" {
  value = aws_iam_role.pipeline.name
}
