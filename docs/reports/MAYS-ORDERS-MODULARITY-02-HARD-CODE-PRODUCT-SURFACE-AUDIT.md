# MAYS-ORDERS-MODULARITY-02 HARD-CODE & PRODUCT-SURFACE AUDIT

## BASELINE
Commit: 31f6f61

## SCOPE
Audit of hard-coding and product surface for reusability.

## HARD-CODE INVENTORY
- terraform/backend.tf: bucket mays-orders-tfstate-central-240571105849, account hardcoded
- terraform/variables.tf: default project_name mays-orders
- installer/cli/main.py: defaults for project_name, region
- lambda environment variables: MY_AWS_REGION, PROJECT_NAME

## TERRAFORM MODULES
- dynamodb: order-specific schema
- iam: generic
- lambda: generic
- cognito: generic
- api: order routes hardcoded
- monitoring: generic
- sqs: generic

## DOMAIN COUPLING
Orders table schema, API routes /orders, order state machine are order domain.

## INSTALLER SURFACE
CLI options generic, defaults to mays-orders.

## CI/CD SURFACE
No CI config found, no hard code.

## PRODUCT SURFACE
CORE: Project identity, IAM, Monitoring, Backup
APPLICATION: API, Lambda, SQS, Cognito, DynamoDB
DOMAIN: Order schema, routes, state machine

## SECOND APPLICATION SCENARIO
Change project_name, replace DynamoDB schema, replace API routes, replace Lambda handlers.

## STATUS
YELLOW

## AWS MUTATION
NONE

## TERRAFORM MUTATION
NONE
