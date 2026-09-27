# MAYS-ORDERS ARCHITECTURE

## OVERVIEW
Generic Core → Application Infrastructure → Order Domain

## GENERIC CORE
- Project identity
- Terraform workspace/state isolation
- IAM foundation
- Monitoring
- Backup

## APPLICATION LAYER
- Cognito
- API Gateway
- Lambda
- SQS
- DynamoDB

## ORDER DOMAIN
- Orders table schema
- API routes /orders
- Order Lambda handlers
- Order state machine

## CONFIGURATION RESOLUTION
project_name → workspace → env:<workspace>/terraform.tfstate
aws_region: CLI > env > default eu-central-1
environment: CLI > env > default Development, tagging only

## BACKEND
Bucket: mays-orders-tfstate-central-240571105849
Key: env:<workspace>/terraform.tfstate

## INSTALLER
Convenience layer, Terraform independent

## PRODUCT SURFACE
Core generic, Application configurable, Domain specific

## SECOND APPLICATION
Keep core, configure project_name, replace domain layer
