variable "project_name" {
  description = "Name des Projekts; wird als Prefix fuer Ressourcen-Namen verwendet."
  type        = string
}

variable "tags" {
  description = "Zusaetzliche Tags, die den Cognito-Ressourcen mitgegeben werden."
  type        = map(string)
  default     = {}
}