# Release Directory — Purpose and Conventions

This directory contains the official release record, technical RC4 release
dossiers, historical release evidence and the assets needed by those documents.

## Naming Convention

Official release documents use:

```text
RELEASE-v<version>.md
RELEASE-v<version>.pdf
```

Examples:

- `RELEASE-v0.4.0.md` / `RELEASE-v0.4.0.pdf`
- `RELEASE-v0.5.0-rc.1.md` / `RELEASE-v0.5.0-rc.1.pdf`
- `RELEASE-v0.5.0-rc.2.md` / `RELEASE-v0.5.0-rc.2.pdf`
- `RELEASE-v0.5.0-rc.3.md` / `RELEASE-v0.5.0-rc.3.pdf`
- `RELEASE-v0.6.0-rc.1.md` / `RELEASE-v0.6.0-rc.1.pdf`

Historical release documents are retained unchanged under this convention.

## Directory Contents

| Category | Files / purpose |
|---|---|
| Official release documents | `RELEASE-v*.md` and `RELEASE-v*.pdf` |
| Technical RC4 dossiers | `RC4-MODULE-RELEASE-CANDIDATE.md`, `RC4-INTEGRATION-MANIFEST.md` |
| Historical release evidence | `RELEASE-GATES-v0.5.0-rc.3.md` |
| RC4 decision and planning record | `MO-RC4-P00-DECISION-REGISTER.md`, dependency graph, execution plan and implementation backlog |
| Internal proposals | `MO-RC4-P00-C-F01-Q09-AMENDMENT-PROPOSAL.md`, `MO-RC4-P00-ADR-008-CONTRACT-COMPARISON.md` |
| Technical detail package | `MAYS-ORDERS-AWS-v0.6.0-rc.1.pdf` |
| Release images | `img/`, `RELEASE-v0.5.0-rc.2-COVER.png` |

## Why Historical Internal Documents Remain Here

The `MO-RC4-P00-*` decision and planning documents are not official release
notes, but they are deliberately kept at their existing paths. Historical
reports and audit logs reference these exact paths. Moving them would break
the historical record, which takes precedence over an idealized directory
layout.

The RC4 integration manifest and release-candidate dossier are technical
release records. They remain in this directory because they are part of the
release evidence and are referenced by current and historical documentation.

## GitHub Release Asset

`MAYS-ORDERS-AWS-v0.6.0-rc.1.pdf` is the technical detail package currently
attached to the GitHub pre-release. It is not removed or replaced by this
directory policy. Any asset replacement requires separate owner approval.

## Known Historical Asset Gap

`RELEASE-v0.4.0.md` references five images that are not present in the
checkout:

- `img/mays-orders-release-overview.png`
- `img/mays-orders-architecture.png`
- `img/mays-orders-e2e-flow.png`
- `img/mays-orders-project-journey.png`
- `img/mays-orders-ecosystem.png`

This is a pre-existing documentation gap. No replacement graphic was
generated and no historical release document was rewritten. The gap remains
documented rather than silently repaired.

## No Additional Subdirectories

This policy intentionally creates no new subdirectories. The existing
`img/` directory remains the release-image location.
