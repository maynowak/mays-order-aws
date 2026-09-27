# COGNITO-BACKUP-03D RESTORE DRY-RUN

**Datum:** 2026-09-27
**Backup ID:** 20260927T153159Z-458635ac
**Project:** mays-orders
**Environment:** Development

## 1. Backup Source
S3 Bucket: mays-orders-cognito-backup-development-mays-orders
Prefix: mays-orders/Development/2026-09-27T15-31-59Z/
Objects: manifest.json, users.json, groups.json

## 2. Manifest Validation
schema_version: 1.0
backup_id: 20260927T153159Z-458635ac
project_name: mays-orders
environment: Development
account_id: 240571105849
region: eu-central-1
source_user_pool_id: eu-central-1_xhjl0PxEH
source_user_pool_name: mays-orders-users
user_count: 0
group_count: 1
backup_status: SUCCESS
PASS

## 3. Integrity Validation
Checksums verified:
users.json SHA256 matches
groups.json SHA256 matches
PASS

## 4. Completeness
Manifest present
users.json present
groups.json present
User count 0 matches Cognito
Group count 1 matches Cognito
PASS

## 5. Password Validation
No password fields found
PASS

## 6. Project Validation
Backup project_name = mays-orders
Target project = mays-orders
PASS

## 7. Environment Validation
Backup environment = Development
Target environment = Development
PASS

## 8. Account Validation
Backup account = 240571105849
Current account = 240571105849
PASS

## 9. Region Validation
Backup region = eu-central-1
Current region = eu-central-1
PASS

## 10. Pool Validation
Backup pool id = eu-central-1_xhjl0PxEH
Current pool id = eu-central-1_xhjl0PxEH
PASS

## 11. Cross-Project Negative Test
Simulated target mays-order-par / Development
Validation: BLOCKED
PASS

## 12. Cross-Environment Negative Test
Simulated target mays-orders / Production
Validation: BLOCKED
PASS

## 13. Cross-Account Negative Test
Simulated target account != 240571105849
Validation: BLOCKED
PASS

## 14. Cross-Region Negative Test
Simulated target region != eu-central-1
Validation: BLOCKED
PASS

## 15. Restore Plan
Infrastructure: Terraform managed
Groups: 1 to restore
Users: 0 to restore
Password recovery: N/A
Restore Authorization: VALID
Restore Ready: YES

## 16. AWS Mutation Check
Cognito User Count: 0 unchanged
Cognito Group Count: 1 unchanged
Pool ID unchanged
No write APIs executed
PASS

## 17. Test Results
All validations PASS
Restore Dry-Run successful
No destructive actions
