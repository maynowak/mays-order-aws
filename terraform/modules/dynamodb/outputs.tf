# T011-02 — DynamoDB-Outputs
output "table_name" {
  description = "Name der DynamoDB-Tabelle fuer May's Orders."
  value       = aws_dynamodb_table.orders.name
}

output "table_arn" {
  description = "ARN der DynamoDB-Tabelle fuer May's Orders."
  value       = aws_dynamodb_table.orders.arn
}

output "table_stream_arn" {
  description = "ARN des DynamoDB-Streams (falls aktiviert)."
  value       = aws_dynamodb_table.orders.stream_arn
}

output "gsi1_name" {
  description = "Name des Global Secondary Index (GSI1)."
  value       = "gsi1"
}

output "gsi1_arn" {
  description = "ARN des Global Secondary Index (GSI1)."
  value       = "${aws_dynamodb_table.orders.arn}/index/gsi1"
}