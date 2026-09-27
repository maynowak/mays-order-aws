# COGNITO-BACKUP-RPO-RTO-01 DEFINE STANDARD RPO/RTO

## RPO
24 hours

Daily automated backup at 02:00 UTC.
Maximum data loss = one backup interval.

## RTO
4 hours

Recovery target for Cognito user data restore.
Includes infrastructure recovery, manifest validation, user/attribute/group restore, password reset, post-restore validation.

## Notes
RTO is a target, not a measured SLA guarantee.

## AWS Mutation
NONE

## Terraform
Unchanged

## Status
GREEN
