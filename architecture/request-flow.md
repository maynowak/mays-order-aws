# Request Flow — May's Orders

## 1. Erfolgsfall: Order erstellen (`POST /orders`)

```text
1. Client         →  Cognito: login (USER_PASSWORD_AUTH) → Access Token (JWT)
2. Client         →  HTTP API POST /orders  (Authorization: Bearer <JWT>, JSON-Body)
3. API Gateway    →  validiert JWT (Signatur, Ablauf) über COGNITO_USER_POOLS
                     ↓ ungültig → 401 UNAUTHORIZED
4. API Gateway    →  invoke Lambda (POST, Body, Claims im Event)
5. Lambda         →  Validierung (Pflichtfelder, Formate)  ↓ ungültig → 400 VALIDATION_ERROR
6. Lambda         →  Berechnung totalAmount (server-seitig)
7. Lambda         →  DynamoDB PutItem (pk=ORDER#<id>, status=PENDING, gsi1pk=LIST, …)
8. Lambda         →  Antwort 201 { orderId, status:PENDING, … }
9. CloudWatch     →  Logs (strukturiert, ohne Secrets/Tokens)
```

## 2. Erfolgsfall: Statusänderung (`PATCH /orders/{orderId}/status`)

```text
1. Client  →  PATCH /orders/{orderId}/status  { "status": "CONFIRMED" }
2. Gateway →  JWT-Validierung
3. Lambda  →  Body-Validierung (gültiger Statuswert)
4. Lambda  →  State Machine: Transition PENDING → CONFIRMED erlaubt?
             ↓ ungültig → 409 INVALID_TRANSITION
5. Lambda  →  DynamoDB UpdateItem (Conditional: status = PENDING, attribute_exists)
             ↓ ConditionCheckFailed → 409 CONFLICTED_UPDATE
6. Lambda  →  200 { status: CONFIRMED, updatedAt, … }
```

## 3. Fehlerfälle → Mapping

| Szenario | Erkennung | Antwort |
|----------|-----------|---------|
| Kein/ungültiges Token | API Gateway JWT-Autorisator | 401 UNAUTHORIZED |
| Auth ok, aber keine Berechtigung | Lambda-Claims/Group-Check | 403 FORBIDDEN |
| Validierungsfehler Body | Lambda-Validierung | 400 VALIDATION_ERROR |
| Order nicht gefunden | DynamoDB-Get/Update Ergebnis | 404 ORDER_NOT_FOUND |
| Ungültiger Übergang | State-Machine-Tabelle | 409 INVALID_TRANSITION |
| Konkurrierendes Update | ConditionalCheckFailedException | 409 CONFLICTED_UPDATE |
| Unerwarteter Fehler | Exception-Handler | 500 INTERNAL_ERROR (generisch) |

## 4. Latenzprofil (Erwartung, Woche 4 gemessen)

| Bestandteil | Erwartung |
|-------------|-----------|
| API Gateway → Lambda | wenige ms |
| Lambda Cold Start | 100–800 ms (erster Request) |
| Lambda Warm | 5–30 ms |
| DynamoDB GetItem/PutItem | 5–20 ms |
| Gesamt (warm) | ~20–80 ms |

**Hinweis:** Dies sind Erwartungswerte. Tatsächliche Messungen erfolgen in Woche 3/4
(Monitoring, `duration`-Metrik) und werden dort dokumentiert — keine erfundenen Zahlen.