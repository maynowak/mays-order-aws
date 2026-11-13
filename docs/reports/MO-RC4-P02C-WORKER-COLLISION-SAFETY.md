# MO-RC4-P02C-WORKER-COLLISION-SAFETY

**Kollisionsschutz der Worker-Abschlussroutine + Access-Review**

**Datum:** 2026-11-01
**Basis:** `2194781`
**Vollständige Details:** `docs/reports/MO-RC4-P02C-WORKER-SQS-SAFETY.md`
(dieser Bericht ist die Kollisions-/Access-Sicht desselben Checkpoints)

---

## 1. Kollisionsschutz

| Prüfung | Ergebnis |
|---|---|
| Worker-Abschlussroutine | `lambda/src/sqs_handler.py::_process_order()` (einzige Routine, keine neue) |
| Conditional Write | `attribute_exists(pk) AND #status = :currentStatus` |
| Versionsschutz | `version = if_not_exists(#version, :zero) + :one` (atomar, Legacy-kompatibel) |
| CANCELLED-Race | verhindert; Konflikt wird als `rejected` klassifiziert (kein Overwrite) |
| Doppelte Nachrichten | idempotent: Zielzustand erreicht → `noop`, kein Write |
| Veraltete Nachricht | `stale` → kein Downgrade, kein DLQ-Eintrag |
| Zwei Worker gleichzeitig | genau ein Write; Verlierer erhält `ConditionalCheckFailed` und wird neu bewertet |
| Status-API-Konsistenz | `PATCH` prüft weiterhin Status **und** Version; beide Pfade nutzen jetzt Status-Conditions |

## 2. Ownership-Review (Befund, keine Änderung)

| Pfad | Owner-Prüfung | Befund |
|---|---|---|
| `GET /orders` | ❌ | listet alle Bestellungen (GSI1 `LIST`) |
| `GET /orders/{orderId}` | ❌ | jede Bestellung lesbar |
| `PATCH /orders/{orderId}/status` | ❌ | jede Bestellung änderbar (State Machine + Version bleiben) |
| `privacy/inspect|export|erase` | ✅ (intern, Secret + optionaler Consumer-Scope) | unverändert |

**Minimaler Fix (Vorschlag, nicht implementiert):** `cognito:groups` (`staff`) auswerten;
Nicht-Staff nur eigene Bestellungen (`subjectId == sub`, Liste über GSI2). Breaking Change
→ eigene Freigabe (V-10).

## 3. Worker-Routing (Befund)

| Aspekt | Befund | Status |
|---|---|---|
| Order-Typ / Ziel | kein Feld | OPEN |
| Routing-Informationen | `orderId`, `status`, `metadata.reason` | IMPLEMENTED (minimal) |
| Agentenauswahl | keine | OPEN |
| Verarbeitung durch MO | Statuswechsel `PENDING→CONFIRMED` | IMPLEMENTED |
| Rückmeldung externer Agenten | kein Kanal | OPEN |

## 4. Tests

`lambda/tests/test_sqs_handler.py` — 18 Tests (Erfolg, zwei Worker, Duplikat, Storno,
veralteter Status, Legacy ohne Version, technischer Fehler, Owner-Attribute, Batch-Fehler).

| Suite | Ergebnis |
|---|---|
| Lambda | 157/157 PASS |
| Module Builder | 90/90 PASS |
| Installer | 81/81 PASS |
| Terraform | validate PASS, fmt PASS |

## 5. Abschlusstabelle

| Prüfung | Ergebnis |
|---|---|
| Ausgangs-HEAD | `2194781` |
| Worker-Abschlussroutine | `sqs_handler._process_order` (unverändert lokalisiert) |
| Conditional Write | ja |
| Versionsschutz | ja (Legacy-kompatibel) |
| CANCELLED-Race | geschlossen |
| Doppelte Nachrichten | idempotent |
| Legacy-Kompatibilität | ja (ohne `version`) |
| Status-API-Konsistenz | ja |
| GET /orders Ownership | **fehlt** (dokumentiert, V-10) |
| GET /orders/{id} Ownership | **fehlt** (dokumentiert, V-10) |
| PATCH Ownership | **fehlt** (dokumentiert, V-10) |
| Vorhandenes Worker-Routing | nur Statuswechsel (kein Ziel-/Agentenrouting) |
| Offene Routing-Fragen | Order-Typ, Agentenzuordnung, Rückmeldung (OPEN) |
| Tests | 157 / 90 / 81 PASS · terraform validate+fmt PASS |
| Commit | siehe Abschlussbericht |
| Working Tree | clean nach Commit |
