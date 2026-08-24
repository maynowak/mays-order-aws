variable "project_name" {
  description = "Name des Projekts; wird als Tabellenname verwendet."
  type        = string
}

variable "tags" {
  description = "Zusaetzliche Tags, die der DynamoDB-Tabelle mitgegeben werden."
  type        = map(string)
  default     = {}
}