variable "project_name" {
  description = "Project name for backup bucket naming and tags"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]*$", var.project_name))
    error_message = "project_name must contain only lowercase letters, digits and hyphens (no leading/trailing hyphen)."
  }
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "Development"
}

variable "tags" {
  description = "Tags for resources"
  type        = map(string)
  default     = {}
}

variable "bucket_name_prefix" {
  description = <<-EOT
    Optional explicit prefix for the backup bucket name. When set, the legacy
    format "<prefix>-<environment>-<project_name>" is used unchanged
    (backwards compatible for existing installations).

    When null (default) the name is derived namespace-safely:
      * project_name = "mays-orders"  -> historical name
        "mays-orders-cognito-backup-<environment>-mays-orders" (unchanged, no replacement)
      * any other project_name        -> "<project_name>-cognito-backup-<environment>"
        (starts with the project prefix, so the Terraform policy gate accepts it)
  EOT
  type        = string
  default     = null

  validation {
    condition     = var.bucket_name_prefix == null || can(regex("^[a-z0-9][a-z0-9-]*$", var.bucket_name_prefix))
    error_message = "bucket_name_prefix must be null or contain only lowercase letters, digits and hyphens (no leading/trailing hyphen)."
  }
}
