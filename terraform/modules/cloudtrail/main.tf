# T011 — CloudTrail Audit Layer
# Fachquelle: security/cloudtrail-design.md, cost/cost-analysis.md, ADR-Stil der restlichen Module.
# Zweck: Account-weiter AWS-API-Audit-Trail (Management Events), der WHO/WHAT/WHEN/WHERE
# für relevante AWS-API-Aktivität beantwortet. CloudTrail ist KEINE Anwendungs-
# Business-Logik, sondern ein Account-Audit-Concern — bewusst ein eigenes, kleines
# Child-Modul (analog module.monitoring, keine Consumer).
#
# CloudWatch (module.monitoring/lambda) = operational/application monitoring.
# CloudTrail (dieses Modul) = AWS API activity / audit trail. Strikte Trennung.

# Account-ID + Region für eindeutigen Bucket-Namen und CloudTrail-Prefix.
# (keine hardcodierte Account-ID; bleibt über Konten/Stages portierbar)
data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

# Dedizierter, zweckgebundener S3-Bucket für CloudTrail-Logs.
# Bucket-Name global eindeutig: <project>-cloudtrail-<account-id>.
resource "aws_s3_bucket" "trail" {
  bucket = "${var.project_name}-cloudtrail-${data.aws_caller_identity.current.account_id}"

  tags          = merge({ "Project" = var.project_name }, var.tags)
  force_destroy = true
}



# Moderne S3-Eigentümer-Kontrolle: ACLs deaktiviert, nur Bucket-Policy entscheidet.
# Verhindert ACL-basierte öffentliche Objekte (AWS-Best-Practice für neue Buckets).
#resource "aws_s3_bucket_ownership_controls" "trail" {
#  bucket = aws_s3_bucket.trail.id

#  rule {
#    object_ownership = "BucketOwnerEnforced"
#  }
#}

# Öffentlicher Zugriff vollständig gesperrt (Verteidigung in der Tiefe;
# Buckets sind zwar default-privat, dies ist die explizite Sicherung).
resource "aws_s3_bucket_public_access_block" "trail" {
  bucket = aws_s3_bucket.trail.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Explizite Verschlüsselung at rest: SSE-S3 (AES256). AWS-managed default wäre nicht
# dokumentierbar genug; hier wird die Verschlüsselung bewusst konfiguriert.
resource "aws_s3_bucket_server_side_encryption_configuration" "trail" {
  bucket = aws_s3_bucket.trail.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
  depends_on = [aws_s3_bucket.trail]
}

# CloudTrail-Bucket-Policy: Nur der CloudTrail-Service darf schreiben.
# Diese Policy ermöglicht das CloudWatch-Tracing in einem dedizierten S3-Bucket.
resource "aws_s3_bucket_policy" "trail_policy" {
  bucket = aws_s3_bucket.trail.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AWSCloudTrailAclCheck"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action   = "s3:GetBucketAcl"
        Resource = aws_s3_bucket.trail.arn
      },
      {
        Sid    = "AWSCloudTrailWrite"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.trail.arn}/AWSLogs/${data.aws_caller_identity.current.account_id}/*"
        Condition = {
          StringEquals = {
            "aws:SourceArn" = "arn:aws:cloudtrail:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:trail/${var.project_name}-trail"
            "s3:x-amz-acl"  = "bucket-owner-full-control"
          }
        }
      },
      {
        Sid    = "AWSCloudTrailWriteAcl"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action   = "s3:PutObjectAcl"
        Resource = "${aws_s3_bucket.trail.arn}/AWSLogs/${data.aws_caller_identity.current.account_id}/*"
      }
    ]
  })

  depends_on = [aws_s3_bucket.trail]
}

resource "time_sleep" "wait_for_bucket_policy" {
  depends_on      = [aws_s3_bucket_policy.trail_policy]
  create_duration = "60s"
}

# CloudTrail-Trail: Alle Regionen, globale Service-Events (IAM etc.), Management-Events
# (Read+Write), Log-File-Validierung (Integrität) und Logging aktiv.
resource "aws_cloudtrail" "trail" {
  name                          = "${var.project_name}-trail"
  s3_bucket_name                = aws_s3_bucket.trail.id
  is_multi_region_trail         = true
  include_global_service_events = true
  enable_log_file_validation    = true
  enable_logging                = true

  event_selector {
    read_write_type           = "All"
    include_management_events = true
  }

  tags = merge({ "Project" = var.project_name }, var.tags)

  depends_on = [aws_s3_bucket.trail, aws_s3_bucket_policy.trail_policy, time_sleep.wait_for_bucket_policy]
}