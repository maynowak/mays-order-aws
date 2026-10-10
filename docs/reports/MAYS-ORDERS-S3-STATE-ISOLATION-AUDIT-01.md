# MAYS-ORDERS-S3-STATE-ISOLATION-AUDIT-01

## AWS Account
240571105849

## Backend Configuration
Bucket: mays-orders-tfstate-central-240571105849
Region: eu-central-1
Backend key: terraform.tfstate
workspace_key_prefix: env:
DynamoDB lock table: mays-orders-terraform-locks

## State Objects
env:/mays-order-par/terraform.tfstate
- Workspace: mays-order-par
- Project: mays-order-par
- LastModified: 2026-09-27T11:03:48+00:00
- Size: 412

env:/mays-orders/terraform.tfstate
- Workspace: mays-orders
- Project: mays-orders
- LastModified: 2026-09-27T16:30:02+00:00
- Size: 55166

mays-orders/terraform.tfstate
- Default/legacy key
- LastModified: 2026-09-27T10:35:47+00:00
- Size: 181

true/mays-orders/terraform.tfstate
- Legacy key
- LastModified: 2026-09-27T10:15:22+00:00
- Size: 181

## Project Mapping
- mays-orders → env:/mays-orders/terraform.tfstate
- mays-order-par → env:/mays-order-par/terraform.tfstate
- mays-orders-privacy-test → kein State Objekt vorhanden

## Default State
Ja, mays-orders/terraform.tfstate existiert. Nicht gelöscht, nur dokumentiert.

## Privacy Test State
Erwarteter Key env:/mays-orders-privacy-test/terraform.tfstate existiert nicht.

## Mays-RIS Isolation
Nicht nachweisbar aus S3 Listing. Keine State-Objekte mit Mays-RIS Namensraum gefunden. Ownership UNKNOWN.

## Kollisionen
Keine Kollisionen zwischen bestehenden Projekten. Unterschiedliche Workspace Prefixe.

## Risiken
- Legacy State Objekte ohne workspace_key_prefix existieren
- Privacy Test Projekt hat noch keinen State, wird bei erstem Plan erst angelegt

## Empfehlungen
Isolation funktioniert via workspace_key_prefix env:. Für neues Projekt wird bei erstem Terraform Init State unter env:/mays-orders-privacy-test/terraform.tfstate angelegt.

## Status
YELLOW
