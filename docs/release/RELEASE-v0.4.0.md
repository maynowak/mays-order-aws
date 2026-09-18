# May’s Orders – AWS
## Official Release Dossier – v0.4.0

![May's Orders AWS — Release Overview](img/mays-orders-release-overview.png)

> **A living serverless Orders & Processing foundation**  
> for the Mays Recruiting Intelligence System.

---

## 1. Release Overview

| Property | Value |
|---|---|
| Project | May's Orders – AWS |
| Release | v0.4.0 |
| Release Type | Week 4 / Phase 2 Milestone |
| Git Tag | `week-4-final-20260914` |
| Commit | `6a34a02` |
| Region | `eu-central-1` |
| Status | Phase 2 E2E verified |

This release represents a stable technical milestone. It does **not** mark the end of development.

---

## 2. What is May's Orders – AWS?

May's Orders – AWS is a serverless order management platform built on AWS. It provides:

- **Generic order processing** with configurable state machine
- **RESTful API** with Cognito JWT authentication
- **DynamoDB** single-table design with GSI for querying
- **SQS integration** for asynchronous processing
- **CloudWatch** logging and monitoring

The platform is designed as a reusable foundation for orders/transactions in the broader Mays Recruiting Intelligence System.

![Architecture](img/mays-orders-architecture.png)

---

## 3. Current Architecture

**Core Components:**

- **API Gateway HTTP API** → JWT Authorizer (Cognito) → Lambda Handler
- **Lambda (Python 3.14)** → Order Service → DynamoDB
- **DynamoDB** (single-table, GSI1 for queries)
- **Cognito User Pool** (authentication)
- **CloudWatch** (logging, monitoring)

**Phase-2 Addition:**

- **SQS Queue** (`mays-orders-orders-queue`)
- **Worker Lambda** (`mays-orders-sqs-worker`)
- **Event Source Mapping** (SQS → Worker)

---

## 4. Verified End-to-End Flow

![E2E Flow](img/mays-orders-e2e-flow.png)

```
Producer
    ↓
POST /orders (Cognito authenticated)
    ↓
DynamoDB: PENDING
    ↓
SQS: Message (orderId, CONFIRMED)
    ↓
Event Source Mapping
    ↓
Worker: Processes message
    ↓
DynamoDB: CONFIRMED
```

**Verified Order:**
- Order ID: `ord_f5f2e35b6be387af71785e98`
- Status: PENDING → CONFIRMED ✅

---

## 5. Challenge → Investigation → Root Cause → Solution

### Challenge

After Phase-2 implementation, the worker appeared to process messages but DynamoDB status remained `PENDING`.

### Investigation

CloudWatch logs showed:
- Worker received SQS message ✅
- Worker processed with `status=CONFIRMED` ✅
- But **no status update occurred** ❌

### Root Cause

**Two issues discovered:**

1. **Incorrect Account-ID in Permissions Boundary Policy**
   - Boundary had: `20571105849` (typo)
   - Correct: `240571105849`
   - This blocked ALL DynamoDB operations

2. **Missing IAM Permission**
   - Worker policy had only `dynamodb:GetItem`
   - Missing: `dynamodb:UpdateItem`

### Solution

1. Corrected Account-ID in permissions boundary
2. Added `dynamodb:UpdateItem` to worker IAM policy
3. Deployed corrected worker Lambda

### Result

`PENDING` → `CONFIRMED` ✅

---

## 6. Project Journey

![Project Journey](img/mays-orders-project-journey.png)

| Week | Focus | Status |
|------|-------|--------|
| Week 1 | Requirements & API/Data Design | ✅ Complete |
| Week 2 | Core Order Management API | ✅ Complete |
| Week 3 | Business Rules, Reliability & Security | ✅ Complete |
| Week 4 | Scalability, SQS Integration | ✅ Complete |

---

## 7. Collaboration with the Mays Ecosystem

![Mays Ecosystem](img/mays-orders-ecosystem.png)

### Current / Planned Projects

| Project | Relationship | Status |
|---|---|---|
| Mays Recruiting Intelligence System | Parent ecosystem / future consumer | Planned |
| Agent Body & Runtime | Agent execution layer | Planned integration |
| Mays Job Search | Job-search domain | Planned |
| Mays Job Matcher | Domain consumer | Planned |

> The actual external connector (`RealMaysOrdersAdapter`) is not yet implemented.

---

## 8. Integration Boundary

```
Mays Recruiting Intelligence System
           ↓
        Agent Runtime
           ↓
       OrdersPort
           ↓
 DevelopmentOrdersAdapter (today)
           ↓
   RealMaysOrdersAdapter (later)
           ↓
    May's Orders – AWS (this project)
```

---

## 9. Education, DCI Certification & Study Context

This project was developed as part of the **DCI (Design & Coding Interview)** program, focusing on:

- **AWS serverless architecture** (Lambda, API Gateway, DynamoDB, SQS, Cognito)
- **IaC with Terraform** (infrastructure as code)
- **Python 3.14** Lambda development
- **Idempotency and reliability patterns**
- **IAM security and permissions boundaries**

The project demonstrates hands-on experience with cloud-native development in a realistic engineering context.

---

## 10. Engineering Challenges & Achievements

### Key Achievements

- ✅ Phase-2 SQS integration completed
- ✅ End-to-end verification with real AWS resources
- ✅ IAM permissions boundary root cause identified and resolved
- ✅ Worker correctly processes SQS → DynamoDB CONFIRMED

### Technical Skills Demonstrated

- AWS Lambda development (Python 3.14)
- DynamoDB operations and state machines
- SQS + Event Source Mappings
- IAM policies and permissions boundaries
- Terraform infrastructure management
- End-to-end testing with real infrastructure

---

## 11. AI-Assisted Engineering

This project was developed with AI-assisted support for:

- **Analysis**: Code review, pattern identification
- **Implementation**: Code generation, debugging support
- **Testing**: Test case generation, verification
- **Documentation**: Structure, accuracy, completeness
- **Recovery**: Execution log maintenance, crash recovery

**Human Responsibility**: All architectural decisions, approvals, verifications, and deployments were made by human engineers. AI served as a productivity and knowledge tool throughout.

---

## 12. Lessons Learned

1. **IAM policy correctness requires checking Permissions Boundaries** — A policy can grant an action while the boundary denies it
2. **Logs prove execution but not necessarily persisted state** — Always verify DynamoDB directly
3. **E2E verification must reach actual persistence** — Simulated tests miss infrastructure issues
4. **Least privilege must include every required operation** — `GetItem` + `UpdateItem` needed together
5. **Git checkpoints provide reliable recovery** — Essential for crash recovery and audit trail

---

## 13. Security & Governance

- **Cognito JWT authentication** for API Gateway
- **Least privilege IAM** with permissions boundaries
- **No credentials in code** — All secrets managed via AWS
- **CloudWatch logging** for audit trails
- **Resource isolation** via account-specific ARNs

---

## 14. Current Scope

### Included

- RESTful API for order management
- SQS asynchronous processing
- DynamoDB order storage with state machine
- Cognito authentication
- CloudFormation/Terraform infrastructure

### Explicitly not included

- Phase 3 (idempotency, DLQ, status query)
- Real external connector (RealMaysOrdersAdapter)
- Production-grade monitoring/alerting
- Cost optimization features

---

## 15. Future Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| Phase 3 | Idempotency, DLQ, Status Query | Planned |
| Integration | RealMaysOrdersAdapter | Planned |
| Monitoring | Production alerts, dashboards | Planned |
| Cost | Billing metrics, optimization | Planned |

---

## 16. Release Artifacts

- [Release Dossier](./RELEASE-v0.4.0.md)
- [Release PDF](./RELEASE-v0.4.0.pdf)
- Git tag: `week-4-final-20260914`

---

## 17. Project Links

- [May's Orders – AWS](../../)
- [Mays Recruiting Intelligence System](https://github.com/maynowak/mays-recruiting-intelligence)
- [Agent Body & Runtime](https://github.com/maynowak/agent-runtime)

---

## 18. Final Statement

May's Orders – AWS is not considered a finished product.

This release establishes a verified, maintainable foundation for continued
development and future integration with the Mays Recruiting Intelligence
System.

**Build the foundation. Verify it. Then build further.**