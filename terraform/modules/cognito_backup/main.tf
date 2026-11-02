locals {
  # MO-RC4-P02I-E1B: Namespace-Vertrag des Cognito-Backup-Buckets.
  #
  # 1) Explizites Praefix (Legacy-Format) gewinnt — Bestandsschutz fuer
  #    Installationen, die das Praefix bereits bewusst gesetzt haben.
  # 2) Die Default-Installation ("mays-orders") behaelt exakt ihren
  #    historischen Bucket-Namen. Eine Aenderung wuerde einen
  #    destroy/create (Bucket-Replacement) im Plan erzeugen.
  # 3) Jedes andere Projekt erhaelt einen Namen in seinem EIGENEN
  #    "<project_name>-"-Namespace. Nur so kann das Policy Gate
  #    (terraform/policy/validate-plan.py, S3-Namespace-Pruefung) die
  #    Bucket-Zugehoerigkeit korrekt validieren.
  explicit_bucket_name = (
    var.bucket_name_prefix == null
    ? null
    : lower("${var.bucket_name_prefix}-${var.environment}-${var.project_name}")
  )
  legacy_default_bucket_name = lower("mays-orders-cognito-backup-${var.environment}-${var.project_name}")
  project_scoped_bucket_name = lower("${var.project_name}-cognito-backup-${var.environment}")

  bucket_name = (
    local.explicit_bucket_name != null ? local.explicit_bucket_name : (
      var.project_name == "mays-orders"
      ? local.legacy_default_bucket_name
      : local.project_scoped_bucket_name
    )
  )
}

resource "aws_s3_bucket" "cognito_backup" {
  bucket = local.bucket_name

  lifecycle {
    # S3-Bucket-Namen sind global eindeutig und auf 63 Zeichen begrenzt.
    # Fail-closed im Plan statt Fehler erst beim Apply.
    precondition {
      condition     = length(local.bucket_name) <= 63 && can(regex("^[a-z0-9][a-z0-9.-]*$", local.bucket_name))
      error_message = "Cognito-Backup-Bucket-Name '${local.bucket_name}' ist ungueltig: maximal 63 Zeichen, nur Kleinbuchstaben, Ziffern, '.' und '-', kein fuehrendes Sonderzeichen."
    }
  }

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
