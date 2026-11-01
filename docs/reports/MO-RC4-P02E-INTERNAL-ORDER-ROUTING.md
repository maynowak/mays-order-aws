# MO-RC4-P02E-INTERNAL-ORDER-ROUTING

**Minimales internes Order-Routing im bestehenden Worker**

**Datum:** 2026-11-01
**Branch:** `feature/mo-rc4-kms-privacy-retention`
**Basis:** `1bd7e8eaa78cc9ad84ab9b6724112a9ab6c03fe9`
**Typ:** Implementierung + Tests (lokal), keine AWS-Operation, kein Push

---

## 1. Umfang (bewusst klein)

Umgesetzt wurden **zwei** Bausteine (Vorschlag D aus P02D):

1. **`orderType`** am Order-Item (optional, Default `generic`, namespace-fähig).
2. **Interne Handler-Registry** im bestehenden Worker.

Nicht umgesetzt (wie gefordert): neue Tabellen/GSIs/Queues, neue Statuswerte,
Callback-API, Agenten-Orchestrierung, M2M, Delegation, PENDING-Recovery, KMS/Secrets.

---

## 2. `orderType`-Vertrag

### 2.1 Feld

| Aspekt | Wert |
|---|---|
| Name | `orderType` |
| Typ | String |
| Pflicht | **nein** (Default `generic`) |
| Ort | Order-Item (DynamoDB) + `POST /orders`-Body (optional) |
| API-Antwort | wird mitgeliefert (additiv) |
| Bedeutung | gewünschte **fachliche Verarbeitung** — nicht Owner/Consumer |

### 2.2 Namenskonvention

```text
generic
ris.document.analyze
jobsearch.match
internal.report.generate
```

Regex: `^[a-z][a-z0-9-]{0,31}(\.[a-z][a-z0-9-]{0,31})*$`, Gesamtlänge ≤ 128
(`validation.py::validate_order_type`).

- Nur Kleinbuchstaben, Ziffern, Bindestrich; Punkt als Segmenttrenner.
- Jedes Segment beginnt mit einem Buchstaben; keine Leerzeichen, Unterstriche, Schrägstriche.
- **Keine** freien Python-Modulnamen/Pfade: es gibt keine dynamischen Imports — die
  Registry ist explizit und entscheidet allein über gültige Ziele.

### 2.3 Validierung

| Fall | Ergebnis |
|---|---|
| Feld fehlt | `generic` |
| `"generic"` | akzeptiert |
| `"ris.document.analyze"` | akzeptiert |
| leer/Whitespace | 400 `VALIDATION_ERROR` |
| Großbuchstaben, `_`, `/`, Leerzeichen, führende Ziffer | 400 |
| > 128 Zeichen, Nicht-String | 400 |
| Body-Felder `subjectId`/`ownerId` | weiterhin 400 (Identität nie aus dem Body) |

---

## 3. Handler-Registry

Datei: `lambda/src/order_handlers.py`

```python
@register("generic")
def _generic_handler(order, payload): ...   # keine Zusatzlogik

get_handler("generic")          # Handler oder None
is_registered("generic")        # bool
registered_types()              # sortierte Liste (Diagnose/Tests)
```

- **Explizite Registrierung**, Duplikate → `ValueError`, ungültige Namen →
  `VALIDATION_ERROR` (nutzt dieselbe Validierung wie die API).
- Keine dynamischen Imports, keine externe Registry, keine AWS-Ressource.
- Handler-Signatur: `(order_item, payload) -> None`; Fehler werden geworfen.
- **Handler schreiben keinen Status** — das macht ausschließlich der Worker.

**Generic Handler:** bewahrt das bisherige Verhalten (keine erfundene Fachlogik).

---

## 4. Worker-Integration

`lambda/src/sqs_handler.py::_process_order()`

```text
SQS-Nachricht → orderId/status
  → Item aus DynamoDB laden (ConsistentRead)
  → Idempotenz/Stale/State-Machine prüfen   (unverändert, P02C)
  → orderType aus dem ITEM lesen            (nie aus der Nachricht)
  → Registry: Handler suchen
      ├─ nicht registriert → OUTCOME_UNKNOWN_TYPE (kein Schreibvorgang, Item-Failure → DLQ)
      └─ gefunden → handler(item, payload)
             ├─ Exception → OUTCOME_HANDLER_FAILED (kein Statuswechsel → DLQ)
             └─ OK → bedingtes Update (P02C: status-Condition + version+1)
```

- **Nachrichtenformat unverändert** (`{orderId, status, metadata}`).
- **Typ-Quelle:** gespeichertes Item. Ein `orderType` in der SQS-Payload wird ignoriert
  (Test: `test_type_from_message_payload_is_ignored`).
- **Legacy:** fehlt `orderType`, gilt `generic` (kein Fehler).
- **Unbekannt ≠ generic:** ein vorhandener, nicht registrierter Typ wird abgelehnt —
  **kein** stiller Fallback (Test).
- **Idempotenz:** Ist der Zielstatus bereits erreicht, läuft **kein** Handler
  (Test `test_duplicate_message_does_not_run_handler`).

---

## 5. Fehlerbehandlung (Zusammenwirken mit P02C)

| Situation | Ergebnis | SQS |
|---|---|---|
| Legacy ohne Typ | `generic` → `processed` | gelöscht |
| `generic` | `processed` | gelöscht |
| registrierter Typ | Handler → `processed` | gelöscht |
| unbekannter Typ | `unknown_type` | Item-Failure → Retry → DLQ |
| ungültiger gespeicherter Typ (z. B. `Bad/Type`) | `unknown_type` | Item-Failure → DLQ |
| Handler wirft | `handler_failed` | Item-Failure → Retry → DLQ |
| Order fehlt | `missing` | Item-Failure → DLQ |
| Ziel bereits erreicht | `noop` | gelöscht (idempotent) |
| überholte Nachricht | `stale` | gelöscht (kein Downgrade) |
| storniert | `rejected` | Item-Failure → DLQ |
| technischer Fehler (DynamoDB) | Exception | Item-Failure → Retry |

Die DLQ-Konfiguration (`maxReceiveCount=1`, Retention 14 Tage) und
`ReportBatchItemFailures` aus P02C bleiben unverändert wirksam.

---

## 6. Statussemantik

- State Machine **unverändert** (`PENDING→CONFIRMED→PROCESSING→SHIPPED→DELIVERED`, `CANCELLED`).
- **`CONFIRMED` bedeutet weiterhin „angenommen", nicht „fachlich abgeschlossen".**
- Kein `COMPLETED`, keine neuen Statuswerte, keine Ergebnis-/Callback-API.
- Storno-Semantik unverändert (kein Überschreiben, P02C).

**Offene Frage für P02G:** Reicht `CONFIRMED` als Abschluss-Signal für echte
Verarbeitungstypen, oder braucht es ein separates Ergebnis-/Abschlussfeld
(und ggf. eine eigene Status- oder Result-Semantik)?

---

## 7. Security / Ownership

- Identity-Felder (`subjectId`, `consumerId`, `ownerType`, `ownerId`, `actorType`,
  `actorId`) werden **nicht** verändert (Test in P02C weiterhin grün; OrderType-Test
  prüft `subjectId`/`gsi2pk`).
- Handler erhalten das Item **lesend**; sie können keine Identität setzen.
- Der Worker nutzt weiterhin IAM (systemweit) und wird nie Owner.
- Keine Delegation, keine Cognito-/RIS-Änderung.
- **V-10 bleibt offen:** `GET /orders` (alle), `GET /{id}` und `PATCH` ohne Owner-Check —
  unverändert, nur dokumentiert.

---

## 8. Tests

Neu: **23 Tests**

| Bereich | Anzahl |
|---|---|
| Registry (`test_order_handlers.py`) | 5 |
| Validierung (`test_validation.py::TestOrderTypeValidationP02E`) | 5 |
| Service (`test_order_service.py::TestOrderTypeP02E`) | 4 |
| Worker-Routing (`test_sqs_handler.py::TestWorkerOrderRoutingP02E`) | 9 |

Abgedeckt: Default/explizit/namespaced/ungültig, Legacy ohne Typ, registrierter
Zusatzhandler, unbekannter Typ, ungültiger gespeicherter Typ, Handler-Exception,
Typ aus Nachricht ignoriert, Duplikat ohne Handler-Aufruf, Batch-Item-Failure,
Ownership unverändert.

| Suite | Ergebnis |
|---|---|
| Lambda | **180/180 PASS** (vorher 157) |
| Module Builder | **90/90 PASS** |
| Installer | **81/81 PASS** |
| Terraform | `validate` PASS, `fmt -check` PASS (keine Schemaänderung nötig) |

---

## 9. Abschlusstabelle

| Prüfung | Ergebnis |
|---|---|
| Ausgangs-HEAD | `1bd7e8e` |
| Branch | `feature/mo-rc4-kms-privacy-retention` |
| orderType implementiert | ja (Item + optionaler API-Body) |
| Default `generic` | ja |
| Legacy-Kompatibilität | ja (fehlendes Feld → generic) |
| Namespaced Typen | ja (`ris.document.analyze` etc.) |
| Handler-Registry | ja, explizit, erweiterbar, ohne dynamische Imports |
| Generic Handler | ja, bewahrt bisheriges Verhalten |
| Worker-Integration | ja (Item-basiert, Nachrichtenformat unverändert) |
| Unbekannte Typen | kontrolliert abgelehnt (kein Fallback) |
| Handler-Fehler | kein Statusabschluss → DLQ |
| P02C-Kollisionsschutz | unverändert wirksam |
| DLQ-/Batch-Verhalten | unverändert wirksam |
| Ownership unverändert | ja (Test) |
| Lambda-Tests | 180/180 |
| Builder-Tests | 90/90 |
| Installer-Tests | 81/81 |
| Terraform-Validierung | PASS |
| Commit | siehe Abschlussbericht |
| Working Tree | clean nach Commit |
| Offene Fragen | P02G: Abschluss-/Ergebnissemantik; PENDING-Recovery; V-10; externe Agenten (V-1/V-9); P02D-Feld `result`/`completedAt` |
