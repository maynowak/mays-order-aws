# DynamoDB Data Model — May's Orders

## 1. Design-Ansatz

**Single-Table-Design** (eine Tabelle `mays-orders`).

### Begründung (Trade-off)

| Kriterium | Single-Table | Multi-Table |
|-----------|--------------|-------------|
| Anzahl Tabellen | 1 | n (orders, events, …) |
| Query-Effizienz | Queries innerhalb einer Tabelle, kein Join | Mehrere Queries/Abrufe nötig |
| Kosten | Weniger RCU/WCU pro Anfrage | Mehr Provisioning/Operationen |
| Komplexität | Modelldokumentation nötig (Item-Shapes) | Schema isolierter |
| Geeignet | eine dominante Entity + Zusatz-Items | viele unabhängige Entities |

Für dieses Projekt existiert **eine dominante Entity (Order)**. Zusätzliche Item-Typen
(z. B. Status-History) lassen sich als GSI/Item-Shape innerhalb derselben Tabelle modellieren.
Ein Multi-Table-Design würde hier keine Abfrage verbessern, aber zusätzliche Verwaltung und
IAM-Permissions erzeugen. **Entscheidung: Single-Table.**

## 2. Item-Modell

### Order-Item

| Attribut | Typ | Beschreibung |
|----------|-----|--------------|
| `pk` | String (Partition Key) | `ORDER#<orderId>` |
| `sk` | String (Sort Key) | `#ORDER` (konstant) |
| `orderId` | String | `ord_` + 24 Zeichen (hex/base62) |
| `status` | String | `PENDING \| CONFIRMED \| PROCESSING \| SHIPPED \| DELIVERED \| CANCELLED` |
| `customer` | Map | `{ name, email }` |
| `items` | List of Maps | `[{ sku, quantity, unitPrice, lineTotal }]` |
| `currency` | String | ISO-4217 |
| `totalAmount` | Number | Server-berechnet (Σ quantity × unitPrice) |
| `createdAt` | String | ISO-8601 UTC |
| `updatedAt` | String | ISO-8601 UTC |
| `version` | Number | Optimistic-Locking-Feld (Reserve für Woche 3) |
| `gsi1pk` | String (GSI1 PK) | `LIST` (konstant) |
| `gsi1sk` | String (GSI1 SK) | `createdAt` (ISO-8601) |

## 3. Index-Struktur

| Index | PK | SK | Projection | Zweck |
|-------|-----|-----|------------|-------|
| (Table) | `pk` | `sk` | ALL | Punktzugriffe `GetItem` / `UpdateItem` |
| `gsi1` | `gsi1pk` | `gsi1sk` | `orderId, status, customer, totalAmount, createdAt, updatedAt` | Listen aller Orders, sortiert nach `createdAt`, paginiert |

## 4. Warum dieses Primärschlüssel-Design?

1. **Punktzugriff (AP2)**: `GetItem` auf `pk = ORDER#<id>` → 1 RCU-freundlich, O(1), kein Scan.
2. **Listing (AP3)**: `Query` auf GSI1 (`gsi1pk = LIST`, `ScanIndexForward = false`) liefert
   alle Orders absteigend nach `createdAt`, mit `LastEvaluatedKey`-Pagination. **Kein Scan.**
3. **Status-Update (AP4)**: `UpdateItem` mit Bedingung auf `pk`, `status` → atomarer,
   konkurrenzsicherer Übergang (Conditional Write).

## 5. Warum GSI statt Scan für Listing?

Ohne GSI wäre `GET /orders` ein `Scan` der gesamten Tabelle — skaliert linear mit der
Datenmenge und verbraucht pro Scan alle Items in RCU. Mit GSI wird das Listing ein
partitionierter `Query`, der exakt die gewünschten Items in sortierter Reihenfolge liefert
und nativ paginiert.

## 6. Hot-Partition-Abwägung (wichtig!)

Der GSI-Partitionsschlüssel `LIST` ist **konstant** → alle Items landen in einer
GSI-Partition.

| Faktor | Bewertung |
|--------|-----------|
| 100 Orders/Tag | Unkritisch |
| 1.000 Orders/Tag | Unkritisch |
| 10.000 Orders/Tag | ~0,12 Requests/s im Schnitt, unkritisch |
| 100.000 Orders/Tag | ~1,2 Requests/s Ø, Spitzen unkritisch bei On-Demand (adaptive Capacity) |

**Grenze:** Eine GSI-Partition hält max. 10 GB. Bei ~400 Byte/Order ≈ 25 Mio. Orders.
Für OrderFlow (kleines Unternehmen) in einem realistischen Horizont unproblematisch.

**Falls nötig (AD-Weg offen, Woche 4):** Sharding der GSI1PK z. B. auf `LIST#<Jahr-Monat>`
oder `LIST#<letzteZiffer>` — würde Hot-Partitions bei sehr hoher Last weiter verteilen,
jedoch Mehrfach-Queries (Union) erfordern. Bewusst NICHT jetzt eingeführt
(keine unnötige Komplexität, siehe Requirements C-03).

## 7. Payload-Grenzen

- Item max. 400 KB (A-07) — eine Order ist ≪ 400 KB.
- `totalAmount` server-seitig als Number (kein Floats-Runden-Fehler: Beträge in Cent
  als Ganzzahl speichern — **Entscheidung offen**, in Woche 2 finalisiert; Vorab-Definition:
  Beträge als Ganzzahl in Cent, um Rundungsfehler zu vermeiden).

## 8. Capacity Mode

**On-Demand** (vorläufig, Entscheidung offen):

- Kein Provisioning-Management, passt zu stark schwankendem Test-/Demo-Verkehr.
- Free-Tier: 25 GB Speicher + 25 WCU/RCU-Kapazität (On-Demand-Anteil).
- Kostenanalyse in `cost/cost-analysis.md` (Woche 1) und Woche 4 (Skalierung).
- Trade-off Provisioned vs. On-Demand wird dort quantifiziert.