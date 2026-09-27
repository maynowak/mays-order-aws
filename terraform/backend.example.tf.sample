# Example Terraform S3 Backend Configuration
# 
# IMPORTANT: Do NOT activate this backend until migration is explicitly approved.
# This file documents the intended remote state configuration.
# 
# To activate:
# 1. Copy this file to backend.tf
# 2. Run `terraform init -migrate-state` AFTER backup and approval
# 
# Multi-Project isolation is achieved via Terraform Workspaces + workspace_key_prefix
# project_name → Terraform Workspace → Remote State Key

terraform {
  backend "s3" {
    bucket         = "mays-orders-tfstate-central-240571105849"
    key            = "terraform.tfstate"
    region         = "eu-central-1"
    dynamodb_table = "mays-orders-terraform-locks"
    encrypt        = true
    workspace_key_prefix = true
  }
}
