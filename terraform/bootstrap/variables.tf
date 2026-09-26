variable "aws_region" {
  description = "AWS Region for state bucket and lock table"
  type        = string
  default     = "eu-central-1"
}

variable "state_bucket_name" {
  description = "S3 bucket name for Terraform remote state"
  type        = string
  default     = "mays-orders-tfstate-central-240571105849"
}

variable "lock_table_name" {
  description = "DynamoDB table name for Terraform state locking"
  type        = string
  default     = "mays-orders-terraform-locks"
}
