# MO-RIS-AGENT-DISPATCH-01 — A05 Dispatch & Work-Id Binding

**Datum:** 2026-11-13
**Typ:** Lokale Implementierung + Cross-Repo-Test (kein Apply, kein Deployment)
**Ergebnis:** LOCAL COMPLETE. Eine gespeicherte Agent-Order wird mit genau einer
serverseitig gebundenen WorkId über den eingefrorenen Transport V1 an RIS
übergeben; der vorhandene A06-Boundary akzeptiert das Ergebnis `42`.

## 1. D00 — Befund

| Frage | Ergebnis |
|---|---|
| Wie prüft A06 `expectedWorkId`? | Wenn gesetzt, muss `execution.workId` gleich sein (`work_mismatch`) |
| Execution/Attempt | `executionId` wird gespeichert und bei Duplikaten verglichen; `attempt` steuert Stale-Erkennung |
| Korrelation | `agentOrder.metadata.requestId` == `correlationId` |
| Erzwingt A06 die Bindung vollständig? | Ja, sobald `expectedWorkId` existiert — vorher nur Korrelation |
| Vorhandene Producer/Consumer | nur Retail-Worker + Retail-Queue; **kein** Dispatch-Producer, **keine** Result-Queue |

## 2. Vertragskonflikt und Auflösung (A05-1)

Der eingefrorene V1-Envelope hat kein dediziertes `workId`-Feld für den
Dispatch. Geprüft am echten Parser:

- `validate_envelope` **akzeptiert** `execution.workId` bei `ORDER_DISPATCH`
  (Feld ist in `TOP_LEVEL_KEYS`, `execution` war bisher nur für Result-Typen
  validiert).
- `dispatch_to_work_item` **ignorierte** den Wert und erzeugte eine neue WorkId.

Damit war es **keine Schemaänderung, sondern eine Mapping-Lücke**. Behoben durch
eine additive, rückwärtskompatible Regel in RIS:

> Ist `execution.workId` beim Dispatch vorhanden, verwendet der Empfänger sie.
> Fehlt sie, bleibt das bisherige Verhalten (Empfänger generiert).

Kein neues Feld, keine Versionserhöhung, keine zweite Transportstruktur.
Bestehende 96 RIS-Tests bleiben grün.

## 3. D01 — WorkId-Bindung

`OrderService.prepare_dispatch(order_id, identity)`:

1. Order laden (roh), Eigentümer prüfen — fremd/unbekannt → `404`.
2. Nur `agent.execution`, nicht `CANCELLED`.
3. `agentOrderFingerprint` gegen den gespeicherten Body prüfen:
   fehlt → `fingerprint_missing`, abweichend → `fingerprint_mismatch`.
4. Ist `expectedWorkId` schon gesetzt → dieselbe ID zurückgeben (`reused=True`).
5. Sonst WorkId serverseitig erzeugen und **atomar** binden:
   `attribute_exists(pk) AND attribute_not_exists(expectedWorkId)`.
   Verliert der Schreiber, wird die bereits gebundene ID gelesen.
6. `dispatch = {status: "PENDING", boundAt}`.

`metadata.requestId` bleibt Korrelation, **nicht** Autorisierung.

## 4. D02 — Envelope

`build_dispatch_envelope(order, work_id)` baut aus der **gespeicherten** Order:

| Feld | Quelle |
|---|---|
| `orderId` | Order |
| `messageId` | `msg_<workId>_dispatch` |
| `correlationId` | `agentOrder.metadata.requestId` (Pflicht) |
| `idempotencyKey` | `metadata.idempotencyKey` oder `<orderId>:dispatch` |
| `recipient.agentId` / `capability` | `agentOrder.target` |
| `payload` | `agentOrder.input.data` |
| `identity.contextRef` | `metadata.apiProfileRef` (Pflicht; RIS muss auflösen, nicht vertrauen) |
| `execution.workId` | die gebundene WorkId |

Fehlende Korrelation, fehlende Identitätsreferenz oder > 16 KiB → kontrollierte
Ablehnung. Keine Secrets im Envelope (Test).

## 5. D04 — Zustellzustand

| Zustand | Bedeutung | Wiederholung |
|---|---|---|
| `PENDING` | WorkId gebunden, Versand nicht bestätigt | erneuter Versand mit **derselben** ID |
| `SENT` | Versand bestätigt | kein automatischer Resend; gleiche `messageId` ist idempotent, andere → `dispatch_conflict` |

Ein Absturz zwischen Bindung und Versand hinterlässt `PENDING` — der Auftrag ist
weder verloren noch doppelt ausgeführt. **Es wird keine Exactly-once-Zustellung
behauptet.**

## 6. D03/D05 — Cross-Repo-Nachweis

`tests/test_mo_dispatch_handoff.py` (im RIS-Repo, Skip ohne `MO_ORDERS_SRC`):

```
Order speichern → prepare_dispatch → Envelope
  → RIS validate_envelope → dispatch_to_work_item (gleiche workId)
    → AdditionAgent → 42
      → result_from_work_item → ORDER_RESULT
        → Orders apply_result → 42 am richtigen Auftrag
```

Belegt: WorkId wird wiederverwendet, Ergebnis landet genau einmal, doppelte
Result-Nachricht ist idempotent, falsche WorkId → `work_mismatch`, stale Attempt
→ `stale_attempt`, unsignierte Nachricht wird abgewiesen, fremder Eigentümer und
stornierte Order werden nicht dispatcht.

Ergebnis: **149 Tests** im RIS-Lauf (96 ohne Cross-Repo, 10 skipped).

## 7. Tests (Orders)

`cd lambda && PYTHONPATH=src python -m unittest discover -s tests`
→ **193 Tests OK** (175 + 18 neu in `tests/test_dispatch.py`).

Abgedeckt: genau eine Bindung, Wiederverwendung, Absturz vor Versand, Versand
idempotent, abgeschlossene Order nicht neu gebunden, storniert, fremder
Eigentümer, Fingerprint-Manipulation, Retail nicht dispatchbar, Envelope-Inhalt
und -Secret-Freiheit, fehlende Identitätsreferenz/-korrelation, Sende-Konflikt,
Sendezustand nicht öffentlich.

## 8. D06 — Infrastruktur (nur Vorbereitung, nicht ausgerollt)

Für den echten Handoff nötig, **nicht** umgesetzt:

| Element | Anforderung |
|---|---|
| Dispatch-Queue | `<project>-agent-dispatch` + DLQ, **eine** Queue für alle Agenten |
| Producer | Orders-Lambda: `sqs:SendMessage` nur auf diese Queue |
| Consumer | RIS-Worker (bestehend) erhält SendMessage-Rechte? **Nein** — RIS liest, nicht Orders |
| Result-Queue | `<project>-processing-results` + DLQ (A06) |
| IAM | RIS-Producer darf nur dorthin senden; Orders-Consumer nur von dort lesen |
| Secret | `ORDER_RESULT_SERVICE_SECRET` in beiden Laufzeiten |
| Verschlüsselung | SSE-SQS, kein KMS-Custom ohne Freigabe |

Keine Queue pro Agent. Alle Punkte sind **freigabepflichtig**.

## 9. Grenzen

- Kein AWS-Aufruf, kein Apply, kein Deployment, kein Merge.
- Keine Änderung am Retail-Lifecycle, an Ownership oder an der Projektion.
- RIS Transport V1 strukturell unverändert (nur Mapping-Verhalten ergänzt).
- Der echte SQS-/IAM-Handoff ist **NOT DEPLOYED / NOT LIVE VERIFIED**.

## 10. Offen

| Punkt | Status |
|---|---|
| A07 lokales Partner-E2E | nächster Schritt |
| Infra-Freigabe (Queues/IAM/Secret) | separat |
