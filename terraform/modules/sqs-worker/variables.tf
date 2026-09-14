variable "project_name" {
  description = "Project name prefix"
  type        = string
}

variable "tags" {
  description = "Tags for resources"
  type        = map(string)
  default     = {}
}

variable "sqs_queue_arn" {
  description = "ARN of the SQS queue"
  type        = string
}

variable "sqs_queue_name" {
  description = "Name of the SQS queue"
  type        = string
}

variable "dynamodb_table_name" {
  description = "Name of DynamoDB table"
  type        = string
}

variable "lambda_execution_boundary" {
  description = "IAM permissions boundary"
  type        = string
  default     = "arn:aws:iam::240571105849:policy/Mays-Orders-Lambda-Execution-Boundary"
}

variable "filename" {
  description = "Path to Lambda zip"
  type        = string
}

variable "handler" {
  description = "Lambda handler"
  type        = string
  default     = "sqs_handler.handler"
}

variable "runtime" {
  description = "Lambda runtime"
  type        = string
  default     = "python3.14"
}

variable "timeout" {
  description = "Lambda timeout"
  type        = number
  default     = 10
}

variable "monitoring_enabled" {
  description = "Enable monitoring"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "Log retention days"
  type        = number
  default     = 7
}