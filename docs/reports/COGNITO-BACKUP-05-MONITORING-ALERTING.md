# COGNITO-BACKUP-05 MONITORING & ALERTING

## Monitoring Implemented
CloudWatch Metric Alarms for Lambda Errors and Invocations
Alarm names:
mays-orders-cognito-backup-lambda-errors
mays-orders-cognito-backup-invocations-failed

## Alerting
Alarms created without SNS target - notification target open per project decision

## Success Path
Lambda invocation successful
Backup generated
Metrics collected

## Failure Path
Alarm triggers on Lambda Errors >0

## Recovery Path
Normal operation resumes

## Cognito Safety
No mutations

## RPO
OPEN

## RTO
OPEN

## Terraform
Validate PASS
Apply PASS
Post-plan PASS

## AI_AUDITLOG
As defined by template - unchanged

## Git
CLEAN
