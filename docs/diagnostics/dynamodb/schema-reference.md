# DynamoDB Schema-Referenz (Orders)

**Stand:** 2026-11-03 · **Quelle:** tatsächlicher Code, nicht Design-Dokumente.
Legende: **VERIFIED** (Code) · **TESTED** (Unit-Tests) · **DOCUMENTED ONLY** ·
**UNKNOWN**

## 1. Tabelle

| Eigenschaft | Befund | Status |
|---|---|---|
| Name | `var.project_name` (z. B. `mays-orders-rc4`) | VERIFIED — `terraform/modules/dynamodb/main.tf:11-12` |
| Modell | Single-Table | VERIFIED — `database/dynamodb-design.md` |
| Billing | `PAY_PER_REQUEST` | VERIFIED — `main.tf:13` |
| Partition Key | `pk` (String) | VERIFIED — `main.tf:13-20` |
| Sort Key | `sk` (String) | VERIFIED — `main.tf:13-24` |
| PITR | enabled | VERIFIED — `main.tf:108-110` (nie restored/getestet) |
| Streams | nicht konfiguriert | VERIFIED — keine `stream_*`-Attribute |
| TTL | nicht konfiguriert | VERIFIED — kein `ttl`-Block |
| Verschlüsselung | AWS-owned (kein KMS) | VERIFIED — keine `server_side_encryption`-Konfiguration |

## 2. Schlüsselmuster (implementiert)

| Schlüssel | Muster | Status |
|---|---|---|
| `pk` | `ord_` + `orderId` → `ord_ord_<24hex>` (orderId = `ord_` + 24 Hex) | VERIFIED — `order_service.py:84-85,201-205`; TESTED — `lambda/tests/test_order_access_authorization.py:43` |
| `sk` | `#ORDER` (konstant) | VERIFIED — `order_types.py:22` |
| `gsi1pk` | `LIST` (konstant) | VERIFIED — `order_types.py:24`; `order_service.py:216` |
| `gsi1sk` | `createdAt` (ISO-8601 UTC) | VERIFIED — `order_service.py:217` |
| `gsi2pk` | `SUBJECT#<subjectId>` | VERIFIED — `order_types.py:27`; `order_service.py:225` |
| `gsi2sk` | `ord_` + `orderId` + `#` + `createdAt` | VERIFIED — `order_service.py:226`; TESTED — `test_order_service.py:641` |
| `gsi3pk` | `PROCESSING#RUNNING` | VERIFIED — `sqs_handler.py:48,336` |
| `gsi3sk` | Claim-Zeitpunkt (ISO-8601) | VERIFIED — `sqs_handler.py:351-353` |

### Bekannte Abweichungen

| Befund | Status |
|---|---|
| Design-Doc nennt `pk = ORDER#<orderId>`; Code verwendet `ord_ord_<24hex>` | **CONFLICT** (Doku veraltet) — `database/dynamodb-design.md:31` vs. Code |
| RIS schreibt direkt in die Tabelle, teils ohne `subjectId` und mit abweichendem `pk`-Muster | DOCUMENTED ONLY — `architecture/architecture-decisions.md:123-131` |
| Legacy-Orders ohne vollständige Identität (kein `subjectId`/`consumerId`) | VERIFIED — `api/endpoints.md:95-97` (404) |

**Regel:** Kein einheitliches Schlüsselmuster annehmen. Diagnose immer mit dem
tatsächlich vorhandenen Schlüssel; bei unbekannten Mustern `UNKNOWN` dokumentieren.

## 3. Order-Item (Kernfelder)

| Attribut | Typ | Bedeutung | PII? |
|---|---|---|---|
| `pk`, `sk` | S | Schlüssel | nein (Order-ID pseudonym) |
| `orderId` | S | `ord_` + 24 Hex | nein |
| `status` | S | siehe §4 | nein |
| `orderType` | S | Routing-Typ (Default `generic`) | nein |
| `customer` | M | `{name, email}` | **JA** |
| `items` | L | `[{sku, quantity, unitPrice, lineTotal}]` | nein |
| `currency`, `totalAmount` | S/N | Betrag/Währung | nein |
| `createdAt`, `updatedAt` | S | ISO-8601 UTC | nein |
| `version` | N | Optimistic Locking | nein |
| `gsi1pk`, `gsi1sk`, `gsi2pk`, `gsi2sk` | S | Indexschlüssel | nein (subjectId pseudonym) |

Quelle: `lambda/src/order_service.py:201-227`.

## 4. Statuswerte

`PENDING`, `CONFIRMED`, `PROCESSING`, `SHIPPED`, `DELIVERED`, `CANCELLED`
(`lambda/src/order_types.py:5-12`). Übergänge: `order-lifecycle/state-machine.md`.

## 5. Identitäts-/Consumer-Felder (ab P02A/P02B)

| Attribut | Bedeutung | PII? |
|---|---|---|
| `subjectId` | Owner (`sub` aus JWT) | pseudonym |
| `consumerId` | `cognito:<issuer>#<client>` | nein |
| `ownerType`, `ownerId`, `actorType`, `actorId`, `identityVersion`, `identityVerification` | Identitätsbindung | teils pseudonym |

Quelle: `order_service.py:228-238`, `architecture/architecture-decisions.md:133-145`.

## 6. Zustell-/Verarbeitungsfelder

| Attribut | Bedeutung |
|---|---|
| `deliveryState` (`pending`/`sending`/`sent`/`failed`) | SQS-Zustellung |
| `deliveryAttempts`, `lastDeliveryAt` | Zustellversuche |
| `processingState`, `processingAttemptId`, `processingAttempts`, `processingClaimedAt` | Worker-Claim/Lease |
| `result`, `processingError`, `completedAt` | Verarbeitungsergebnis (kann fachliche Daten enthalten) |
| `gsi3pk`, `gsi3sk` | nur während aktiver Claims gesetzt, danach entfernt |

Quellen: `order_service.py:219,248-249`; `sqs_handler.py:350-353,419-434`.

## 7. GSIs

| Index | PK | SK | Projektion | Nicht-Schlüssel-Attribute | Status |
|---|---|---|---|---|---|
| `gsi1` | `gsi1pk` | `gsi1sk` | `INCLUDE` | `orderId`, `status`, `customer`, `totalAmount`, `createdAt`, `updatedAt` | VERIFIED — `main.tf:59-73` |
| `gsi2` | `gsi2pk` | `gsi2sk` | `INCLUDE` | `orderId`, `subjectId`, `version`, `createdAt`, `status`, `updatedAt`, `customer`, `totalAmount`, `currency` | VERIFIED — `main.tf:75-92` |
| `gsi3` | `gsi3pk` | `gsi3sk` | **`KEYS_ONLY`** | — (nur Schlüssel) | VERIFIED — `main.tf:94-110` |

**Wichtig:**

- `gsi3` liefert **nur** `pk`/`sk`/`gsi3pk`/`gsi3sk`; alle Details erfordern einen
  zweiten `GetItem` über die Basistabelle.
- `gsi2` projiziert **kein** `consumerId` und keine Processing-/Ergebnis-Felder;
  Privacy-Abfragen laden deshalb das vollständige Item per `GetItem`
  (`order_service.py`, P02G-A) — Consumer-Filterung ist nicht über die
  GSI2-Projektion allein möglich.
- `gsi1`/`gsi2` enthalten `customer` (PII) in der Projektion — Indexabfragen können
  PII zurückgeben; Projektionen in Diagnoseabfragen eng halten.

## 8. Anonymisierung / Löschung

- `ERASE` löscht das Item (`DeleteItem`, Conditional auf `subjectId`/`version`).
- `ANONYMIZE` setzt `customer.name/email` auf `ANONYMIZED` und entfernt
  `subjectId`, `gsi2pk`, `gsi2sk`, `result`, `processingError`, `processingAttemptId`,
  `gsi3pk`, `gsi3sk` (`order_service.py:730-755`).
- Nach `ANONYMIZE` ist die Order **nicht mehr über GSI2** auffindbar; ein leeres
  GSI2-Ergebnis bedeutet daher nicht zwingend „Order existiert nicht“.
- **Kein Erasure-Ledger** vorhanden → Restore kann gelöschte PII wiederbringen (P3E).

## 9. Nicht belegte Annahmen

| Annahme | Status |
|---|---|
| TTL/Retention-Felder | UNKNOWN/nicht vorhanden |
| Streams/CDC | nicht vorhanden |
| KMS-Verschlüsselung | nicht vorhanden |
| Einheitliches `pk`-Muster über alle Schreiber | **widerlegt** (Doku/RIS-Abweichungen) |
