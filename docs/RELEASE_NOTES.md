# Release Notes — Mays Orders

## v0.2.0-rc.1 (Candidate)
**Date:** 2026-10-11
**Baseline:** ce41de2

### Highlights
- Privacy Capability intern implementiert: inspect_subject, export_subject, erase_subject
- GSI2 Integration für subjectId-basierte Queries
- IAM Least Privilege Split für DynamoDB/GSI
- Installer Härtungen: AWS Profile/Context Validation, Workspace Safety, Artifact Integrity Gate
- Terraform Policy Gate stabil, Cognito Backup optional

### Tests
- Lambda Unit Tests 76 OK
- Installer Unit Tests 81 OK
- Privacy E2E VERIFIED, Security Negativtests fail-closed
- Terraform fmt/validate OK

### Known Limitations
- Dauerhafte Secret-Verwaltung/Rotation nicht implementiert (Ephemeral für Tests)
- Uncommitted Formatting-Änderungen in cognito_backup_automation/backend.tf ausstehend

### Changelog
Siehe `docs/reports/MAYS-ORDERS-PRIVACY-DESTROY-AND-RELEASE-01.md`

### Destroy Verification
Privacy-Testinstallation mays-orders-privacy-test vollständig entfernt: 37 Ressourcen gelöscht, State leer, kein verbleibender AWS-Ressourcenbestand.

---
**Status:** Release Candidate YELLOW — Produktionsfreigabe ausstehend bis Secret-Management geklärt.
