# T011-05 — Cognito: User Pool + App Client + Gruppe `staff`
# Fachquelle: security/authentication-decision.md (ADR-003), F002, security/iam-design.md
# Scope T011-05: nur Pool, Client, Gruppe. API Gateway / JWT-Authorizer / Lambda
# Invoke-Permission folgen in T011-06 (HTTP API + Routen + Authorizer).
# Kein user_pool_domain: Login via USER_PASSWORD_AUTH (kein Hosted-UI/OAuth-Redirect nötig,
# siehe terraform/README.md — Domain nur "falls nötig").

resource "aws_cognito_user_pool" "users" {
  name = "${var.project_name}-users"

  # Staff-Benutzer werden administrativ angelegt (T002-04 via AWS CLI); keine offene
  # Selbst-Registrierung (keine Signup-Anforderung im Repo dokumentiert, requirements/).
  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  # Passwortrichtlinie: Standardwerte (security/authentication-decision.md §6 — Verfeinerung nur falls gefordert)
  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_uppercase = true
    require_numbers   = true
    require_symbols   = true
  }

  # MFA optional — Standard (OFF), Verfeinerung nur falls gefordert (§6)
  mfa_configuration = "OFF"

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_cognito_user_pool_client" "app" {
  name         = "${var.project_name}-client"
  user_pool_id = aws_cognito_user_pool.users.id

  # Login via USER_PASSWORD_AUTH + Refresh (security/authentication-decision.md §3 JWT-Flow)
  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  # Public Client (kein Secret) — Voraussetzung fuer USER_PASSWORD_AUTH;
  # Benutzer-Login laeuft ueber Cognito/JWT, nie ueber IAM Access Keys (TR-15).
  generate_secret = false
}

resource "aws_cognito_user_group" "staff" {
  name         = "staff"
  user_pool_id = aws_cognito_user_pool.users.id

  # Claim `cognito:groups` im Access Token → Basis der Authorization (A-09, §5)
}