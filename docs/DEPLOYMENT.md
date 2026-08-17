# Deployment — May's Orders

> Stand: Woche 1 — Planung. **Kein Deployment durchgeführt, keine AWS-Ressourcen.**

## Deployment-Weg (Woche 2, geplant)

```text
1. Terraform-Plan erstellen und reviewen (menschlich)
2. Freigabe für `terraform apply` erteilen
3. `terraform apply` ausführen (DynamoDB, IAM, Cognito, API GW, Lambda)
4. Lambda-Code bauen und hochladen (Zip/Bundle)
5. API-Gateway-Invoke-URL ermitteln
6. Cognito-Benutzer anlegen (Test-Staff)
7. Live-API-Verifikation mit `curl` (Auth + 4 Endpoints + Fehlerfälle)
```

## Infrastruktur (Terraform)

| Ressource | Status |
|-----------|--------|
| DynamoDB `mays-orders` | ⏳ PLANNED |
| IAM (Lambda Execution Role) | ⏳ PLANNED |
| Lambda (Order Handler) | ⏳ PLANNED |
| Cognito User Pool + Client + Gruppe | ⏳ PLANNED |
| HTTP API + Route + Authorizer | ⏳ PLANNED |
| CloudWatch (Logs/Metriken) | ⏳ PLANNED |

Konfiguration: `terraform/` (Variablen, Outputs). Terraform-State: anfangs lokal;
S3-Backend-Entscheidung offen (Woche 2).

## Environment & Secrets

- Keine Secrets in Terraform/Code.
- Cognito verwaltet Passwörter/Benutzer (keine manuellen Keys).
- Lambda-Umgebungsvariablen nur für unkritische Werte (z. B. Table-Name).
- `terraform.tfvars` ist gitignored; Beispiel-Datei `terraform/terraform.example.tfvars`.

## Live-URL (nach Deployment)

Wird nach erfolgreichem `terraform apply` dokumentiert (API-Gateway-Invoke-URL).

## Bereitstellungs-Status

| Schritt | Status |
|---------|--------|
| Terraform validate/plan | NOT RUN |
| Terraform apply | NOT RUN (Freigabe erforderlich) |
| Lambda-Deployment | NOT RUN |
| Live-API-Verifikation | NOT RUN |

## Cleanup

Nach abgeschlossenen Testphasen: `terraform destroy` nur nach Freigabe, um Kosten zu vermeiden.