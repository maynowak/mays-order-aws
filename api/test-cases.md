# Test Cases — May's Orders

> Status der Ausführung wird in `tests/test-results.md` dokumentiert.
> Stand Woche 1: **spezifiziert, noch nicht ausgeführt.**

## 1. API-Testfälle

| ID | Operation | Input | Erwartung |
|----|-----------|-------|-----------|
| T-01 | POST /orders | gültiger Body | 201, `status=PENDING`, `totalAmount` korrekt |
| T-02 | POST /orders | fehlendes `customer.name` | 400 VALIDATION_ERROR |
| T-03 | POST /orders | ungültige E-Mail | 400 VALIDATION_ERROR |
| T-04 | POST /orders | leere `items` | 400 VALIDATION_ERROR |
| T-05 | POST /orders | `quantity=0` | 400 VALIDATION_ERROR |
| T-06 | POST /orders | unbekanntes Feld | 400 VALIDATION_ERROR |
| T-07 | GET /orders/{id} | vorhandene ID | 200, vollständiges Objekt |
| T-08 | GET /orders/{id} | nicht vorhandene ID | 404 ORDER_NOT_FOUND |
| T-09 | GET /orders/{id} | ungültiges ID-Format | 400 VALIDATION_ERROR |
| T-10 | GET /orders | ohne Parameter | 200, Liste + `count` |
| T-11 | GET /orders | `limit=5`, >5 vorhanden | 200, 5 Items + `nextToken` |
| T-12 | GET /orders | `nextToken` aus T-11 | 200, nächste Seite, kein Überschneiden |
| T-13 | PATCH /orders/{id}/status | gültiger Übergang | 200, neuer Status + updatedAt |
| T-14 | PATCH /orders/{id}/status | ungültiger Übergang | 409 INVALID_TRANSITION |
| T-15 | PATCH /orders/{id}/status | ungültiger Status-String | 400 VALIDATION_ERROR |
| T-16 | PATCH /orders/{id}/status | nicht vorhandene ID | 404 ORDER_NOT_FOUND |

## 2. Auth-Testfälle

| ID | Szenario | Erwartung |
|----|----------|-----------|
| A-01 | Request ohne Token | 401 |
| A-02 | Request mit abgelaufenem/gefälschtem Token | 401 |
| A-03 | Request mit gültigem Token | Operation ausgeführt |
| A-04 | Benutzer außerhalb `staff` (falls Rollen etabliert) | 403 |

## 3. State-Machine-Unit-Tests

| ID | Von | Nach | Erwartung |
|----|-----|------|-----------|
| SM-01 | PENDING | CONFIRMED | erlaubt |
| SM-02 | PENDING | CANCELLED | erlaubt |
| SM-03 | CONFIRMED | PROCESSING | erlaubt |
| SM-04 | CONFIRMED | CANCELLED | erlaubt |
| SM-05 | PROCESSING | SHIPPED | erlaubt |
| SM-06 | SHIPPED | DELIVERED | erlaubt |
| SM-07…18 | alle ungültigen Kombinationen | | abgelehnt |

## 4. Konkurrenz-Testfälle

| ID | Szenario | Erwartung |
|----|----------|-----------|
| R-01 | Zwei parallele Updates von `CONFIRMED` (→PROCESSING, →CANCELLED) | genau einer gewinnt, anderer 409 CONFLICTED_UPDATE; Endzustand konsistent |
| R-02 | Update nach bereits erreichtem Zielstatus | 409 (Idempotenz-Entscheidung, vgl. transition-rules §5) |

## 5. Nicht-funktionale Prüfungen (Woche 4)

- Lambda `Duration`-Metrik im erwarteten Bereich (Messung dokumentieren).
- Listing über 100/1.000/10.000 Items: `Query`-Latenz und `nextToken`-Korrektheit.
- Kosten-Schätzung vs. tatsächliche Metered Usage (CloudWatch Billing/Metrics).