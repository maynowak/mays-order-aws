# MO-RC4-P02C-WORKER-SQS-SAFETY

**Worker-Kollisionsschutz, SQS-Zuverlässigkeit und Batch-Fehlerbehandlung**

**Datum:** 2026-11-01
**Branch:** `feature/mo-rc4-kms-privacy-retention`
**Basis:** `2194781928ac3294bb204292bc1431db441441da`
**Typ:** Implementierung (lokal) — keine AWS-Operation, kein Push

---

## 1. Worker-Abschlussroutine (bestehend, erweitert)

`lambda/src/sqs_handler.py::_process_order()` — **einzige** Abschlussroutine, keine neue
angelegt. Aufrufkette unverändert:

```text
POST /orders (index.handler)
  → OrderService.create_order (put_item, status=PENDING)
  → index._send_to_sqs  ({orderId, status:"CONFIRMED", metadata.reason})
  → SQS (orders-queue)
  → Lambda sqs_worker (event source mapping, batch_size 5)
  → sqs_handler.handler → _process_order
  → DynamoDB update_item (jetzt bedingt)
```

### 1.1 Neuer Schreibschutz

```python
ConditionExpression = "attribute_exists(pk) AND #status = :currentStatus"
UpdateExpression    = "SET #status = :newStatus, updatedAt = :now,
                          #version = if_not_exists(#version, :zero) + :one"
```

- **Erwarteter Ausgangsstatus** wird geprüft (gelesener Status).
- **Version** wird atomar erhöht; Legacy-Items ohne `version` starten über
  `if_not_exists(..., 0)` bei 0 und erhalten dann 1 (keine Migration nötig).
- `updatedAt` bleibt wie bisher; `subjectId`, `consumerId`, `ownerId`, `actorId`,
  `identityVersion`, `identityVerification` werden **nie** berührt (Test).
- Der API-Pfad (`PATCH`) war bereits bedingt (Status + `version`) und bleibt unverändert;
  beide Pfade schreiben jetzt mit Status-Condition — der schnellere Pfad gewinnt,
  der andere erhält `ConditionalCheckFailed` und wird klassifiziert.

### 1.2 Klassifikation nach Konflikt (kein pauschales Verschlucken)

| Fall | Ergebnis | SQS-Verhalten |
|---|---|---|
| Status bereits = Ziel | `noop` (idempotent) | Nachricht gelöscht |
| Bestellung weiter fortgeschritten (z. B. `PROCESSING` bei Ziel `CONFIRMED`) | `stale` | Nachricht gelöscht (kein Downgrade) |
| Zwischenzeitlich storniert (`CANCELLED`) | `rejected` | Nachricht = Fehlschlag → DLQ |
| Bestellung existiert nicht (mehr) | `missing` | Fehlschlag → DLQ |
| Status unverändert (echter Wettlauf) / technischer Fehler | Exception | Fehlschlag → Retry (maxReceiveCount) |
| Zwei Worker gleichzeitig | einer `processed`, anderer `noop`/`rejected` | siehe oben |

**`CANCELLED → CONFIRMED`:** durch Condition ausgeschlossen (Write schlägt fehl) und
anschließend als `rejected` gemeldet — der Storno wird nie überschrieben.

## 2. SQS-Konfiguration (Terraform)

### 2.1 Befund vorher (verifiziert)

| Einstellung | Vorher |
|---|---|
| Queue-Typ | **Standard** (keine FIFO-Konfiguration) |
| Visibility Timeout | 30 s |
| Message Retention | **120 s** (2 Minuten) |
| DLQ | **keine** |
| Redrive Policy | **keine** |
| Worker Batch Size | 5 |
| Max Receive Count | nicht konfiguriert |
| Worker-Lambda-Timeout | 10 s (`modules/sqs-worker` default) |

**Bewertung:** 120 s Retention + keine DLQ = fehlgeschlagene Aufträge verschwanden
binnen zwei Minuten spurlos. 30 s Visibility bei 10 s Timeout = nur 3× statt der von AWS
empfohlenen ≥ 6× → Doppelzustellung während der Verarbeitung möglich.

### 2.2 Neue Konfiguration (Default-Werte, ausdrücklich dokumentiert)

| Variable | Default | Begründung |
|---|---|---|
| `sqs_visibility_timeout_seconds` | **60** | 6 × Lambda-Timeout (10 s), AWS-Empfehlung |
| `sqs_message_retention_seconds` | **345600** (4 Tage) | Aufträge bleiben untersuchbar |
| `sqs_dlq_message_retention_seconds` | **1209600** (14 Tage, AWS-Max) | DLQ-Analyse und kontrollierte Wiederverarbeitung |
| `sqs_max_receive_count` | **1** | erster Fehlversuch → beim nächsten Empfang in die DLQ |
| `dlq_name` (modulintern) | `null` → `<queue>-dlq` | eindeutige Benennung |

- DLQ: `aws_sqs_queue.dlq` mit eigenem Retention-Wert.
- Redrive: `redrive_policy` mit `deadLetterTargetArn` + `maxReceiveCount`.
- Ausgaben: `dlq_url`, `dlq_arn`, `dlq_name` (zusätzlich zu bestehenden Queue-Outputs).
- Root-Variablen `sqs_*` verdrahtet; Builder-Katalog ordnet sie dem Modul `sqs` zu.

**AWS-Semantik von `maxReceiveCount = 1` (keine Exactly-once-Behauptung):**
SQS zählt Empfänge. Eine Nachricht, die beim ersten Empfang nicht gelöscht wird, wird beim
**nächsten** Empfangsversuch in die DLQ verschoben. Es gibt also genau **einen**
Verarbeitungsversuch; bei Batch-Fehlerantwort wird die Nachricht erneut zugestellt (und
landet dann in der DLQ). SQS bleibt **at-least-once** — Duplikate sind möglich und werden
durch die Idempotenz-Logik abgefangen.

### 2.3 Batch-Fehlerbehandlung

- `function_response_types = ["ReportBatchItemFailures"]` am Event-Source-Mapping.
- Handler liefert `{"batchItemFailures":[{"itemIdentifier":"<messageId>"}]}`.
- Erfolgreiche/`noop`/`stale` Nachrichten werden gelöscht, fehlgeschlagene gezielt
  wiederholt — kein unnötiger Re-Processing des ganzen Batches.
- Fehlt eine `messageId` bei einem Fehler, wird der Batch bewusst wiederholt
  (kein stiller Verlust).

### 2.4 Fehlerfall-Matrix

| Fall | Behandlung |
|---|---|
| Technischer Fehler (DynamoDB, Netz) | Item-Failure → Retry → DLQ nach `maxReceiveCount` |
| Ungültiges JSON / fehlende Felder | Item-Failure → DLQ (sichtbar, untersuchbar) |
| Bestellung fehlt | Item-Failure → DLQ |
| Unerlaubter Übergang (z. B. `CANCELLED→CONFIRMED`) | Item-Failure → DLQ |
| Konflikt, Ziel bereits erreicht | idempotenter Erfolg (kein DLQ-Eintrag) |
| Überholte Nachricht (`stale`) | Erfolg (kein Downgrade, kein DLQ) |
| Leerer Batch | Erfolg, keine Failures |

## 3. Ownership- und Listenlogik (Befund, **nicht** geändert)

| Pfad | Prüfung | Befund |
|---|---|---|
| `POST /orders` | Identität erzwungen (P02/P02A) | ✅ Owner = JWT-`sub` |
| `GET /orders` | keine Filterung | **listet ALLE Bestellungen** (GSI1 `LIST`), jeder authentifizierte Nutzer |
| `GET /orders/{orderId}` | kein Owner-Check | **jede Bestellung lesbar** |
| `PATCH /orders/{orderId}/status` | kein Owner-Check | **jede Bestellung änderbar** (nur State Machine + Version) |
| `privacy/inspect|export|erase` | interne Auth + Secret, GSI2 + optionaler Consumer-Scope | unverändert korrekt |

**Konkreter Pfad:** `index.handler` → `OrderService.get_order()` /
`update_order_status()` / `list_orders()` — keine `subjectId`-Auswertung. Das ist kein
Regressionsfehler dieses Auftrags, sondern der dokumentierte Bestand (Spike §E).

**Minimaler Fix (Vorschlag, nicht implementiert):**
1. `staff`-Gruppe aus `cognito:groups` auswerten (existiert, ungenutzt) → Staff darf alles.
2. Nicht-Staff: `GET /{id}` vergleicht `subjectId` mit `sub` (403 sonst).
3. `GET /orders` für Nicht-Staff über GSI2 (`SUBJECT#<sub>`) statt GSI1.
→ **Breaking Change** für bestehende Clients → braucht eigene Freigabe (V-10).

## 4. Worker-Routing (Befund)

| Aspekt | Befund | Status |
|---|---|---|
| Order-Typ / Verarbeitungsziel | **kein Feld** im Item oder in der Nachricht | OPEN |
| Routing-Informationen | nur `orderId`, `status`, `metadata.reason` | IMPLEMENTED (minimal) |
| SQS-Nachrichtenformat | `{"orderId","status","metadata":{"reason":"order_created"}}` | IMPLEMENTED |
| Agenten-/Routinenauswahl | **keine** — ein Worker, eine Aktion | OPEN |
| Verarbeitung durch MO-Worker | Statuswechsel `PENDING→CONFIRMED` | IMPLEMENTED |
| Rückmeldung externer Agenten | **nicht vorhanden** (kein Callback/Kanal) | OPEN |
| Vorgesehene Statusübergänge | State Machine (`PENDING…DELIVERED`, `CANCELLED`) | IMPLEMENTED |

Keine Agenten-Orchestrierung implementiert (nicht Teil des Auftrags).

## 5. Tests

Neu: `lambda/tests/test_sqs_handler.py` (18 Tests): Erfolg mit Condition/Version,
zwei konkurrierende Worker, Storno zwischen Lesen/Schreiben, Duplikat, veralteter Status,
`CANCELLED`, fehlende Order, Legacy ohne `version`, technischer Fehler, Owner-Attribute
unberührt, Batch-Failures (einzeln), ungültiges JSON, unvollständige Nachricht,
technische Exception, leerer Batch, fehlende `messageId`.

| Suite | Ergebnis |
|---|---|
| Lambda | **157/157 PASS** (vorher 139) |
| Module Builder | **90/90 PASS** |
| Installer | **81/81 PASS** |
| `terraform validate` (Root) | PASS |
| `terraform fmt -check -recursive` | PASS |
| Generiertes Projekt (`complete`, `/tmp`) | init 0, validate PASS, fmt PASS, DLQ im Modul |

## 6. Abschlusstabelle

| Prüfung | Ergebnis |
|---|---|
| Ausgangs-HEAD | `2194781` (erwartet) |
| Worker-ConditionExpression | `attribute_exists(pk) AND #status = :currentStatus` |
| Versionsschutz | `version = if_not_exists(version, 0) + 1` (Legacy-kompatibel) |
| CANCELLED-Race | verhindert (Condition) + als `rejected` klassifiziert |
| Idempotenz | `noop` (Ziel erreicht), `stale` (überholt) — kein DLQ-Eintrag |
| SQS Queue-Typ | Standard |
| Visibility Timeout | 60 (vorher 30), konfigurierbar |
| Hauptqueue-Retention | 345600 s = 4 Tage (vorher 120 s) |
| DLQ-Retention | 1209600 s = 14 Tage |
| maxReceiveCount | 1 |
| Redrive Policy | vorhanden |
| Batch-Fehlerbehandlung | `ReportBatchItemFailures` + partielle Batch-Antwort |
| Ownership / Bestelllisten | Lesen/Ändern ohne Owner-Check — dokumentiert, Fix vorgeschlagen (V-10) |
| Worker-Routing | nur Statuswechsel; keine Agenten-/Zielzuordnung (OPEN) |
| Lambda-Tests | 157/157 |
| Builder-Tests | 90/90 |
| Installer-Tests | 81/81 |
| Terraform-Validierung | PASS (+ generiertes Projekt PASS) |
| Commit | siehe Abschlussbericht |
| Working Tree | clean nach Commit |
| Offene Fragen | V-10 (Ownership beim Lesen), V-11 (DLQ-Alarm), V-12 (FIFO?) |
