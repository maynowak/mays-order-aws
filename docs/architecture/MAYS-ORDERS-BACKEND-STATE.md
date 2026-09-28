# MAYS-ORDERS BACKEND / STATE / LOCKING

## BACKEND STATE OWNER
Terraform State belongs to central Terraform State infrastructure for Mays-Orders deployment model.

## REMOTE STATE BACKEND
Backend Type: S3
Bucket: mays-orders-tfstate-central-240571105849
Region: eu-central-1
Key: terraform.tfstate
Workspace Key Prefix: env:
State Path: env:<workspace>/terraform.tfstate

## STATE LOCKING
Mechanism: DynamoDB
Table: mays-orders-terraform-locks
Encryption: true

## WORKSPACE ISOLATION
project_name → Terraform workspace → env:<workspace>/terraform.tfstate

Examples:
mays-orders → env:/mays-orders/terraform.tfstate
mays-order-par → env:/mays-order-par/terraform.tfstate

## ENVIRONMENT ROLE
environment is governance/tagging context, not state isolation.

## SOURCES
terraform/backend.tf
installer/terraform/runner.py
docs/architecture/MAYS-ORDERS-ARCHITECTURE.md
