# Bootstrap infrastructure for Terraform Remote State
# This configuration creates S3 bucket and DynamoDB lock table for remote state
# Bootstrap state remains LOCAL. Do NOT configure remote backend for this config.

# S3 bucket for Terraform remote state
resource "aws_s3_bucket" "terraform_state" {
  bucket = var.state_bucket_name

  tags = {
    Project     = "mays-orders"
    ManagedBy   = "Terraform"
    Environment = "Development"
    Purpose     = "TerraformRemoteState"
  }
}

resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Tags are set directly on aws_s3_bucket resource
# aws_s3_bucket_tags resource removed as tags argument is sufficient

# DynamoDB table for Terraform state locking
resource "aws_dynamodb_table" "terraform_locks" {
  name         = var.lock_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = {
    Project     = "mays-orders"
    ManagedBy   = "Terraform"
    Environment = "Development"
    Purpose     = "TerraformStateLocking"
  }
}
