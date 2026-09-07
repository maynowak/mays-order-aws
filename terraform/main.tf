terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

# Identity / provenance (erste sichere Installations-Schicht, T013).
# Trennung gemäß architecture/installation-concept.md:
#   Project     = var.project_name      → KONFIGURIERBAR (Ressourcen-Namen + "Project"-Tag)
#   Maker       = local.maker           → UNVERÄNDERLICH (Original-/Provenance-Identität,
#                                         nur als "Maker"-Tag, NIE in Ressourcen-Namen)
#   Environment = local.environment     → Governance-Tag (Policy-Gate Pflichtfeld).
#                                         Entwicklungs-/Prototyp-Stand "Development";
#                                         "Production" ist vom Developer-Gate gesperrt.
#   ManagedBy / CreatedBy               → optionale Deployment-Metadaten via var.tags
#                                         (keine eigenen Variablen in dieser Schicht)
# `Maker` ist bewusst ein neutraler Projekt-Slug (kein Personen-Name) und lebt nur
# als Tag, damit eine spätere Umbenennung von `project_name` die Provenance nicht
# verliert. Siehe terraform/README.md §9.
locals {
  maker       = "mays-orders"
  environment = "Development"
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = merge(
      {
        "Project"     = var.project_name
        "Maker"       = local.maker
        "Environment" = local.environment
      },
      var.tags
    )
  }
}

# T011-02 — DynamoDB-Tabelle + GSI1
# Fachquelle: database/dynamodb-design.md, database/access-patterns.md, ADR-002, ADR-007

module "dynamodb" {
  source       = "./modules/dynamodb"
  project_name = var.project_name
  tags         = var.tags
}

# T011-03 — IAM: Lambda Execution Role (Least Privilege)
# Fachquelle: security/iam-design.md §2.1
# Kein dynamodb:Scan/DeleteItem/BatchWriteItem/CreateTable; keine s3/sqs/iam-Aktionen.

module "iam" {
  source             = "./modules/iam"
  project_name       = var.project_name
  tags               = var.tags
  dynamodb_table_arn = module.dynamodb.table_arn
  dynamodb_gsi1_arn  = module.dynamodb.gsi1_arn
}

# T011-04 — Lambda: Order Handler (Zip-Build, Python 3.14)
# Fachquelle: ADR-001 (Serverless), api/endpoints.md, database/access-patterns.md (AP1..AP4)
# Execution Role: module.iam.role_arn. Zip-Build reproduzierbar via lambda/ (python3 build_zip.py).
# Migration: nodejs22.x → python3.14 (feature/lambda-python-314). Handler "index.handler" gilt für Python (index.py am ZIP-Root).
# API-GW→Lambda Invoke-Permission folgt in T011-06 (HTTP API + Routen + Authorizer).

module "lambda" {
  source              = "./modules/lambda"
  project_name        = var.project_name
  tags                = var.tags
  iam_role_arn        = module.iam.role_arn
  dynamodb_table_name = module.dynamodb.table_name
  monitoring_enabled  = var.monitoring_enabled
  log_retention_days  = var.log_retention_days
  filename            = "${path.root}/../lambda/dist/lambda.zip"
}

# T011-05 — Cognito: User Pool + App Client + Gruppe `staff`
# Fachquelle: security/authentication-decision.md (ADR-003), F002, security/iam-design.md
# Scope T011-05: nur Pool, Client, Gruppe. API Gateway / JWT-Authorizer / Lambda
# Invoke-Permission folgen in T011-06 (HTTP API + Routen + Authorizer).
# Kein user_pool_domain: Login via USER_PASSWORD_AUTH (kein Hosted-UI/OAuth-Redirect nötig,
# siehe terraform/README.md — Domain nur "falls nötig").

module "cognito" {
  source       = "./modules/cognito"
  project_name = var.project_name
  tags         = var.tags
}

# T011-06 — API Gateway HTTP API + Routen + JWT Authorizer
# Fachquelle: ADR-004 (HTTP API V2), api/endpoints.md, api/api-documentation.md,
# security/authentication-decision.md (JWT-Flow §3), security/iam-design.md §3.
# Scope: HTTP API + Stage, Lambda-Integration (Payload v2), vier dokumentierte
# Routen, JWT-Authorizer (Cognito), Lambda-Invoke-Permission.

module "api" {
  source                      = "./modules/api"
  project_name                = var.project_name
  tags                        = var.tags
  lambda_invoke_arn           = module.lambda.invoke_arn
  lambda_function_name        = module.lambda.function_name
  cognito_user_pool_endpoint  = module.cognito.user_pool_endpoint
  cognito_user_pool_client_id = module.cognito.user_pool_client_id
}

# DynamoDB-Beispiel-Daten-Seed (opt-in) — siehe docs/reports/DYNAMODB-SEED-DEMO-50.md
# Läuft NUR wenn var.seed_example_data = true. Trigger ist der SHA256 der
# Seed-Datei + Tabellenname: bei unveränderter Datei KEIN Re-Run bei jedem apply
# (der Importer selbst ist zusätzlich idempotent). Standardmäßig (count = 0)
# bleibt der Plan unverändert (kein Beispiel-Import).
resource "terraform_data" "seed_orders" {
  count = var.seed_example_data ? 1 : 0

  input = {
    seed_file_sha256 = filebase64sha256("${path.module}/../${var.seed_file_path}")
    table_name       = module.dynamodb.table_name
  }

  provisioner "local-exec" {
    command = "python3 ${path.module}/../scripts/seed_orders.py --table ${module.dynamodb.table_name} --file ${path.module}/../${var.seed_file_path}"
  }

  depends_on = [module.dynamodb]
}

# T011-11 — CloudWatch Monitoring (Dashboard + Alarme)
# Fachquelle: monitoring/monitoring-design.md, cost/cost-analysis.md §2
# Scope T011-11: Dashboard + 6 Alarme (API, Lambda, DynamoDB). Kein SNS, keine Log-Group.
# Log-Group ist im Lambda-Modul.

# T011 — CloudTrail Audit Layer (Account-Audit, KEINE Anwendungs-Business-Logik)
# Fachquelle: security/cloudtrail-design.md
# Scope: Trail (multi-region, Management Events Read+Write) + dedizierter S3-Bucket
# (SSE-S3 at rest, Public-Access-Block, CloudTrail-Bucket-Policy) + Log-Validierung.
# Kein Consumer-Modul → keine neuen Root-Inputs/-Outputs. Bewusst eigenes kleines
# Child-Modul (analog module.monitoring). CloudWatch bleibt getrennt für operational
# monitoring; CloudTrail ist der AWS-API-Audit-Trail.

module "cloudtrail" {
  source       = "./modules/cloudtrail"
  project_name = var.project_name
  tags         = var.tags
}

module "monitoring" {
  source                       = "./modules/monitoring"
  project_name                 = var.project_name
  tags                         = var.tags
  monitoring_enabled           = var.monitoring_enabled
  dashboard_enabled            = var.dashboard_enabled
  aws_region                   = var.aws_region
  alarm_period_seconds         = var.alarm_period_seconds
  alarm_evaluation_periods     = var.alarm_evaluation_periods
  api_5xx_threshold            = var.api_5xx_threshold
  api_4xx_threshold            = var.api_4xx_threshold
  lambda_error_threshold       = var.lambda_error_threshold
  lambda_duration_threshold_ms = var.lambda_duration_threshold_ms
  lambda_throttle_threshold    = var.lambda_throttle_threshold
  dynamodb_throttled_threshold = var.dynamodb_throttled_threshold
  lambda_function_name         = module.lambda.function_name
  api_id                       = module.api.api_id
  api_stage_name               = module.api.api_stage_name
  dynamodb_table_name          = module.dynamodb.table_name
}