# COGNITO-BACKUP-03C-RETRY FIRST REAL BACKUP

**Datum:** 2026-09-27
**Profile:** mayaws
**Account:** 240571105849
**Region:** eu-central-1

## 1. AWS Identity
AWS_PROFILE=mayaws
Account: 240571105849
OK

## 2. Project
mays-orders
Development

## 3. Cognito Pool
ID: eu-central-1_xhjl0PxEH
Name: mays-orders-users
User Count: 0
Group Count: 1

## 4. Backup Execution
Backup ID: 20260927T153159Z-458635ac
Timestamp: 2026-09-27T15-31-59Z
S3 Bucket: mays-orders-cognito-backup-development-mays-orders
S3 Prefix: mays-orders/Development/2026-09-27T15-31-59Z/

## 5. Manifest Validation
schema_version: 1.0
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

## 6. Checksum Validation
users.json SHA256: 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945 - PASS
groups.json SHA256: d228b25a9bb9045365db7c844fb288381e187760552bfd920a40cba6495e0583 - PASS

## 7. Readback Validation
S3 objects present:
- manifest.json
- users.json
- groups.json
Readback successful, checksums match
PASS

## 8. Password Exclusion
No password, password_hash, credentials, temporary_password, secret found in backup
PASS

## 9. Multi-Project Validation
project_name = mays-orders
environment = Development
Cross-project validation passes
PASS

## 10. Cognito Mutation Check
User Count after backup: 0
Group Count after backup: 1
No changes detected
PASS

## 11. Terraform State Check
Terraform state unchanged
Remote state unchanged
Backup bucket unchanged

## 12. Test Results
Unit tests: PASS
Integration test: PASS
Backup Status: SUCCESS

## 13. Known Limitations
User count zero is valid
No user data to export
Group membership export works but no members
