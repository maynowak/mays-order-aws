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

variable "backup_schedule" {
  type    = string
  default = "cron(0 2 ? * * *)"
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "notification_email" {
  type    = string
  default = null
  description = "Optional email address for SNS notifications. If null, no subscription is created."
}
