# D8 CI/CD Pipeline Infrastructure
# 
# This module creates the CodePipeline + CodeBuild infrastructure
# for the Mays-Order-AWS-installer CI/CD pipeline.

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

variable "github_owner" {
  type        = string
  description = "GitHub repository owner"
}

variable "github_repo" {
  type        = string
  description = "GitHub repository name"
}

variable "github_branch" {
  type        = string
  default     = "main"
  description = "GitHub branch to deploy"
}

variable "github_token_arn" {
  type        = string
  description = "ARN of GitHub token in Secrets Manager"
}

variable "artifact_bucket_name" {
  type        = string
  description = "S3 bucket for pipeline artifacts"
}

variable "pipeline_role_arn" {
  type        = string
  description = "IAM role for CodePipeline"
}

variable "codebuild_role_arn" {
  type        = string
  description = "IAM role for CodeBuild projects"
}

# ============================================================
# Data Sources
# ============================================================

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

data "aws_s3_bucket" "artifact_bucket" {
  bucket = var.artifact_bucket_name
}

# ============================================================
# CodeBuild Projects
# ============================================================

# ============================================================
# VALIDATE Stage CodeBuild Project
# ============================================================
resource "aws_codebuild_project" "validate" {
  name         = "${var.project_name}-${var.environment}-ci-validate"
  description  = "CI/CD Validate Stage - Read-only validation with installer"
  service_role = var.codebuild_role_arn

  artifacts {
    type = "CODEPIPELINE"
  }

  cache {
    type  = "LOCAL"
    modes = ["LOCAL_DOCKER_LAYER_CACHE", "LOCAL_CUSTOM_CACHE"]
  }

  environment {
    compute_type                = "BUILD_GENERAL1_SMALL"
    image                       = "aws/codebuild/amazonlinux2-x86_64-standard:5.0"
    type                        = "LINUX_CONTAINER"
    image_pull_credentials_type = "CODEBUILD"
    privileged_mode             = false

    environment_variable {
      name  = "AWS_DEFAULT_REGION"
      value = var.aws_region
    }

    environment_variable {
      name  = "DEPLOYMENT_VERSION"
      value = "0.1.0"
    }

    environment_variable {
      name  = "DEVELOPMENT_PHASE"
      value = "H2"
    }

    environment_variable {
      name  = "DEVELOPMENT_STEP"
      value = "0"
    }

    environment_variable {
      name  = "DEVELOPMENT_STATUS"
      value = "development"
    }
  }

  source {
    type      = "CODEPIPELINE"
    buildspec = "ci/buildspecs/validate.yml"
  }


  tags = {
    Project     = var.project_name
    Environment = var.environment
    Stage       = "validate"
    ManagedBy   = "mays-installer"
  }
}

# ============================================================
# PLAN Stage CodeBuild Project
# ============================================================
resource "aws_codebuild_project" "plan" {
  name         = "${var.project_name}-${var.environment}-ci-plan"
  description  = "CI/CD Plan Stage - Read-only plan generation with installer"
  service_role = var.codebuild_role_arn

  artifacts {
    type = "CODEPIPELINE"
  }

  cache {
    type  = "LOCAL"
    modes = ["LOCAL_DOCKER_LAYER_CACHE", "LOCAL_CUSTOM_CACHE"]
  }

  environment {
    compute_type                = "BUILD_GENERAL1_SMALL"
    image                       = "aws/codebuild/amazonlinux2-x86_64-standard:5.0"
    type                        = "LINUX_CONTAINER"
    image_pull_credentials_type = "CODEBUILD"
    privileged_mode             = false

    environment_variable {
      name  = "AWS_DEFAULT_REGION"
      value = var.aws_region
    }

    environment_variable {
      name  = "DEPLOYMENT_VERSION"
      value = "0.1.0"
    }

    environment_variable {
      name  = "DEVELOPMENT_PHASE"
      value = "H2"
    }

    environment_variable {
      name  = "DEVELOPMENT_STEP"
      value = "0"
    }

    environment_variable {
      name  = "DEVELOPMENT_STATUS"
      value = "development"
    }
  }

  source {
    type      = "CODEPIPELINE"
    buildspec = "ci/buildspecs/plan.yml"
  }


  tags = {
    Project     = var.project_name
    Environment = var.environment
    Stage       = "plan"
    ManagedBy   = "mays-installer"
  }
}

# ============================================================
# DEPLOY Stage CodeBuild Project
# ============================================================
resource "aws_codebuild_project" "deploy" {
  name         = "${var.project_name}-${var.environment}-ci-deploy"
  description  = "CI/CD Deploy Stage - Mutation with exact saved plan"
  service_role = var.codebuild_role_arn

  artifacts {
    type = "CODEPIPELINE"
  }

  cache {
    type  = "LOCAL"
    modes = ["LOCAL_DOCKER_LAYER_CACHE", "LOCAL_CUSTOM_CACHE"]
  }

  environment {
    compute_type                = "BUILD_GENERAL1_SMALL"
    image                       = "aws/codebuild/amazonlinux2-x86_64-standard:5.0"
    type                        = "LINUX_CONTAINER"
    image_pull_credentials_type = "CODEBUILD"
    privileged_mode             = false

    environment_variable {
      name  = "AWS_DEFAULT_REGION"
      value = var.aws_region
    }

    environment_variable {
      name  = "ALLOW_AWS_OPERATIONS"
      value = "true"
    }

    environment_variable {
      name  = "DRY_RUN"
      value = "false"
    }
  }

  source {
    type      = "CODEPIPELINE"
    buildspec = "ci/buildspecs/deploy.yml"
  }


  tags = {
    Project     = var.project_name
    Environment = var.environment
    Stage       = "deploy"
    ManagedBy   = "mays-installer"
  }
}

# ============================================================
# VERIFY Stage CodeBuild Project
# ============================================================
resource "aws_codebuild_project" "verify" {
  name         = "${var.project_name}-${var.environment}-ci-verify"
  description  = "CI/CD Verify Stage - Read-only post-deploy verification"
  service_role = var.codebuild_role_arn

  artifacts {
    type = "CODEPIPELINE"
  }

  cache {
    type  = "LOCAL"
    modes = ["LOCAL_DOCKER_LAYER_CACHE", "LOCAL_CUSTOM_CACHE"]
  }

  environment {
    compute_type                = "BUILD_GENERAL1_SMALL"
    image                       = "aws/codebuild/amazonlinux2-x86_64-standard:5.0"
    type                        = "LINUX_CONTAINER"
    image_pull_credentials_type = "CODEBUILD"
    privileged_mode             = false

    environment_variable {
      name  = "AWS_DEFAULT_REGION"
      value = var.aws_region
    }
  }

  source {
    type      = "CODEPIPELINE"
    buildspec = "ci/buildspecs/verify.yml"
  }


  tags = {
    Project     = var.project_name
    Environment = var.environment
    Stage       = "verify"
    ManagedBy   = "mays-installer"
  }
}

# ============================================================
# DESTROY PLAN Stage CodeBuild Project
# ============================================================
resource "aws_codebuild_project" "destroy_plan" {
  name         = "${var.project_name}-${var.environment}-ci-destroy-plan"
  description  = "CI/CD Destroy Plan Stage - Read-only destroy plan generation"
  service_role = var.codebuild_role_arn

  artifacts {
    type = "CODEPIPELINE"
  }

  cache {
    type  = "LOCAL"
    modes = ["LOCAL_DOCKER_LAYER_CACHE", "LOCAL_CUSTOM_CACHE"]
  }

  environment {
    compute_type                = "BUILD_GENERAL1_SMALL"
    image                       = "aws/codebuild/amazonlinux2-x86_64-standard:5.0"
    type                        = "LINUX_CONTAINER"
    image_pull_credentials_type = "CODEBUILD"
    privileged_mode             = false

    environment_variable {
      name  = "AWS_DEFAULT_REGION"
      value = var.aws_region
    }

    environment_variable {
      name  = "ALLOW_AWS_OPERATIONS"
      value = "true"
    }

    environment_variable {
      name  = "DRY_RUN"
      value = "false"
    }
  }

  source {
    type      = "CODEPIPELINE"
    buildspec = "ci/buildspecs/destroy-plan.yml"
  }


  tags = {
    Project     = var.project_name
    Environment = var.environment
    Stage       = "destroy-plan"
    ManagedBy   = "mays-installer"
  }
}

# ============================================================
# DESTROY Stage CodeBuild Project
# ============================================================
resource "aws_codebuild_project" "destroy" {
  name         = "${var.project_name}-${var.environment}-ci-destroy"
  description  = "CI/CD Destroy Stage - Mutation with exact saved destroy plan"
  service_role = var.codebuild_role_arn

  artifacts {
    type = "CODEPIPELINE"
  }

  cache {
    type  = "LOCAL"
    modes = ["LOCAL_DOCKER_LAYER_CACHE", "LOCAL_CUSTOM_CACHE"]
  }

  environment {
    compute_type                = "BUILD_GENERAL1_SMALL"
    image                       = "aws/codebuild/amazonlinux2-x86_64-standard:5.0"
    type                        = "LINUX_CONTAINER"
    image_pull_credentials_type = "CODEBUILD"
    privileged_mode             = false

    environment_variable {
      name  = "AWS_DEFAULT_REGION"
      value = var.aws_region
    }

    environment_variable {
      name  = "ALLOW_AWS_OPERATIONS"
      value = "true"
    }

    environment_variable {
      name  = "DRY_RUN"
      value = "false"
    }
  }

  source {
    type      = "CODEPIPELINE"
    buildspec = "ci/buildspecs/destroy.yml"
  }


  tags = {
    Project     = var.project_name
    Environment = var.environment
    Stage       = "destroy"
    ManagedBy   = "mays-installer"
  }
}

# ============================================================
# CodePipeline
# ============================================================

resource "aws_codepipeline" "main" {
  name     = "${var.project_name}-${var.environment}-ci-cd"
  role_arn = var.pipeline_role_arn

  artifact_store {
    type     = "S3"
    location = var.artifact_bucket_name
  }

  # Stage 1: Source
  stage {
    name = "Source"

    action {
      name             = "Source"
      category         = "Source"
      owner            = "ThirdParty"
      provider         = "GitHub"
      version          = "1"
      output_artifacts = ["source_output"]

      configuration = {
        Owner                = var.github_owner
        Repo                 = var.github_repo
        Branch               = var.github_branch
        OAuthToken           = var.github_token_arn
        PollForSourceChanges = "false"
      }

      run_order = 1
    }
  }

  # Stage 2: Validate
  stage {
    name = "Validate"

    action {
      name             = "Validate"
      category         = "Build"
      owner            = "AWS"
      provider         = "CodeBuild"
      version          = "1"
      input_artifacts  = ["source_output"]
      output_artifacts = ["validate_output"]

      configuration = {
        ProjectName = aws_codebuild_project.validate.name
      }

      run_order = 1
    }
  }

  # Stage 3: Plan
  stage {
    name = "Plan"

    action {
      name             = "Plan"
      category         = "Build"
      owner            = "AWS"
      provider         = "CodeBuild"
      version          = "1"
      input_artifacts  = ["validate_output"]
      output_artifacts = ["plan_output"]

      configuration = {
        ProjectName = aws_codebuild_project.plan.name
      }

      run_order = 1
    }
  }

  # Stage 4: Manual Approval
  stage {
    name = "Approval"

    action {
      name            = "ManualApproval"
      category        = "Approval"
      owner           = "AWS"
      provider        = "Manual"
      version         = "1"
      input_artifacts = ["plan_output"]

      configuration = {
        NotificationArn = "" # Optional: SNS topic for notifications
        CustomData      = "Review Terraform plan before deployment. Check plan summary, safety analysis, and policy gate results."
      }

      run_order = 1
    }
  }

  # Stage 5: Deploy
  stage {
    name = "Deploy"

    action {
      name             = "Deploy"
      category         = "Build"
      owner            = "AWS"
      provider         = "CodeBuild"
      version          = "1"
      input_artifacts  = ["plan_output"]
      output_artifacts = ["deploy_output"]

      configuration = {
        ProjectName = aws_codebuild_project.deploy.name
      }

      run_order = 1
    }
  }

  # Stage 6: Verify
  stage {
    name = "Verify"

    action {
      name             = "Verify"
      category         = "Build"
      owner            = "AWS"
      provider         = "CodeBuild"
      version          = "1"
      input_artifacts  = ["deploy_output"]
      output_artifacts = ["verify_output"]

      configuration = {
        ProjectName = aws_codebuild_project.verify.name
      }

      run_order = 1
    }
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "mays-installer"
  }
}

# ============================================================
# Outputs
# ============================================================

output "pipeline_name" {
  value       = aws_codepipeline.main.name
  description = "Name of the CI/CD pipeline"
}

output "pipeline_arn" {
  value       = aws_codepipeline.main.arn
  description = "ARN of the CI/CD pipeline"
}

output "validate_project_name" {
  value       = aws_codebuild_project.validate.name
  description = "Name of the validate CodeBuild project"
}

output "plan_project_name" {
  value       = aws_codebuild_project.plan.name
  description = "Name of the plan CodeBuild project"
}

output "deploy_project_name" {
  value       = aws_codebuild_project.deploy.name
  description = "Name of the deploy CodeBuild project"
}

output "verify_project_name" {
  value       = aws_codebuild_project.verify.name
  description = "Name of the verify CodeBuild project"
}

output "destroy_plan_project_name" {
  value       = aws_codebuild_project.destroy_plan.name
  description = "Name of the destroy plan CodeBuild project"
}

output "destroy_project_name" {
  value       = aws_codebuild_project.destroy.name
  description = "Name of the destroy CodeBuild project"
}