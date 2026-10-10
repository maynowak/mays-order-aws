# T011-02 — DynamoDB-Tabelle + GSI1
# Fachquelle: database/dynamodb-design.md, database/access-patterns.md, ADR-002, ADR-007
#
# ⚠️ UPGRADE NOTE — DATA TRANSFORMATION REQUIRED
# Änderungen an bestehendem DynamoDB Datenmodell, Schema,
# Partition-/Sort-Key-Struktur oder inkompatiblen Attributmodellen
# können eine versionierte Datenmigration/Transformation erfordern.
# PITR/Backup schützt Daten vor Verlust, ersetzt aber keine
# Schema-/Datenmigration.
#
resource "aws_dynamodb_table" "orders" {
  name         = var.project_name
  billing_mode = "PAY_PER_REQUEST" # ADR-007: On-Demand
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  attribute {
    name = "gsi1pk"
    type = "S"
  }

  attribute {
    name = "gsi1sk"
    type = "S"
  }

  attribute {
    name = "gsi2pk"
    type = "S"
  }

  attribute {
    name = "gsi2sk"
    type = "S"
  }

  global_secondary_index {
    name               = "gsi1"
    projection_type    = "INCLUDE"
    non_key_attributes = ["orderId", "status", "customer", "totalAmount", "createdAt", "updatedAt"]

    key_schema {
      attribute_name = "gsi1pk"
      key_type       = "HASH"
    }

    key_schema {
      attribute_name = "gsi1sk"
      key_type       = "RANGE"
    }
  }

  global_secondary_index {
    name               = "gsi2"
    projection_type    = "INCLUDE"
    non_key_attributes = ["orderId", "subjectId", "version", "createdAt", "status", "updatedAt", "customer", "totalAmount", "currency"]

    key_schema {
      attribute_name = "gsi2pk"
      key_type       = "HASH"
    }

    key_schema {
      attribute_name = "gsi2sk"
      key_type       = "RANGE"
    }
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = merge({ "Project" = var.project_name }, var.tags)
}