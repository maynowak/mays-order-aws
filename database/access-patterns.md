# Access Patterns — May's Orders

## 1. Access-Pattern-Analyse

| # | Pattern | Datenzugriff | API-Endpoint | Zugriffsmethode | Effizient? |
|---|---------|--------------|--------------|-----------------|------------|
| AP1 | Order anlegen | Vollständiges Item schreiben | `POST /orders` | `PutItem` | ✅ O(1) |
| AP2 | Order per ID lesen | Ein Item | `GET /orders/{orderId}` | `GetItem` | ✅ O(1) |
| AP3 | Alle Orders listen (neueste zuerst, paginiert) | Teilmenge Items, sortiert | `GET /orders` | `Query` auf GSI1 | ✅ Query, kein Scan |
| AP4 | Status ändern (Conditional) | Ein Item atomar aktualisieren | `PATCH /orders/{orderId}/status` | `UpdateItem` + Condition | ✅ O(1) |

## 2. Zugriffsmethoden im Detail

### 2.1 AP1 — Create

```text
PutItem(pk=ORDER#<id>, sk=#ORDER, gsi1pk=LIST, gsi1sk=<createdAt>, status=PENDING, ...)
```

### 2.2 AP2 — Get by ID

```text
GetItem(pk=ORDER#<id>, sk=#ORDER)
```

Ein einziger Point-Read. Kein Scan, kein Query-Overhead.

### 2.3 AP3 — List (paginated)

```text
Query(Index=gsi1, KeyConditionExpression=gsi1pk = :LIST,
      ScanIndexForward=false, Limit=:limit, ExclusiveStartKey=:nextToken)
```

- `ScanIndexForward=false` → neueste zuerst (`createdAt` ISO-8601 sortiert lexikografisch korrekt).
- `ExclusiveStartKey` = `LastEvaluatedKey` aus der vorherigen Antwort → Pagination ohne Offset.
- **Kein Scan** — das Listing bleibt auch bei wachsender Datenmenge effizient.

### 2.4 AP4 — Status update (Conditional Write)

```text
UpdateItem(
  Key={pk=ORDER#<id>, sk=#ORDER},
  UpdateExpression="SET #status=:new, updatedAt=:now, version=version+1",
  ConditionExpression="attribute_exists(pk) AND #status=:current",
  ReturnValues=ALL_NEW
)
```

- `attribute_exists(pk)` → 404, wenn Order fehlt (statt Überschreiben).
- `#status = :current` → atomarer Schutz gegen konkurrierende Updates (siehe `transition-rules.md` §4).
- Verlierer erhält `ConditionalCheckFailedException` → HTTP 409.

## 3. Query vs. Scan — Warum kein Scan nötig ist

| Zugriff | Methode | Warum kein Scan |
|---------|---------|-----------------|
| Punktzugriff | `GetItem` | Primärschlüssel bekannt |
| Listing | `Query` (GSI1) | Eigener Index mit konstantem PK |
| Status-Update | `UpdateItem` | Primärschlüssel bekannt |

Es existiert **kein Access Pattern, das einen Scan erfordert**. Alle Abfragen sind
primärschlüssel- bzw. indexbasiert. Damit bleiben Kosten und Latenz unabhängig von der
Gesamtmenge der Orders (nur Listing hängt von der Seitengröße ab).

## 4. Wachsende Datenmenge

| Orders gesamt | Effekt |
|---------------|--------|
| 1.000 | Identisch: GetItem/Query unverändert |
| 10.000 | Identisch |
| 100.000 | Identisch; GSI1-Partition wächst, aber weiterhin Query. 10-GB-Grenze nicht erreicht. |
| ≫ 100.000 über Jahre | Sharding-Option dokumentiert (`dynamodb-design.md` §6) |

## 5. Pagination-Konzept

- `GET /orders` liefert `nextToken` (Base64-kodierter `LastEvaluatedKey`).
- Client übergibt ihn als `?nextToken=…` bei der nächsten Anfrage.
- Keine Offset-Seiten; DynamoDB-nativ, ohne zusätzliche Zustandslogik.
- `nextToken` wird aus Datenschutzgründen nicht im Log ausgegeben (Security).

## 6. Filterung (bewusst minimal)

- **Kein Status-Filter** in Woche 1: Nicht gefordert. Würde ein zweites Pattern (Query)
  oder FilterExpression erfordern. Falls später benötigt: GSI auf `status` oder
  Query-Param + Filter (mit dokumentierter Kostenfolge).
- **Kein Kunden-Filter**: Nicht gefordert. Bei Bedarf: GSI1PK = `CUSTOMER#<id>` als
  separates Pattern (würde List-all-Orders-Query verdrängen).

**Prinzip:** Erst Access Pattern, dann Index. Kein Index „just in case".