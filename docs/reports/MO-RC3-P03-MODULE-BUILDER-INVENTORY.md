# MO-RC3-P03-MODULE-BUILDER-INVENTORY

**Module Builder Inventory für RC.3 Release**

**Datum:** 2026-10-30
**Commit:** `d7bf2ff`

## 1. Builder-Einstiegspunkt

| File | Zweck |
|------|-------|
| `module_builder/__init__.py` | Package-Initialisierung, Version |
| `module_builder/builder.py` | Kern-Generator (build, build_module) |
| `module_builder/catalog.py` | Modul-Katalog und Validierungsfunktionen |
| `module_builder/spec.py` | Presets und Vertragsdefinitionen |

## 2. CLI-Schnittstellen

```bash
# Haupt-Builder (Preset complete)
python -m module_builder build --target <path> --project-name <name>

# Module-Build (WP5)
python -m module_builder build --target <path> --preset orders-service

# Freie Modulauswahl (B1)
python -m module_builder build --target <path> --modules dynamodb iam lambda

# Mit Pflicht-Dependencies (B2)
python -m module_builder build --target <path> --modules lambda --with-deps
```

## 3. Generierte Terraform-Module

| Modul | Status | Pfad |
|-------|--------|------|
| `api` | ✅ IMPLEMENTED | `terraform/modules/api/` |
| `cognito` | ✅ IMPLEMENTED | `terraform/modules/cognito/` |
| `dynamodb` | ✅ IMPLEMENTED | `terraform/modules/dynamodb/` |
| `iam` | ✅ IMPLEMENTED | `terraform/modules/iam/` |
| `lambda` | ✅ IMPLEMENTED | `terraform/modules/lambda/` |
| `monitoring` | ✅ IMPLEMENTED | `terraform/modules/monitoring/` |
| `sqs` | ✅ IMPLEMENTED | `terraform/modules/sqs/` |
| `sqs-worker` | ✅ IMPLEMENTED | `terraform/modules/sqs-worker/` |
| `cloudtrail` | ✅ IMPLEMENTED | `terraform/modules/cloudtrail/` |

## 4. Eingabevariablen

### Root-Variables (terraform/variables.tf)
| Variable | Typ | Default | Status |
|----------|-----|---------|--------|
| `project_name` | string | "mays-orders" | ✅ IMPLEMENTED |
| `tags` | map(string) | `{}` | ✅ IMPLEMENTED |
| `monitoring_enabled` | bool | `true` | ✅ IMPLEMENTED |
| `log_retention_days` | number | `7` | ✅ IMPLEMENTED |
| `lambda_execution_boundary` | string | `null` | ✅ IMPLEMENTED |
| `enable_cognito_backup` | bool | `true` | ✅ IMPLEMENTED |
| `sqs_enabled` | bool | `true` | ✅ IMPLEMENTED |

### Orders-Service Module Contract (ORDERS_SERVICE_VARIABLES)
| Variable | Typ | Default | Status |
|----------|-----|---------|--------|
| `project_name` | string | "{project_name}" | ✅ IMPLEMENTED |
| `tags` | map(string) | `{}` | ✅ IMPLEMENTED |
| `monitoring_enabled` | bool | `true` | ✅ IMPLEMENTED |
| `log_retention_days` | number | `7` | ✅ IMPLEMENTED |
| `lambda_execution_boundary` | string | `null` | ✅ IMPLEMENTED |
| `external_cognito` | object | `null` | ✅ IMPLEMENTED |

## 5. Outputs

### Root Outputs (terraform/outputs.tf)
| Output | Status |
|--------|--------|
| `api_gateway_endpoint` | ✅ IMPLEMENTED |
| `api_gateway_id` | ✅ IMPLEMENTED |
| `api_gateway_stage_name` | ✅ IMPLEMENTED |
| `api_gateway_authorizer_id` | ✅ IMPLEMENTED |
| `dynamodb_table_name` | ✅ IMPLEMENTED |
| `dynamodb_table_arn` | ✅ IMPLEMENTED |
| `sqs_queue_url` | ✅ IMPLEMENTED |
| `sqs_queue_arn` | ✅ IMPLEMENTED |
| `sqs_queue_name` | ✅ IMPLEMENTED |
| `sqs_worker_lambda_arn` | ✅ IMPLEMENTED |
| `lambda_function_name` | ✅ IMPLEMENTED |
| `lambda_function_arn` | ✅ IMPLEMENTED |
| `lambda_invoke_arn` | ✅ IMPLEMENTED |
| `iam_handler_role_name` | ✅ IMPLEMENTED |
| `iam_handler_role_arn` | ✅ IMPLEMENTED |
| `cognito_user_pool_id` | ✅ IMPLEMENTED |
| `cognito_user_pool_arn` | ✅ IMPLEMENTED |

### Orders-Service Module Contract Outputs
Siehe `ORDERS_SERVICE_README_TEMPLATE` in `module_builder/builder.py`

## 6. IAM-Konfiguration

### IAM-Portabilität-FIX-01 & FIX-02
- ✅ Keine hartcodierten Account-IDs in Defaults
- ✅ `lambda_execution_boundary` default auf `null` im generierten Modul
- ✅ SQS-Gate count-gated (`sqs_enabled = true` erfordert Queue-ARN)

### IAM-Module
- `iam/main.tf`: Least Privilege Policy (DynamoDB, Logs, optionales SQS)
- `iam/variables.tf`: `sqs_enabled` Variable für SQS-Gate

## 7. SQS-Konfiguration

### SQS Policy Fix (F-03)
- ✅ Wildcard-Principal (`Principal = "*"`) entfernt
- ✅ Zugriff nur über IAM-Rollen-Policies
- ✅ Policy entfernt, Kommentar hinterlassen

### SQS-Module
- `sqs/main.tf`: Queue-Erstellung, ohne Resource Policy
- `sqs-worker/variables.tf`: Worker-Konfiguration

## 8. Lambda-Artefakte

### Lambda-Handler
| Komponente | Status |
|------------|--------|
| Quelle | `lambda/src/index.py` | ✅ IMPLEMENTED |
| Build-Skript | `lambda/build_zip.py` | ✅ IMPLEMENTED |
| Artefakt | `lambda/dist/lambda.zip` | ✅ IMPLEMENTED |
| Handler | `index.handler` | ✅ IMPLEMENTED |
| Runtime | `python3.14` | ✅ IMPLEMENTED |

### Build-Reproduzierbarkeit
- ✅ Deterministischer SHA256-Hash im Manifest
- ✅ `python3 build_zip.py` reproduziert `lambda.zip`

## 9. Versionierungs- und Abhängkeitsverträge

### Terraform Versions
- `required_version >= 1.3`
- `provider.aws ~> 6.0`

### Module-Katalog (catalog.py)
```python
MODULE_CATALOG = {
    "api": {"dir": "api", "deps": {"iam", "lambda"}},
    "cognito": {"dir": "cognito", "deps": set()},
    "dynamodb": {"dir": "dynamodb", "deps": set()},
    "iam": {"dir": "iam", "deps": {"dynamodb"}},
    "lambda": {"dir": "lambda", "deps": {"iam", "dynamodb"}},
    "sqs": {"dir": "sqs", "deps": set()},
    "sqs_worker": {"dir": "sqs-worker", "deps": {"iam", "dynamodb", "sqs"}},
    "monitoring": {"dir": "monitoring", "deps": {"lambda"}},
    "cloudtrail": {"dir": "cloudtrail", "deps": set()},
}
```

### Pflicht-Abhängigkeiten (fail-closed)
- `api` benötigt `iam` + `lambda`
- `lambda` benötigt `iam` + `dynamodb`
- `sqs_worker` benötigt `iam` + `dynamodb` + `sqs`

## 10. Builder-Vertrag (MAYS-ORDERS-MODULE-CONTRACT-01)

### Feste 7-Modul-Zusammensetzung
```
API + Handler (lambda, api, iam)
Worker (sqs-worker, sqs)
DynamoDB (dynamodb)
IAM (iam)
Cognito (cognito)
```

### Eingabe-Contract
- `project_name`: string
- `tags`: map(string), optional
- `monitoring_enabled`: bool, optional
- `log_retention_days`: number, optional
- `lambda_execution_boundary`: string, optional
- `external_cognito`: object, optional (MANAGED/EXTERNAL-Modus)

### Output-Contract
- API: endpoint, id, stage, authorizer
- DynamoDB: table_name, table_arn
- SQS: url, arn, name
- Lambda: function_name, function_arn, invoke_arn
- IAM: handler_role_name, handler_role_arn
- Cognito: user_pool_id, user_pool_arn

## 11. Reproduzierbarkeit des Build-Prozesses

### Preset `complete`
```bash
python -m module_builder build --target ./output --project-name my-project
```
- Byte-identisch mit Foundation-Stand
- Alle 8 Module inkl. CloudTrail/Monitoring

### Preset `orders-service`
```bash
python -m module_builder build --target ./output --preset orders-service --project-name my-project
```
- 7 Module für Orders-Service
- Keine Cognito-Ressourcen wenn `external_cognito` gesetzt

## 12. Status-Zusammenfassung

| Komponente | Status |
|------------|--------|
| Builder-Kern | ✅ IMPLEMENTED / VERIFIED |
| CLI-Schnittstellen | ✅ IMPLEMENTED / VERIFIED |
| Terraform-Module | ✅ IMPLEMENTED / VERIFIED |
| Eingabevariablen | ✅ IMPLEMENTED / VERIFIED |
| Outputs | ✅ IMPLEMENTED / VERIFIED |
| IAM-Konfiguration | ✅ IMPLEMENTED / VERIFIED |
| SQS-Konfiguration | ✅ IMPLEMENTED / VERIFIED |
| Lambda-Artefakte | ✅ IMPLEMENTED / VERIFIED |
| Versionierungsvertrag | ✅ IMPLEMENTED / VERIFIED |
| Reproduzierbarkeit | ✅ VERIFIED (Manifest, SHA256) |

**Alle Komponenten sind implementiert und verifiziert.**