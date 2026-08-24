variable "project_name" {
  description = "Name des Projekts; wird als Prefix fuer Ressourcen-Namen verwendet."
  type        = string
}

variable "tags" {
  description = "Zusaetzliche Tags, die den API-Gateway-Ressourcen mitgegeben werden."
  type        = map(string)
  default     = {}
}

variable "lambda_invoke_arn" {
  description = "Invoke ARN der Lambda-Funktion (fuer API Gateway Integration)."
  type        = string
}

variable "lambda_function_name" {
  description = "Name der Lambda-Funktion (fuer Lambda Permission)."
  type        = string
}

variable "cognito_user_pool_endpoint" {
  description = "Endpoint des Cognito User Pools (fuer JWT Issuer URL)."
  type        = string
}

variable "cognito_user_pool_client_id" {
  description = "Client-ID des Cognito App Clients (fuer JWT Audience)."
  type        = string
}