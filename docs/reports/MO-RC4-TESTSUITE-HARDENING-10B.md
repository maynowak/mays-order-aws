# MO-RC4-TESTSUITE-HARDENING-10B

**Deterministische lokale Komponententests für den RC4-Order-Verarbeitungsablauf**

**Datum:** 2026-11-11
**Referenz:** `test/mo-rc4-testsuite-hardening-10a` @ `e703f9678c5e85c91411d8bfa7dd7515c602dd56`
**Arbeitsbranch:** `test/mo-rc4-testsuite-hardening-10a`
**Modus:** Lokale Tests; keine AWS-Verbindung, keine Terraform-Mutation, keine
SQS-/DynamoDB-Live-Operation, keine Credentials, kein Push/Merge.

```text
MO-RC4-TESTSUITE-HARDENING-10B — VERIFIED
```

---

## 1. Ausgangsbaseline

| Feld | Wert |
|---|---|
| Referenzbranch | `test/mo-rc4-testsuite-hardening-10a` |
| Referenz-HEAD | `e703f9678c5e85c91411d8bfa7dd7515c602dd56` |
| Vorheriger Status | `MO-RC4-TESTSUITE-HARDENING-10A — VERIFIED` |
| Ausgangs-Working-Tree | CLEAN |
| Ausgangs-Regression | Installer 621, Builder 128, Lambda 326 = **1.075 PASS** |
| Neuer Testumfang | **+11** Lambda-Komponententests |

---

## 2. Tatsächliche RC4-Verarbeitungskette

Die Implementierung folgt der produktiven Architektur, nicht einer
angenommenen Schnittstelle:

```text
HTTP-API-v2-Event
  routeKey = "POST /orders"
        |
        v
index.handler
  resolve_order_identity_from_event(event)
    -> requestContext.authorizer.jwt.claims
       (sub, iss, client_id)
        |
        v
OrderService.create_order(...)
  validation.py: validate_create_order
  item: status=PENDING, version=1, orderType=generic,
        subjectId/consumerId/ownerId/actorId, gsi1/gsi2
        |
        +--> DynamoDB put_item (Fake)
        |
        +--> index._send_to_sqs(orderId)
                 |
                 v
             SQS-Nachricht
             {"orderId": "...", "status": "CONFIRMED",
              "metadata": {"reason": "order_created"}}
        |
        v
index._mark_delivery -> OrderService.mark_delivery_state
        |
        v
API-Antwort 201 mit Order im Status PENDING
```

Worker-Pfad:

```text
SQS-Record
  sqs_handler.handler
    -> _process_order
       -> _read_item (DynamoDB-Client, typed values)
       -> orderType aus dem gespeicherten Item (nicht aus SQS)
       -> order_handlers.get_handler_spec
       -> generischer Handler: keine Fachlogik
       -> state_machine.can_transition(PENDING, CONFIRMED)
       -> conditional update_item:
            attribute_exists(pk) AND #status = :currentStatus
            status = CONFIRMED, version += 1
       -> {"batchItemFailures": []}
```

Relevante Quellen:

- `lambda/src/index.py` — HTTP-Routen, JWT-Identität, Order-Erstellung, SQS-Publish,
  Delivery-Vermerk.
- `lambda/src/order_service.py` — `create_order`, `mark_delivery_state`,
  `get_order`, Conditional Update/Version.
- `lambda/src/sqs_handler.py` — SQS-Batchverarbeitung, Statusübergang,
  Conditional Update, Retry-Signal.
- `lambda/src/order_handlers.py` — Handler-Registry, `generic`.
- `lambda/src/state_machine.py` — erlaubte Statusübergänge.
- `lambda/src/identity.py` — ausschließlich JWT-Claims als Identitätsquelle.
- `docs/phase2-async-order-ingest.md:154-162` — dokumentiert: kein
  client-provided Idempotency-Key; API-Deduplizierung ist nicht implementiert.

### Statusübergänge

```text
PENDING    -> CONFIRMED, CANCELLED
CONFIRMED  -> PROCESSING, CANCELLED
PROCESSING -> SHIPPED
SHIPPED    -> DELIVERED
DELIVERED  -> (keine)
CANCELLED  -> (keine)
```

Ungültige oder rückwärts gerichtete Übergänge werden vom Worker abgelehnt; ein
bereits erreichter Zielstatus wird als idempotent behandelt.

---

## 3. Neue Testdatei

`lambda/tests/test_order_processing_component.py`

Die Datei enthält ausschließlich lokale Komponententests und den zugehörigen
Harness. Produktiver Code wurde nicht verändert.

---

## 4. Fake-DynamoDB-/SQS-Architektur

### 4.1 Gemeinsamer Zustand

`FakeDynamoStore` hält kanonische Items unter `(pk, sk)`. Zwei Adapter greifen
auf denselben Store zu:

| Adapter | Verwendung | Werteformat |
|---|---|---|
| `FakeTable` | `OrderService` (boto3-Resource-Stil) | native Python-Werte |
| `FakeClient` | `sqs_handler` (boto3-Client-Stil) | typed DynamoDB-Werte (`{"S": ...}`) |

Damit sehen API- und Worker-Pfad denselben Zustand.

### 4.2 DynamoDB-Semantik

Unterstützt werden die tatsächlich benötigten Operationen:

- `put_item`
- `get_item` (inkl. `ConsistentRead`-Argument)
- `update_item`
- `ConditionExpression` für `attribute_exists`, `attribute_not_exists`,
  Gleichheit/Ungleichheit und Größenvergleiche
- `UpdateExpression` mit `SET`, `REMOVE`, `if_not_exists(...) + :one`
- `ReturnValues="ALL_NEW"`
- Conditional-Check-Fehler über `FakeClientError`

Ein Conditional Write ist **nicht** pauschal erfolgreich: Der Store wertet die
Bedingung gegen das aktuelle Item aus. Zusätzlich kann
`force_conditional_failure` einen Konflikt kontrolliert auslösen; der Test
prüft dann, dass weder Status noch Version geschrieben werden.

### 4.3 SQS-Semantik

`FakeSQS` unterstützt:

- `send_message` mit `QueueUrl`, `MessageBody`, `MessageAttributes`
- Nachrichtenpuffer mit deterministischen `messageId`s
- `records()` zur kontrollierten Zustellung an den Worker

Es gibt keine echte Queue, keine SQS-API und kein Netzwerk.

### 4.4 Identität

Der Test-Event enthält ausschließlich einen vertrauenswürdigen
API-Gateway-Authorizer-Kontext:

```text
requestContext.authorizer.jwt.claims
  sub       = user-a / user-b
  iss       = Test-Issuer
  client_id = component-client
```

`subjectId` im Request-Body wird nicht als Identitätsquelle verwendet.

---

## 5. Testmatrix

| ID | Test | Ergebnis |
|---|---|---|
| T10B-01 | Order-Erstellung: 201, PENDING, Persistenz, SQS-Publish, Delivery-Vermerk | **PASS** |
| T10B-02 | Worker verarbeitet SQS-Nachricht, Status PENDING -> CONFIRMED, Version 1 -> 2 | **PASS** |
| T10B-03a | Wiederholte identische API-Requests erzeugen getrennte Orders (keine API-Deduplizierung) | **PASS** |
| T10B-03b | Wiederholte SQS-Zustellung ist idempotent; kein zweiter Statuswechsel/Version-Bump | **PASS** |
| T10B-03c | Conditional-Conflict schreibt nicht und erhöht die Version nicht | **PASS** |
| T10B-04a | Ungültige SQS-Nachricht -> `batchItemFailures`, keine Mutation | **PASS** |
| T10B-04b | Temporärer Repository-Fehler -> Retry-Signal, Status bleibt PENDING | **PASS** |
| T10B-04c | Fehler im registrierten Handler -> Retry-Signal, kein Statuswrite | **PASS** |
| T10B-05a | Manipulierte `subjectId` im Body -> 400, keine Order, kein SQS-Publish | **PASS** |
| T10B-05b | Fremde Identität -> 404; Eigentümer -> 200; Owner-/Consumer-Bindung gespeichert | **PASS** |
| T10B-06 | Ungültiger Übergang PENDING -> SHIPPED abgelehnt; gültiger Übergang versioniert; Wiederholung ohne Version-Bump | **PASS** |

### Wichtige Assertions

- Order-ID beginnt mit `ord_`; Initialstatus `PENDING`; Gesamtbetrag `200`.
- `subjectId`, `ownerId`, `actorId` und `consumerId` stammen aus dem
  Authorizer-Kontext.
- SQS-Nachricht enthält dieselbe `orderId`, Status `CONFIRMED` und
  `orderId`-Message-Attribut.
- API-Response und gespeicherter Status werden nach dem Worker über einen
  echten `GET /orders/{orderId}`-Handleraufruf verglichen.
- Fremdzugriff liefert 404 (keine Existenzoffenlegung).
- `batchItemFailures` ist die tatsächliche Retry-Schnittstelle des Workers.

---

## 6. Testresultate

### Fokussierte Tests

```bash
cd lambda
PYTHONPATH=src python3 -m unittest -v tests/test_order_processing_component.py
```

```text
Ran 11 tests in 0.038s
OK
```

### Gesamte lokale Regression

```bash
python3 -m unittest discover -s installer/tests
python3 -m unittest discover -s module_builder/tests
cd lambda && PYTHONPATH=src python3 -m unittest discover -s tests
```

```text
Installer:  Ran 621 tests — OK
Builder:    Ran 128 tests — OK
Lambda:     Ran 337 tests — OK
Gesamt:     1.086 PASS
```

Die Baseline von 1.075 ist um die **11 neuen Komponententests** gewachsen.
Es gab keine Skips.

---

## 7. Mutationstest-Nachweise

Beide Mutationen wurden ausschließlich in temporären Kopien außerhalb des
Repositories durchgeführt. Der Arbeitsbranch blieb unverändert.

### Mutation 1 — Idempotenzprüfung entfernt

Entfernt wurden die beiden Gleichstatus-Prüfungen im generischen
`_process_order`- und `_apply_status_transition`-Pfad. Danach:

```text
FAIL: test_t10b_03_duplicate_worker_delivery_is_idempotent
AssertionError: {'batchItemFailures': [{'itemIdentifier': 'worker-message'}]}
                != {'batchItemFailures': []}
Ran 1 test — FAILED (failures=1)
```

Der Test erkennt die fehlende Worker-Idempotenz.

### Mutation 2 — Statusübergangsprüfung entfernt

Entfernt wurden die `can_transition`-Prüfungen im generischen
`_process_order`- und `_apply_status_transition`-Pfad. Danach:

```text
FAIL: test_t10b_06_invalid_transition_is_rejected_and_valid_transition_is_versioned
AssertionError: {'batchItemFailures': []}
                != {'batchItemFailures': [{'itemIdentifier': 'invalid'}]}
Ran 1 test — FAILED (failures=1)
```

Der Test erkennt, dass PENDING -> SHIPPED fälschlich akzeptiert worden wäre.

---

## 8. Sicherheitsprüfung

| Prüfung | Ergebnis |
|---|---|
| Produktcode geändert | **NEIN** — nur neue Testdatei und Doku |
| AWS-Credentials benötigt | **NEIN** |
| Echte AWS-API-Aufrufe | **NEIN** — `_get_dynamodb_resource`, `_get_dynamodb_client`, `_get_sqs_client` gepatcht |
| Terraform Apply/Destroy/Import | **NEIN** |
| Echte SQS-Nachrichten | **NEIN** |
| Echte DynamoDB-Schreibzugriffe | **NEIN** |
| Cognito-/IAM-/RIS-/CloudFront-Änderung | **NEIN** |
| Backup/Restore | **NEIN** |
| Externe Netzwerkaufrufe | **NEIN** |
| Credentials in Logs | **NEIN** — nur Order-IDs/Outcomes, keine Secrets |
| Platzhalter-Assertions | **NEIN** |

Die SQS-/DynamoDB-Grenzen sind über `unittest.mock.patch` ersetzt. Die
produktiven Handler werden aufgerufen, aber jede AWS-Grenze ist ein lokaler
Fake.

---

## 9. Bekannte Einschränkungen

- **API-Idempotenz ist nicht implementiert.** RC4 hat keinen
  client-provided Idempotency-Key (`docs/phase2-async-order-ingest.md:154-162`).
  Der Test dokumentiert daher korrekt: zwei identische POSTs erzeugen zwei
  getrennte Orders. Worker-Idempotenz und Conditional-Update-Schutz sind
  dagegen vorhanden und getestet.
- Der Harness bildet die für den generischen Status-Pfad benötigte
  DynamoDB-Teilmenge ab. Processing-Claim/Lease-/Ergebnisübernahme wird
  weiterhin durch die bestehenden Processing-Lifecycle-Tests abgedeckt, nicht
  durch diesen Komponentenpfad.
- Der Fake ist kein vollständiger DynamoDB-Emulator: keine Transaktionen,
  keine echten GSI-Queries, keine Kapazitäts-/Throttling-Semantik.
- Die Tests ersetzen keine Live-E2E-Prüfung gegen Cognito, API Gateway, SQS
  oder DynamoDB.

---

## 10. Verbleibende Live-E2E-Lücken

Weiterhin nicht live geprüft:

- echte Cognito-JWT-Ausstellung und API-Gateway-Autorisierung,
- echtes SQS-Publish/Receive inklusive Visibility/Retry,
- echtes DynamoDB-Conditional-Update und GSI1/GSI2/GSI3,
- DLQ-Zustellung,
- Worker-Processing-Claim/Lease unter realer Konkurrenz,
- RC3-zu-RC4-Kompatibilität mit echten Daten.

Diese Lücken sind bewusst nicht durch Produkt-Bypässe geschlossen.

---

## 11. Git-Abschluss

Geplant:

```text
Branch:  test/mo-rc4-testsuite-hardening-10a
Datei:   lambda/tests/test_order_processing_component.py
Commit:  test(rc4): add deterministic order processing component tests
```

Kein Push, kein Merge. Der finale Commit-SHA und der CLEAN-Status werden nach
dem Commit verifiziert.
