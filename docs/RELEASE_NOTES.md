# Release Notes — Mays Orders

RELEASE: v0.5.0-rc.2
Date: 2026-10-14
Baseline: adddca8 (Remote main); Tag zeigt auf Release-Commit inkl. dieser Doku
Vorgänger: v0.5.0-rc.1 → f6e737b (unverändert)

HARDENING (rc.2 — Incident-Aufarbeitung, keine neuen Produktfunktionen):
- AWS-Namenskollisions-Preflight `aws_project_collision` bei jedem validate/plan
  (read-only, Duplikat- + Ownership-Warnung; installer/core/collision_scan.py)
- Kontrollierter Abbau des mays-orders Backup-Stack-Rests: 20 Ressourcen,
  Plan-Isolation nachgewiesen, RIS-Installation unangetastet
- CLI-Flag `--guide` (Installer-Handbuch-Pfad + Inhaltsverzeichnis, read-only)
- Installer-Handbuch detailliert aktualisiert (Ablauf, Parallel-Installations-Warnung,
  Destroy-Nachweise, Bucket-ohne-force_destroy-Hinweis, Testmatrix)

VERIFICATION (2026-10-14 real ausgeführt):
- Installer Unit Tests 129/129 PASS (inkl. 19 Collision- + 9 Guide-Tests)
- Lambda Unit Tests 76/76 PASS
- Artifact Integrity 5/5 PASS
- Terraform fmt -check PASS, Terraform validate PASS
- git diff --check CLEAN, Secret-Audit CLEAN

LIMITATIONS:
- Kein produktives Secret-Management / keine Rotation (Produktion Privacy BLOCKED)
- Ownership-Klassifikation namensbasiert (State-Cross-Check offen)
- 9 Projektnamen-Treffer im Konto gehören RIS-Installation/Backend-Infra
- GitHub-Pre-Release manuell zu veröffentlichen

Details: docs/release/RELEASE-v0.5.0-rc.2.md (+ PDF)

---

# Historisch: v0.5.0-rc.1

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
