# Mays-Orders-AWS — Development Roadmap

**Status:** canonical roadmap
**Updated:** 2026-11-24
**Current main:** `0fc8972`
**Current release:** `v0.6.0-rc.1`

> This is the single canonical development roadmap. The older
> `docs/roadmap/future-extensions.md` is a historical idea catalogue and must not
> be used as the current status source.

## Status Legend

| Status | Meaning |
|---|---|
| `DONE` | Implemented and locally verified; evidence exists in the repository. |
| `IN PROGRESS` | Partially implemented or actively being completed; not release-complete. |
| `PLANNED` | Agreed/understood scope, no implementation yet. |
| `BLOCKED` | Cannot proceed without an owner, legal, security, infrastructure or external decision. |

## Roadmap

| ID | Area | Description | Status | Evidence | Dependencies / open decisions | Next concrete step |
|---|---|---|---|---|---|---|
| RC4-01 | RC4 | Release `v0.6.0-rc.1`, tag, GitHub pre-release, main merge and push | `DONE` | `docs/release/RELEASE-v0.6.0-rc.1.md/.pdf`; tag `5bc154e`; merge `82f7ae1`; main `7724c43` | Production not included | Keep release history immutable; decide next release separately |
| ORD-01 | Orders | Optional `orderDescription` (1–1.024 chars after trim, privacy-aware, additive) | `DONE` | `docs/reports/MO-ORDER-DESCRIPTION-01…03`; Lambda 456/456; ZIP `117299c9…`; `main` `0fc8972` | Client rollout after Lambda deployment | Deploy Lambda before clients use the field; no deployment yet |
| MB-01 | Module Builder | Presets `complete` and `orders-service`; explicit module selection | `DONE` | `module_builder/spec.py`; 129 builder tests | Existing module contract | Add only modules with a concrete consumer need |
| MB-02 | Module Builder | Deterministic Terraform/Lambda artifact generation | `DONE` | Two-build identity; Lambda ZIP SHA-256 `20f4bab5…` | Artifact freshness gate | Re-run after future module changes |
| MB-03 | Module Builder | Safe upgrade, fingerprints and user-file protection | `DONE` | `module_builder/upgrade.py`; upgrade tests/reports | None for current scope | Validate upgrades against real consumer projects |
| MB-04 | Module Builder | Versioned module contract for external consumers | `IN PROGRESS` | `orders-service` contract and reports | Q-03 placement/consumer decisions | Define consumer acceptance and version compatibility matrix |
| INST-01 | Installer | Validate, remote plan, deploy, destroy and state guards | `DONE` | CLI; installer 674 tests; lifecycle reports | Human mutation approval | Keep destructive operations separately gated |
| INST-02 | Installer | Policy Gate, context binding and artifact integrity | `DONE` | `terraform/policy/`, plan manifest, release reports | Q-09 rules | Extend only when a new resource type is introduced |
| INST-03 | Installer | Upgrade readiness, drift and backup evidence gates | `DONE` | P0A/P0B/P0C/P1/P3A reports and tests | Existing consumer evidence | Apply to a real upgrade when an approved target exists |
| SEC-01 | Security | IAM least privilege and exact ARNs | `DONE` | Terraform IAM modules and policy gate | None | Re-review on each new AWS resource |
| SEC-02 | Security | Secrets Manager, AWS_MANAGED and optional CMK reference | `DONE` | P00-C/P00-E code and reports | Customer CMK policy when used | Provision production secret only after owner approval |
| SEC-03 | Security | APP_MANAGED HMAC-SHA256, rotation and revocation mechanics | `DONE` | P00-D/P00-F code; rotation tests | Operational key transport and activation | Define production key custody and activation procedure |
| SEC-04 | Security | Production secret/KMS activation | `BLOCKED` | P00-F/P00-G reports | Q-11 operational activation; CMK key policy; production approval | Owner decision and security review |
| PRIV-01 | Privacy | Inspect/export/erase under internal trust boundary | `DONE` | Lambda privacy tests and reports | No public production activation | Keep behind approved internal boundary |
| PRIV-02 | Privacy | Retention/TTL and automatic deletion | `BLOCKED` | `MO-RC4-P00-G-RETENTION-DISABLED-01.md` | Q-05, Q-06, Q-07, Q-14 | Decide periods/semantics before any code |
| PRIV-03 | Privacy | DSGVO-oriented operating model | `BLOCKED` | Technical privacy reports | Legal basis, retention, deletion, processor and operational review | Owner/legal review; no conformity claim |
| RIS-01 | RIS integration | Versioned module contract and controlled consumer upgrades | `PLANNED` | Module contract exists; no RC4 consumer acceptance | Separate RIS path and pin decision | Agree a versioned handoff and compatibility gate |
| CI-01 | CI/CD | Existing security workflows (CodeQL, dependency and security checks) | `IN PROGRESS` | `.github/workflows/codeql.yml`, `dependency-check.yml`, `security.yml` | Current-run evidence and branch protection decisions | Inspect latest CI runs and document gaps |
| CI-02 | CI/CD | Full build/test/policy pipeline | `PLANNED` | Local suites and installer gates | CI runtime, credentials and cost decisions | Define required jobs and branch protection |
| PRD-01 | Production readiness | Production deployment approval and operating controls | `BLOCKED` | RC4 reports; production privacy remains blocked | Security/privacy approvals; deployment owner | Complete production readiness review |
| PRD-02 | Production readiness | Monitoring, backup and recovery operations | `IN PROGRESS` | CloudWatch/CloudTrail; backup/restore reports | Production RTO/RPO and restore drill | Execute an approved restore/operations drill |
| NEXT-01 | Next release | Scope, version and dependencies | `PLANNED` | No version assigned | Owner scope decision after production gates | Create a separate release-planning task |

## Open Decisions

| Decision | Status | Effect |
|---|---|---|
| Q-05 `tenantId` | `READY_FOR_OWNER` | Retention model and consumer isolation |
| Q-06 Retention periods | `BLOCKED_BY_EXTERNAL_DECISION` | No TTL or legal period may be invented |
| Q-07 Cancel anonymization | `READY_FOR_OWNER` | Cancel and erasure semantics |
| Q-14 Legacy without retention | `READY_FOR_OWNER` | No automatic backfill or deletion |
| Q-11 P00-F operation | P00-D contract approved; operational activation open | Warm-environment revocation, existing signatures, key transport |
| Q-12 Release label | `APPROVED — v0.6.0-rc.1` | Closed; do not reopen |
| Production privacy activation | `BLOCKED` | No production secret/retention rollout |
| CMK key policy (external key) | `BLOCKED` | Required before using a customer-managed key |

## Release Boundary

`v0.6.0-rc.1` is a published release candidate with a verified AWS Development
lifecycle. It is **not** a production activation. The tag points to the release
commit; README, PDF and post-merge documentation are later documentation
commits on `main`/the release branch and are not part of the tagged tree.
