locals {
  bucket_name = lower("${var.bucket_name_prefix}-${var.environment}-${var.project_name}")
}

resource "aws_s3_bucket" "cognito_backup" {
  bucket = local.bucket_name

  tags = merge(
    {
      "Project"     = var.project_name
      "Environment" = var.environment
      "Purpose"     = "CognitoUserDataBackup"
    },
    var.tags
  )
}

resource "aws_s3_bucket_versioning" "cognito_backup" {
  bucket = aws_s3_bucket.cognito_backup.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "cognito_backup" {
  bucket = aws_s3_bucket.cognito_backup.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "cognito_backup" {
  bucket = aws_s3_bucket.cognito_backup.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "cognito_backup" {
  bucket = aws_s3_bucket.cognito_backup.id

  rule {
    id     = "cognito-backup-lifecycle"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

output "bucket_name" {
  description = "Backup bucket name"
  value       = aws_s3_bucket.cognito_backup.id
}

output "bucket_arn" {
  description = "Backup bucket ARN"
  value       = aws_s3_bucket.cognito_backup.arn
}
