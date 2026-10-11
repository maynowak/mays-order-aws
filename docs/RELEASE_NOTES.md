# Release Notes — Mays Orders

RELEASE: v0.5.0-rc.1
Date: 2026-10-11
Baseline: f6e737b

FEATURES:
- Privacy inspect_subject (intern, GSI2)
- Privacy export_subject (intern, JSON/Decimal, Pagination)
- Privacy erase_subject (intern, fail-closed)
- DynamoDB GSI2 subjectId-status-index
- Interner Privacy Invoke Dispatch ohne öffentliche API-Route

IMPROVEMENTS:
- Installer AWS Profile Resolution & Context Validation
- Terraform Workspace Isolation & Plan Discovery
- Optional Cognito Backup Module (enable_cognito_backup)
- Lambda Artifact Integrity Gate
- Terraform Policy Gate stabil

FIXES:
- Decimal JSON Serialization
- DynamoDB reserved keyword `status` Alias
- Lambda Packaging Staleness Gate

VERIFICATION:
- Lambda Unit Tests 76 OK
- Installer Unit Tests 81 OK
- Artifact Integrity 5 OK
- Terraform fmt -check OK
- Terraform validate OK
- Historische AWS E2E VERIFIED
- Destroy Lifecycle VERIFIED (37 Deletes)

LIMITATIONS:
- Kein produktives Secret-Management
- Keine automatische Secret-Rotation
- Privacy-Funktionen nicht für produktive Nutzung freigegeben
- Uncommitted Formatting-Änderungen in cognito_backup_automation/backend.tf ausstehend

Changelog: siehe docs/reports/MAYS-ORDERS-PRIVACY-DESTROY-AND-RELEASE-01.md

Status: Release Candidate YELLOW
