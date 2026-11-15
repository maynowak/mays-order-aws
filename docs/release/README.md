# Release Directory — Purpose and Conventions

This directory contains official release documents, technical RC4 release
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
| Technical detail package | `MAYS-ORDERS-AWS-v0.6.0-rc.1.pdf` |
| Release images | `img/`, `RELEASE-v0.5.0-rc.2-COVER.png` |

## Relocated Internal Documents

The following internal RC4 documents were moved out of `docs/release/` to
their functional homes. Historical reports and audit logs retain their original
references as historical evidence; current documentation uses the new paths.

| Former path | Current path |
|---|---|
| `docs/release/MO-RC4-P00-ADR-008-CONTRACT-COMPARISON.md` | `docs/adr/MO-RC4-P00-ADR-008-CONTRACT-COMPARISON.md` |
| `docs/release/MO-RC4-P00-DECISION-REGISTER.md` | `docs/adr/MO-RC4-P00-DECISION-REGISTER.md` |
| `docs/release/MO-RC4-P00-C-F01-Q09-AMENDMENT-PROPOSAL.md` | `docs/reports/MO-RC4-P00-C-F01-Q09-AMENDMENT-PROPOSAL.md` |
| `docs/release/MO-RC4-P00-DEPENDENCY-GRAPH.md` | `docs/roadmap/MO-RC4-P00-DEPENDENCY-GRAPH.md` |
| `docs/release/MO-RC4-P00-EXECUTION-PLAN.md` | `docs/roadmap/MO-RC4-P00-EXECUTION-PLAN.md` |
| `docs/release/MO-RC4-P00-IMPLEMENTATION-BACKLOG.md` | `docs/roadmap/MO-RC4-P00-IMPLEMENTATION-BACKLOG.md` |

The release directory now contains only official release documents, technical
release dossiers, historical release evidence and release assets.

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
