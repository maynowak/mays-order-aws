# Build & Validation — May's Orders

> Stand: Woche 1 — Planung. Keine Code-Builds bisher (keine Implementierung).

## Lokale Entwicklung (Woche 2, geplant)

```bash
npm install
npm run build        # tsc --noEmit + ggf. Bundle (TypeScript-Lambda-Handler)
npm test             # Unit-Tests (Vitest/Jest, State Machine + Validierung)
```

## Infrastruktur-Validierung

```bash
terraform init
terraform validate
terraform plan       # Review — kein blindes Apply
terraform apply      # NUR nach expliziter menschlicher Freigabe
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
| TypeScript-Build | NOT APPLICABLE (kein Code, Woche 1) |
| Unit-Tests | NOT RUN |
| Terraform validate | NOT RUN (Woche 2) |
| Terraform plan | NOT RUN |
| Terraform apply | NOT RUN (Freigabe erforderlich) |
| Live-API | NOT RUN |
| `git diff --check` | PASS (letzter Checkpoint) |

## Erwartete Artefakte

- `dist/` bzw. Lambda-Bundle (Zip) — Woche 2
- Terraform-Plan/Apply-Output — Woche 2
- `tests/test-results.md` — laufend ab Woche 2