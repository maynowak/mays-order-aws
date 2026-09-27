variable "project_name" {
  description = "Project name for backup bucket naming and tags"
  type        = string
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
  description = "Prefix for backup bucket name"
  type        = string
  default     = "mays-orders-cognito-backup"
}
