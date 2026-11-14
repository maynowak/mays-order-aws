output "arn" {
  description = "ARN of the optional privacy secret container (no secret value)."
  value       = aws_secretsmanager_secret.privacy.arn
}

output "name" {
  description = "Name of the optional privacy secret container."
  value       = aws_secretsmanager_secret.privacy.name
}
