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

variable "artifact_bucket_name" {
  type        = string
  description = "S3 bucket for pipeline artifacts"
}

variable "kms_key_arn" {
  type        = string
  description = "KMS key ARN for encryption (optional)"
  default     = ""
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
# CodeBuild Projects
# ============================================================

# Stage 1: Validate
resource "aws_codebuild_project" "validate" {
  name           = "${var.project_name}-${var.environment}-ci-validate"
  description    = "CI/CD Validate Stage - Read-only validation with installer"
  service_role   = var.codebuild_role_arn
  build_timeout  = 60
  queued_timeout = 480

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
    image_pull_credentials_type = "CODEBUILD"
    privileged_mode             = false
    type                        = "LINUX_CONTAINER"

    environment_variable {
      name  = "AWS_DEFAULT_REGION"
      type  = "PLAINTEXT"
      value = var.aws_region
    }
    environment_variable {
      name  = "DEPLOYMENT_VERSION"
      type  = "PLAINTEXT"
      value = "0.1.0"
    }
    environment_variable {
      name  = "DEVELOPMENT_PHASE"
      type  = "PLAINTEXT"
      value = "H2"
    }
    environment_variable {
      name  = "DEVELOPMENT_STEP"
      type  = "PLAINTEXT"
      value = "0"
    }
    environment_variable {
      name  = "DEVELOPMENT_STATUS"
      type  = "PLAINTEXT"
      value = "development"
    }
  }

  source {
    type      = "CODEPIPELINE"
    buildspec = "ci/buildspecs/validate.yml"
  }
}

# Stage 2: Plan
resource "aws_codebuild_project" "plan" {
  name           = "${var.project_name}-${var.environment}-ci-plan"
  description    = "CI/CD Plan Stage - Read-only plan generation with installer"
  service_role   = var.codebuild_role_arn
  build_timeout  = 60
  queued_timeout = 480

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
    image_pull_credentials_type = "CODEBUILD"
    privileged_mode             = false
    type                        = "LINUX_CONTAINER"

    environment_variable {
      name  = "AWS_DEFAULT_REGION"
      type  = "PLAINTEXT"
      value = var.aws_region
    }
    environment_variable {
      name  = "DEPLOYMENT_VERSION"
      type  = "PLAINTEXT"
      value = "0.1.0"
    }
    environment_variable {
      name  = "DEVELOPMENT_PHASE"
      type  = "PLAINTEXT"
      value = "H2"
    }
    environment_variable {
      name  = "DEVELOPMENT_STEP"
      type  = "PLAINTEXT"
      value = "0"
    }
    environment_variable {
      name  = "DEVELOPMENT_STATUS"
      type  = "PLAINTEXT"
      value = "development"
    }
  }

  source {
    type      = "CODEPIPELINE"
    buildspec = "ci/buildspecs/plan.yml"
  }
}

# Stage 3: Deploy
resource "aws_codebuild_project" "deploy" {
  name           = "${var.project_name}-${var.environment}-ci-deploy"
  description    = "CI/CD Deploy Stage - Mutation with exact saved plan"
  service_role   = var.codebuild_role_arn
  build_timeout  = 60
  queued_timeout = 480

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
    image_pull_credentials_type = "CODEBUILD"
    privileged_mode             = false
    type                        = "LINUX_CONTAINER"

    environment_variable {
      name  = "AWS_DEFAULT_REGION"
      type  = "PLAINTEXT"
      value = var.aws_region
    }
    environment_variable {
      name  = "ALLOW_AWS_OPERATIONS"
      type  = "PLAINTEXT"
      value = "true"
    }
    environment_variable {
      name  = "DRY_RUN"
      type  = "PLAINTEXT"
      value = "false"
    }
  }

  source {
    type      = "CODEPIPELINE"
    buildspec = "ci/buildspecs/deploy.yml"
  }
}

# Stage 4: Verify
resource "aws_codebuild_project" "verify" {
  name           = "${var.project_name}-${var.environment}-ci-verify"
  description    = "CI/CD Verify Stage - Read-only post-deploy verification"
  service_role   = var.codebuild_role_arn
  build_timeout  = 60
  queued_timeout = 480

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
    image_pull_credentials_type = "CODEBUILD"
    privileged_mode             = false
    type                        = "LINUX_CONTAINER"

    environment_variable {
      name  = "AWS_DEFAULT_REGION"
      type  = "PLAINTEXT"
      value = var.aws_region
    }
  }

  source {
    type      = "CODEPIPELINE"
    buildspec = "ci/buildspecs/verify.yml"
  }
}

# Stage 5: Destroy Plan
resource "aws_codebuild_project" "destroy_plan" {
  name           = "${var.project_name}-${var.environment}-ci-destroy-plan"
  description    = "CI/CD Destroy Plan Stage - Read-only destroy plan generation"
  service_role   = var.codebuild_role_arn
  build_timeout  = 60
  queued_timeout = 480

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
    image_pull_credentials_type = "CODEBUILD"
    privileged_mode             = false
    type                        = "LINUX_CONTAINER"

    environment_variable {
      name  = "AWS_DEFAULT_REGION"
      type  = "PLAINTEXT"
      value = var.aws_region
    }
    environment_variable {
      name  = "ALLOW_AWS_OPERATIONS"
      type  = "PLAINTEXT"
      value = "true"
    }
    environment_variable {
      name  = "DRY_RUN"
      type  = "PLAINTEXT"
      value = "false"
    }
  }

  source {
    type      = "CODEPIPELINE"
    buildspec = "ci/buildspecs/destroy-plan.yml"
  }
}

# Stage 6: Destroy
resource "aws_codebuild_project" "destroy" {
  name           = "${var.project_name}-${var.environment}-ci-destroy"
  description    = "CI/CD Destroy Stage - Mutation with exact saved destroy plan"
  service_role   = var.codebuild_role_arn
  build_timeout  = 60
  queued_timeout = 480

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
    image_pull_credentials_type = "CODEBUILD"
    privileged_mode             = false
    type                        = "LINUX_CONTAINER"

    environment_variable {
      name  = "AWS_DEFAULT_REGION"
      type  = "PLAINTEXT"
      value = var.aws_region
    }
    environment_variable {
      name  = "ALLOW_AWS_OPERATIONS"
      type  = "PLAINTEXT"
      value = "true"
    }
    environment_variable {
      name  = "DRY_RUN"
      type  = "PLAINTEXT"
      value = "false"
    }
  }

  source {
    type      = "CODEPIPELINE"
    buildspec = "ci/buildspecs/destroy.yml"
  }
}

# ============================================================
# CodePipeline
# ============================================================

resource "aws_codepipeline" "main" {
  name     = "${var.project_name}-${var.environment}-ci-cd"
  role_arn = var.pipeline_role_arn
  artifact_store {
    location = var.artifact_bucket_name
    type     = "S3"
  }

  stage {
    name = "Source"

    action {
      name             = "Source"
      category         = "Source"
      owner            = "AWS"
      provider         = "CodeStarSourceConnection"
      version          = "1"
      output_artifacts = ["source_output"]

      configuration = {
        ConnectionArn        = "arn:aws:codeconnections:eu-central-1:240571105849:connection/b0fa25d8-874f-4639-8e91-3ed87b2bb59b"
        FullRepositoryId     = "maynowak/mays-order-aws"
        BranchName           = var.github_branch
        OutputArtifactFormat = "CODEBUILD_CLONE_REF"
      }
    }
  }

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

  stage {
    name = "Plan"

    action {
      name             = "Plan"
      category         = "Build"
      owner            = "AWS"
      provider         = "CodeBuild"
      version          = "1"
      input_artifacts  = ["source_output", "validate_output"]
      output_artifacts = ["plan_output"]
      configuration = {
        ProjectName   = aws_codebuild_project.plan.name
        PrimarySource = "source_output"
      }
      run_order = 1
    }
  }

  stage {
    name = "Approval"

    action {
      name     = "ManualApproval"
      category = "Approval"
      owner    = "AWS"
      provider = "Manual"
      version  = "1"
      configuration = {
        CustomData = "Review Terraform plan before deployment. Check plan summary, safety analysis, and policy gate results."
      }
      run_order = 1
    }
  }

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
}

# ============================================================
# Outputs
# ============================================================

output "pipeline_arn" {
  value = aws_codepipeline.main.arn
}

output "pipeline_name" {
  value = aws_codepipeline.main.name
}

output "validate_project_name" {
  value = aws_codebuild_project.validate.name
}

output "plan_project_name" {
  value = aws_codebuild_project.plan.name
}

output "deploy_project_name" {
  value = aws_codebuild_project.deploy.name
}

output "verify_project_name" {
  value = aws_codebuild_project.verify.name
}

output "destroy_plan_project_name" {
  value = aws_codebuild_project.destroy_plan.name
}

output "destroy_project_name" {
  value = aws_codebuild_project.destroy.name
}
