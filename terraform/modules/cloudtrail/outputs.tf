# T011 — CloudTrail-Outputs
# Bewusst NUR Modul-Outputs (kein Root-Re-Export): kein anderer Modul/Operator
# konsumiert CloudTrail-IDs; sie dienen lediglich der nachgelagerten Verifikation
# (terraform output nach apply). Root-Design-Prinzip: Outputs nur bei echten Consumern.
output "trail_name" {
  description = "Name des CloudTrail-Trails (Account-Audit-Trail)."
  value       = aws_cloudtrail.trail.name
}

output "trail_arn" {
  description = "ARN des CloudTrail-Trails."
  value       = aws_cloudtrail.trail.arn
}

output "s3_bucket_name" {
  description = "Name des S3-Buckets fuer CloudTrail-Logs."
  value       = aws_s3_bucket.trail.id
}

output "s3_bucket_arn" {
  description = "ARN des S3-Buckets fuer CloudTrail-Logs."
  value       = aws_s3_bucket.trail.arn
}