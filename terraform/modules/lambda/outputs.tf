# T011-04 — Lambda-Outputs
output "function_name" {
  description = "Name der Lambda-Funktion fuer den Order Handler."
  value       = aws_lambda_function.handler.function_name
}

output "function_arn" {
  description = "ARN der Lambda-Funktion fuer den Order Handler."
  value       = aws_lambda_function.handler.arn
}

output "invoke_arn" {
  description = "Invoke ARN der Lambda-Funktion (fuer API Gateway Integration)."
  value       = aws_lambda_function.handler.invoke_arn
}

output "log_group_name" {
  description = "Name der CloudWatch Log Group der Lambda-Funktion."
  value       = aws_cloudwatch_log_group.handler[0].name
}