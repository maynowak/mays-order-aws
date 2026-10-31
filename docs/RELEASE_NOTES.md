# Release Notes — Mays Orders

RELEASE: v0.5.0-rc.3 (Pre-Release Candidate — Module Builder & RIS Integration)
Date: 2026-10-31
Baseline: v0.5.0-rc.2 -> 5cf50a0; Tag zeigt auf den Packaging-Commit inkl. dieser Doku
Vorgaenger: v0.5.0-rc.2 -> 5cf50a0 (unveraendert)

FEATURES:
- Terraform Module Builder `python -m module_builder` mit zwei Presets:
  `complete` (11 Module) und `orders-service` (wiederverwendbares 7-Modul-Vertragsmodul)
- Freie Modulauswahl `--modules` (fail-closed) und `--with-deps` (transitive Pflicht-Deps)
- Policy-Gate wird in generierte Projekte uebernommen (projektspezifische resource-policy.json)
- Reproduzierbare Lambda-/Cognito-Backup-Artefakte, SHA-256 im Builder-Manifest
- EXTERNAL-Cognito-Modus (MANAGED bleibt Default, fail-closed validiert)
- Orders-Service-Modulvertrag: 6 Inputs, 20 Outputs, Quelle via path.module

SECURITY:
- F-03 behoben: SQS-Resource-Policy mit Principal="*" entfernt (Zugriff nur via IAM)
- IAM-Portabilitaet: `lambda_execution_boundary` default null, kein hartcodiertes Konto
- GAP-06: plan-stabiles SQS-Gate `count = var.sqs_enabled ? 1 : 0`

INTEGRATION (RIS):
- RIS pinnt Builder 1dbb0cb; code-identisch zum Release (`git diff -w` leer)
- RIS-MO-RC-01 (2026-10-30, Konto 262370457690): Plan 169 add -> Apply -> No-Op ->
  7/7 Live-Tests inkl. SQS->Worker->DynamoDB (PENDING->CONFIRMED) -> Destroy -> CLEAN

VERIFICATION (2026-10-31 lokal erneut ausgefuehrt):
- Lambda 76/76 PASS, Module Builder 90/90 PASS, Installer 81/81 PASS
- terraform init 0, validate PASS, fmt -check 0
- Generiertes orders-service-Modul: init/validate/fmt PASS

LIMITATIONS:
- Privacy-Produktivbetrieb BLOCKED (Secret-Management/Rotation offen)
- IAM-Portabilitaet in EINEM Testkonto belegt = keine allgemeine Multi-Account-Produktionsreife
- F-01: explizit gesetzter Boundary-ARN bleibt cross-account-Frage
- EXTERNAL-Cognito: id/arn/group = null; MANAGED->EXTERNAL nicht automatisiert
- RIS-Pin noch 1dbb0cb (kosmetisch); Tag/GitHub-Release menschlich

Details: docs/release/RELEASE-v0.5.0-rc.3.md (+ PDF), docs/release/RELEASE-GATES-v0.5.0-rc.3.md

---

# Historisch: v0.5.0-rc.2

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
