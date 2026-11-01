# Runbook — Processing Recovery (May's Orders)

**Gültig ab:** RC4 (P02G-B / P02I-A)
**Zielgruppe:** Betrieb / On-Call mit AWS-Leserechten
**Status:** Diagnose dokumentiert · **automatische Wiederaufnahme: BLOCKED**
**Letzte Prüfung:** 2026-11-01 (Code `d2510f6`)

> **Grundregel:** Dieses Runbook beschreibt zuerst die **Diagnose**. Jede schreibende
> Aktion ist als „autorisiert erforderlich" markiert und setzt eine menschliche Freigabe
> sowie passende IAM-Rechte voraus. Es gibt **keinen** Operator-Vertrag im Produkt —
> nichts hier ist ein garantiertes Verfahren.

---

## 1. Begriffe strikt trennen

| Ebene | Feld | Bedeutung |
|---|---|---|
| Order-Status | `status` | fachlicher Lebenszyklus (`PENDING…DELIVERED`, `CANCELLED`) |
| Zustellung | `deliveryState` | `pending` → `sending` → `sent` \| `failed` (P02F) |
| Verarbeitung | `processingState` | `pending` \| `running` \| `succeeded` \| `failed` (P02G-B) |
| SQS | Nachricht | sichtbar / in-flight / gelöscht / **DLQ** |

`CONFIRMED` heißt **„angenommen"**, nicht „verarbeitet". `deliveryState=sent` heißt **nur**,
dass SQS die Nachricht angenommen hat.

---

## 2. Bekannte Zeitwerte

| Mechanismus | Wert |
|---|---|
| SQS Visibility Timeout | 60 s |
| Processing-Lease (`processingClaimedAt`) | 300 s |
| Worker-Lambda-Timeout | 10 s |
| SQS `maxReceiveCount` | 1 (→ erster Fehlversuch landet beim nächsten Empfang in der DLQ) |
| Hauptqueue-Retention | 4 Tage |
| DLQ-Retention | 14 Tage |
| P02F-Scheduler | 5 min, **standardmäßig deaktiviert** (`recovery_enabled=false`) |

---

## 3. Diagnose (nur lesend)

Alle Schritte sind read-only. `PROJECT` und `ORDER_ID` ersetzen.

```bash
# 1) Order-Zustand (alle relevanten Felder)
aws dynamodb get-item --region eu-central-1 \
  --table-name "$PROJECT" \
  --key '{"pk":{"S":"ord_'"$ORDER_ID"'"},"sk":{"S":"#ORDER"}}'
# Felder prüfen: status, deliveryState, processingState, processingAttemptId,
#                processingClaimedAt, processingAttempts, completedAt, processingError

# 2) Queue-Tiefe / DLQ
aws sqs get-queue-attributes --region eu-central-1 \
  --queue-url "$QUEUE_URL" \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible

# 3) DLQ-Inhalt (nur metadaten, keine Bodies kopieren)
aws sqs get-queue-attributes --region eu-central-1 \
  --queue-url "$DLQ_URL" --attribute-names ApproximateNumberOfMessages

# 4) Worker-Logs der letzten 24 h (Beispiel; Log-Gruppe)
aws logs filter-log-events --region eu-central-1 \
  --log-group-name "/aws/lambda/$PROJECT-sqs-worker" \
  --filter-pattern "processing event=" --start-time $(( ($(date +%s) - 86400) * 1000 ))
```

**Ereignisnamen in den Logs (strukturiert, ohne Payload/PII):**
`PROCESSING_CLAIMED`, `PROCESSING_LEASE_EXPIRED`, `PROCESSING_ALREADY_RUNNING`,
`PROCESSING_TERMINAL_FAILED`, `PROCESSING_ATTEMPT_EXHAUSTED`, `PROCESSING_SUCCEEDED`,
`PROCESSING_FAILED`, `PROCESSING_REJECTED`, `PROCESSING_RECOVERY_REQUIRED`,
`PROCESSING_RETRY_RELEASED`, `PROCESSING_TECHNICAL_ERROR`.

**Wichtig:** Es gibt **keinen Index** auf `processingState`. Eine Order kann nur über ihre
`orderId` gefunden werden; „alle hängenden Orders" sind **nicht** effizient abfragbar.

---

## 4. Fallmatrix

| # | Zustand | Bedeutung | Zulässige Aktion |
|---|---|---|---|
| 1 | `processingState=running`, `processingClaimedAt` < jetzt−300 s | abgelaufene Lease, Versuch abgestürzt | **erneute Zustellung** (siehe §5), sonst nichts |
| 2 | `processingState=running`, Lease gültig | aktiver Versuch | **nichts tun** (kein Eingriff) |
| 3 | `processingAttempts >= 2` | Budget erschöpft | **keine automatische Wiederaufnahme**; fachliche Klärung |
| 4 | Nachricht in DLQ | Verarbeitung nicht abgeschlossen | DLQ inspizieren; **kein blindes Redrive** |
| 5 | `processingState=failed` | kontrollierter fachlicher Fehler | `processingError` lesen; fachliche Entscheidung; **kein Retry** |
| 6 | Order anonymisiert (`subjectId` fehlt) | Datenschutz-Löschung | **keine Wiederaufnahme** |
| 7 | Order gelöscht (kein Item) | Erase | **keine Wiederaufnahme** |
| 8 | `status=CANCELLED` | Storno | **keine Wiederaufnahme** |
| 9 | `processingState=succeeded` | abgeschlossen (idempotent) | **nichts tun** |
| 10 | Verdacht auf doppelte Seiteneffekte | Seiteneffekt ohne Ergebnis/umgekehrt | fachliche Prüfung **beim Zielsystem**; MO liefert keine Exactly-once-Garantie |

---

## 5. Erneute Zustellung (autorisierte Aktion)

**Voraussetzungen (alle):**
1. `status` ∈ {`PENDING`, `CONFIRMED`, `PROCESSING`} (nicht `CANCELLED`)
2. `subjectId` vorhanden (nicht anonymisiert)
3. `processingState` = `running` **mit abgelaufener Lease** oder `pending`
4. `processingAttempts` < 2
5. Menschliche Freigabe dokumentiert (Ticket/Incident-ID)
6. IAM-Recht `sqs:SendMessage` auf die Order-Queue (vom Stack **nicht** vergeben)

**Verfahren:** Nachricht mit dem bestehenden Format erneut senden:

```json
{"orderId":"ord_...","status":"CONFIRMED","metadata":{"reason":"manual_recovery"}}
```

Der Worker übernimmt den Claim nur, wenn die Bedingungen passen — sonst bleibt die Order
unverändert (`PROCESSING_ALREADY_RUNNING` / `PROCESSING_ATTEMPT_EXHAUSTED`).

**Nicht zulässig:**
- `processingAttempts` zurücksetzen oder `processingState` direkt überschreiben
- `processingAttemptId` manuell setzen
- DLQ-Nachrichten ungeprüft zurückzuspielen
- Anonymisierte/gelöschte/stornierte Orders wiederbeleben

---

## 6. DLQ-Behandlung

1. DLQ-Tiefe und Nachrichten-Metadaten prüfen (keine Bodies in Tickets kopieren).
2. Ursache über Worker-Logs (`PROCESSING_REJECTED` / `PROCESSING_TECHNICAL_ERROR`) und
   Order-Felder bestimmen.
3. Nur wenn §5 erfüllt ist: erneute Zustellung.
4. Nach Bearbeitung: Nachricht bewusst löschen oder für Audit aufbewahren
   (DLQ-Retention 14 Tage).

---

## 7. Doppelte fachliche Seiteneffekte (Verdacht)

MO garantiert nur idempotente **Status-/Ergebnisübernahme**, **nicht** idempotente externe
Seiteneffekte. Bei Verdacht:

1. `processingAttemptId` und `completedAt` der Order mit den Logs abgleichen.
2. Im Zielsystem prüfen, ob die Aktion für `orderId` mehrfach angewendet wurde.
3. Handler sollen `orderId` als **stabilen** Idempotency Key verwenden (Attempt-ID ist
   pro Versuch neu und nur für MO-internes Fencing geeignet).

---

## 8. Bekannte Grenzen (BLOCKED/OPEN)

| Grenze | Status |
|---|---|
| Automatische Erkennung hängender `running`-Orders | **OPEN** (kein Index, kein Trigger) |
| Automatischer Processing-Retry über SQS | **BLOCKED** (`maxReceiveCount=1`, Nachricht in DLQ) |
| Operator-Vertrag (Rechte, Freigabe, Audit) | **BLOCKED** (nicht implementiert) |
| DLQ-Alarm | **OPEN** (kein Alarm vorhanden) |
| P02F hilft bei Processing-Hängern | **NEIN** (nur nicht zugestellte `PENDING`-Orders) |

Weiteres Vorgehen erfordert einen eigenen Checkpoint (Processing-Recovery-Auslöser,
Suchindex, DLQ-Monitoring, Operator-Rechte).
