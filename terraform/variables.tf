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

# DynamoDB-Beispiel-Daten-Seed (opt-in, standardmäßig DEAKTIVIERT):
# nur mit bewusstem `terraform apply -var="seed_example_data=true"` werden die
# 50 Demo-Orders (database/seed/orders_seed_demo_50.json) in die Tabelle geladen.
# Siehe docs/reports/DYNAMODB-SEED-DEMO-50.md.
variable "seed_example_data" {
  description = "Importiert die bereitgestellten Beispiel-Orders in DynamoDB."
  type        = bool
  default     = false
}

variable "seed_file_path" {
  description = "Pfad zur Demo-Seed-Datei (JSON) relativ zum Repo-Root."
  type        = string
  default     = "database/seed/orders_seed_demo_50.json"
}