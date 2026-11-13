# API Endpoint Design — May's Orders

## 1. Übersicht

| Methode | Pfad | Zweck |
|---------|------|-------|
| POST | `/orders` | Bestellung anlegen |
| GET | `/orders/{orderId}` | Bestellung abrufen |
| GET | `/orders` | Bestellungen listen (paginiert) |
| PATCH | `/orders/{orderId}/status` | Status einer Bestellung ändern |

## 2. Endpoint-Spezifikation

> **Eigentümerbindung (MO-AGENT-ORDER-OWNERSHIP-02):** Jede Route liest `iss` und
> `sub` aus den vom Gateway verifizierten JWT-Claims. Der Eigentümer wird beim
> Anlegen serverseitig gespeichert. `GET`, `PATCH` und `GET` (Liste) sind auf den
> Eigentümer begrenzt; fremde und nicht zuordenbare Orders liefern `404`
> `ORDER_NOT_FOUND` (keine Unterscheidung zu „existiert nicht").
> Orders ohne Eigentümerbindung (Bestand) bleiben für normale Aufrufer gesperrt.
> Es gibt keinen `staff`/`admin`-Pauschalzugriff.

### 2.1 `POST /orders`

**Auth:** erforderlich (Cognito JWT).

**Request-Body:**

```json
{
  "customer": {
    "name": "Max Mustermann",
    "email": "max@example.com"
  },
  "items": [
    { "sku": "SKU-1001", "quantity": 2, "unitPrice": 19.99 }
  ],
  "currency": "EUR"
}
```

**Validierung (400 VALIDATION_ERROR):**

- `customer.name`: Pflicht, nicht leer
- `customer.email`: Pflicht, gültiges E-Mail-Format
- `items`: Pflicht, mindestens 1 Position
- `items[].sku`: Pflicht
- `items[].quantity`: Ganzzahl ≥ 1
- `items[].unitPrice`: Zahl > 0
- `currency`: Pflicht, 3 Zeichen (ISO-4217)
- Unbekannte Felder → 400 (strikte Validierung)

**Antwort 201:**

```json
{
  "orderId": "ord_2f4b1c9e...",
  "status": "PENDING",
  "customer": { "name": "Max Mustermann", "email": "max@example.com" },
  "items": [ { "sku": "SKU-1001", "quantity": 2, "unitPrice": 19.99, "lineTotal": 39.98 } ],
  "currency": "EUR",
  "totalAmount": 39.98,
  "createdAt": "2026-08-17T12:00:00.000Z",
  "updatedAt": "2026-08-17T12:00:00.000Z"
}
```

**Semantik:** `totalAmount` = Σ (quantity × unitPrice). Server berechnet den Betrag, nie der Client.

### 2.2 `GET /orders/{orderId}`

**Auth:** erforderlich.

**Pfad:** `orderId` (String, Format `ord_` + Alphanumerisch)

**Antwort 200:** Order-Objekt wie oben.

**Eigentümer-Detail (MO-AGENT-ORDER-PROJECTION-01):** Bei
`orderType = "agent.execution"` enthält die Antwort für den **verifizierten
Eigentümer** zusätzlich ein freigegebenes `agentOrder`-Objekt mit `schemaVersion`,
`target`, `input`, `metadata` (`source`, `requestId`) und `resultContract`.
Nicht enthalten: `processing`, `metadata.partnerApplicationRef`,
`metadata.apiProfileRef`, `metadata.idempotencyKey` sowie alle internen
Identitäts- und Indexfelder. Listen-, Create- und Patch-Antworten enthalten
`agentOrder` nicht.

**Ergebnisprojektion (A06):** Liegt ein übernommenes Agentenergebnis vor, enthält
die Eigentümer-Detailantwort zusätzlich `processing` mit `status`
(`COMPLETED`/`FAILED`), `attempt`, `completedAt` und entweder `result` oder
`error.message`. Interne Korrelationstokens (`workId`, `messageId`,
`idempotencyKey`, `executionId`) werden nicht ausgegeben. Der fachliche
Order-`status` bleibt unverändert; das Ergebnis ist ein eigenes Feld.

**Fehler:**
- 404 `ORDER_NOT_FOUND` — Order existiert nicht
- 400 `VALIDATION_ERROR` — ungültiges `orderId`-Format

### 2.3 `GET /orders`

**Auth:** erforderlich.

**Query-Parameter (alle optional):**

| Parameter | Typ | Standard | Zweck |
|-----------|-----|----------|-------|
| `limit` | int | 20 | Max. Anzahl Items (1–100) |
| `nextToken` | string | – | Pagination-Token (nicht öffentliche Order-ID) |

**Antwort 200:**

```json
{
  "orders": [ { "orderId": "...", "status": "PENDING", "customer": { "name": "..." }, "totalAmount": 39.98, "createdAt": "...", "updatedAt": "..." } ],
  "nextToken": "eyJ...",
  "count": 20
}
```

`nextToken` fehlt, wenn keine weiteren Seiten existieren.

### 2.4 `PATCH /orders/{orderId}/status`

**Auth:** erforderlich.

**Request-Body:**

```json
{ "status": "CONFIRMED" }
```

**Validierung:**
- `status` Pflicht, muss ein gültiger Statuswert sein (`PENDING|CONFIRMED|PROCESSING|SHIPPED|DELIVERED|CANCELLED`)

**Antwort 200:** aktualisiertes Order-Objekt (neuer `status`, neuer `updatedAt`).

**Fehler:**
- 404 `ORDER_NOT_FOUND`
- 400 `VALIDATION_ERROR` (ungültiger Status-String)
- 409 `INVALID_TRANSITION` (Transition nicht erlaubt, enthält `currentStatus` + `requestedStatus`)
- 409 `CONFLICTED_UPDATE` (Conditional-Check verloren → konkurrierendes Update hat gewonnen)

## 3. Fehlerformat (einheitlich)

```json
{
  "error": {
    "code": "INVALID_TRANSITION",
    "message": "Transition from PROCESSING to CANCELLED is not allowed",
    "details": { "currentStatus": "PROCESSING", "requestedStatus": "CANCELLED" }
  }
}
```

| HTTP | Code | Bedeutung |
|------|------|-----------|
| 400 | `VALIDATION_ERROR` | Request validiert nicht |
| 401 | `UNAUTHORIZED` | Fehlendes/ungültiges Token |
| 403 | `FORBIDDEN` | Authentifiziert, aber nicht berechtigt |
| 404 | `ORDER_NOT_FOUND` | Order existiert nicht **oder** gehört einem anderen Aufrufer |
| 409 | `INVALID_TRANSITION` | Statusübergang ungültig |
| 409 | `CONFLICTED_UPDATE` | Konkurrierendes Update (Conditional Check verloren) |
| 500 | `INTERNAL_ERROR` | Unerwarteter Fehler (nur generisch nach außen) |
| 503 | `SERVICE_UNAVAILABLE` | Eigentümer-Index oder Identitätskonfiguration fehlt (fail-closed) |

## 4. Offene API-Entscheidungen (Woche 1/2)

| Frage | Stand |
|-------|-------|
| `GET /orders` Sortierung (createdAt absteigend) | Fix: absteigend |
| Vollständige Order-Objekte vs. kompakte Liste | Fix: kompakte Liste (Sparsamkeit) |
| `POST /orders` Response 201 inkl. Location-Header | Entscheidung offen, in API-Dokumentation Woche 2 finalisiert |