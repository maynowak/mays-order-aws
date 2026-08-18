# Build & Validation — May's Orders

> Stand: Woche 2 — aktiver Lambda-Bestand: Python 3.14. Die historische
> Node.js/TypeScript-Baseline (T011-04) wurde im Cleanup entfernt und ist über
> Git-Historie (Commit `449cdd7`) nachvollziehbar.

## Lokale Entwicklung (aktiv, Python)

```bash
cd lambda
python3 -m compileall -q src tests      # Syntax-Check
PYTHONPATH=src python3 -m unittest discover -s tests -v   # Unit-Tests (unittest)
python3 build_zip.py                    # → dist/lambda.zip (6 Module, ~6,6 KB)
unzip -t dist/lambda.zip                # ZIP-Integrität
```

## Infrastruktur-Validierung

```bash
cd terraform
terraform init
terraform validate
terraform plan       # Review — kein blindes Apply (T011-07)
terraform apply      # NUR nach expliziter menschlicher Freigabe (T011-08)
terraform destroy    # nur nach Freigabe (Cleanup)
```

## Live-API-Verifikation (nach Deployment)

```bash
# Token via Cognito beschaffen (Login)
curl -H "Authorization: Bearer <TOKEN>" https://<api-id>.execute-api.<region>.amazonaws.com/orders
curl -X POST -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
     -d '{"customer":{...},"items":[...]}' \
     https://<api-id>.execute-api.<region>.amazonaws.com/orders
```

## Aktueller Stand

| Prüfung | Status |
|---------|--------|
| Python compileall | PASS |
| Python unittest | PASS (49/49) |
| ZIP-Build + Integrität | PASS |
| Terraform validate | PASS (T011-01…06; Provider 6.60.0) |
| Terraform plan | NOT RUN (T011-07) |
| Terraform apply | NOT RUN (Freigabe erforderlich) |
| Live-API | NOT RUN |
| `git diff --check` | PASS (letzter Checkpoint) |

## Erwartete Artefakte

- `lambda/dist/lambda.zip` (Python-Bundle) — erzeugt durch `python3 build_zip.py`
- Terraform-Plan/Apply-Output — Woche 2 (T011-07/08)
- `tests/test-results.md` — laufend ab Woche 2