# MAYS-ORDERS-COGNITO-STATE-FORENSICS-01

## Git HEAD
e5849fc

## AWS Identität
Profile: mayaws
Account: 240571105849
Region: eu-central-1

## Projekt Kontext
PROJECT_NAME: mays-orders-privacy-test
InstallationContext.project_name: mays-orders-privacy-test
InstallationContext.terraform_workspace: mays-orders-privacy-test
TERRAFORM_WORKSPACE: mays-orders-privacy-test
TF_VAR_project_name: mays-orders-privacy-test

## Terraform Workspace
Aktuell aktive Workspaces:
- default
- mays-order-par
- mays-orders
- mays-orders-privacy-test *

## Backend
Bucket: mays-orders-tfstate-central-240571105849
Key Prefix: env:
Workspace State Key: env:/mays-orders-privacy-test/terraform.tfstate
State existiert ab 2026-10-10T14:09:17+00:00

## Plan Forensik
Plan Datei: .mays-installer/runs/20261010-160045/plans/mays-orders-privacy-test-development-0.1.0-H2-240571105849-deploy-0003.tfplan

Cognito Ressourcen:

module.cognito.aws_cognito_user_pool.users
- Address: module.cognito.aws_cognito_user_pool.users
- Resource ID: eu-central-1_xhjl0PxEH
- Actions: update
- Diff: name mays-orders-users → mays-orders-privacy-test-users
  tags Project mays-orders → mays-orders-privacy-test

module.cognito.aws_cognito_user_pool_client.app
- Address: module.cognito.aws_cognito_user_pool_client.app
- Resource ID: 5tac9c0uh5q6d5tjdse94jpf8s
- Actions: update
- Diff: name mays-orders-client → mays-orders-privacy-test-client

module.cognito_backup.aws_s3_bucket.cognito_backup
- Actions: delete then create replacement
- Bucket: mays-orders-cognito-backup-development-mays-orders → mays-orders-cognito-backup-development-mays-orders-privacy-test

## Analyse
Die UPDATE Aktionen referenzieren bestehende Ressourcen mit IDs:
- User Pool eu-central-1_xhjl0PxEH
- Client 5tac9c0uh5q6d5tjdse94jpf8s

Diese Ressourcen gehören zum Projekt mays-orders, nicht zu mays-orders-privacy-test.

Der Plan wurde erzeugt, während Terraform Workspace mays-orders aktiv war.
Der Installer hat die Workspace-Erstellung mays-orders-privacy-test nicht vor Terraform Init/Plan ausgeführt, sodass die bestehende State env:/mays-orders/terraform.tfstate verwendet wurde.

## Root Cause
B. Falscher Workspace aktiv
Der Workspace mays-orders-privacy-test existierte zum Zeitpunkt der Plan-Erzeugung nicht.
TerraformRunner.__init__ liest TERRAFORM_WORKSPACE korrekt, aber Workspace-Selektion/Erstellung erfolgte erst im run_and_get_result, das bei init/plan nicht zuverlässig vor dem Backend-Lock ausgeführt wurde.
Resultat: Plan nutzte State von mays-orders → Cognito UPDATE/Replacement.

## Minimal notwendige Korrektur
Workspace explizit vor Terraform Init selektieren/erstellen und State-Isolation sicherstellen.
Aktuell ist Workspace mays-orders-privacy-test manuell angelegt und State existiert.

## Sicherheitsbewertung
Keine Ressourcenmutationen durchgeführt. Plan war nur Read-Only.
Kein Datenverlust. Keine Cross-Project-Änderungen ausgeführt.
Risiko: Bei Apply hätten bestehende Cognito Ressourcen überschrieben werden können.

## Status
YELLOW – Ursache nachgewiesen, Korrektur manuell durchgeführt, automatische Workspace-Erstellung muss sichergestellt werden.
