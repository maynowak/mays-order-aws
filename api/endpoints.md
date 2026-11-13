# API Endpoint Design — May's Orders

## 1. Übersicht

| Methode | Pfad | Zweck |
|---------|------|-------|
| POST | `/orders` | Bestellung anlegen |
| GET | `/orders/{orderId}` | Bestellung abrufen |
| GET | `/orders` | Bestellungen listen (paginiert) |
| PATCH | `/orders/{orderId}/status` | Status einer Bestellung ändern |

## 2. Endpoint-Spezifikation

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
    { "sku": "SKU-1001", "quantity": 2, "unitPrice": 20 }
  ],
  "currency": "EUR",
  "orderType": "generic"
}
```

`orderType` ist **optional** (Default `generic`). Er beschreibt die gewünschte fachliche
Verarbeitung (Routing), **nicht** den Eigentümer oder die aufrufende Anwendung:
namespace-fähig (`ris.document.analyze`, `jobsearch.match`), ausschließlich Kleinbuchstaben,
Ziffern, Bindestrich und Punkt als Segmenttrenner, jedes Segment beginnt mit einem Buchstaben,
max. 128 Zeichen. Unbekannte Typen werden vom Worker abgelehnt (DLQ), nicht als `generic`
verarbeitet. (MO-RC4-P02E)

**Validierung (400 VALIDATION_ERROR):**

- `customer.name`: Pflicht, nicht leer
- `customer.email`: Pflicht, gültiges E-Mail-Format
- `items`: Pflicht, mindestens 1 Position
- `items[].sku`: Pflicht
- `items[].quantity`: Ganzzahl ≥ 1
- `items[].unitPrice`: Ganzzahl ≥ 1 (Integer, keine Nachkommastellen)
- `currency`: Pflicht, 3 Zeichen (ISO-4217)
- `orderType`: optional, Default `generic`; Namensschema s. o.
- Unbekannte Felder → 400 (strikte Validierung)

**Antwort 201:**

```json
{
  "orderId": "ord_2f4b1c9e...",
  "status": "PENDING",
  "orderType": "generic",
  "customer": { "name": "Max Mustermann", "email": "max@example.com" },
  "items": [ { "sku": "SKU-1001", "quantity": 2, "unitPrice": 20, "lineTotal": 40 } ],
  "currency": "EUR",
  "totalAmount": 40,
  "createdAt": "2026-08-17T12:00:00.000Z",
  "updatedAt": "2026-08-17T12:00:00.000Z"
}
```

**Semantik:** `totalAmount` = Σ (quantity × unitPrice). Server berechnet den Betrag, nie der Client.

**Eigentümer (MO-RC4-P02):** Jede Bestellung gehört genau einem Benutzer. Der Eigentümer
wird **ausschließlich** aus dem verifizierten JWT-Kontext gelesen (`sub` aus
`requestContext.authorizer.jwt.claims`) und dauerhaft gespeichert (`subjectId` + GSI2).
Der Request-Body kann keinen Eigentümer setzen: ein Feld `subjectId` ist ein unbekanntes
Feld und wird mit **400 `VALIDATION_ERROR`** abgelehnt. Fehlt die verifizierte Identität
(z. B. direkter Lambda-Invoke ohne Autorizer), antwortet der Handler mit
**401 `UNAUTHORIZED`** — es wird kein Ersatz-Eigentümer abgeleitet (fail-closed).
Zusätzlich muss der Consumer aus dem Token ableitbar sein (`iss` + `client_id` bzw. `aud`);
fehlt er, wird der Aufruf mit 401 abgelehnt (MO-RC4-P02A).

### 2.2 `GET /orders/{orderId}`

**Auth:** erforderlich.

**Pfad:** `orderId` (String, Format `ord_` + Alphanumerisch)

**Antwort 200:** Order-Objekt wie oben.

**Fehler:**
- 404 `ORDER_NOT_FOUND` — Order existiert nicht **oder** gehört einem anderen Owner/Consumer
- 400 `VALIDATION_ERROR` — ungültiges `orderId`-Format
- 401 `UNAUTHORIZED` — fehlende/ungültige Identität

**Autorisierung (MO-RC4-P02H-A):** Zugriff nur, wenn `order.subjectId == JWT.sub`
**und** `order.consumerId == verifizierter Consumer`. Legacy-Orders ohne vollständige
Identität liefern 404 (fail-closed, keine Migration).

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
  "orders": [ { "orderId": "...", "status": "PENDING", "customer": { "name": "..." }, "totalAmount": 40, "createdAt": "...", "updatedAt": "..." } ],
  "nextToken": "eyJ...",
  "count": 20
}
```

`nextToken` fehlt, wenn keine weiteren Seiten existieren.

**Autorisierung (MO-RC4-P02H-A):** Die Liste enthält ausschließlich Orders des
verifizierten Owners **und** Consumers (GSI2-Partition `SUBJECT#<sub>` plus
Consumer-Prüfung). Fremde Orders erscheinen nicht. `nextToken` ist ein GSI2-Cursor;
alte GSI1-Token werden mit **400 `VALIDATION_ERROR`** abgelehnt. Ohne Identität: **401**.

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
- 404 `ORDER_NOT_FOUND` — fremde/legacy Order (die Owner- und Consumer-Bedingung ist Teil
  derselben Conditional-Expression; ein fremder Storno schlägt fehl und verändert nichts)
- 401 `UNAUTHORIZED` — fehlende/ungültige Identität

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
| 404 | `ORDER_NOT_FOUND` | Order existiert nicht |
| 409 | `INVALID_TRANSITION` | Statusübergang ungültig |
| 409 | `CONFLICTED_UPDATE` | Konkurrierendes Update (Conditional Check verloren) |
| 500 | `INTERNAL_ERROR` | Unerwarteter Fehler (nur generisch nach außen) |

## 4. Offene API-Entscheidungen (Woche 1/2)

| Frage | Stand |
|-------|-------|
| `GET /orders` Sortierung (createdAt absteigend) | Fix: absteigend |
| Vollständige Order-Objekte vs. kompakte Liste | Fix: kompakte Liste (Sparsamkeit) |
| `POST /orders` Response 201 inkl. Location-Header | Entscheidung offen, in API-Dokumentation Woche 2 finalisiert |