variable "project_name" {
  description = "Project name used for the secret name prefix."
  type        = string
}

variable "tags" {
  description = "Additional tags for the secret."
  type        = map(string)
  default     = {}
}

variable "kms_key_arn" {
  description = "Optional existing customer-managed KMS key ARN; empty uses the AWS-managed Secrets Manager key. No key is created here."
  type        = string
  default     = ""

  validation {
    condition = (
      var.kms_key_arn == "" ||
      can(regex("^arn:aws:kms:[a-z0-9-]+:[0-9]{12}:key/[A-Za-z0-9-]+$", var.kms_key_arn))
    )
    error_message = "kms_key_arn must be empty or an exact KMS key ARN (arn:aws:kms:<region>:<account>:key/<id>)."
  }
}
