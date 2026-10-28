# MO-CONSUMER-HANDOFF-01

**Übergabepaket für externe Consumer**

## MO-Commit

`a2fb385` (aktueller Stand)

## Builder-Aufruf

```bash
python -m module_builder build --target <path> --project-name <name> --preset orders-service
```

## Modul-Inputs

- project_name
- tags
- monitoring_enabled
- log_retention_days
- lambda_execution_boundary — optional, ARN oder null
- external_cognito — null = MANAGED, Objekt = EXTERNAL

## Modul-Outputs

api_gateway_endpoint, api_gateway_id, api_gateway_stage_name, api_gateway_authorizer_id, dynamodb_table_name, dynamodb_table_arn, sqs_queue_url, sqs_queue_arn, sqs_queue_name, sqs_worker_lambda_arn, lambda_function_name, lambda_function_arn, lambda_invoke_arn, iam_handler_role_name, iam_handler_role_arn, cognito_user_pool_id, cognito_user_pool_arn, ...

## IAM-Boundary-Vertrag

- Optional, default null
- Falls gesetzt, muss gültige IAM Policy ARN sein
- Kein hartcodiertes Konto

## Lambda-Artefaktvertrag

- Quelle: `lambda/src/`
- Build: `python3 lambda/build_zip.py`
- ZIP: `lambda/dist/lambda.zip`
- Handler: `index.handler`, Runtime `python3.14`

## SQS-Sicherheitsvertrag

- Keine Resource Policy mit Wildcard-Principal
- Zugriff ausschließlich über IAM-Rollen

## Terraform-Voraussetzungen

- Terraform >= 1.5
- Provider aws >= 6.0.0
- Kein AWS Apply im MO-Repo

## Bekannte Einschränkungen

- Boundary optional, Sicherheitsvertrag liegt beim Consumer
- Keine dynamische Policy-Erstellung durch MO

## Tests

- 90 Module Builder Tests OK
- Terraform validate OK
