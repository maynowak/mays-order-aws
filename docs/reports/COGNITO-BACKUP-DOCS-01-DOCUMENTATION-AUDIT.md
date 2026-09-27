# COGNITO-BACKUP-DOCS-01 DOCUMENTATION + INSTALLATION FLOW AUDIT

## COGNITO BACKUP OPERATIONS

### What is secured
- Cognito Users
- User Attributes
- Groups
- Group Memberships
Passwords are NOT exported.

### Infrastructure
Terraform reproduces:
- Cognito User Pool
- App Client
- Groups
- Backup Infrastructure
- Lambda
- Scheduler
- IAM
- Monitoring
- SNS

### Backup storage
S3 Bucket: mays-orders-cognito-backup-development-mays-orders
Structure: mays-orders/Development/<timestamp>/<backup-id>/

### Backup composition
- Backup ID
- Manifest
- Counts
- Checksums
- S3 Storage
- Readback/Validation

### Automation flow
EventBridge Scheduler
→ Lambda
→ Cognito Export
→ S3 Backup
→ Manifest / Checksum
→ Validation

### Monitoring
Lambda Metrics
→ CloudWatch Alarms
→ SNS Topic

### Alerting
CloudWatch Alarm
→ SNS Topic
→ Email Subscription
→ confirmed recipient

SNS Topic: mays-orders-cognito-backup-notifications
Recipient: nowakbewerbung@gmail.com
Subscription: Confirmed

## INSTALLER AUDIT

Installer entry point: ./Mays-Order-AWS-installer
Entry: installer/cli/main.py

Global options:
--profile
--region
--project-name
--environment
--terraform-dir
--run-dir
--deployment-version
--development-phase
--development-step
--development-status

Notification / SNS / Email option: NOT FOUND

No notification email variable / CLI argument exists in installer.

Installer currently does NOT expose notification configuration.

## RECOMMENDATION

Notification email should be optional during installation.

Current state: No option exists.

Documented as NOT FOUND.

## RPO
OPEN

## RTO
OPEN

## Status
DOCUMENTATION COMPLETE
INSTALLER AUDIT COMPLETE
NOTIFICATION OPTION NOT FOUND
