# Installation Concept — Decisions Before Infrastructure

> **Status: PLANNING / DESIGN — with the FIRST SAFE LAYER IMPLEMENTED (project identity, T013),
> the COST-PROFILE decision defined (T014), the REGION decision defined (T015), the
> AVAILABILITY decision defined (T016), and the DATA-STRATEGY decision defined (T017).**
> This document defines a reusable *installation decision architecture* for the
> May's Orders Terraform project. As of T013, the **project identity** layer
> (`project_name` + immutable `Maker` tag) is implemented — see `terraform/README.md` §9.
> As of T014, the **COST PROFILE** decision is defined (default profile `LOWEST / PROTOTYPE`,
> matching the current configuration) — see §3.1 and `terraform/README.md` §9.5.
> As of T015, the **REGION** decision is defined (default `eu-central-1`, variable-driven
> via `var.aws_region`) — see §3.2 and `terraform/README.md` §9.6.
> As of T016, the **AVAILABILITY** decision is defined (profile `LOW / PROTOTYPE`, single
> region, managed serverless, no VPC/failover) — see §3.3 and `terraform/README.md` §9.7.
> As of T017, the **DATA STRATEGY** decision is defined (single-region DynamoDB, no
> replication, PITR/KMS/streams deferred) — see §3.4 and `terraform/README.md` §9.8.
> As of T018, the **SECURITY PROFILE** decision is defined (profile `LOW / PROTOTYPE`:
> IAM least privilege, Cognito + JWT, managed encryption, CloudWatch/CloudTrail; group
> authorization & KMS/hardening deferred) — see §3.5 and `terraform/README.md` §9.9.
> All remaining decisions (optional features, user confirmation) remain **design-only**.
>
> Stand: 2026-09-03 · Branch `main` · HEAD `4c4c4c2` · companion logs:
> `docs/reports/T012-INSTALLATION-CONCEPT-EXECUTION-LOG.md` (planning) ·
> `docs/reports/T013-INSTALLATION-IDENTITY-EXECUTION-LOG.md` (first implementation step) ·
> `docs/reports/T014-INSTALLATION-COST-PROFILE-EXECUTION-LOG.md` (cost-profile decision) ·
> `docs/reports/T015-INSTALLATION-REGION-EXECUTION-LOG.md` (region decision) ·
> `docs/reports/T016-INSTALLATION-AVAILABILITY-EXECUTION-LOG.md` (availability decision) ·
> `docs/reports/T017-INSTALLATION-DATA-STRATEGY-EXECUTION-LOG.md` (data-strategy decision) ·
> `docs/reports/T018-INSTALLATION-SECURITY-PROFILE-EXECUTION-LOG.md` (security-profile decision)

---

## 1. Purpose

The current Terraform project is a **single-region prototype** with a fixed identity
(`project_name = "mays-orders"`). A future installer should be able to make **explicit,
pre-creation decisions** about:

- **Cost** — how much cost and operational complexity to accept,
- **Availability** — single region vs. multi-region, and whether the *data layer*
  matches the requested availability,
- **¿Security hardening** — which optional features to enable,
- **Project identity** — the deployed organization/customer name, without losing the
  original maker/provenance identity.

This concept does **not** change the existing architecture. It prepares the *decision
logic* that a future installer (or CLI wizard) will consume.

---

## 2. Design Principles

1. **Cost is a first-class, explicit decision** — never silently enabled.
2. **Availability is a connected architectural chain**, not a checkbox:
   API → compute → data → replication → recovery → cost.
3. **Identity is split** into *configurable* (deployed project) and *preserved* (maker/provenance).
4. **No fabricated pricing.** Only relative cost categories (`LOW` / `MEDIUM` / `HIGH` /
   `VARIABLE`) plus a disclaimer that these are estimates, not billing guarantees.
5. **Nothing is created before explicit user confirmation.**

---

## 3. Cost Profiles

The primary installation question is:

> *"How much cost and operational complexity are you willing to accept?"*

| # | Profile | Intent | Relative cost |
|---|---------|--------|---------------|
| 1 | **LOWEST COST / PROTOTYPE** | Development, demo, prototype. Single region, no multi-region replication, no optional paid security features unless required. | `LOW` |
| 2 | **STANDARD** | Production-oriented baseline with stronger operational/security defaults where justified. | `MEDIUM` |
| 3 | **HIGH AVAILABILITY** | Regional resilience, additional compute/data infrastructure, multi-region data strategy where necessary. | `HIGH` |
| 4 | **CUSTOM** | Installer selects individual capabilities explicitly. | `VARIABLE` |

### Important disclaimer

- A profile is a **cost estimate / category**, **not a billing guarantee**.
- Actual cost depends on usage, Region, traffic, storage, requests and enabled features.
- No profile is literally free. AWS Free Tier may absorb low usage, but that is a
  billing outcome, not a promise made by the installer.

### Cost-impact warning/confirmation pattern

Every cost-relevant option must use a warning/confirmation before the decision is
accepted. Canonical wording:

> **Estimated cost impact: HIGH**
> This option may create additional regional resources and data replication costs.
> Do you want to enable it?  `[Enable]` / `[Skip]`

The decision is captured *before* installation; the installer never silently toggles a
cost-increasing feature.

### 3.1 Cost-profile decision (T014) — default profile + recommended representation

**Decision:** The four profiles in §3 are the canonical cost-profile taxonomy. The current
Terraform configuration **already implements the `LOWEST / PROTOTYPE` profile** by default:

| Characteristic | Current value (verified) | Profile trait |
|---|---|---|
| Region count | 1 (`var.aws_region`, default `eu-central-1`) | LOWEST / PROTOTYPE |
| DynamoDB capacity | On-Demand (`PAY_PER_REQUEST`) | LOWEST (no provisioned cost) |
| DynamoDB PITR / backups / streams | none | LOWEST |
| CloudTrail encryption | SSE-S3 (AES256), no KMS | LOWEST (no key mgmt) |
| App transport | HTTP (`protocol_type = "HTTP"`), no custom domain/ACM | LOWEST (prototype) |
| CloudWatch | dashboard + 6 alarms + 7-day log retention | LOW/MEDIUM |
| Optional hardening (KMS, data events, lifecycle, SNS, MFA delete) | all deferred | LOWEST |

**Recommended Terraform representation (documented, NOT implemented in T014):** a single
`cost_profile` variable with `validation {}`, defaulting to `"lowest"`. It would *gate* the
cost-increasing features (not itself create resources):

```hcl
variable "cost_profile" {
  description = "Kosten-/Komplexitäts-Profil der Installation (install-Entscheidung, T014)."
  type        = string
  default     = "lowest"
  validation {
    condition     = contains(["lowest", "standard", "high_availability", "custom"], var.cost_profile)
    error_message = "cost_profile muss einer der Werte 'lowest', 'standard', 'high_availability', 'custom' sein."
  }
}
```

**Why NOT implemented now:** the current installation workflow has **no consumer** for a
cost-profile value — every cost-relevant feature is already pinned to the LOWEST profile.
Introducing an unused variable today would be dead configuration. The variable should be
introduced in the same task that first makes a feature cost-profile-dependent (e.g. the
Availability/Data-Strategy or Optional-Features task). `CUSTOM` must additionally trigger the
explicit confirmation described in §10 before any cost-increasing option is enabled.

### 3.2 Region decision (T015) — default `eu-central-1`

**Decision:** The current project region is **`eu-central-1`** ("Europe (Frankfurt)"). It is
already cleanly variable-driven and does **not** need a new Terraform variable.

- **Where configured (verified):** `terraform/variables.tf` `var.aws_region` (default
  `"eu-central-1"`), consumed by the root `provider "aws"` (`terraform/main.tf:27`,
  `region = var.aws_region`), forwarded to `module.monitoring` (`main.tf:152` for the
  CloudWatch dashboard widget region), and derived by `module.cloudtrail` via
  `data "aws_region" "current"` (for the CloudTrail log destination region).
- **Human-readable name:** Europe (Frankfurt).
- **Variable-driven (not hard-coded):** yes — the single `aws_region` variable is the one
  region lever; all modules inherit the provider region (no provider aliases; single-region
  design). No duplicate region variable is needed.
- **Rationale (project choice, not an absolute claim):** the project targets a
  European/German context; Frankfurt is a well-established EU region that supports all
  services used (DynamoDB, Lambda, Cognito, API Gateway HTTP API, CloudWatch, CloudTrail, S3).
  It is chosen for proximity/appropriateness to that context, not as a universal "best".
- **Relationship to cost profile (T014 `LOWEST / PROTOTYPE`):** single region is preferred;
  a second region is NOT introduced (would raise infrastructure/ops/sync/monitoring/
  deployment complexity without a documented need).
- **Relationship to availability (T016):** *deferred*. A region containing multiple
  Availability Zones does **not** mean the app is deployed across them — AZ architecture is a
  separate Availability decision.
- **Relationship to data strategy (T017):** *deferred*. "API in Region A + Region B" does
  **not** mean "DynamoDB data in Region A + Region B".
- **Effect of changing region:** before first `apply` (state empty), changing `aws_region`
  simply targets another region. After first `apply`, a region change redeploys all regional
  resources into the new region (see §12; state is per-config). Multi-region is only
  revisited under a later `HIGH AVAILABILITY` or `CUSTOM` profile with explicit confirmation.

### 3.3 Availability decision (T016) — `LOW / PROTOTYPE`

**Decision:** the selected availability profile is **`LOW / PROTOTYPE`** — single region
(`eu-central-1`), fully on AWS-managed serverless services, with **no custom networking and
no additional failover infrastructure**.

- **Verified current architecture (see §6 for the model):** no VPC, no public/private
  subnets, no Internet Gateway, no NAT Gateway, no VPC endpoints, no EC2. Lambda uses the
  AWS-managed execution environment (**no `vpc_config`**); API Gateway HTTP API, DynamoDB,
  Cognito, CloudWatch, CloudTrail and the S3 audit bucket are all AWS-managed services.
- **Important (not an availability defect):** the *absence of a VPC* for this serverless
  architecture is **not** an availability problem — managed services provide their own
  regional durability/availability. A VPC is deliberately **not** introduced just to create
  the appearance of high availability.
- **Critical distinctions (T016):** region ≠ Availability Zone ≠ service availability ≠
  data replication. A region having multiple AZs does **not** mean the app is deployed
  across them; a VPC-less Lambda is **not** a manually-managed single server; a regional
  DynamoDB table is **not** auto-replicated to another region.
- **Cost relationship (T014 `LOWEST/PROTOTYPE`, `LOW`):** no additional region, no extra
  networking/failover infra → cost stays `LOW`.
- **Not implemented (deliberately deferred):** VPC/subnets, NAT/IGW, VPC endpoints, Route 53
  failover, a second region, DynamoDB Global Tables, replication, extra failover services.
  These are only reconsidered under a later `HIGH AVAILABILITY` or `CUSTOM` profile with
  explicit user confirmation.
- **Relationship to Data Strategy (T017):** *deferred* — availability at the API/compute
  layer is a separate decision from data replication (see §4).

### 3.4 Data strategy decision (T017) — single-region DynamoDB, LOWEST/PROTOTYPE

**Decision:** **DynamoDB is the primary data store, single-region (`eu-central-1`), with no
cross-region replication.** Backup/PITR, streams, and customer-managed KMS are **not enabled**
— deferred to T019 (Optional Features) / later hardening. The current configuration already
represents the LOWEST/PROTOTYPE data strategy; no Terraform change is required.

- **Primary data store (verified, `terraform/modules/dynamodb/main.tf`):** one table
  `aws_dynamodb_table.orders` (name = `var.project_name`), `billing_mode = "PAY_PER_REQUEST"`
  (On-Demand), composite key `pk` (HASH) / `sk` (RANGE), plus GSI1 (`gsi1pk`/`gsi1sk`, `INCLUDE`
  projection).
- **Replication:** single region; **no Global Tables, no cross-region replicas** (no
  `replica`/`global_table` resources).
- **Backup / PITR:** **NOT enabled** (no `point_in_time_recovery` block). Deliberate
  LOWEST/PROTOTYPE trade-off: lower cost/simplicity vs. recovery capability; revisit as an
  explicit Optional-Feature decision (T019).
- **Encryption:** all DynamoDB data is encrypted at rest by default; **no explicit
  `server_side_encryption` block → AWS-managed (AWS-owned KMS) encryption**, **not**
  customer-managed KMS. Customer-managed KMS is a later Security-Profile / Optional-Feature
  decision (§3.5 / §11).
- **Deletion protection / TTL / streams:** none configured. The module exposes a
  `table_stream_arn` output, but no `stream` block exists → the ARN is empty (stream disabled).
- **Consistency (verified at code level):** the Lambda access patterns use default DynamoDB
  reads (GetItem/Query); no `ConsistentRead` / transacted reads are used. Consistency model is
  DynamoDB's default (eventually consistent reads). Business rules/strongly-consistent or
  transactional needs belong to Week-3 implementation; not introduced here.
- **Data residency / region:** regional resources are provisioned in `eu-central-1`; no legal/
  compliance (e.g. GDPR) claim implied. Additional regions or residency controls are an
  explicit future installation decision if ever needed.
- **Cost relationship (T014 `LOWEST/PROTOTYPE`, `LOW`):** avoids Global Tables, cross-region
  replication, duplicate storage, KMS and complex backup infrastructure — cost stays `LOW`
  without removing any existing durability (managed-service regional durability remains).
- **Not implemented (deferred):** Global Tables, cross-region replication, second region,
  Route 53, PITR/backups, KMS key architecture, streams/change-data-capture.

### 3.5 Security profile decision (T018) — `LOW / PROTOTYPE`

**Decision:** the selected security profile is **`LOW / PROTOTYPE`** — IAM least privilege,
Cognito authentication + API-Gateway JWT validation, AWS-managed encryption, CloudWatch
logging and CloudTrail management auditing; stronger controls are intentionally deferred.

- **Identity / authentication (verified):** Cognito user pool (`admin_create_user_only`, no
  open self-signup; password policy min 8 + upper/lower/number/symbol; MFA `OFF`), app client
  (`USER_PASSWORD_AUTH` + refresh, public client `generate_secret = false`), group `staff`.
  Users authenticate via Cognito (JWT), **not** IAM access keys (TR-15).
- **API Gateway authorization (verified):** JWT authorizer (issuer = Cognito endpoint,
  audience = app-client ID); **all four routes** (`POST /orders`, `GET /orders/{orderId}`,
  `GET /orders`, `PATCH /orders/{orderId}/status`) set `authorization_type = "JWT"` with this
  authorizer — no public routes.
- **Application authorization (verified gap):** group-based authorization
  (`cognito:groups` in the Lambda handler) is **NOT implemented** — the JWT authorizer only
  verifies token issuer/audience. Deferred to Week-3 application work (A-09). Not invented here.
- **IAM (verified):** single Lambda execution role with an inline least-privilege policy —
  `dynamodb:PutItem/GetItem/UpdateItem/Query` scoped to the table + GSI1 only, plus
  `logs:CreateLogGroup/CreateLogStream/PutLogEvents`. **No** `Scan/Delete/Batch`, no `s3:*`,
  no `iam:*`, **no `iam:PassRole`**, no `AdministratorAccess`. API Gateway → Lambda uses a
  separate resource-based permission (`aws_lambda_permission`, principal
  `apigateway.amazonaws.com`, `source_arn` scoped to this API).
- **Terraform developer permissions:** deployment identity is external (human/CI) and is **not
  encoded in the Terraform modules**; only the runtime Lambda role is managed here.
- **Permissions boundary (optional hardening):** `MaysOrders-Terraform-Developer-Boundary` is
  documented in the Policy Gate (not part of the Terraform modules) and constrains the
  deployment identity's maximum permissions. It is **optional**, not a May's-Orders application
  requirement.
- **Encryption (verified):** DynamoDB uses AWS-managed default at-rest encryption (no explicit
  `server_side_encryption`, no customer-managed KMS); CloudTrail S3 bucket uses explicit
  **SSE-S3 / AES256** + public-access-block + `BucketOwnerEnforced`. **No customer-managed KMS.**
- **Transport (verified):** HTTP API V2 (`protocol_type = "HTTP"`), **no custom domain / ACM
  certificate**. AWS-managed API-Gateway endpoint provides TLS/HTTPS at the AWS edge; custom
  domain/ACM is optional (not introduced for appearance).
- **Audit / logging (verified):** CloudWatch = Lambda log group (7-day retention) + dashboard +
  6 alarms; CloudTrail = multi-region trail, global service events, management events Read+Write,
  log-file validation, S3 destination with least-privilege bucket policy. **Deferred (→ T019):**
  SSE-KMS, DynamoDB data events, S3 lifecycle/retention, SNS/EventBridge eventing, MFA Delete.
- **Network (verified):** no VPC/subnets/SG/NACL/NAT/IGW. The absence of a VPC is **not** a
  security failure for this managed-serverless architecture; no custom network layer exists.
- **Cost relationship (T014 `LOWEST/PROTOTYPE`, `LOW`):** no customer-managed KMS, no data
  events, no WAF/GuardDuty/Security Hub, no custom domain — cost stays `LOW` without removing
  any baseline control.
- **What changes under `STANDARD` / `HIGH/PRODUCTION`:** customer-managed KMS, CloudTrail data
  events + hardening, tighter group authorization, custom domain/ACM (TLS for the app), possibly
  WAF/GuardDuty — all with explicit user confirmation and higher cost/complexity.

---

## 4. Availability Drives Data Architecture

Availability must not be treated as an API-only question. The decision flow recognizes a
dependency chain:

```text
API availability
  → compute availability
  → data availability
  → replication strategy
  → recovery strategy
  → cost
```

### Canonical example

```text
SINGLE REGION                     MULTI REGION
API A                             API A + API B
Lambda A                          Lambda A + Lambda B
DynamoDB A                        DynamoDB regional replicas / Global Tables
                                  + routing + recovery strategy
```

### Critical constraint (must be documented to the installer)

> **Regional API availability does not automatically provide regional application
> availability if the data layer remains single-region.**

### Multi-region decision questions (must be answered before proceeding)

When a multi-region option is selected, the installer must answer:

1. **Which Regions?**
2. **Is the data layer also multi-region?**
3. **Write strategy:** single-writer / primary-secondary, or multi-active?
4. **Routing:** how is traffic routed (e.g. latency-based DNS, custom logic)?
5. **Failure behavior:** what happens during a regional failure?
6. **Consistency/conflict strategy:** last-write-wins vs. application-level conflict resolution?
7. **RPO / RTO expectations?**
8. **Additional AWS cost accepted?**

None of these are implemented here; they are decision points the future installer surfaces.

---

## 5. Project / Company Identity

The current project hard-codes `project_name = "mays-orders"` as the deployed identity.
The future installer must allow a deploying organization/customer to choose a different
**project/system name**.

### Investigation result (verified against repo)

Current use of identity:

| Artifact | Current value | Notes |
|---|---|---|
| Terraform `var.project_name` | `"mays-orders"` (default) | `terraform/variables.tf:1` |
| `default_tags` `Project` | `var.project_name` | `terraform/main.tf:15-17` |
| Per-module tag `Project` | `var.project_name` | all modules use `merge({ "Project" = var.project_name }, var.tags)` |
| Resource names | `"${var.project_name}-handler"`, `-users`, `-api`, `-trail`, `-cloudtrail-<acc>`, etc. | every module: `${var.project_name}-...` prefix |
| Root outputs | descriptive (not identity-dependent) | `terraform/outputs.tf` |
| CloudTrail bucket | `"${var.project_name}-cloudtrail-<account-id>"` | `modules/cloudtrail/main.tf:20` |

### Where configured project identity can safely replace hard-coded naming

- `var.project_name` **already** flows into every resource name and the `Project` tag.
  It is the correct *single* configuration lever for deployed identity.
- The default value `"mays-orders"` is the only "hard-coding", and it lives in one place
  (`terraform/variables.tf`). An installer override (e.g. `-var="project_name=acme-orders"`)
  would propagate to all resources today — but **this is a planning observation, not a
  tested guarantee** (see §8 impact analysis).

### Identifiers that MUST remain stable

- **AWS resource names** that are referenced once created (e.g. DynamoDB table name baked
  into the Lambda env var `ORDERS_TABLE`) — changing `project_name` *after* first apply
  would fork the deployment.
- **Cognito User Pool / App Client IDs** — AWS-generated, immutable.
- **CloudTrail S3 bucket name** — globally unique, `...-<account-id>`; effectively immutable
  once created (S3 bucket names are global and not reusable after deletion).
- **Terraform state addresses** — renaming a resource forces destroy/replace.

---

## 6. Identity / Provenance Design

Clean separation of:

- **DEPLOYED PROJECT IDENTITY** (configurable) and
- **ORIGINAL MAKER / PROVENANCE** (preserved).

### Conceptual labels (baseline example)

| Field | Value (example) | Role | Mutable? |
|---|---|---|---|
| `Project` | `"Acme Orders"` | what the deployed customer/project sees; resource-name prefix + `Project` tag | mutable *before* install; immutable after first apply (resource-name coupling) |
| `ManagedBy` | `"Mays Orders"` | deployment/organization steward | configurable / deployment-specific |
| `CreatedBy` | `"May"` | original human maker | configurable or deployment-specific |
| `Maker` | `"Mays Orders"` (preserved) | **original project/maker provenance — never lost on rename** | immutable |

### Identity questions answered

- **What name does the deployed customer/project see?** `Project` (resource names + `Project` tag).
- **What name appears in AWS tags?** `Project` (and, when implemented, `ManagedBy` /
  `CreatedBy` / `Maker`).
- **What name is used for resource naming?** `Project` (via `project_name`).
- **How is the original maker retained?** an immutable `Maker` tag / provenance field,
  independent of `Project`.
- **Can the customer rename without losing provenance?** Yes — `Maker` is preserved,
  but a *post-install* rename of `Project` is not a rename; it creates a new resource set
  (see §5 "MUST remain stable"). Re-brand at *install time* is the supported path.
- **Mutable vs. immutable:** `Project`/`ManagedBy`/`CreatedBy` mutable at install time;
  `Maker` immutable; `Project` effectively immutable *after* first apply.

### Personal-identity recommendation (documented separately — not silently applied)

> **Recommendation:** prefer a **neutral maker/project identity field** (e.g. the project
> name `"Mays Orders"` or a maker slug like `mays-orders`) over a personal name in the
> default/example. If `CreatedBy = "May"` is retained as a conceptual example, it should be
> treated as **example data**, not the shipped default. This avoids unnecessary exposure of
> personal information in tags that propagate to every AWS resource.

This recommendation changes nothing about the agreed conceptual example above; it only
governs the *final default value* chosen at implementation time.

---

## 7. Installation Decision Matrix

Legend — cost: `LOW / MEDIUM / HIGH / VARIABLE`; availability: `NONE / PARTIAL / FULL`;
security: `NONE / LOW / MEDIUM / HIGH`; complexity: `LOW / MEDIUM / HIGH`.

| Decision | Options | Cost impact | Availability impact | Security impact | Operational complexity | Dependencies | Recommendation |
|---|---|---|---|---|---|---|---|
| Region count | 1 (single) / 2+ (multi) | LOW → HIGH | NONE → FULL | – (scope) | LOW → HIGH | none for single | SINGLE (prototype) |
| Multi-Region API | enable / disable | MEDIUM | PARTIAL (API only) | – | MEDIUM | multi-region Lambda | Disable unless data layer is multi-region |
| Multi-Region DynamoDB | enable / disable | HIGH | FULL (data) | – | HIGH | Global Tables / replicas | Disable (prototype) |
| DynamoDB replication | none / Global Tables | HIGH | FULL | – | HIGH | multi-region decision set | NONE (prototype) |
| HTTPS / custom domain | HTTP (current) / HTTPS (ACM+domain) | LOW–MEDIUM | – | MEDIUM (TLS for app) | MEDIUM (DNS+ACM) | Route 53 / ACM / domain ownership | Depends on demo/live requirement |
| CloudTrail SSE-KMS | SSE-S3 (current) / SSE-KMS | MEDIUM | – | HIGH (key isolation) | MEDIUM (key mgmt) | `aws_kms_key` + key policy | DEFERRED (optional) |
| DynamoDB Data Events | enable / disable | MEDIUM–HIGH (volume) | – | HIGH (data audit) | MEDIUM | `event_selector` data_resource | DEFERRED (optional) |
| S3 Lifecycle / Retention | enable / disable | LOW | – | MEDIUM (retention compliance) | LOW–MEDIUM | `aws_s3_bucket_lifecycle_configuration` | DEFERRED (compliance-driven) |
| Security Eventing (SNS/EventBridge) | enable / disable | LOW–MEDIUM | – | MEDIUM–HIGH (active alerting) | MEDIUM | CT → EventBridge → SNS | DEFERRED (optional) |
| Additional log protection (MFA Delete) | enable / disable | LOW (S3 versioning) | – | HIGH (tamper resistance) | HIGH (Root session) | S3 versioning + MFA | DEFERRED (optional) |
| DynamoDB PITR / backup | enable / disable | MEDIUM | PARTIAL (recovery) | – | MEDIUM | `point_in_time_recovery` | DEFERRED (recovery requirement?) |
| Terraform remote state | local (current) / S3 + DynamoDB lock | LOW | – (reproducibility) | LOW–MEDIUM (locking) | LOW–MEDIUM | S3 bucket + DynamoDB table | RECOMMENDED (Week 2 decision) |

Only options *already* documented in the project are listed; no arbitrary features were
invented to enlarge the matrix.

---

## 8. Installation Flow

Future flow (implemented later, not now):

```text
START
  ↓
Project Identity        (Project / ManagedBy / CreatedBy / Maker)
  ↓
Cost Profile            (LOWEST / STANDARD / HA / CUSTOM)
  ↓
Region Selection        (which Region(s))
  ↓
Availability Req.       (single / multi; API + compute + data)
  ↓
Data Strategy           (DynamoDB single / Global Tables / replicas)
  ↓
Security Profile        (baseline vs. hardened options)
  ↓
Optional Features       (CloudTrail hardening, PITR, HTTPS, …)
  ↓
Cost / Architecture Summary
  ↓
User Confirmation
  ↓
AI Developer Profile    (separate AWS CLI profile recommended — see §8.1)
  ↓
Terraform Installation  (init → validate → plan → human-approved apply)
```

### AI Developer Identity / Profile Setup

During installation, the user is recommended to use a **separate AWS CLI profile for the AI
Developer** (`maysOrdersAiDeveloper`) so that the **Human Developer identity ≠ AI Developer
identity**. This supports least privilege, independent IAM policy/boundary governance, clearer
audit/provenance and safer AI-assisted infrastructure work.

> Recommends **identity separation**: a recommended profile, no automatic credential creation,
> no credential storage in Git. The name is a recommendation — the user may reuse an existing
> AWS CLI profile.

Full documentation: `docs/ai-developer-profile.md`. This step is **preparation/documentation only**
— it does **not** create IAM roles, policies, boundaries or credentials, and is **separate** from
the later *IAM Capability Preflight* installation check.

### Pre-confirmation summary example

> **Selected deployment:**
> Project: `Acme Orders`
> Regions: `eu-central-1`
> Availability: Single Region
> Data: Single DynamoDB
> Security: Standard
> Estimated cost profile: `LOW`
>
> Continue?  `[Yes]` `[Change selection]`

### Higher-cost warning example

> **WARNING:**
> This selection enables additional regional resources and may increase AWS costs.
>
> Continue?  `[Yes]` `[Change selection]`

---

## 9. Profile Compatibility / Warning Matrix

Classification: `SUPPORTED` · `SUPPORTED WITH WARNING` · `NOT RECOMMENDED` · `INVALID`.
No combination is rejected unless technically invalid.

| Combination | Classification | Rationale |
|---|---|---|
| Multi-Region API + single-region data | `NOT RECOMMENDED` | API-level HA without data-level HA is misleading; regional API does not imply app availability (§4). |
| Multi-Region API + multi-Region data | `SUPPORTED` | Internally consistent; highest cost/complexity. |
| Lowest-cost profile + expensive optional hardening | `SUPPORTED WITH WARNING` | Technically valid but contradicting; warn on cost intent mismatch. |
| Prototype profile + production retention requirements | `NOT RECOMMENDED` | Retention (S3 lifecycle / PITR) implies production, not prototype. |
| HTTP application + HTTPS optional feature | `SUPPORTED WITH WARNING` | HTTP app over AWS-TLS endpoints is valid for prototype; HTTPS would be needed for production exposure. |
| DynamoDB Data Events + insufficient audit requirement | `SUPPORTED WITH WARNING` | Data Events add volume/cost; enable only when a concrete data-plane audit need exists. |
| SSE-KMS + cost-minimal profile | `SUPPORTED WITH WARNING` | Valid but conflicts with LOWEST-COST intent; require explicit opt-in. |

---

## 10. Cost Transparency

The installer never silently enables a feature known to increase cost or operational
complexity. Every such feature must surface:

| Field | Meaning |
|---|---|
| **WHAT IT ENABLES** | the concrete capability |
| **WHY IT EXISTS** | the security/ops justification |
| **COST LEVEL** | relative category (LOW/MEDIUM/HIGH/VARIABLE) |
| **OPERATIONAL IMPACT** | key-management, routing, retention, etc. |
| **USER DECISION REQUIRED** | enabled only on explicit confirmation |

No fabricated monthly prices. If exact pricing is later needed, it must be a **separate
pricing-research task** using current AWS pricing.

---

## 11. Relation to Existing CloudTrail Hardening

The existing CloudTrail baseline (`module.cloudtrail`) remains **unchanged**. The following
features are already documented as optional/deferred (`security/cloudtrail-design.md` §9):

- SSE-KMS
- DynamoDB Data Events
- S3 Lifecycle / Retention
- SNS / EventBridge security eventing
- MFA Delete / additional log protection

They integrate into this installation concept as **optional security-profile choices** with
cost/complexity warnings — **not implemented** in this task.

---

## 12. Terraform Impact Analysis

Mapping: installation decision → future variable / module interface → affected modules →
resource impact → state / migration consideration. **This is analysis only — no `.tf`
files are modified.**

| Installation decision | Future variable / interface | Affected modules | Resource impact | State / migration consideration |
|---|---|---|---|---|
| Project identity (`Project`) | `project_name` (already exists) | all 7 modules | renames every `${var.project_name}-*` resource; changes `Project` tag | post-apply rename = destroy/replace (new identity = new resources) |
| Provenance (`Maker`) | new tag variable (e.g. `maker` / `provenance`) or merge in `default_tags` | root provider + all modules (via tags) | pure tag addition (no resource rename) | SAFE / no state migration |
| `ManagedBy` / `CreatedBy` | new tag variables | root provider `default_tags` | pure tag addition | SAFE / no state migration |
| Region | `aws_region` (already exists) | root provider (all modules inherit) | re-deploys resources into different Region | full rebuild in new Region (state is per-config, not global) |
| Multi-Region API | new `aws_region` list + provider aliases + conditional module calls | root, `module.api`, `module.lambda` | additional API + Lambda instances per Region | additive; new resource addresses |
| DynamoDB replication / Global Tables | new module/toggle + cross-region table config | `module.dynamodb` (or new replication module) | additional replica tables | needs multi-cluster definition; careful (Global Tables create repl. resources) |
| DynamoDB PITR | `point_in_time_recovery` toggle | `module.dynamodb` | attribute change, no rename | in-place (no replace) |
| CloudTrail SSE-KMS | `cloudtrail_kms_enabled` | `module.cloudtrail` | new `aws_kms_key`/alias + key policy | additive |
| Data Events | `cloudtrail_data_events` + event_selector | `module.cloudtrail` | event_selector change | in-place, low risk |
| S3 lifecycle/retention | `cloudtrail_retention_days` | `module.cloudtrail` | new `aws_s3_bucket_lifecycle_configuration` | additive |
| Security eventing | SNS/EventBridge module or resources | new module / `module.cloudtrail` + consumer | new SNS topic + EventBridge rule | additive |
| Terraform remote state | `backend "s3"` + DynamoDB lock | root (`terraform` block) | no AWS resource in service modules; adds state bucket/table | state migration (local → remote) — needs `terraform init -migrate-state` |
| HTTPS / custom domain | `aws_apigatewayv2_domain_name` + ACM | `module.api` | new domain name + certificate | additive; DNS ownership prerequisite |

---

## 13. Documentation Placement

- **New (this task):** `architecture/installation-concept.md` — this document (single
  source for the installation decision concept).
- **Execution log (this task):** `docs/reports/T012-INSTALLATION-CONCEPT-EXECUTION-LOG.md`.
- **Existing docs extended later (implementation, not this task):** `terraform/README.md`
  (§ installation), `docs/roadmap/future-extensions.md`, `cost/cost-analysis.md`
  (relative cost categories), `architecture/architecture-and-security.md` (new optional
  sections), `docs/PROJECT_STATUS.md` (status line).

### Documentation status convention

| Label | Meaning |
|---|---|
| `CURRENT IMPLEMENTATION` | exists and is valid today |
| `PLANNED INSTALLATION CONCEPT` | this document — design only |
| `OPTIONAL FUTURE FEATURE` | deferred hardening, opt-in install mode |

---

## 14. Validation (this task = planning only)

- Git status inspected (see execution log).
- Terraform structure inspected (no `.tf` modified).
- Documentation consistency checked (no contradictions with `terraform/README.md`,
  `security/cloudtrail-design.md`, `architecture/architecture-and-security.md`).
- **NOT run:** `terraform apply`, `terraform destroy`, any deployment, any AWS resource
  creation, any commit, any push.

---

## 15. Resume Point

Project now has a clear installation decision concept covering:

```
COST → REGION → AVAILABILITY → DATA → SECURITY →
PROJECT IDENTITY → MAKER / PROVENANCE → USER CONFIRMATION → INSTALLATION
```

Next: implement the installer (variables + tag strategy + wizard/CLI) as a **separate,
future task**, with human approval before any `terraform apply`.