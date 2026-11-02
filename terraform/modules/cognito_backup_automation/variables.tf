variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "user_pool_id" {
  type = string
}

variable "user_pool_name" {
  type = string
}

variable "bucket_name" {
  type = string
}

variable "bucket_arn" {
  description = <<-EOT
    ARN des Cognito-Backup-Buckets (aus dem Backup-Modul). Bevorzugt fuer
    IAM-Ressourcen, damit keine ARN aus einem Bucket-Namen rekonstruiert wird.
    null = Legacy-Fallback auf "arn:aws:s3:::<bucket_name>" (bestehender
    Modulvertrag bleibt gueltig).
  EOT
  type        = string
  default     = null

  validation {
    condition     = var.bucket_arn == null || can(regex("^arn:aws[a-z-]*:s3:::[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$", var.bucket_arn))
    error_message = "bucket_arn must be null or a valid S3 bucket ARN (arn:aws:s3:::<bucket-name>)."
  }
}

variable "backup_schedule" {
  type    = string
  default = "cron(0 2 ? * * *)"
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "notification_email" {
  type        = string
  default     = null
  description = "Optional email address for SNS notifications. If null, no subscription is created."
}
