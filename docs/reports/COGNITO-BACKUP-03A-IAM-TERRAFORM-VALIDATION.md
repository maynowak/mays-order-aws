# COGNITO-BACKUP-03A IAM / TERRAFORM VALIDATION

**Datum:** 2026-09-27
**Branch:** main
**Commit Basis:** a60820d

## 1. AccessDenied Ermittlung

Ursprünglicher Fehler:
```
Error loading state: failed to lock s3 state: operation error DynamoDB: PutItem
AccessDeniedException: User: arn:aws:iam::992382612204:user/maymilly is not authorized to perform: dynamodb:PutItem on resource: arn:aws:dynamodb:eu-central-1:992382612204:table/mays-orders-terraform-locks
```

- Verwendetes AWS Profile: Default / nicht gesetzt
- Account: 992382612204
- IAM Identity: arn:aws:iam::992382612204:user/maymilly
- Aufgerufene API: dynamodb:PutItem, dynamodb:GetItem
- Resource: mays-orders-terraform-locks
- Fehlerursache: Terraform wurde ohne korrektes AWS Profile ausgeführt

Korrektes Profile:
```
AWS_PROFILE=mayaws
Account: 240571105849
User: arn:aws:iam::240571105849:user/Mayaws
Region: eu-central-1
```

Mit korrektem Profile:
- terraform init -backend=false: PASS
- terraform validate: Success!
- terraform plan -lock=false: PASS

## 2. Bestehendes IAM Design

Bestehende IAM-Struktur:
- Terraform Deployment wird über User Mayaws im Account 240571105849 ausgeführt
- Remote State Backend: S3 Bucket mays-orders-tfstate-central-240571105849, DynamoDB mays-orders-terraform-locks
- Keine parallele IAM-Architektur erforderlich

## 3. Backup IAM Requirements

Terraform Infrastruktur:
- s3:CreateBucket, s3:PutBucketVersioning, s3:PutEncryptionConfiguration, s3:PutPublicAccessBlock, s3:PutLifecycleConfiguration, s3:TagResource
- Resource: arn:aws:s3:::mays-orders-cognito-backup-Development-mays-orders

Backup Runtime später:
- cognito-idp:ListUsers, cognito-idp:ListGroups
- s3:PutObject, s3:GetObject, s3:ListBucket
- Resource Scope: Bucket + Prefix project/environment/*

## 4. Least Privilege

Kein AdministratorAccess erforderlich.
Resource Scoping auf Bucket und Prefix möglich.

## 5. Terraform Validierung

- terraform init -backend=false: SUCCESS
- terraform validate: SUCCESS
- terraform plan -lock=false: SUCCESS
Plan zeigt Erstellung von:
  - module.cognito_backup.aws_s3_bucket.cognito_backup
  - module.cognito_backup.aws_s3_bucket_versioning.cognito_backup
  - module.cognito_backup.aws_s3_bucket_server_side_encryption_configuration.cognito_backup
  - module.cognito_backup.aws_s3_bucket_public_access_block.cognito_backup
  - module.cognito_backup.aws_s3_bucket_lifecycle_configuration.cognito_backup

Kein Apply ausgeführt.

## 6. Multi-Project

- Backup Bucket zentral, Prefix project/environment/timestamp
- Terraform Workspace unverändert
- Remote State unverändert

## 7. Tests

- terraform fmt: OK
- terraform validate: PASS
- terraform plan: PASS
- Unit Tests: PASS

## 8. Offene Punkte

- IAM Policy für Backup Runtime noch nicht implementiert
- RPO/RTO noch offen
- Terraform Apply noch ausstehend

## Zusammenfassung

Blockade behoben durch korrekte Verwendung von AWS_PROFILE=mayaws.
Keine IAM Änderungen am bestehenden Deployment-Account erforderlich.
Terraform Validation erfolgreich.
