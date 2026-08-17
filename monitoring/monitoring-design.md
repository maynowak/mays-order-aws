# Monitoring Design — May's Orders

## 1. Ziele

- Betriebszustand der API jederzeit erkennbar.
- Fehler schnell lokalisierbar (welcher Endpoint, welche Lambda, welches DynamoDB-Pattern).
- Kostenkontrolle (CloudWatch-Logs nicht unkontrolliert wachsen lassen).

## 2. Metriken

| Metrik | Quelle | Alarm? |
|--------|--------|--------|
| API-Requests (count) | API Gateway (`ApiGateway` Namespace: Count, 4xx, 5xx) | nein (Basis-Diagnose) |
| API-4xx | API Gateway | ja bei Rate (Schwellenwert definieren) |
| API-5xx | API Gateway | ja |
| Lambda-Errors | Lambda (`Errors`, `Throttles`) | ja |
| Lambda-Duration | Lambda (`Duration`, p95) | ja (Cold-Start / Regression) |
| DynamoDB-Throttling | DynamoDB (`ThrottledRequests`, `ConditionalCheckFailedRequests`) | ja (Drosselung) |
| DynamoDB-ConsumedCapacity | DynamoDB | nein (Kosten-Diagnose) |

## 3. Logging

- **Strukturiertes JSON-Logging** in der Lambda (korrelierte Request-ID).
- **Keine** Secrets/Tokens/Kunden-PII ungefiltert (Anonymisierung/Pruning Woche 3).
- Log-Retention: **z. B. 7 Tage** (kostenbewusst; Entscheidung Woche 2).
- API-Gateway-Access-Logs optional (Log-Format klein halten).

## 4. Alarme

| Alarm | Metrik/Bedingung | Aktion |
|-------|------------------|--------|
| `api-5xx` | 5xx-Rate > Schwellwert (z. B. 5 in 5 min) | SNS-Notify (oder Log-Check) |
| `lambda-errors` | Errors > 0 in 5 min (nach Stabilisierung) | SNS-Notify |
| `dynamodb-throttled` | ThrottledRequests > 0 | SNS-Notify |

**Vorsicht (C-06/C-03):** Alarme erst in Woche 3/4 und nur, wenn sie einen echten Mehrwert
bieten. SNS-Topic kostet, soll aber für den Fall realer Fehler sinnvoll bleiben. Minimaler
Umfang wird final mit `cost/cost-analysis.md` abgeglichen.

## 5. Verifikation (geplant)

- Terraform-Deployment → CloudWatch-Dashboard mit den Metriken.
- Fehler-Szenarien (401, 409, 500) auslösen und in CloudWatch-Logs nachweisen.