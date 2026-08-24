# T011-03 — IAM-Outputs
output "role_name" {
  description = "Name der Lambda Execution Role fuer den Order Handler."
  value       = aws_iam_role.handler.name
}

output "role_arn" {
  description = "ARN der Lambda Execution Role fuer den Order Handler."
  value       = aws_iam_role.handler.arn
}

output "policy_name" {
  description = "Name der Inline-Policy fuer den Order Handler."
  value       = aws_iam_role_policy.handler.name
}