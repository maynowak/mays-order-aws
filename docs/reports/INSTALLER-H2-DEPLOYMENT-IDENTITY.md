# H2 — Versioned Deployment Identity, Plan Isolation & AWS Tagging Report

**Date:** 2026-09-19
**Status:** ✅ COMPLETED
**Milestone:** H2 (Post-H1 Checkpoint)

---

## Executive Summary

Extended the installer with versioned deployment identity, plan isolation, and AWS resource tagging to enable multiple projects to safely coexist in the same AWS account/region. All 125 tests passing (125/125).

---

## Implementation Summary

### H2-1: Deployment Identity ✅
**File:** `installer/core/deployment_identity.py`

- **DeploymentId** class: canonical identity `<account>:<project>:<environment>`
- Example: `240571105849:mays-orders:development`
- Version explicitly excluded from identity (upgrade = same deployment)
- Case-insensitive environment matching
- Available via `InstallationContext.get_deployment_id()` and `get_deployment_context()`

### H2-2: Versioned Development State ✅
**File:** `installer/core/deployment_identity.py`

- **SemanticVersion**: `major.minor.patch` parsing/comparison
- **DevelopmentPhase**: phase identifier (H2, D8, etc.) + step number
- **DevelopmentState**: combines version + phase + status
- **DevelopmentStatus** enum: development, testing, staging, production, archived
- **VersionComparison** enum: SAME, DEVELOPMENT_UPDATE, PATCH_UPDATE, MINOR_UPGRADE, MAJOR_UPGRADE, MIGRATION_REQUIRED, INCOMPATIBLE

### H2-3: Plan Identity ✅
**File:** `installer/core/deployment_identity.py`, `installer/cli/main.py`

- **PlanMetadata**: deployment_id, version, development_phase, operation, sequence_number
- **Filename format**: `<project>-<environment>-<version>-<phase>-<account>-<operation>-<sequence>.tfplan`
  - Deploy: `mays-orders-development-0.3.0-H2-240571105849-deploy-0042.tfplan`
  - Destroy: `mays-orders-development-0.3.0-H2-240571105849-destroy-0043.tfplan`
- **PlanSequenceManager**: monotonically increasing sequence per deployment+operation
- Metadata saved as `.meta.json` alongside plan
- Deployment context saved as `.context.json`

### H2-4: Plan Discovery / Auto-Selection ✅
**File:** `installer/core/deployment_identity.py`, `installer/cli/main.py`

- **PlanDiscovery** class with hardened filtering
- `find_plans()` / `find_latest_plan()` filter by: DeploymentId, Version, DevelopmentPhase, Operation
- `validate_plan_context()` validates plan file matches expected deployment identity
- Auto-detection uses hardened filtering (not just newest file)
- `--yes` CANNOT bypass context/version/phase mismatch

### H2-5: Destroy Isolation ✅
**File:** `installer/cli/main.py`

- Destroy explicitly scoped to current DeploymentId
- Plan validation rejects destroy plans from different deployments
- Resources with ambiguous ownership surfaced, not silently adopted
- H1 destroy safety mechanisms preserved

### H2-6: AWS Resource Tagging ✅
**File:** `installer/core/deployment_identity.py`

- **TagSet** class with canonical tags:
  - Identity: Project, Environment, DeploymentId
  - Version/Development: Version, DevelopmentPhase, DevelopmentStep
  - Governance: ManagedBy, Owner, Maker
  - System/Component: System, Component
  - Custom: prefixed with `Custom:`
- `merge_with_existing()` preserves unrelated tags, canonical tags take precedence
- `TagSet.from_context()` factory from DeploymentContext

### H2-7: Existing Resource / Upgrade Awareness ✅
**File:** `installer/core/deployment_identity.py`

- **OwnershipAnalyzer** classifies resources:
  - `OWNED` — current deployment
  - `FOREIGN` — different project/env/account
  - `AMBIGUOUS` — same deployment ID, different version/phase
  - `UNMANAGED` — no deployment metadata
- `is_destroyable_by()` check for safe destroy
- Ambiguous ownership surfaced, not silently adopted

### H2-8: Configuration / Context Separation ✅
**File:** `installer/core/deployment_identity.py`, `installer/core/context.py`

- **INSTALLER CONTEXT**: installer_name, installer_version, installer_commit
- **TARGET CONTEXT**: account, region, project, environment, deployment_id, version, development_phase/step
- `DeploymentContext` class separates concerns
- `InstallationContext.get_deployment_context()` factory
- CLI arguments for H2 fields: `--deployment-version`, `--development-phase`, `--development-step`, `--development-status`

### H2-9: Tests ✅
All 125 tests passing (46 installer + 51 lambda + 28 scripts)

### H2-10: Documentation ✅
- `docs/INSTALLER-LIFECYCLE.md` — H2 section added
- `docs/reports/INSTALLER-H2-DEPLOYMENT-IDENTITY.md` — this report

---

## Plan Naming Examples

```
# Deploy plans
mays-orders-development-0.1.0-H2-240571105849-deploy-0001.tfplan
mays-orders-development-0.3.0-H217-240571105849-deploy-0042.tfplan
mays-orders-production-1.0.0-H2-240571105849-deploy-0100.tfplan

# Destroy plans
mays-orders-development-0.1.0-H2-240571105849-destroy-0001.tfplan
mays-orders-development-0.3.0-H217-240571105849-destroy-0043.tfplan
```

**Components:**
| Component | Example |
|-----------|---------|
| Project | mays-orders |
| Environment | development |
| Version | 0.3.0 |
| Phase | H2 or H217 |
| Account | 240571105849 |
| Operation | deploy / destroy |
| Sequence | 0001, 0042, 0100 |

---

## Deployment ID Examples

```
# Development
240571105849:mays-orders:development

# Production
240571105849:mays-orders:production

# Different project, same account
240571105849:other-project:development
```

---

## Tagging Model

### Required Identity Tags
| Tag | Value | Source |
|-----|-------|--------|
| Project | mays-orders | context.project_name |
| Environment | development | context.environment |
| DeploymentId | 240571105849:mays-orders:development | deployment_id |

### Version/Development Tags
| Tag | Value | Source |
|-----|-------|--------|
| Version | 0.3.0 | context.deployment_version |
| DevelopmentPhase | H217 | context.development_phase + step |
| DevelopmentStep | 17 | context.development_step |

### Governance Tags
| Tag | Value | Default |
|-----|-------|---------|
| ManagedBy | mays-installer | Fixed |
| Owner | (configurable) | None |
| Maker | (configurable) | None |

### System/Component Tags
| Tag | Value | Default |
|-----|-------|---------|
| System | mays-orders | context.system_name |
| Component | api | context.component_name |

### Custom Tags
| Prefix | Example |
|--------|---------|
| Custom: | Custom:CostCenter=IT |

---

## Existing-Resource Handling

| Ownership | Description | Destroyable |
|-----------|-------------|-------------|
| OWNED | Current deployment | ✅ Yes |
| FOREIGN | Different project/env/account | ❌ No |
| AMBIGUOUS | Same ID, different version/phase | ❌ No (surfaced) |
| UNMANAGED | No deployment tags | ❌ No |

**Rule:** Ambiguous ownership surfaced, never silently adopted.

---

## Future Upgrade TODOs

1. **Migration Execution** — Not yet implemented; metadata/comparison model established
2. **State Migration** — Terraform state migration between versions not implemented
3. **Cross-Deployment References** — Validation for cross-deployment dependencies
4. **Rollback Automation** — Automated rollback on failed upgrade not implemented

---

## Security Review

| Check | Status |
|-------|--------|
| No AWS credentials in repo | ✅ |
| No secrets in logs | ✅ |
| No state files committed | ✅ |
| .terraform/ ignored | ✅ |
| Plan sanitization active | ✅ |
| AWS profile/account/region boundary | ✅ |
| Plan identity validation | ✅ |
| --yes cannot bypass context mismatch | ✅ |
| Destroy isolation enforced | ✅ |
| H1 safety gates intact | ✅ |

---

## Git Status

### Files Changed
| File | Change |
|------|--------|
| `installer/core/deployment_identity.py` | New — H2 models |
| `installer/core/context.py` | Modified — H2 fields, DeploymentContext integration |
| `installer/cli/main.py` | Modified — H2 CLI args, plan naming, PlanDiscovery |
| `docs/INSTALLER-LIFECYCLE.md` | Modified — H2 section added |
| `docs/reports/INSTALLER-H2-DEPLOYMENT-IDENTITY.md` | New — This report |

### Test Results
```
125/125 PASSING
├── installer/tests:  46/46
├── lambda/tests:     51/51
└── scripts/tests:    28/28
```

### Current Commit
```
<to be committed>
```

### Proposed Immutable Tag
```
mays-installer-h2-deployment-identity-20260919
```

---

## Next Milestone

H2 → Immutable Git Checkpoint → D8 CI/CD → H3 Hardening → Shell GUI → MI Integration

**NO D8 IMPLEMENTATION STARTED.**