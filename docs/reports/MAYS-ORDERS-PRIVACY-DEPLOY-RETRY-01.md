# MAYS-ORDERS-PRIVACY-DEPLOY-RETRY-01

## Baseline
Commit `2417552` (AWS-Profil-Kontext-Fix). Remote main als Source of Truth.

## Verifikation (alle GREEN)
- **AWS-Identität:** `identity --profile mayaws` → Account `240571105849`,
  ARN `arn:aws:iam::240571105849:user/Mayaws`. Stimmt mit
  `aws sts get-caller-identity --profile mayaws` überein (Profil-Fix bestätigt).
- **Workspace:** `mays-orders-privacy-test` (explizit via Kontext, keine
  globalen Env-Mutationen mehr).
- **Frischer Plan:** `.mays-installer/runs/20261011-111121/plans/mays-orders-privacy-test-development-0.1.0-H2-240571105849-deploy-0006.tfplan`
  - 61 Resource-Changes: 56× `create`, 5× `read`, 0 Update/Delete.
  - Keine Cross-Projekt-Adressen. Safety Analysis: PASS.

## Policy Gate: RED → STOP
Deploy mit frischem Plan `deploy-0006` wurde vom Policy Gate blockiert
(kein Apply, keine Mutationen). 12 Findings, identisch zum Vorlauf:
- `module.cognito_backup.aws_s3_bucket.cognito_backup`: Bucket-Name
  `mays-orders-cognito-backup-development-mays-orders-privacy-test` außerhalb
  Namespace `mays-orders-privacy-test-*`.
- Nicht erlaubte Typen: `aws_s3_bucket_lifecycle_configuration`,
  `aws_s3_bucket_versioning`, `aws_iam_policy` (×2),
  `aws_iam_role_policy_attachment` (×2), `aws_scheduler_schedule`,
  `aws_sns_topic`, `aws_sns_topic_policy`, `aws_sns_topic_subscription`.
- `module.cognito_backup_automation.aws_lambda_function.backup`:
  Timeout 300s > max 10s.

Keine Policy-Umgehung vorgenommen.

## Nicht ausgeführt (per STOP-Regel)
- Deployment (blockiert), AWS-Smoke-Tests, Privacy-E2E, Regression: NOT TESTED.

## Mutationen
NONE. DynamoDB-Tabellen unverändert (kein Privacy-Test-Table), Workspace
weiter `mays-orders-privacy-test`, bestehende Installationen unberührt.
Kein Destroy, keine neuen Installer, keine Refactorings.

## Verbleibende Blocker (exakt)
1. `cognito_backup`-Bucket-Namensschema verletzt Projekt-Namespace.
2. `cognito_backup`/`cognito_backup_automation`-Ressourcentypen fehlen in
   `terraform/policy/resource-policy.json` (Allowlist).
3. Backup-Lambda-Timeout (300s) verletzt Policy-Maximum (10s).
→ Entscheidung erforderlich: Policy erweitern ODER Backup-Module für
Testprojekt deaktivierbar machen. Beides ist eine Governance-Entscheidung
mit menschlicher Freigabe, kein automatischer Fix.

## Status: RED (Policy Gate)
Nächste Aktion: Menschliche Entscheidung zu Blocker 1–3 einholen.
