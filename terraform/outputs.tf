# T011-02 — DynamoDB-Outputs
output "dynamodb_table_name" {
  description = "Name der DynamoDB-Tabelle fuer May's Orders (mays-orders)."
  value       = aws_dynamodb_table.orders.name
}

output "dynamodb_table_arn" {
  description = "ARN der DynamoDB-Tabelle fuer May's Orders."
  value       = aws_dynamodb_table.orders.arn
}
