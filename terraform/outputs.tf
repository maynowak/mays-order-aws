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
