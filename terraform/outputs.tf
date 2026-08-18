# T011-02 — DynamoDB-Outputs
output "dynamodb_table_name" {
  description = "Name der DynamoDB-Tabelle fuer May's Orders (mays-orders)."
  value       = aws_dynamodb_table.orders.name
}

output "dynamodb_table_arn" {
  description = "ARN der DynamoDB-Tabelle fuer May's Orders."
  value       = aws_dynamodb_table.orders.arn
}

# T011-03 — IAM-Outputs
output "iam_handler_role_name" {
  description = "Name der Lambda Execution Role fuer den Order Handler."
  value       = aws_iam_role.handler.name
}

output "iam_handler_role_arn" {
  description = "ARN der Lambda Execution Role fuer den Order Handler."
  value       = aws_iam_role.handler.arn
}

# T011-04 — Lambda-Outputs
output "lambda_function_name" {
  description = "Name der Lambda-Funktion fuer den Order Handler."
  value       = aws_lambda_function.handler.function_name
}

output "lambda_function_arn" {
  description = "ARN der Lambda-Funktion fuer den Order Handler."
  value       = aws_lambda_function.handler.arn
}

# T011-05 — Cognito-Outputs
output "cognito_user_pool_id" {
  description = "ID des Cognito User Pools fuer May's Orders."
  value       = aws_cognito_user_pool.users.id
}

output "cognito_user_pool_arn" {
  description = "ARN des Cognito User Pools fuer May's Orders."
  value       = aws_cognito_user_pool.users.arn
}

output "cognito_user_pool_client_id" {
  description = "Client-ID des Cognito App Clients (Public Client, USER_PASSWORD_AUTH)."
  value       = aws_cognito_user_pool_client.app.id
}

output "cognito_user_pool_group_name" {
  description = "Name der Cognito-Gruppe 'staff' (Claim cognito:groups fuer Authorization)."
  value       = aws_cognito_user_group.staff.name
}
