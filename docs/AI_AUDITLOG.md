==================================================
EXECUTION LOG / CRASH RECOVERY — MANDATORY
==================================================

Maintain a current execution log throughout the audit:

docs/reports/[NO. OF TASK ++]-[SUBWORKING NO.]-[TASK]-EXECUTION_LOG.md

This is mandatory even though the audit is READ-ONLY.

The execution log must be created or updated continuously after
meaningful audit milestones, NOT only at the end.

The log must preserve the latest verified state so that work can be
resumed safely after an agent crash, terminal failure, streaming
failure, IDE restart, or interrupted session.

Record only verified facts. Never invent findings or validation results.

The execution log must contain:

- current status
- audit date/time
- current Git branch and HEAD
- audit scope
- completed audit sections
- actual findings
- evidence / file references
- GREEN / YELLOW / ORANGE / RED / GRAY classification
- Terraform checks actually executed and their results
- Git status
- files changed, if any
- explicit confirmation when no files were changed
- open questions
- risks
- recommended next actions
- current resume point

After each major section, update the execution log before continuing.

At the end, finalize the log with the complete audit summary.

IMPORTANT:
The execution log itself is part of the audit workflow and must be
kept accurate even if the audit remains completely read-only.

==================================================

## SUBAGENT-REPORT-PFLICHT (verbindlich)

Jeder beauftragte Subagent (Research/Explore/Review — read-only oder schreibend)
liefert sein Ergebnis als strukturierten Report nach den 16 Pflichtpunkten des
Execution-Log-Templates oben. Die Agenten-Beschreibung (Prompt) MUSS diese
Report-Pflicht ausdrücklich enthalten. Der Orchestrator trägt die Subagent-
Reports eigenständig nach unter:

    docs/reports/<TASK-ID>-<SUBWORKING>-<AUFGABE>-EXECUTION_LOG.md

und indiziert sie unten im AUDIT LOG INDEX. So sind Research-Ergebnisse
crash-sicher, revisionsfähig und für Folge-Checkpoints wiederverwendbar —
der Chatverlauf ist keine Recovery-Quelle.

==================================================

## AUDIT LOG INDEX

Current Branch: main
Latest HEAD: siehe `git log -1` (RC.3-Basis vor diesem Doku-Commit: `8b61922`)

The following tasks have been completed with reports in docs/reports/:
- B8.6 FINAL-CONSISTENCY-RECOVERY-AUDIT-AND-DOCUMENTATION-01 → docs/reports/BACKUP-08.6-FINAL-REMOTE-STATE-RECOVERY-AUDIT.md
- COGNITO-ORPHAN-CLEANUP-01 → docs/reports/COGNITO-ORPHAN-CLEANUP-01-OWNERSHIP-AUDIT.md
- COGNITO-ORPHAN-CLEANUP-02 → docs/reports/COGNITO-ORPHAN-CLEANUP-02-EXECUTION.md
- COGNITO-BACKUP-01 → docs/reports/COGNITO-BACKUP-01-BACKUP-RECOVERY-AUDIT.md
- COGNITO-BACKUP-02 → docs/reports/COGNITO-BACKUP-02-MULTI-PROJECT-USER-DATA-BACKUP-DESIGN.md
- COGNITO-BACKUP-03 → docs/reports/COGNITO-BACKUP-03-IMPLEMENTATION.md
- COGNITO-BACKUP-03A → docs/reports/COGNITO-BACKUP-03A-IAM-TERRAFORM-VALIDATION.md
- COGNITO-BACKUP-03B → docs/reports/COGNITO-BACKUP-03B-AWS-INTEGRATION.md
- COGNITO-BACKUP-03C → docs/reports/COGNITO-BACKUP-03C-FIRST-REAL-BACKUP.md
- COGNITO-INFRA-RECREATE-01 → docs/reports/COGNITO-INFRA-RECREATE-01-PRECHECK.md
- COGNITO-INFRA-RECREATE-02 → docs/reports/COGNITO-INFRA-RECREATE-02-APPLY.md
- MAYS-ORDERS-DSGVO-PRIVACY-ERASURE-01 → docs/reports/MAYS-ORDERS-DSGVO-PRIVACY-ERASURE-01.md
- MAYS-ORDERS-PRIVACY-SECURITY-GATE-01 → docs/reports/MAYS-ORDERS-PRIVACY-SECURITY-GATE-01.md
- MAYS-ORDERS-PRIVACY-INTERNAL-FINALIZATION-01 → docs/reports/MAYS-ORDERS-PRIVACY-INTERNAL-FINALIZATION-01.md
- MAYS-ORDERS-PRIVACY-TRUST-FIX-01 → docs/reports/MAYS-ORDERS-PRIVACY-TRUST-FIX-01.md
- MAYS-ORDERS-DSGVO-PRIVACY-INTEGRATION-01 → docs/reports/MAYS-ORDERS-DSGVO-PRIVACY-INTEGRATION-01.md
- MAYS-ORDERS-PRIVACY-GSI2-INTEGRATION-FIX-01 → docs/reports/MAYS-ORDERS-PRIVACY-GSI2-INTEGRATION-FIX-01.md
- MAYS-ORDERS-PRIVACY-GSI2-PROJECTION-FIX-01 → docs/reports/MAYS-ORDERS-PRIVACY-GSI2-PROJECTION-FIX-01.md
- MAYS-ORDERS-PRIVACY-INTEGRATION-READINESS-01 → docs/reports/MAYS-ORDERS-PRIVACY-INTEGRATION-READINESS-01.md
- MAYS-ORDERS-PRIVACY-AWS-TEST-PREFLIGHT-01 → docs/reports/MAYS-ORDERS-PRIVACY-AWS-TEST-PREFLIGHT-01.md
- MAYS-ORDERS-PRIVACY-INTEGRATION-FIX-01 → docs/reports/MAYS-ORDERS-PRIVACY-INTEGRATION-FIX-01.md
- MAYS-ORDERS-PRIVACY-IAM-LEAST-PRIVILEGE-01 → docs/reports/MAYS-ORDERS-PRIVACY-IAM-LEAST-PRIVILEGE-01.md
- MAYS-ORDERS-PRIVACY-INSTALLER-TEST-PLAN-01 → docs/reports/MAYS-ORDERS-PRIVACY-INSTALLER-TEST-PLAN-01.md
- MAYS-ORDERS-PRIVACY-PLAN-EXECUTION-01 → docs/reports/MAYS-ORDERS-PRIVACY-PLAN-EXECUTION-01.md
- MAYS-ORDERS-PRIVACY-E2E-LIFECYCLE-01 → docs/reports/MAYS-ORDERS-PRIVACY-E2E-LIFECYCLE-01.md
- MAYS-ORDERS-MULTIPROJECT-CLI-FIX-AND-TEST-01 → docs/reports/MAYS-ORDERS-MULTIPROJECT-CLI-FIX-AND-TEST-01.md
- MAYS-ORDERS-S3-STATE-ISOLATION-AUDIT-01 → docs/reports/MAYS-ORDERS-S3-STATE-ISOLATION-AUDIT-01.md
- MAYS-ORDERS-PRIVACY-E2E-INSTALL-01 → docs/reports/MAYS-ORDERS-PRIVACY-E2E-INSTALL-01.md
- MAYS-ORDERS-COGNITO-STATE-FORENSICS-01 → docs/reports/MAYS-ORDERS-COGNITO-STATE-FORENSICS-01.md
- MAYS-ORDERS-PLAN-DISCOVERY-STATE-CONSISTENCY-01 → docs/reports/MAYS-ORDERS-PLAN-DISCOVERY-STATE-CONSISTENCY-01.md
- MAYS-INSTALLER-METADATA-PARALLEL-CONSISTENCY-01 → docs/reports/MAYS-INSTALLER-METADATA-PARALLEL-CONSISTENCY-01.md
- MAYS-ORDERS-INSTALLER-METADATA-LIFECYCLE-FIX-01 → docs/reports/MAYS-ORDERS-INSTALLER-METADATA-LIFECYCLE-FIX-01.md
- MAYS-ORDERS-PLAN-METADATA-LIFECYCLE-CONSOLIDATION-01 → docs/reports/MAYS-ORDERS-PLAN-METADATA-LIFECYCLE-CONSOLIDATION-01.md
- MAYS-ORDERS-INSTALLER-END-TO-END-COMPLETION-01 → docs/reports/MAYS-ORDERS-INSTALLER-END-TO-END-COMPLETION-01.md
- MAYS-INSTALLER-METADATA-Vergleich-Orders-RIS → docs/reports/MAYS-INSTALLER-METADATA-Vergleich-Orders-RIS.md
- MAYS-ORDERS-INSTALLER-AWS-PROFILE-CONTEXT-FIX-01 → docs/reports/MAYS-ORDERS-INSTALLER-AWS-PROFILE-CONTEXT-FIX-01.md
- MAYS-ORDERS-PRIVACY-DEPLOY-RETRY-01 → docs/reports/MAYS-ORDERS-PRIVACY-DEPLOY-RETRY-01.md
- MAYS-ORDERS-PRIVACY-BACKUP-OPTIONAL-01 → docs/reports/MAYS-ORDERS-PRIVACY-BACKUP-OPTIONAL-01.md
- MAYS-ORDERS-PRIVACY-E2E-VERIFY-01 → docs/reports/MAYS-ORDERS-PRIVACY-E2E-VERIFY-01.md
- MAYS-ORDERS-PRIVACY-RUNTIME-FIX-01 → docs/reports/MAYS-ORDERS-PRIVACY-RUNTIME-FIX-01.md
- MAYS-ORDERS-LAMBDA-ARTIFACT-INTEGRITY-01 → docs/reports/MAYS-ORDERS-LAMBDA-ARTIFACT-INTEGRITY-01.md
- MAYS-ORDERS-PRIVACY-FINAL-E2E-ACCEPTANCE-01 → docs/reports/MAYS-ORDERS-PRIVACY-FINAL-E2E-ACCEPTANCE-01.md
- MAYS-ORDERS-PRIVACY-SECRET-E2E-01 → docs/reports/MAYS-ORDERS-PRIVACY-SECRET-E2E-01.md
- MAYS-ORDERS-PRIVACY-FINAL-EVIDENCE-AND-DESTROY-01 → docs/reports/MAYS-ORDERS-PRIVACY-FINAL-EVIDENCE-AND-DESTROY-01.md
- MAYS-ORDERS-PRIVACY-DESTROY-AND-RELEASE-01 → docs/reports/MAYS-ORDERS-PRIVACY-DESTROY-AND-RELEASE-01.md
- MAYS-ORDERS-RELEASE-CANDIDATE-HARDENING-01 → docs/reports/MAYS-ORDERS-RELEASE-CANDIDATE-HARDENING-01.md (Nachtrag: Eintrag fehlte im Index)
- MAYS-ORDERS-RC-DOCUMENTATION-FINAL-REVIEW-01 → docs/reports/MAYS-ORDERS-RC-DOCUMENTATION-FINAL-REVIEW-01.md
- MAYS-ORDERS-V050-RC1-RELEASE-FINALIZATION-01 → GitHub-Pre-Release v0.5.0-rc.1: Tag/Docs/PDF-Platzhalter fertig; Veröffentlichung NICHT durchgeführt (keine GitHub-Credentials in der Sandbox) — Release offen, manuell via `gh release create` möglich
- MAYS-ORDERS-INSTALLER-COLLISION-PREFLIGHT-01 → docs/reports/MAYS-ORDERS-INSTALLER-COLLISION-PREFLIGHT-01.md
- MAYS-ORDERS-LEFTOVER-STATE-CLEANUP-01 → docs/reports/MAYS-ORDERS-LEFTOVER-STATE-CLEANUP-01.md (inkl. Installer-Guide-Detailupdate + --guide Flag, 129/129 Installer-Tests)
- MAYS-ORDERS-V050-RC2-RELEASE-PREPARATION-01 → docs/release/RELEASE-v0.5.0-rc.2.md (+ echtes PDF, LibreOffice-generiert, 6 Seiten)
- MAYS-ORDERS-RIS-HANDOFF-MO-INSTALLATION-01 → docs/reports/MAYS-ORDERS-RIS-HANDOFF-MO-INSTALLATION-01.md (Übergabe-Bericht an Team RIS: Vorgehen + Lösungsvarianten A/B/C für die MO-Installation mit lokalem State; Produktiv-Abhängigkeit GATE-6 dokumentiert; eigene Positionen: keine AWS-Mutation, kein Zugriff auf RIS)
- MAYS-ORDERS-MODULE-USAGE-ASSESSMENT-01 → docs/reports/MAYS-ORDERS-MODULE-USAGE-ASSESSMENT-01.md (Modul-Verwendungsbewertung: Ist-Analyse Modulreife, 4 Szenarien S1–S4, Aufwandsschätzung Stufe 1 2–4 PT / Stufe 2 8–14 PT / S3 5–8 PT, Aufbau-Zielarchitektur Tenant-isolierter Shared Service)
- MAYS-ORDERS-MODULE-BUILDER-OPTIONS-01 → docs/reports/MAYS-ORDERS-MODULE-BUILDER-OPTIONS-01.md (Nachtrags-Assessment: Modul-Baukasten-Angebot Stufe A Ganz-Stack-Meta-Modul 2–3 PT / B Katalog 7–10 PT / C Registry 3–5 PT + Bonus-Fix S3-Artifact 0,5 PT; Portabilitäts-Befunde code-verifiziert; DECISION PENDING — kein Start ohne Freigabe)
- MAYS-ORDERS-MODULE-BUILDER-FOUNDATION-01 → docs/reports/MAYS-ORDERS-MODULE-BUILDER-FOUNDATION-01.md (IMPLEMENTED/VERIFIED: Python-CLI-Builder `python -m module_builder` — Preset complete erzeugt eigenständige Terraform-Bereitstellung in frei wählbarem Zielordner; fail-closed Preflight, kein backend.tf/state/plan, keine Repo-Abhängigkeit, Artefakt-Hashes im Manifest; 23/23 Builder-Tests, Live-Build terraform fmt/init/validate PASS, 129/129 Installer + 76/76 Lambda Regression, deterministische Builds)
- MAYS-ORDERS-MODULE-BUILDER-HARDENING-01 → docs/reports/MAYS-ORDERS-MODULE-BUILDER-HARDENING-01.md (F1 VERIFIED: cognito_backup.zip reproduzierbar — Quelle im Repo (Package + Handler auf deployed-Stand MY_AWS_REGION), deterministisches Build-Skript, Artefakt getrackt, Rebuild im Ziel sha256-identisch; F2 VERIFIED: Policy-Gate (validate-plan.py + resource-policy.json mit Projektnamen-Substitution) in generierte Projekte, Positiv-/Negativtests Exit 0/1, keine Policy-Aufweichung; Commits 92be267 + da80271; 30/30 Builder + 129/129 Installer + 76/76 Lambda)
- MAYS-ORDERS-MODULE-BUILDER-B1-SELECTION-01 → docs/reports/MAYS-ORDERS-MODULE-BUILDER-B1-SELECTION-01.md (B1 VERIFIED: freie Modulauswahl --modules mit Modulkatalog, Pflicht-Abhängigkeits-Checks fail-closed, keine stille Ergänzung (B2 stoppt); auswahlgetriebene Generierung von main/variables/outputs, Artefakte nur bei Bedarf, Policy-Gate immer; --preset complete byte-identisch erhalten; 44/44 Builder-Tests, Live terraform validate auf Einzel-/Kombi-/Vollauswahl PASS, 129/129 Installer + 76/76 Lambda)
- MAYS-ORDERS-MODULARIZATION-01-A-WORKER-IAM-RESEARCH → docs/reports/MAYS-ORDERS-MODULARIZATION-01-A-WORKER-IAM-RESEARCH-EXECUTION_LOG.md (Subagent A, read-only: IAM-Policy-Struktur, optionale Modul-Variablen, Handler-graceful-ohne-SQS, Worker-Rolle self-contained, Root-Wiring-Kopplungen, Boundary-Befund; GREEN)
- MAYS-ORDERS-MODULARIZATION-01-B-RIS-CONTRACTS-RESEARCH → docs/reports/MAYS-ORDERS-MODULARIZATION-01-B-RIS-CONTRACTS-RESEARCH-EXECUTION_LOG.md (Subagent B, read-only: OrdersPort-Vertrag, RIS-Zwei-Stufen-Integration (HTTP eigene API + orders_reader schreibt MO-Tabelle direkt), RIS-IAM ARN-präzise, Vertragspunkte Statusmaschine/ord_*/Schema/Queue-Form/Naming-Contract; RIS hängt NICHT an MO-Handler-Policy-Form; GREEN)
- MAYS-ORDERS-MODULARIZATION-01-C-IAM-RESEARCH → docs/reports/MAYS-ORDERS-MODULARIZATION-01-C-IAM-RESEARCH-EXECUTION_LOG.md (Subagent C, read-only: IAM-Inventar beider Repos komplett, Permissions Boundaries [nur Worker, extern ohne IaC], pauschale Kopplungen, Least-Privilege-Abgleich; ORANGE — Queue-Policy Principal=* als Security-Finding [Härtung freigabepflichtig, RIS-Live-Pfad], Boundary-Provenance extern, Doku-Drift; Modularisierungs-Hebel bestätigt: SQS-Gating im iam-Modul nötig)
- MAYS-ORDERS-MODULARIZATION-01-PHASE2 → docs/reports/MAYS-ORDERS-MODULARIZATION-01-PHASE2.md (VERIFIED: IAM-SQS-Berechtigung count-gated optional [ohne Queue-ARN KEINE sqs-Aktion], Builder-Deps gelockert [iam: dynamodb; lambda: dynamodb+iam; sqs optional], SQS-Wiring-Stripping bei Nicht-Auswahl, Worker-Deps hart erhalten, RIS-Verträge unangetastet, Complete rückwärtskompatibel, Doku-Sync iam-design; 49/49 Builder + 129/129 Installer + 76/76 Lambda, terraform validate PASS auf Quelle + 4 generierten Varianten; Queue-Policy-Finding bleibt OPEN)
- MAYS-ORDERS-MODULE-BUILDER-B2-WITH-DEPS-01 → docs/reports/MAYS-ORDERS-MODULE-BUILDER-B2-WITH-DEPS-01.md (VERIFIED: --with-deps — transitive Pflichtabhängigkeits-Ergänzung, optionale Deps NIEMALS, Zyklus-/Inkonsistenz-Erkennung fail-closed, deterministisch; WP3-Beispiele A–E live exakt; B1 ohne Flag unverändert fail-closed, Complete unverändert; Transparenz in CLI/README/Manifest; 64/64 Builder + 129/129 Installer + 76/76 Lambda, terraform validate PASS; kein .tf angefasst)
- MAYS-ORDERS-MODULE-CONTRACT-01 → docs/reports/MAYS-ORDERS-MODULE-CONTRACT-01.md (VERIFIED: orders-service Terraform-Modul-Vertrag — feste 7-Modul-Zusammensetzung [API+Handler, Worker, SQS, DynamoDB, IAM, Cognito], Builder-Modus generiert lokales sourcebares Modul [kein Provider-Block, path.module-Artefakte, Tag-Parität via local.default_tags]; Input-Audit 4 Variablen, Output-Audit +3 additive Root-Outputs [Queue-URL/ARN, Worker-ARN]; Wrapper-Integration live validate PASS; 76/76 Builder + 129/129 Installer + 76/76 Lambda)
- MAYS-ORDERS-EXTERNAL-COGNITO-INTEGRATION-01 → docs/reports/MAYS-ORDERS-EXTERNAL-COGNITO-INTEGRATION-01.md (VERIFIED, Scope ausschließlich generiertes Modul: MANAGED [external_cognito=null, Standard] / EXTERNAL [vorhandener Pool via Objekt {endpoint ohne Scheme, client_id}, keine Cognito-Ressourcen], JWT-Authorizer aktiv, fail-closed per HCL-validation [live: leerer client_id → validate-Error]; 19 Output-Namen erhalten, endpoint/client_id geben externe Referenzen, id/arn/group=null dokumentiert; Wrapper MANAGED+EXTERNAL+Negativ live PASS/FAIL-wie-erwartet; 87/87 Builder + 129/129 Installer + 76/76 Lambda; Stamm-Repo unangetastet)

- MAYS-ORDERS-MODULE-BUILDER-CLI-CLEANUP-01 → docs/reports/MAYS-ORDERS-MODULE-BUILDER-CLI-CLEANUP-01.md (VERIFIED: totes --no-policy-check [nur Installer plan-Subparser, nie konsumiert, keine Aufrufer — RIS-Treffer = gepinnter Clone] entfernt, Policy-Gate unverändert bedingungslos; B3 minimal = FUNCTIONALLY COVERED / NO SEPARATE PRESET [--modules+--with-deps + orders-service-Modul]; 87/87 Builder + 129/129 Installer + 76/76 Lambda, Modul+Wrapper live validate PASS)

Overall Status: GREEN (RC) - RC v0.5.0-rc.3 **GO, Packaging COMPLETE** (Tag/Release offen, P09 menschlich) (RIS-AWS-E2E verifiziert, Tag/GitHub-Release nur noch menschlich); v0.5.0-rc.2 veröffentlicht; Module Builder Foundation + Hardening + B1 + PHASE2 + B2 + MODULE-CONTRACT + EXTERNAL-COGNITO + CLI-Cleanup verifiziert; B3 minimal bewusst nicht gebaut (funktional abgedeckt); RESOLVED: Queue-Policy-Härtung (F-03 Wildcard entfernt, im RIS-E2E bestätigt), IAM-Portabilität (FIX-01/02, Installation in Fremdkonto gelungen); OFFEN: Boundary-Explizitsetzung (F-01, Consumer-Verantwortung), optional-Felder für EXTERNAL-Cognito-Outputs, MANAGED→EXTERNAL-Migration (separat freizugeben); Privacy-Produktivbetrieb bleibt BLOCKED (Secret-Management offen, 5–8 PT)

## MO-RC3 Progress

- MO-RC3-P00-BASELINE: COMPLETE - Git-Baseline geprüft und dokumentiert
- MO-RC3-P01-MERGE-READINESS: COMPLETE - Merge-Readiness analysiert, keine Konflikte, alle Tests bestanden
- MO-RC3-P02-MERGE: COMPLETE - Integrationsbranch nach `main` gemerged, Branch erhalten
- MO-RC3-P03-RELEASE-BASELINE: COMPLETE - Baseline, Builder-Inventar, Gate-Matrix dokumentiert
- MO-RC3-P04-MODULE-BUILDER-VERIFICATION: COMPLETE - 90/90 Builder, 76/76 Lambda, 81/81 Installer, validate PASS
- MO-RC3-P05-RIS-EVIDENCE: COMPLETE (Nachtrag 2026-10-31: RIS-Repo read-only ausgewertet)
- MO-RC3-P06-RIS-E2E: **VERIFIED** — RIS-MO-RC-01 (2026-10-30) Full-Lifecycle in Account 262370457690 auf Builder-Pin `1dbb0cb`; Delta zu `8b61922` nur Whitespace (`git diff -w` leer) → RC.3 = **GO**, Produktion **BLOCKED** (Privacy)
- MO-RC3-P07-P08-PACKAGING: **COMPLETE** — Dossier (MD+PDF), Release Notes, Changelog, Gate-Report; **kein Tag/Release** (P09 menschlich)
- MO-RC4-P00: **COMPLETE (Planung)** — Baseline verifiziert, Branch angelegt, Inventar + Plan + offene Fragen dokumentiert; **keine Implementierung, keine AWS-Operation**
- MO-RC4-P01: **COMPLETE (Analyse)** — Contract-Inventar, Orphan-/Secret-Design, ADR-008 (PROPOSED), 23 offene Fragen; keine Implementierung, keine AWS-Operation
- MO-RC4-P02: **COMPLETE (Implementierung, lokal)** — Ownership erzwungen, Privacy-Konsistenz, 93/93 Tests; Delegationsvertrag für technische Consumer bleibt offen; kein Push
- MO-RC4-P02A: **COMPLETE (lokal)** — zentrale Identity-Resolution, Legacy-Kompatibilität, GSI2/Privacy unverändert, 120/120 Lambda; Delegation BLOCKED
- MO-RC4-P02B: **COMPLETE (lokal, teilweise BLOCKED)** — interner Identitätsvertrag + Privacy-Scope, 139/139 Lambda; RIS-Bindung und Mehr-Consumer-Isolation BLOCKED
- MO-RC4-P02C: **COMPLETE (lokal)** — Worker kollisionssicher (Condition+Version), SQS-DLQ/Retention/Visibility, partielle Batch-Fehler; 157/157 Lambda, terraform validate PASS
- MO-RC4-P02E: **COMPLETE (lokal)** — internes Order-Routing (orderType, Registry, generischer Handler), 180/180 Lambda; Statusmaschine unverändert
- MO-RC4-P02F: **COMPLETE (lokal)** — PENDING-Recovery (deliveryState, GSI1-Fenster, Lease, recovery/scan, Scheduler opt-in); 204/204 Lambda, terraform validate PASS
- MO-RC4-P02G-A: **COMPLETE (lokal)** — Ergebnis-Datenvertrag + Privacy-Integration, keine Schreibfunktion; 233/233 Lambda
- MO-RC4-P02G-B: **COMPLETE (lokal)** — Processing-Claim + atomarer Abschluss (result/error), Anonymize/Cancel blockieren Abschluss; 255/255 Lambda
- MO-RC4-P02H-A: **COMPLETE (lokal)** — Owner-/Consumer-Autorisierung (V-10), Legacy fail-closed, Worker unverändert; 281/281 Lambda
- MO-RC4-P02I-A: **COMPLETE (lokal)** — Recovery-Safety-Klassifikation + Runbook; automatische Processing-Recovery bleibt OPEN
- MO-RC4-P02I-B2: **COMPLETE (lokal, nicht deployed)** — GSI3-Recovery, separater Schedule (default aus), DLQ-Alarm; 321/321 Lambda, terraform validate PASS
- MO-RC4-P02I-C1: **COMPLETE (lokal)** — Lambda-Artefakt vollständig (11 Module, deterministisch), Builder+Installer fail-closed; nicht deployed
- MO-RC4-P02I-C2: **COMPLETE (lokal)** — CI-Artefakt-Gate in Validate (verify → rebuild → cmp → Tests); CodeBuild-Lauf offen

==================================================

### Retroaktive Index-Vervollständigung (MAYS-ORDERS-AUDITLOG-CONSISTENCY-SCAN-01, 2026-10-19)

_Nachtrag laut Template-Pflicht (Index = vollständiges Report-Verzeichnis).
Rein registrativ (Dateiname → Pfad); inhaltliche Quelle bleibt die jeweilige Datei._

- 00-AI_AUDITLOG-MIGRATED-EXECUTION_LOG → docs/reports/00-AI_AUDITLOG-MIGRATED-EXECUTION_LOG.md (retroaktiv indexiert)
## 09-0x-Parallel-Serie (retroaktiv)

- 09-01-PARALLEL-PROJECT-TEST-EXECUTION_LOG → docs/reports/09-01-PARALLEL-PROJECT-TEST-EXECUTION_LOG.md (retroaktiv indexiert)
- 09-02-PARALLEL-INSTALLER-UPGRADE-EXECUTION_LOG → docs/reports/09-02-PARALLEL-INSTALLER-UPGRADE-EXECUTION_LOG.md (retroaktiv indexiert)
- 09-03-FULL-PARALLEL-INSTALLER-AUDIT-EXECUTION_LOG → docs/reports/09-03-FULL-PARALLEL-INSTALLER-AUDIT-EXECUTION_LOG.md (retroaktiv indexiert)
- 09-04-UPGRADE-PARALLEL-DEPLOYMENT-FIX-EXECUTION_LOG → docs/reports/09-04-UPGRADE-PARALLEL-DEPLOYMENT-FIX-EXECUTION_LOG.md (retroaktiv indexiert)
- 09-05-DOCUMENTATION-REVIEW-EXECUTION_LOG → docs/reports/09-05-DOCUMENTATION-REVIEW-EXECUTION_LOG.md (retroaktiv indexiert)
- AI-DEVELOPER-PROFILE-SETUP-EXECUTION-LOG → docs/reports/AI-DEVELOPER-PROFILE-SETUP-EXECUTION-LOG.md (retroaktiv indexiert)
## BACKUP-Serie 01–08.5 (retroaktiv)

- BACKUP-01-BACKUP-RECOVERY-INVENTORY → docs/reports/BACKUP-01-BACKUP-RECOVERY-INVENTORY.md (retroaktiv indexiert)
- BACKUP-02-RECOVERY-STRATEGY → docs/reports/BACKUP-02-RECOVERY-STRATEGY.md (retroaktiv indexiert)
- BACKUP-03-MULTI-PROJECT-BACKUP-PROTECTION-FOUNDATION → docs/reports/BACKUP-03-MULTI-PROJECT-BACKUP-PROTECTION-FOUNDATION.md (retroaktiv indexiert)
- BACKUP-04-MULTI-PROJECT-DYNAMODB-PROTECTION → docs/reports/BACKUP-04-MULTI-PROJECT-DYNAMODB-PROTECTION.md (retroaktiv indexiert)
- BACKUP-05-MULTI-PROJECT-TERRAFORM-STATE-PROTECTION → docs/reports/BACKUP-05-MULTI-PROJECT-TERRAFORM-STATE-PROTECTION.md (retroaktiv indexiert)
- BACKUP-06-REMOTE-STATE-MIGRATION-PLAN → docs/reports/BACKUP-06-REMOTE-STATE-MIGRATION-PLAN.md (retroaktiv indexiert)
- BACKUP-06-REMOTE-TERRAFORM-STATE-PROTECTION → docs/reports/BACKUP-06-REMOTE-TERRAFORM-STATE-PROTECTION.md (retroaktiv indexiert)
- BACKUP-07-REMOTE-STATE-INFRASTRUCTURE → docs/reports/BACKUP-07-REMOTE-STATE-INFRASTRUCTURE.md (retroaktiv indexiert)
- BACKUP-08.1-REMOTE-STATE-BOOTSTRAP-DEPLOYMENT → docs/reports/BACKUP-08.1-REMOTE-STATE-BOOTSTRAP-DEPLOYMENT.md (retroaktiv indexiert)
- BACKUP-08.2-INSTALLER-REMOTE-STATE-LIFECYCLE-AUDIT → docs/reports/BACKUP-08.2-INSTALLER-REMOTE-STATE-LIFECYCLE-AUDIT.md (retroaktiv indexiert)
- BACKUP-08.3-INSTALLER-REMOTE-STATE-LIFECYCLE → docs/reports/BACKUP-08.3-INSTALLER-REMOTE-STATE-LIFECYCLE.md (retroaktiv indexiert)
- BACKUP-08.4-MIGRATION-MAYS-ORDERS → docs/reports/BACKUP-08.4-MIGRATION-MAYS-ORDERS.md (retroaktiv indexiert)
- BACKUP-08.5-REMOTE-STATE-MULTI-PROJECT-E2E → docs/reports/BACKUP-08.5-REMOTE-STATE-MULTI-PROJECT-E2E.md (retroaktiv indexiert)
- CI-REPOSITORY-BOOTSTRAP-01 → docs/reports/CI-REPOSITORY-BOOTSTRAP-01.md (retroaktiv indexiert)
## COGNITO-BACKUP-Serie (03C–11, retroaktiv)

- COGNITO-BACKUP-03C-RETRY-FIRST-REAL-BACKUP → docs/reports/COGNITO-BACKUP-03C-RETRY-FIRST-REAL-BACKUP.md (retroaktiv indexiert)
- COGNITO-BACKUP-03D-RESTORE-DRY-RUN → docs/reports/COGNITO-BACKUP-03D-RESTORE-DRY-RUN.md (retroaktiv indexiert)
- COGNITO-BACKUP-03E-CONTROLLED-USER-RECOVERY → docs/reports/COGNITO-BACKUP-03E-CONTROLLED-USER-RECOVERY.md (retroaktiv indexiert)
- COGNITO-BACKUP-04-OPERATIONALIZATION → docs/reports/COGNITO-BACKUP-04-OPERATIONALIZATION.md (retroaktiv indexiert)
- COGNITO-BACKUP-04A-APPLY-VALIDATION → docs/reports/COGNITO-BACKUP-04A-APPLY-VALIDATION.md (retroaktiv indexiert)
- COGNITO-BACKUP-05-MONITORING-ALERTING → docs/reports/COGNITO-BACKUP-05-MONITORING-ALERTING.md (retroaktiv indexiert)
- COGNITO-BACKUP-06-NOTIFICATION-DELIVERY → docs/reports/COGNITO-BACKUP-06-NOTIFICATION-DELIVERY.md (retroaktiv indexiert)
- COGNITO-BACKUP-07-NOTIFICATION-SUBSCRIPTION → docs/reports/COGNITO-BACKUP-07-NOTIFICATION-SUBSCRIPTION.md (retroaktiv indexiert)
- COGNITO-BACKUP-08-NOTIFICATION-TARGET-DEFINITION → docs/reports/COGNITO-BACKUP-08-NOTIFICATION-TARGET-DEFINITION.md (retroaktiv indexiert)
- COGNITO-BACKUP-09-SNS-EMAIL-SUBSCRIPTION → docs/reports/COGNITO-BACKUP-09-SNS-EMAIL-SUBSCRIPTION.md (retroaktiv indexiert)
- COGNITO-BACKUP-10-END-TO-END-NOTIFICATION → docs/reports/COGNITO-BACKUP-10-END-TO-END-NOTIFICATION.md (retroaktiv indexiert)
- COGNITO-BACKUP-11-FINAL-VERIFICATION → docs/reports/COGNITO-BACKUP-11-FINAL-VERIFICATION.md (retroaktiv indexiert)
- COGNITO-BACKUP-DOCS-01-DOCUMENTATION-AUDIT → docs/reports/COGNITO-BACKUP-DOCS-01-DOCUMENTATION-AUDIT.md (retroaktiv indexiert)
- COGNITO-BACKUP-RPO-RTO-01-DEFINITION → docs/reports/COGNITO-BACKUP-RPO-RTO-01-DEFINITION.md (retroaktiv indexiert)
- CURRENT-INFRA-AUDIT-EXECUTION-LOG → docs/reports/CURRENT-INFRA-AUDIT-EXECUTION-LOG.md (retroaktiv indexiert)
- D8-AWS-CICD-CREDENTIAL-ABSTRACTION-01 → docs/reports/D8-AWS-CICD-CREDENTIAL-ABSTRACTION-01.md (retroaktiv indexiert)
- DETAILLIERTER-BERICHT-CICD-INSTALLER-PARALLEL → docs/reports/DETAILLIERTER-BERICHT-CICD-INSTALLER-PARALLEL.md (retroaktiv indexiert)
- DYNAMODB-SEED-1000 → docs/reports/DYNAMODB-SEED-1000.md (retroaktiv indexiert)
- DYNAMODB-SEED-DEMO-50 → docs/reports/DYNAMODB-SEED-DEMO-50.md (retroaktiv indexiert)
- GESAMTBERICHT-2026-09-24-26 → docs/reports/GESAMTBERICHT-2026-09-24-26.md (retroaktiv indexiert)
- GITHUB-AUTH-CI-INTEGRATION-01 → docs/reports/GITHUB-AUTH-CI-INTEGRATION-01.md (retroaktiv indexiert)
- INFRASTRUCTURE-INSTALLER-AUDIT-EXECUTION-LOG → docs/reports/INFRASTRUCTURE-INSTALLER-AUDIT-EXECUTION-LOG.md (retroaktiv indexiert)
- INSTALLER-D8-CICD → docs/reports/INSTALLER-D8-CICD.md (retroaktiv indexiert)
## Installer-/CI-/Parallel-Serie (retroaktiv)

- INSTALLER-H1-CHECKPOINT → docs/reports/INSTALLER-H1-CHECKPOINT.md (retroaktiv indexiert)
- INSTALLER-H1-FINAL → docs/reports/INSTALLER-H1-FINAL.md (retroaktiv indexiert)
- INSTALLER-H1-HARDENING → docs/reports/INSTALLER-H1-HARDENING.md (retroaktiv indexiert)
- INSTALLER-H2-DEPLOYMENT-IDENTITY → docs/reports/INSTALLER-H2-DEPLOYMENT-IDENTITY.md (retroaktiv indexiert)
- INSTALLER-SECURITY-01 → docs/reports/INSTALLER-SECURITY-01.md (retroaktiv indexiert)
- KONSOLIDIERUNG-CICD-SOURCE-AUTH-AUDIT → docs/reports/KONSOLIDIERUNG-CICD-SOURCE-AUTH-AUDIT.md (retroaktiv indexiert)
- KONSOLIDIERUNG-PARALLEL-PROJECT-MECHANISMUS → docs/reports/KONSOLIDIERUNG-PARALLEL-PROJECT-MECHANISMUS.md (retroaktiv indexiert)
- LAMBDA-PYTHON-3.14-MIGRATION → docs/reports/LAMBDA-PYTHON-3.14-MIGRATION.md (retroaktiv indexiert)
- MAYS-ORDERS-AUDITLOG-CONSISTENCY-SCAN-01 → docs/reports/MAYS-ORDERS-AUDITLOG-CONSISTENCY-SCAN-01.md (retroaktiv indexiert)
- MAYS-ORDERS-DSGVO-CONSOLIDATION-01-EXECUTION_LOG → docs/reports/MAYS-ORDERS-DSGVO-CONSOLIDATION-01-EXECUTION_LOG.md (retroaktiv indexiert)
- MAYS-ORDERS-DSGVO-CONSOLIDATION-01 → docs/reports/MAYS-ORDERS-DSGVO-CONSOLIDATION-01.md (retroaktiv indexiert)
## Mays-Orders-Workstreams (retroaktiv)

- MAYS-ORDERS-DSGVO-PRIVACY-CAPABILITY-01 → docs/reports/MAYS-ORDERS-DSGVO-PRIVACY-CAPABILITY-01.md (retroaktiv indexiert)
- MAYS-ORDERS-DSGVO-PRIVACY-CORE-01 → docs/reports/MAYS-ORDERS-DSGVO-PRIVACY-CORE-01.md (retroaktiv indexiert)
- MAYS-ORDERS-DSGVO-PRIVACY-EXPORT-01 → docs/reports/MAYS-ORDERS-DSGVO-PRIVACY-EXPORT-01.md (retroaktiv indexiert)
- MAYS-ORDERS-MODULARITY-01-REUSABILITY-AUDIT → docs/reports/MAYS-ORDERS-MODULARITY-01-REUSABILITY-AUDIT.md (retroaktiv indexiert)
- MAYS-ORDERS-MODULARITY-01A-INSTALLER-TERRAFORM-BACKEND-AUDIT → docs/reports/MAYS-ORDERS-MODULARITY-01A-INSTALLER-TERRAFORM-BACKEND-AUDIT.md (retroaktiv indexiert)
- MAYS-ORDERS-MODULARITY-02-HARD-CODE-PRODUCT-SURFACE-AUDIT → docs/reports/MAYS-ORDERS-MODULARITY-02-HARD-CODE-PRODUCT-SURFACE-AUDIT.md (retroaktiv indexiert)
- MAYS-ORDERS-PRIVACY-E2E-DEPLOY-01 → docs/reports/MAYS-ORDERS-PRIVACY-E2E-DEPLOY-01.md (retroaktiv indexiert)
- MAYS-ORDERS-PRIVACY-PARALLEL-DEPLOYMENT-01 → docs/reports/MAYS-ORDERS-PRIVACY-PARALLEL-DEPLOYMENT-01.md (retroaktiv indexiert)
- MAYS-ORDERS-PRIVACY-TEST-CLEAN-REPLAN-01 → docs/reports/MAYS-ORDERS-PRIVACY-TEST-CLEAN-REPLAN-01.md (retroaktiv indexiert)
- MAYS-ORDERS-RESOURCE-COUNT-RECONCILIATION-01 → docs/reports/MAYS-ORDERS-RESOURCE-COUNT-RECONCILIATION-01.md (retroaktiv indexiert)
- NORMALIZATION-AUDIT-EXECUTION-LOG → docs/reports/NORMALIZATION-AUDIT-EXECUTION-LOG.md (retroaktiv indexiert)
- PRESENTATION-TECHNICAL-QA → docs/reports/PRESENTATION-TECHNICAL-QA.md (retroaktiv indexiert)
- PROFESSOR-ACCEPTANCE-AUDIT-EXECUTION-LOG → docs/reports/PROFESSOR-ACCEPTANCE-AUDIT-EXECUTION-LOG.md (retroaktiv indexiert)
- PROJECT-OVERVIEW → docs/reports/PROJECT-OVERVIEW.md (retroaktiv indexiert)
- R10-PARALLEL-DEPLOY-NAMING-ANALYSIS → docs/reports/R10-PARALLEL-DEPLOY-NAMING-ANALYSIS.md (retroaktiv indexiert)
- T011-04-LAMBDA-RUNTIME-DOC-CLEANUP → docs/reports/T011-04-LAMBDA-RUNTIME-DOC-CLEANUP.md (retroaktiv indexiert)
## T011–T018-Entwicklungsreihe (retroaktiv)

- T011-04-PYTHON-CLEANUP → docs/reports/T011-04-PYTHON-CLEANUP.md (retroaktiv indexiert)
- T011-05-COGNITO → docs/reports/T011-05-COGNITO.md (retroaktiv indexiert)
- T011-06-HTTP-API → docs/reports/T011-06-HTTP-API.md (retroaktiv indexiert)
- T011-06-RECOVERY → docs/reports/T011-06-RECOVERY.md (retroaktiv indexiert)
- T011-07-TERRAFORM-PLAN-REVIEW → docs/reports/T011-07-TERRAFORM-PLAN-REVIEW.md (retroaktiv indexiert)
- T011-10-SEED-FINALIZATION-EXECUTION-LOG → docs/reports/T011-10-SEED-FINALIZATION-EXECUTION-LOG.md (retroaktiv indexiert)
- T011-11-CLOUDWATCH-MONITORING-EXECUTION-LOG → docs/reports/T011-11-CLOUDWATCH-MONITORING-EXECUTION-LOG.md (retroaktiv indexiert)
- T011-11-CLOUDWATCH-MONITORING → docs/reports/T011-11-CLOUDWATCH-MONITORING.md (retroaktiv indexiert)
- T011-12-TERRAFORM-MODULES-EXECUTION-LOG → docs/reports/T011-12-TERRAFORM-MODULES-EXECUTION-LOG.md (retroaktiv indexiert)
- T011-CLOUDTRAIL-EXECUTION-LOG → docs/reports/T011-CLOUDTRAIL-EXECUTION-LOG.md (retroaktiv indexiert)
- T012-INSTALLATION-CONCEPT-EXECUTION-LOG → docs/reports/T012-INSTALLATION-CONCEPT-EXECUTION-LOG.md (retroaktiv indexiert)
- T013-INSTALLATION-IDENTITY-EXECUTION-LOG → docs/reports/T013-INSTALLATION-IDENTITY-EXECUTION-LOG.md (retroaktiv indexiert)
- T014-INSTALLATION-COST-PROFILE-EXECUTION-LOG → docs/reports/T014-INSTALLATION-COST-PROFILE-EXECUTION-LOG.md (retroaktiv indexiert)
- T015-INSTALLATION-REGION-EXECUTION-LOG → docs/reports/T015-INSTALLATION-REGION-EXECUTION-LOG.md (retroaktiv indexiert)
- T016-INSTALLATION-AVAILABILITY-EXECUTION-LOG → docs/reports/T016-INSTALLATION-AVAILABILITY-EXECUTION-LOG.md (retroaktiv indexiert)
- T017-INSTALLATION-DATA-STRATEGY-EXECUTION-LOG → docs/reports/T017-INSTALLATION-DATA-STRATEGY-EXECUTION-LOG.md (retroaktiv indexiert)
- T018-INSTALLATION-SECURITY-PROFILE-EXECUTION-LOG → docs/reports/T018-INSTALLATION-SECURITY-PROFILE-EXECUTION-LOG.md (retroaktiv indexiert)
- TAG-ROLE-GOVERNANCE-REVIEW-EXECUTION-LOG → docs/reports/TAG-ROLE-GOVERNANCE-REVIEW-EXECUTION-LOG.md (retroaktiv indexiert)
- TERRAFORM-COST-RESOURCE-POLICY-GATE → docs/reports/TERRAFORM-COST-RESOURCE-POLICY-GATE.md (retroaktiv indexiert)
## Historische Projektdoks/Wochen/Strategien (retroaktiv)

- WEEK-01 → docs/reports/WEEK-01.md (retroaktiv indexiert)
- WEEK-02 → docs/reports/WEEK-02.md (retroaktiv indexiert)
- WEEK-03 → docs/reports/WEEK-03.md (retroaktiv indexiert)
- WEEK-04 → docs/reports/WEEK-04.md (retroaktiv indexiert)
- cost-strategy → docs/reports/cost-strategy.md (retroaktiv indexiert)
- documentation-correction-report → docs/reports/documentation-correction-report.md (retroaktiv indexiert)
- documentation-transfer-report → docs/reports/documentation-transfer-report.md (retroaktiv indexiert)
- feature-report-week1 → docs/reports/feature-report-week1.md (retroaktiv indexiert)
- four-week-plan → docs/reports/four-week-plan.md (retroaktiv indexiert)
- recovery-checkpoint-strategy → docs/reports/recovery-checkpoint-strategy.md (retroaktiv indexiert)
- test-strategy → docs/reports/test-strategy.md (retroaktiv indexiert)
- MAYS-ORDERS-MODULE-DOC-INTEGRATION-01 → docs/reports/MAYS-ORDERS-MODULE-DOC-INTEGRATION-01.md (VERIFIED: Nutzer-Doku für den Modulbau integriert — Week-1..4 byte-identisch nach docs/initialweekcontest/ verschoben, Modul-Testleitfaden gegengeprüft [34 Dateien, MANAGED/EXTERNAL, Negativtest] und 12 Evidenz-Stellen auf Repo-Reports umgestellt, AGENTS.md/README-Referenzen konsistent; keine Funktionsänderung)
- MAYS-ORDERS-MODULE-IAM-PORTABILITY-AUDIT-01 → docs/reports/MAYS-ORDERS-MODULE-IAM-PORTABILITY-AUDIT-01.md
- MAYS-ORDERS-MODULE-IAM-PORTABILITY-FIX-01 → docs/reports/MAYS-ORDERS-MODULE-IAM-PORTABILITY-FIX-01.md
- MO-RC-BASELINE-RECONCILIATION-01 → docs/reports/MO-RC-BASELINE-RECONCILIATION-01.md
- MAYS-ORDERS-MODULE-IAM-PORTABILITY-FIX-02 → docs/reports/MAYS-ORDERS-MODULE-IAM-PORTABILITY-FIX-02.md
- MO-MODULE-LAMBDA-ARTIFACT-READINESS-01 → docs/reports/MO-MODULE-LAMBDA-ARTIFACT-READINESS-01.md
- MO-MODULE-SQS-RESOURCE-POLICY-FIX-03 → docs/reports/MO-MODULE-SQS-RESOURCE-POLICY-FIX-03.md
- MO-CONSUMER-HANDOFF-01 → docs/reports/MO-CONSUMER-HANDOFF-01.md
- MO-RC-READINESS-DECISION-01 → docs/reports/MO-RC-READINESS-DECISION-01.md
- MO-RC-READINESS-CONSOLIDATED-2026-10 → docs/reports/MO-RC-READINESS-CONSOLIDATED-2026-10.md
- MO-RC3-P00-BASELINE → docs/reports/MO-RC3-P00-BASELINE.md (P00 Git-Baseline für RC.3 Release Preparation)
- MO-RC3-P01-MERGE-READINESS → docs/reports/MO-RC3-P01-MERGE-READINESS.md (P01 Merge-Readiness-Analyse)
- MO-RC3-P02-MERGE-DONE → docs/reports/MO-RC3-P02-MERGE-RESULT.md (P02 Merge completed to main)
- MO-RC3-P00-P01-AUDIT-EXECUTION-LOG → docs/reports/MO-RC3-P00-P01-AUDIT-EXECUTION-LOG.md
- MO-RC3-P03-RELEASE-BASELINE → docs/reports/MO-RC3-P03-RELEASE-BASELINE.md
- MO-RC3-P03-MODULE-BUILDER-INVENTORY → docs/reports/MO-RC3-P03-MODULE-BUILDER-INVENTORY.md
- MO-RC3-P03-RELEASE-GATES → docs/reports/MO-RC3-P03-RELEASE-GATES.md
- MO-RC3-P04-MODULE-BUILDER-VERIFICATION → docs/reports/MO-RC3-P04-MODULE-BUILDER-VERIFICATION.md
- MO-RC3-P05-RIS-INTEGRATION-EVIDENCE → docs/reports/MO-RC3-P05-RIS-INTEGRATION-EVIDENCE.md
- MO-RC3-P06-RIS-E2E-EVIDENCE-VERIFICATION → docs/reports/MO-RC3-P06-RIS-E2E-EVIDENCE-VERIFICATION.md (Rev. 2: RIS-Repo read-only geprüft; Builder-Pin `1dbb0cb` code-identisch zu RC.3; RIS-MO-RC-01 Full-Lifecycle E2E PASS → RC GO)
- RIS-RC3-E2E-TEST-PREPARATION → docs/reports/RIS-RC3-E2E-TEST-PREPARATION.md (Rev. 2: kein neuer E2E vor RC.3 erforderlich)
- MO-RC3-P07-P08-RELEASE-PACKAGING → docs/reports/MO-RC3-P07-P08-RELEASE-PACKAGING.md (Packaging v0.5.0-rc.3: Gates aus Evidence verifiziert, kein Tag/Release)
- RELEASE-v0.5.0-rc.3 (Dossier + PDF) → docs/release/RELEASE-v0.5.0-rc.3.md / .pdf (5 Seiten A4, LibreOffice)
- RELEASE-GATES-v0.5.0-rc.3 → docs/release/RELEASE-GATES-v0.5.0-rc.3.md (18 Gates, GO für RC, BLOCKED für Produktion)
- MO-RC4-P00-BASELINE → docs/reports/MO-RC4-P00-BASELINE.md (RC4-Basis `086a8be`, Branch `feature/mo-rc4-kms-privacy-retention`, Architektur-Inventar; Hinweis: `v0.5.0-rc.3` ist NICHT getaggt)
- MO-RC4-P00-MODULE-PLAN → docs/reports/MO-RC4-P00-MODULE-PLAN.md (15 Arbeitspakete P-01…P-15, ~18,5 PT, Abhängigkeitsgraph, Risiken)
- MO-RC4-P00-OPEN-QUESTIONS → docs/reports/MO-RC4-P00-OPEN-QUESTIONS.md (14 Entscheidungen Q-01…Q-14, 6 blockierend)
- MO-RC4-P01-CONTRACT-INVENTORY → docs/reports/MO-RC4-P01-CONTRACT-INVENTORY.md (Ist-Verträge: kein subjectId im API-Pfad, kein userId/tenantId/retention, COMPLETED/FAILED nicht implementiert, RIS-Fremdschreibpfad)
- MO-RC4-P01-ORPHAN-CLEANUP-DESIGN → docs/reports/MO-RC4-P01-ORPHAN-CLEANUP-DESIGN.md (enges Orphan-Kriterium, 5 Auslöser bewertet, TTL nicht als Lösch-Nachweis, Dry-Run/Idempotenz)
- MO-RC4-P01-SECRET-PROVIDER-DESIGN → docs/reports/MO-RC4-P01-SECRET-PROVIDER-DESIGN.md (AWS_MANAGED/APP_MANAGED/geführte Rotation; keine Eigenbau-Chiffre)
- MO-RC4-P01-OPEN-QUESTIONS → docs/reports/MO-RC4-P01-OPEN-QUESTIONS.md (23 Entscheidungen, 6 blockierend)
- ADR-008 (Auftrag: ADR-007) → architecture/architecture-decisions.md (`ADR-008: Privacy-Secret-Management, Retention und Orphan-Cleanup`, Status PROPOSED; Nummer 007 war vergeben)
- MO-RC4-P02-ORDER-OWNERSHIP → docs/reports/MO-RC4-P02-ORDER-OWNERSHIP.md (subjectId aus JWT, 401 ohne Identität, GSI2-Persistenz, inspect-Pagination, idempotentes Erase; 93/93 Lambda; RIS-Delegation BLOCKED)
- MO-RC4-P02A-IDENTITY-RESOLUTION → docs/reports/MO-RC4-P02A-IDENTITY-RESOLUTION.md (OrderIdentity, Consumer/Owner/Actor, kollisionsfreier Schlüssel, 18+9 Tests)
- MO-RC4-P02A-LEGACY-COMPATIBILITY → docs/reports/MO-RC4-P02A-LEGACY-COMPATIBILITY.md (Fälle A–E, RIS `orders_reader` schreibt direkt, GSI2 unverändert)
- MO-RC4-P02A-INTEGRATION-GATES → docs/reports/MO-RC4-P02A-INTEGRATION-GATES.md (13 Gates, Delegation/Agent/Service BLOCKED, V-1…V-6 offen)
- MO-RC4-P02B-INTERNAL-IDENTITY-CONTRACT → docs/reports/MO-RC4-P02B-INTERNAL-IDENTITY-CONTRACT.md (identityVerification, interne Auflösung nur mit verifiziertem Kontext, Owner≠Actor BLOCKED)
- MO-RC4-P02B-RIS-COMPATIBILITY → docs/reports/MO-RC4-P02B-RIS-COMPATIBILITY.md (RIS schreibt direkt; Put/Update verifiziert; RIS-Eigentümerbindung BLOCKED; Vertragszusatz V-1/V-3)
- MO-RC4-P02B-PRIVACY-ISOLATION → docs/reports/MO-RC4-P02B-PRIVACY-ISOLATION.md (GSI2 ohne Consumer-Trennung; opt-in Scope nur einschränkend; Mehr-Consumer-Isolation BLOCKED inkl. Migrationsentwurf)
- MO-RC4-P02C-WORKER-SQS-SAFETY → docs/reports/MO-RC4-P02C-WORKER-SQS-SAFETY.md (Worker-Condition/Version, DLQ + maxReceiveCount=1, Retention/Visibility konfigurierbar, ReportBatchItemFailures)
- MO-RC4-P02C-WORKER-COLLISION-SAFETY → docs/reports/MO-RC4-P02C-WORKER-COLLISION-SAFETY.md (Kollisions-/Access-Sicht: Ownership beim Lesen fehlt, Worker-Routing OPEN)
- MO-RC4-P02E-INTERNAL-ORDER-ROUTING → docs/reports/MO-RC4-P02E-INTERNAL-ORDER-ROUTING.md (orderType + interne Handler-Registry, unbekannter Typ → DLQ, Legacy → generic; 180/180 Lambda)
- MO-RC4-P02F-PENDING-RECOVERY → docs/reports/MO-RC4-P02F-PENDING-RECOVERY.md (Zustellattribute + GSI1-Recovery + Claim/Lease + 5-min-Scheduler, opt-in; 204/204 Lambda)
- MO-RC4-P02G-A-PROCESSING-RESULT-PRIVACY-CONTRACT → docs/reports/MO-RC4-P02G-A-PROCESSING-RESULT-PRIVACY-CONTRACT.md (Ergebnisvertrag + Inspect/Export/Anonymize, GSI2-Projektionsfehler behoben; 233/233 Lambda)
- MO-RC4-P02G-B-PROCESSING-LIFECYCLE-AND-RESULT-PERSISTENCE → docs/reports/MO-RC4-P02G-B-PROCESSING-LIFECYCLE-AND-RESULT-PERSISTENCE.md (Claim/Lease, atomare Ergebnisübernahme, Privacy-Race-Schutz; 255/255 Lambda)
- MO-RC4-P02H-A-ORDER-OWNER-CONSUMER-AUTHORIZATION → docs/reports/MO-RC4-P02H-A-ORDER-OWNER-CONSUMER-AUTHORIZATION.md (V-10 geschlossen: LIST via GSI2, GET/PATCH Owner+Consumer, atomare Bedingung; 281/281 Lambda)
- MO-RC4-P02I-A-PROCESSING-RECOVERY-SAFETY → docs/reports/MO-RC4-P02I-A-PROCESSING-RECOVERY-SAFETY.md (präzise Claim-Klassifikation, payload-freies Ereignis-Logging, Runbook; 298/298 Lambda)
- MO-RC4-P02I-B2-AUTOMATIC-PROCESSING-RECOVERY → docs/reports/MO-RC4-P02I-B2-AUTOMATIC-PROCESSING-RECOVERY.md (GSI3 + processing/scan + DLQ-Alarm, default aus; 321/321 Lambda)
- MO-RC4-P02I-C1-LAMBDA-ARTIFACT-INTEGRITY → docs/reports/MO-RC4-P02I-C1-LAMBDA-ARTIFACT-INTEGRITY.md (ZIP 7→11 Module, deterministischer Build, Builder-Gate fail-closed, 508 Tests)
- MO-RC4-P02I-C2-CI-ARTIFACT-QUALITY-GATE → docs/reports/MO-RC4-P02I-C2-CI-ARTIFACT-QUALITY-GATE.md (Validate-Buildspec: Artefaktprüfung vor Rebuild, cmp-Reproduzierbarkeit, Packaging-Tests; 514 Tests)
- MO-RC4-POLICY-GATE-REPAIR-01 → Commit `94c706a` (7 Allowlist-Typen für Cognito-Backup/SNS, ressourcenspezifisches Lambda-Timeout 10 s/300 s, gezielte S3-/IAM-/SNS-Prüfungen)
- MO-RC4-TERRAFORM-TIMEOUT-FIX-01 → Commit `64e1a25` (Apply/Destroy 900 s, Plan/State/Read 180 s, `MAYS_TERRAFORM_APPLY_TIMEOUT`, fail-closed, kein Retry)
- MO-RC4-DEV-APPLY-03 → RC4-Development-Apply: 58/58 Ressourcen, Policy Gate PASS, E2E 9/9 PASS (Cognito/API/DDB/Worker/DLQ/Observability/Backup-Config), Testdaten bereinigt
- MO-RC4-DEV-INSTALL-LIFECYCLE-TEST-01 → docs/reports/MO-RC4-DEV-INSTALL-LIFECYCLE-TEST-01-EXECUTION_LOG.md (Verify PASS, Apply 58, Destroy 58, RC4-State inkl. Versionen entfernt, Shared Backend + RIS unverändert)
- MO-RC4-MAIN-INTEGRATION-01 → BLOCKED: `directAWSGit-Mays-Order-AWS` triggert bei Push auf `main` `terraform apply -auto-approve` ohne Approval; Push/Merge bis Pipeline-Sicherheitsgate nicht durchgeführt
- MO-INSTALLER-UPGRADE-SAFETY-P0A-01 → docs/reports/MO-INSTALLER-UPGRADE-SAFETY-P0A-01.md (aktionsbasierte DELETE/REPLACE-Blockade für DynamoDB/S3/Cognito/SQS, Gate bei Plan und Apply, Destroy-Guard, Migrationsplan; 315 Tests)
- MO-INSTALLER-UPGRADE-VERSIONING-P0B-01 → docs/reports/MO-INSTALLER-UPGRADE-VERSIONING-P0B-01.md (Git-Commit-/Dirty-Bindung, Manifest v2 mit source/targetVersion, installierte Version via `mo_version`-Output, Legacy-Erkennung, Apply-Gate; 347 Tests)
- MO-BUILDER-INSTALLER-UPGRADE-MIGRATION-PLAN → docs/reports/MO-BUILDER-INSTALLER-UPGRADE-MIGRATION-PLAN.md (10-Phasen-Fahrplan, Status je Phase; keine AWS-Autorisierung)
- MO-INSTALLER-UPGRADE-DRIFT-SAFETY-P0C-01 → docs/reports/MO-INSTALLER-UPGRADE-DRIFT-SAFETY-P0C-01.md (State-Baseline mit Serial/Lineage/Fingerprint, Drift-Erkennung aus `resource_drift`, No-op-Klassifikation, Baseline-Gate vor Apply, `upgrade-drift-report.json/.md`; 377 Tests)
- MO-INSTALLER-UPGRADE-ORCHESTRATION-P1-01 → docs/reports/MO-INSTALLER-UPGRADE-ORCHESTRATION-P1-01.md (expliziter `plan --remote --upgrade`, Versionskompatibilität, SAFE/REVIEW/CRITICAL, `upgrade-readiness.json/.md`, Review-Gate; 422 Tests)
- MO-BUILDER-UPGRADE-P2-01 → docs/reports/MO-BUILDER-UPGRADE-P2-01.md (Builder-Manifest Schema 2 mit Datei-Fingerprints, Projektstatus/Datei-Diff, Konfigurationserhalt, `upgrade --dry-run|--apply`, Konflikt-/Pfadschutz; 35 neue Builder-Tests, Builder 128 PASS)
- MO-ORDER-DATA-MIGRATION-P3-PLANNING-01 → docs/reports/MO-ORDER-DATA-MIGRATION-P3-PLANNING-01.md (P3-Architektur: DynamoDB-Backup/Restore, Migration/Cutover, PartiQL-Diagnose, DSGVO/Erasure-Ledger, P0A–P2-Integration; reine Planung)
- MO-ORDER-PARTIQL-DIAGNOSTICS-P3D-01 → docs/reports/MO-ORDER-PARTIQL-DIAGNOSTICS-P3D-01.md (read-only PartiQL-Diagnosepaket unter docs/diagnostics/dynamodb/, Schema-Referenz mit ORDER#/-Konflikt, GSI3 KEYS_ONLY, IAM-/DSGVO-Grenzen, 15 statische Tests; keine AWS-Ausführung)
- MO-ORDER-BACKUP-ORCHESTRATION-P3A-01 → docs/reports/MO-ORDER-BACKUP-ORCHESTRATION-P3A-01.md (Order-Backup-Kern mit Tabellenidentität gegen Deployment-Kontext, AVAILABLE-only-Polling, PITR-Laufzeitprüfung, Evidenzvertrag, Dry-Run/doppelt gesperrte CLI; 53 Fake-Client-Tests, Installer 490 PASS; kein AWS-Aufruf)
- MO-ORDER-ERASURE-LEDGER-P3E-01 → docs/reports/MO-ORDER-ERASURE-LEDGER-P3E-01.md (lokales OrderErasureLedgerV1 mit HMAC-Pseudonymisierung, Integritäts-/Vollständigkeitsprüfung, fail-closed Restore-Reconciliation-Planer und Privacy-Gates; 49 Tests, Installer 539 PASS; keine Persistenz/Restore/Datenänderung)
- MO-ORDER-LEDGER-PERSISTENCE-P3E-02 → docs/reports/MO-ORDER-LEDGER-PERSISTENCE-P3E-02.md (RC4-Scope-Gate POST_RC4: keine Ledger-Persistenz, keine AWS-Ressource; Erasure-Konsistenz/Transaktionsanalyse; Restore/Cutover bleiben gesperrt) + docs/reports/MO-RC4-READINESS-PRECHECK-01.md (lokal 539/128/326 PASS, RC4 CONDITIONAL, kein realer AWS-Backup-/Upgrade-Nachweis)
- MO-RC4-UPGRADE-RELEASE-GATES-01 → docs/reports/MO-RC4-UPGRADE-RELEASE-GATES-01.md (P3A-Backup-Evidenz in Readiness/Manifest/Apply gebunden, Hash-/Identitaets-/State-Pruefung, exakte Minor-Matrix 0.1.0→0.2.0; 42 neue Tests, Installer 582 PASS, Builder 128, Lambda 326; kein AWS/Apply/Push)
- MO-RC4-AWS-UPGRADE-PLAN-02 → docs/reports/MO-RC4-AWS-UPGRADE-PLAN-02.md (RC4 2e09e72 gegen RC3 0.1.0; Plan 2 create/7 update/0 delete/0 replace/1 read, GSI3 additiv; Backup-Evidence VERIFIED/SHA 9475284f…; P0C BLOCKED durch Drift aws_s3_bucket.trail + cognito_user_pool.users; State 4/lineage 45f61e6a…/fingerprint cbb81a…; kein Manifest/Apply)
- MO-RC4-P0C-DRIFT-FORENSIC-01 → docs/reports/MO-RC4-P0C-DRIFT-FORENSIC-01.md (S3-Policy-Drift = computed/state representation, AWS=State-Policy 2a6c5525…; Cognito null→[] Provider-Normalisierung, Plan no-op; State-Fingerprint instabil durch check_results-Reihenfolge, 3 Pulls verschiedene Hashes bei identischem State; P0C zu streng, Backup-Gate ohne Fingerprint; keine AWS-/State-Mutation)
- MO-RC4-P0C-DRIFT-FIX-01 → docs/reports/MO-RC4-P0C-DRIFT-FIX-01.md (S3 computed-policy + Cognito null/[] nur bei no-op als benigne; kanonischer State-Fingerprint canonical-sha256-v1; Backup-Gate verlangt Fingerprint+Version, Legacy-Evidence fail-closed; 22 neue Tests, Installer 604/Builder 128/Lambda 326 PASS; keine AWS-/State-Mutation)
- MO-RC4-P3A-EVIDENCE-REBIND-01 → docs/reports/MO-RC4-P3A-EVIDENCE-REBIND-01.md (bestehendes Backup ARN 017937… erneut AWS-verifiziert AVAILABLE/PITR; kanonischer Fingerprint 670bc917…/canonical-sha256-v1; neue Evidence 4e2129ff… als EXISTING_BACKUP_REVALIDATION; Gate VERIFIED, Legacy INVALID; negatives Backup-ARN-Gate passiert fälschlich → CONTRACT DECISION REQUIRED; kein neues Backup/keine AWS-Mutation)
