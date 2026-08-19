variable "project_name" {
  description = "Name des Projekts; wird als Prefix fuer Ressourcen-Namen verwendet."
  type        = string
  default     = "mays-orders"
}

variable "aws_region" {
  description = "AWS-Region, in der die Infrastruktur erzeugt wird."
  type        = string
  default     = "eu-central-1"
}

variable "tags" {
  description = "Zusaetzliche Tags, die allen Ressourcen mitgegeben werden."
  type        = map(string)
  default     = {}
}

# DynamoDB-Testdaten-Seed (opt-in, standardmäßig DEAKTIVIERT):
# nur mit bewusstem `terraform apply -var="seed_test_data=true"` werden die
# deterministischen Test-Orders (database/seed/orders_seed_1000.jsonl,
# ord_00001..ord_01000) in die Tabelle geladen. Siehe DYNAMODB-SEED-1000.md.
variable "seed_test_data" {
  description = "Testdaten (1.000 Beispiel-Orders) in die DynamoDB-Tabelle laden (opt-in)."
  type        = bool
  default     = false
}

variable "seed_file_path" {
  description = "Pfad zur Seed-Datei (JSONL) relativ zum Repo-Root."
  type        = string
  default     = "database/seed/orders_seed_1000.jsonl"
}