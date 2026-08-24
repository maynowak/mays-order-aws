# T011-06 — API Gateway HTTP API + Routen + JWT Authorizer
# Fachquelle: ADR-004 (HTTP API V2), api/endpoints.md, api/api-documentation.md,
# security/authentication-decision.md (JWT-Flow §3), security/iam-design.md §3.
# Scope: HTTP API + Stage, Lambda-Integration (Payload v2), vier dokumentierte
# Routen, JWT-Authorizer (Cognito), Lambda-Invoke-Permission.

resource "aws_apigatewayv2_api" "orders" {
  name          = "${var.project_name}-api"
  protocol_type = "HTTP"
  description   = "May's Orders HTTP API (API Gateway V2) — vier Order-Routen"

  tags = merge({ "Project" = var.project_name }, var.tags)
}

# $default-Stage mit Auto-Deploy: jede Route-/Integration-Änderung wird direkt deployed
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.orders.id
  name        = "$default"
  auto_deploy = true

  tags = merge({ "Project" = var.project_name }, var.tags)
}

# JWT-Authorizer: Cognito User Pool als Issuer, App Client ID als Audience.
# Issuer = https://<cognito-idp endpoint> (= "cognito-idp.<region>.amazonaws.com/<pool-id>"),
# abgeleitet aus cognito_user_pool_endpoint (keine hardcodierte Region/ID).
resource "aws_apigatewayv2_authorizer" "jwt" {
  api_id           = aws_apigatewayv2_api.orders.id
  authorizer_type  = "JWT"
  name             = "${var.project_name}-jwt-authorizer"
  identity_sources = ["$request.header.Authorization"]

  jwt_configuration {
    audience = [var.cognito_user_pool_client_id]
    issuer   = "https://${var.cognito_user_pool_endpoint}"
  }
}

# Einzige Integration: bestehende Lambda (Python 3.14).
# AWS_PROXY + Payload Format 2.0 → Event-Contract des Handlers
# (routeKey, pathParameters, queryStringParameters, body, isBase64Encoded; v2-Proxy-Response).
resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.orders.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.lambda_invoke_arn
  payload_format_version = "2.0"
}

# Vier dokumentierte Routen (api/endpoints.md, api/api-documentation.md) — alle Auth:
# erforderlich (Cognito JWT). Keine zusätzlichen/öffentlichen Routen.
resource "aws_apigatewayv2_route" "create_order" {
  api_id             = aws_apigatewayv2_api.orders.id
  route_key          = "POST /orders"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "get_order" {
  api_id             = aws_apigatewayv2_api.orders.id
  route_key          = "GET /orders/{orderId}"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "list_orders" {
  api_id             = aws_apigatewayv2_api.orders.id
  route_key          = "GET /orders"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "update_order_status" {
  api_id             = aws_apigatewayv2_api.orders.id
  route_key          = "PATCH /orders/{orderId}/status"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

# Lambda Invoke-Permission (security/iam-design.md §3): NUR API Gateway als Principal,
# Resource-Scope eng auf diese HTTP API (source_arn = execution_arn + "/*/*").
# Kein öffentlicher Lambda-Aufruf. Bewusst NICHT Teil der IAM-Rolle (Richtung:
# API GW → Lambda; nicht Lambda → DynamoDB).
resource "aws_lambda_permission" "api_gateway" {
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.orders.execution_arn}/*/*"
}