# Project Overview — May's Orders

**Date:** 2026-09-11  
**Status:** Documentation checkpoint completed

## Project Purpose

May's Orders is a serverless order management system for OrderFlow GmbH, implementing a complete order lifecycle: `PENDING → CONFIRMED → PROCESSING → SHIPPED → DELIVERED`.

## Current Architecture

**Client** → (Cognito JWT) → **API Gateway** (HTTP API) → **Lambda** → **DynamoDB**

Primary AWS services:
- API Gateway HTTP API V2 with JWT Authorizer
- Lambda (Python 3.14 runtime)
- DynamoDB (Single-table design with GSI1)
- Cognito User Pool for authentication

## Authentication & Security

- Cognito User Pool (`mays-orders-users`)
- App Client (`mays-orders-client`)
- JWT-based API authorization
- Staff group for user management

## Order Processing

- Direct DynamoDB writes from Lambda
- SQS worker module implemented but not integrated
- Order producer sends directly to DynamoDB (bypassing SQS for now)

## SQS Architecture

```
Client
  ↓
API Gateway
  ↓
Producer Lambda
  ├──→ DynamoDB
  │
  └──→ SQS
          ↓
    Lambda Event Source Mapping
          ↓
     Worker Lambda
          ↓
       DynamoDB
```

Note: SQS does not directly trigger Lambda. The Event Source Mapping polls the queue and invokes the worker when messages are available.

## Monitoring

- CloudWatch Dashboard (`mays-orders-overview`)
- 6 monitoring alarms (API 5xx/4xx, Lambda errors/duration/throttles, DynamoDB throttled)
- Log retention: 7 days
- IaC: `terraform/monitoring.tf`

## CloudTrail / Audit

- CloudTrail trail with S3 log bucket
- SSE-S3 encryption
- Public access block enabled
- No IAM changes (terraform apply pending)

## Region & Environment

- Region: `eu-central-1` (Frankfurt)
- Environment: Development/Prototype
- **NOT** in production

## Backup / Disaster Recovery

**Status:** NOT IMPLEMENTED

- Backup vault planned but not created
- KMS encryption planned
- Requires `terraform apply` to implement

## Encryption

- AWS-managed SSE-S3 for CloudTrail logs
- Customer-managed KMS planned for production

## Week 1–4 Documentation Status

- Week 1: ✅ COMPLETE
- Week 2: COMPLETE (Terraform configuration complete, no apply)
- Week 3: ✅ COMPLETE (Review, State Machine, Reliability, Security)
- Week 4: ⏳ IN PROGRESS

## Professor Acceptance

See `docs/reports/PROFESSOR-ACCEPTANCE-AUDIT-EXECUTION-LOG.md` for requirements verification.

## Implementation Boundary

This is a **prototype** implementation. Planned production features:
- Multi-region deployment
- VPC networking
- Customer-managed KMS keys
- Comprehensive backup strategy

## Current Outstanding Work

1. **Integration Testing**: Execute SQS integration tests with test-user
2. **SQS Integration**: Complete production sender Lambda integration
3. **Backup Verification**: Test backup/restore procedures
4. **Terraform Apply**: Deploy infrastructure (requires human approval)

## AWS Development Profiles

### `maysOrdersAiDeveloper`

- Recommended profile for AI-assisted development
- Profile name (not IAM role), configured in `~/.aws/`
- Used for: `AWS_PROFILE=maysOrdersAiDeveloper terraform plan`

### Human Developer Profile

- Developers may use their own AWS CLI profile
- No specific naming requirement
- Separate from AI developer for audit clarity

## Recommendations

1. Use `docs-checkpoint-20260911` reference point for current state
2. Verify all SSO/auth flows before production deployment
3. Review and test backup strategy before relying on it