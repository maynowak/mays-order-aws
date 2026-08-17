# API Documentation — May's Orders

> Detaillierte Felddefinitionen: siehe `api/endpoints.md`.
> Test-Spezifikation: siehe `api/test-cases.md`.

## 1. Basis

- **Basis-URL:** wird beim Terraform-Deployment vergeben (API Gateway Invoke URL, Woche 2).
- **Auth:** `Authorization: Bearer <Cognito-Access-Token>` (JWT).
- **Format:** JSON; Beträge als Ganzzahl in Cent (Entscheidung offen, Woche 2 finalisiert).

## 2. Operationen (Kurzübersicht)

| Methode | Pfad | Auth | Erfolg | Fehler |
|---------|------|------|--------|--------|
| POST | `/orders` | ✅ | 201 | 400, 401, 500 |
| GET | `/orders/{orderId}` | ✅ | 200 | 400, 401, 404, 500 |
| GET | `/orders?limit=&nextToken=` | ✅ | 200 | 400, 401, 500 |
| PATCH | `/orders/{orderId}/status` | ✅ | 200 | 400, 401, 404, 409, 500 |

## 3. Request-/Response-Schemas (vgl. endpoints.md)

### Order-Objekt

```json
{
  "orderId": "ord_<id>",
  "status": "PENDING",
  "customer": { "name": "string", "email": "string" },
  "items": [ { "sku": "string", "quantity": 1, "unitPrice": 1999, "lineTotal": 3998 } ],
  "currency": "EUR",
  "totalAmount": 3998,
  "createdAt": "ISO-8601",
  "updatedAt": "ISO-8601"
}
```

## 4. Statuswerte

`PENDING`, `CONFIRMED`, `PROCESSING`, `SHIPPED`, `DELIVERED`, `CANCELLED`

## 5. Konsistenz-Regeln

- Server berechnet `totalAmount` (nie der Client).
- Statusübergänge: nur gemäß Transition Matrix (`order-lifecycle/transition-rules.md`).
- Alle Datumsangaben in UTC (ISO-8601).
- Response bei Listen: kompakte Order-Darstellung + `nextToken`.