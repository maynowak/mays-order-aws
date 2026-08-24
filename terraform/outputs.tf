# T011-02 — DynamoDB-Outputs
output "dynamodb_table_name" {
  description = "Name der DynamoDB-Tabelle fuer May's Orders (mays-orders)."
  value       = module.dynamodb.table_name
}

output "dynamodb_table_arn" {
  description = "ARN der DynamoDB-Tabelle fuer May's Orders."
  value       = module.dynamodb.table_arn
}

# T011-03 — IAM-Outputs
output "iam_handler_role_name" {
  description = "Name der Lambda Execution Role fuer den Order Handler."
  value       = module.iam.role_name
}

output "iam_handler_role_arn" {
  description = "ARN der Lambda Execution Role fuer den Order Handler."
  value       = module.iam.role_arn
}

# T011-04 — Lambda-Outputs
output "lambda_function_name" {
  description = "Name der Lambda-Funktion fuer den Order Handler."
  value       = module.lambda.function_name
}

output "lambda_function_arn" {
  description = "ARN der Lambda-Funktion fuer den Order Handler."
  value       = module.lambda.function_arn
}

# T011-05 — Cognito-Outputs
output "cognito_user_pool_id" {
  description = "ID des Cognito User Pools fuer May's Orders."
  value       = module.cognito.user_pool_id
}

output "cognito_user_pool_arn" {
  description = "ARN des Cognito User Pools fuer May's Orders."
  value       = module.cognito.user_pool_arn
}

output "cognito_user_pool_client_id" {
  description = "Client-ID des Cognito App Clients (Public Client, USER_PASSWORD_AUTH)."
  value       = module.cognito.user_pool_client_id
}

output "cognito_user_pool_group_name" {
  description = "Name der Cognito-Gruppe 'staff' (Claim cognito:groups fuer Authorization)."
  value       = module.cognito.user_pool_group_staff_name
}

# T011-06 — API Gateway-Outputs
output "api_gateway_endpoint" {
  description = "Invoke-URL der HTTP API fuer May's Orders."
  value       = module.api.api_endpoint
}

output "api_gateway_id" {
  description = "ID der HTTP API fuer May's Orders."
  value       = module.api.api_id
}

output "api_gateway_authorizer_id" {
  description = "ID des JWT-Authorizers der HTTP API (Cognito User Pool)."
  value       = module.api.authorizer_id
}
