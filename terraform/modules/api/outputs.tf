# T011-06 — API Gateway-Outputs
output "api_id" {
  description = "ID der HTTP API fuer May's Orders."
  value       = aws_apigatewayv2_api.orders.id
}

output "api_endpoint" {
  description = "Invoke-URL der HTTP API fuer May's Orders."
  value       = aws_apigatewayv2_api.orders.api_endpoint
}

output "api_stage_name" {
  description = "Name der API Stage ($default)."
  value       = aws_apigatewayv2_stage.default.name
}

output "authorizer_id" {
  description = "ID des JWT-Authorizers der HTTP API (Cognito User Pool)."
  value       = aws_apigatewayv2_authorizer.jwt.id
}

output "integration_id" {
  description = "ID der Lambda Integration."
  value       = aws_apigatewayv2_integration.lambda.id
}