# May's Orders — AI Developer Profile

> **Status:** Concept / installation preparation — documentation only. No IAM resources, no
> policies, no boundaries, no credentials are implemented or created by this page.
> **Audience:** Human Developer, AI coding agents, reviewers.

## 1. Purpose

This page defines a clear recommendation for a **dedicated AWS CLI identity/profile for the AI
Developer** during the May's Orders installation process. The goal is clean **identity
separation** between the *Human Developer* and the *AI Developer*, so that governance,
least privilege and audit/provenance stay understandable — without ever storing credentials in
the repository.

## 2. Why separate identities are recommended

Using a distinct AI Developer identity supports:

- **Least privilege** — the AI identity can be granted only the minimum permissions needed.
- **Independent IAM policy/boundary governance** — human and AI roles can evolve separately.
- **Clearer audit/provenance** — CloudTrail activity is attributable to the correct actor.
- **Safer AI-assisted work** — a mis-applied agent action is easier to detect and contain.
- **Explicit human approval** — the human boundary remains distinct from the automated identity.

## 3. Human Developer vs. AI Developer

| Dimension | Human Developer | AI Developer |
|---|---|---|
| Actor | a person | an AI coding agent |
| Decision authority | final technical + approval decisions | proposals, constrained execution |
| Approval | owns `terraform apply`/destroy release | never deploys without human release |
| Identity | own AWS CLI profile | separate recommended profile |
| Provenance tag (conceptual) | `Actor = HumanDeveloper` | `Actor = AIDeveloper` |

These are governance concepts, not a statement that two IAM roles already exist in Terraform
today (see §11).

## 4. Recommended profile

Recommended AWS CLI profile name:

```
maysOrdersAiDeveloper
```

This is a **recommendation**, not a hard requirement. The installer must **not** silently create
or modify AWS credentials, and the user may select an existing AWS CLI profile instead.

## 5. AWS CLI profile concept

The AI Developer uses the standard AWS CLI credential/profile mechanism — configured **outside**
this repository (`~/.aws/config` + `~/.aws/credentials`, or equivalents managed by the user).

```text
Human Developer                    AI Developer
      |                                  |
      v                                  v
Human AWS CLI profile             AI AWS CLI profile
                                    maysOrdersAiDeveloper
```

## 6. Credential safety

- AWS credentials **remain outside Git** and are never committed to the repository.
- This repository contains **no** access keys, secret keys, session tokens, passwords or
  credential files.
- Credentials are managed exclusively through the user's normal AWS CLI / credential mechanism.
- Only the **profile name** (`maysOrdersAiDeveloper`) and setup *procedure* are documented here.

## 7. Installation workflow

```text
May's Orders Installation
        |
        v
Identity / IAM Capability
        |
        v
AI Developer Setup
        |
        v
"Separate AI Developer AWS CLI profile is recommended."
        |
   +----+------------------+
   |                       |
   v                       v
recommended profile   existing profile
maysOrdersAiDeveloper selected by user
   |                       |
   +-----------+-----------+
               |
               v
           AWS CLI
               |
               v
         AI Developer
               |
               v
       Terraform / Agent
```

The installer recommends, but never forces, the profile choice.

## 8. Example configuration (placeholders only — no real credentials)

```ini
# ~/.aws/credentials  (illustrative — use placeholders, never real keys)
[maysOrdersAiDeveloper]
aws_access_key_id     = AKIA################
aws_secret_access_key = ########################################
```

```ini
# ~/.aws/config  (illustrative)
[profile maysOrdersAiDeveloper]
region = eu-central-1
output = json
```

```bash
# Use the dedicated profile for AI-assisted Terraform operations
export AWS_PROFILE=maysOrdersAiDeveloper
terraform plan
```

Replace `AKIA###…` / `###…` with values managed **outside** the repository. Never paste real
credentials into any repo file or log.

## 9. Relationship to Terraform

- Terraform uses the **active AWS CLI profile** to authenticate plan/apply operations against
  the target account.
- The repository's Terraform code describes **Lambda runtime IAM** (the `mays-orders-handler-role`
  execution role) — it does **not** describe the AI Developer's deployment identity.
- The AI Developer profile is a **deployment identity** concern, orthogonal to the runtime IAM
  resources in `terraform/modules/iam/`.

## 10. Relationship to Policy Gate

The Policy Gate (`terraform/policy/`, `docs/TERRAFORM_POLICY_GATE.md`) is a governance check
between `terraform plan` and `terraform apply`. It is profile-agnostic: whichever AWS identity
runs Terraform, the plan must still satisfy the encoded rules.

- The AI Developer profile does **not** bypass the gate.
- The gate does **not** encode AI vs. human identity — identity separation is expressed through
  the AWS profile + (conceptually) governance tags, not through the gate.

Governance tags remain conceptual and **not** mandatory (see §13): `Actor = AIDeveloper`,
`Role = Developer`, `AIManaged = true`, `ApprovalPolicy = HumanApprovalRequired`.

## 11. Human approval boundary

Separation of identities enables a clear approval boundary:

```text
Human Developer
      |
      +--------------------+
      |                    |
      v                    v
Human AWS CLI         AI Developer AWS CLI
   profile              maysOrdersAiDeveloper
      |                    |
      v                    v
Human identity        AI identity
      |                    |
      +---------+----------+
                |
                v
          Terraform Plan
                |
                v
           Policy Gate
                |
                v
         Human Approval
                |
                v
     Controlled Terraform Apply
```

> This diagram represents the **governance flow**, not a claim that two IAM roles are already
> implemented in Terraform.

`terraform apply`, `terraform destroy`, cost-increasing or architecture-changing operations still
require explicit human approval regardless of which profile runs the plan (see
`docs/AGENTS.md` — Commit-/Push-Regel).

## 12. Relationship to future IAM Capability Preflight

The **IAM Capability Preflight** is a separate, future installation mechanism that will verify —
before or during installation — that the target AWS environment permits the required IAM
operations/resources.

- This page is **preparation/documentation only** and does **not** implement the preflight.
- The AI Developer profile is part of *deciding which identity* performs installation; the
  preflight is part of *verifying what the identity is allowed to do*.
- Do not conflate them.

## 13. Governance tag relationship (conceptual, not implemented)

The following governance tags are referenced conceptually but are **not** new mandatory tags and
are **not** implemented in the Policy Gate in this task:

| Tag | Conceptual value for AI Developer |
|---|---|
| `Actor` | `AIDeveloper` |
| `Role` | `Developer` |
| `AIManaged` | `true` |
| `ApprovalPolicy` | `HumanApprovalRequired` |

## 14. Troubleshooting / profile verification

Safely verify the active identity (read-only, no credential exposure):

```bash
# Which identity/profile will Terraform use?
aws sts get-caller-identity --profile maysOrdersAiDeveloper
```

- Confirm the reported `Account` and `Arn` match the intended AI Developer identity.
- If the profile is not found, verify `~/.aws/config` / `~/.aws/credentials` outside the repo.
- If permissions are insufficient, resolve them via AWS IAM (outside this repository) — never by
  broadening the repository's Lambda runtime policy.

## 15. Personality / profile choice

- `maysOrdersAiDeveloper` is a **recommendation**.
- The user may reuse an existing AWS CLI profile instead.
- The installer must never mutate AWS credentials on the user's behalf.

## 16. Security notes

- Never store credentials in Git, logs, reports, README, or issue text.
- Never log `AWS_SECRET_ACCESS_KEY` / session tokens.
- Prefer short-lived credentials / role assumption where the account setup supports it.
- The AI Developer identity should carry the minimum permissions required — reinforce
  least privilege, do not grant `AdministratorAccess`.

---

Full installation concept: `architecture/installation-concept.md` (§8.1).
Execution log: `docs/reports/AI-DEVELOPER-PROFILE-SETUP-EXECUTION-LOG.md`.