# COGNITO-INFRA-RECREATE-02 APPLY

**Datum:** 2026-09-27
**Profile:** mayaws
**Account:** 240571105849
**Region:** eu-central-1
**Workspace:** mays-orders

## Terraform Apply

Target: module.cognito
Resources created: 3
- aws_cognito_user_pool.users
- aws_cognito_user_pool_client.app
- aws_cognito_user_group.staff

## AWS Readback

User Pool:
ID: eu-central-1_xhjl0PxEH
Name: mays-orders-users
Status: ACTIVE
EstimatedNumberOfUsers: 0
Tags: Project=mays-orders, Environment=Development, Maker=Maymilly Nowak

App Client:
ClientId: 5tac9c0uh5q6d5tjdse94jpf8s
ClientName: mays-orders-client
UserPoolId: eu-central-1_xhjl0PxEH
ExplicitAuthFlows: ALLOW_USER_PASSWORD_AUTH, ALLOW_REFRESH_TOKEN_AUTH

Groups:
staff
UserPoolId: eu-central-1_xhjl0PxEH

User Count: 0
Group Count: 1

## Terraform Post-Check

terraform plan -target module.cognito: No changes
terraform validate: Success

## Backup Bucket

Unchanged: mays-orders-cognito-backup-development-mays-orders

## Remote State

Unchanged

## No destructive actions

No users created
No Cognito data modified beyond infrastructure
