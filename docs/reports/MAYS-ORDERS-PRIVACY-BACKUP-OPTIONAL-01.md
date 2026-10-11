# MAYS-ORDERS-PRIVACY-BACKUP-OPTIONAL-01

## Entscheidung
Keine Policy-Allowlist-Erweiterung. Stattdessen sind `cognito_backup` und
`cognito_backup_automation` pro Deployment deaktivierbar (Standard: aktiviert).

## Änderungen (minimal)
- `terraform/variables.tf`: neu `enable_cognito_backup` (default `true`),
  `enable_cognito_backup_automation` (default `true`). Keine bestehenden
  Schalter vorhanden, keine Defaults geändert → Bestandsverhalten erhalten.
- `terraform/main.tf`:
  - Beide Module mit `count` (`automation` nur wenn Backup ebenfalls an:
    `var.enable_cognito_backup && var.enable_cognito_backup_automation`).
  - `bucket_name = try(module.cognito_backup[0].bucket_name, "")` für
    count=0-Verträglichkeit.
  - `moved`-Blöcke `module.cognito_backup → module.cognito_backup[0]` und
    `module.cognito_backup_automation → module.cognito_backup_automation[0]`
    erhalten den bestehenden State (kein Replace bei Bestandsinstallationen).

## Privacy-Testprojekt
- Frischer Plan `...-deploy-0007.tfplan` mit
  `--var enable_cognito_backup=false --var enable_cognito_backup_automation=false`:
  39 Changes (37× create, 2× read), **0 Backup-Ressourcen**, nur 2 Lambdas
  (handler + sqs-worker, keine 300s-Backup-Lambda), keine Cross-Projekt-Adressen.
- Policy Gate: **PASSED**. Safety: PASS. 37 to add, 0 change/destroy/replace.
- Deployment mit `--yes` (Task-Freigabe für isoliertes Testprojekt):
  **successful**, Post-Apply-Verifikation OK (State + Identity).

## Bestandsnachweis mays-orders (nur Plan, kein Apply)
- Read-only Plan: 58 Changes (36× create noch nie deployed/neu in Config,
  20× no-op, 2× read), **0 delete/update/replace**.
- Backup-Module: 17× no-op (moved-Blöcke wirken), 2× create
  (`scheduler_policy`, `scheduler_attach`) = Config-Drift seit Deployment,
  nicht durch diese Änderung verursacht (fehlen im State `env:/mays-orders/`).
- Bestehende Installation unverändert.

## Tests
- `terraform validate` + `fmt -check`: PASS.
- Installer-Unit-Tests (AWS-Kontext, Workspace, Parallel-Isolation,
  Plan-Discovery): 14/14 OK.

## Governance
Keine Policy-Lockerung, kein Destroy, kein State-Import, keine Änderungen an
`mays-orders`/`mays-ris` (nur lesender Plan für Nachweis).

## Status: GREEN
