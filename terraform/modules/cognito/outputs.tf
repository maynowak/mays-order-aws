# T011-05 — Cognito-Outputs
output "user_pool_id" {
  description = "ID des Cognito User Pools fuer May's Orders."
  value       = aws_cognito_user_pool.users.id
}

output "user_pool_arn" {
  description = "ARN des Cognito User Pools fuer May's Orders."
  value       = aws_cognito_user_pool.users.arn
}

output "user_pool_endpoint" {
  description = "Endpoint des Cognito User Pools (fuer JWT Issuer URL)."
  value       = aws_cognito_user_pool.users.endpoint
}

output "user_pool_client_id" {
  description = "Client-ID des Cognito App Clients (Public Client, USER_PASSWORD_AUTH)."
  value       = aws_cognito_user_pool_client.app.id
}

output "user_pool_group_staff_name" {
  description = "Name der Cognito-Gruppe 'staff' (Claim cognito:groups fuer Authorization)."
  value       = aws_cognito_user_group.staff.name
}