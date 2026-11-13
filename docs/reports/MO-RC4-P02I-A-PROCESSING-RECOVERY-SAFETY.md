# MO-RC4-P02I-A-PROCESSING-RECOVERY-SAFETY

**Processing Recovery Safety — begrenzte Härtung, Klassifikation und Runbook**

**Datum:** 2026-11-01
**Branch:** `feature/mo-rc4-kms-privacy-retention`
**Basis:** `d2510f6f80b6e44be9e46b699dc462eac94961a0`
**Typ:** Implementierung + Tests (lokal) — keine AWS-Operation, kein Push, keine neue Infrastruktur

---

## 1. Git-Baseline

| Prüfung | Ergebnis |
|---|---|
| Branch | `feature/mo-rc4-kms-privacy-retention` ✔ |
| HEAD | `d2510f6` ✔ |
| Working Tree | CLEAN ✔ |
| Ausgangstests | Lambda 281 · Builder 90 · Installer 81 = 452 |

---

## 2. Tatsächlicher Worker-Ablauf (verifiziert)

```text
handler(Records)                              sqs_handler.py:181-233
  → _process_order(orderId, status, payload)   :451
      → _read_item (ConsistentRead)            :115
      → Status-Handler?  → Statuswechsel → Handler → bedingtes Update  (:251-277)
      → Processing-Handler?
          → Statuswechsel (falls nötig)        :478
          → Re-Read (Version/State)            :484
          → _claim_processing                  :295
          → spec.handler(item, payload, ctx)   :507
          → _complete_processing               :392
  → batchItemFailures / ACK                    :225-232
```

**ACK bedeutet:** Nachricht erledigt. **Nicht:** Order fachlich abgeschlossen.

| Outcome | ACK? | Bedeutung |
|---|---|---|
| `processed`, `noop`, `stale` | ja | Status-Pfad erfolgreich/duplikat |
| `processing_succeeded` | ja | Ergebnis atomar übernommen |
| `processing_failed` | ja | kontrollierter fachlicher Fehler persistiert |
| `processing_already_running` | ja | fremder aktiver Claim |
| `processing_terminal_failed` | ja | terminal `failed`, kein Retry |
| `processing_attempt_exhausted` | ja | Budget erschöpft |
| `processing_skipped` | ja | Zustand/Konflikt unklar (Recovery-Hinweis im Log) |
| `processing_rejected` | ja | storniert/anonymisiert (kein Ergebnis) |
| `missing` | **nein** | Item weg → Retry → DLQ |
| `unknown_type`, `handler_failed` | **nein** | Retry → DLQ |

---

## 3. Identifizierte Safety-Lücken

| ID | Befund | Bewertung |
|---|---|---|
| L-1 | Sammel-Outcome `processing_skipped` für drei verschiedene Zustände (aktiv/failed/Budget) → Operatoren können Fälle nicht unterscheiden | **behoben** (Klassifikation) |
| L-2 | Kein strukturiertes Ereignis-Log; nur Freitext-Prints | **behoben** (Ereignis-Logger) |
| L-3 | Technische Handler-Exception wurde mit Exception-Text geloggt (kann Nutzdaten enthalten) | **behoben** (kein Text mehr) |
| L-4 | Abgestürzter Claim wird nicht automatisch neu angestoßen | **OPEN** (kein Trigger, bewusst nicht gebaut) |
| L-5 | `maxReceiveCount=1` macht Budget 2 automatisch unerreichbar | **OPEN** (Infra-Änderung verboten) |
| L-6 | Kein Index auf `processingState` → hängende Orders nicht auffindbar | **OPEN** (neue GSI verboten) |
| L-7 | Kein Operator-Vertrag / IAM / DLQ-Alarm | **BLOCKED** |

**Kein Fehler im Claim-/Abschlussvertrag gefunden** — die Bedingungen sind bereits
fail-closed (subjectId, Status≠CANCELLED, State=running, Attempt-ID, Version).

---

## 4. Implementierte Änderungen

| Datei | Änderung |
|---|---|
| `lambda/src/sqs_handler.py` | 3 neue, präzise Outcomes (`processing_already_running`, `processing_terminal_failed`, `processing_attempt_exhausted`); Reklassifikation; `_log_event()` (payload-frei); `_processing_attempts()`; Lease-Ablauf-Erkennung; technische Exception ohne Text; `PROCESSING_RECOVERY_REQUIRED` bei Konflikt |
| `lambda/src/order_handlers.py` | Idempotenzvertrag dokumentiert (`orderId` = stabiler Key, `attemptId` = Fencing) |
| `lambda/tests/test_processing_recovery_safety.py` | **+17 Tests** (Klassifikation, ACK-Matrix, Crash-Safety, Log-Hygiene) |
| `docs/runbooks/MO-PROCESSING-RECOVERY.md` | **neu**: Diagnose-/Recovery-Runbook |

**Keine** Änderung an: SQS-Konfiguration, Timeouts, Lease, Budget, IAM, Scheduler, P02F,
API, Privacy.

---

## 5. Bewusst unveränderte Mechanismen

- Claim-Bedingungen, Lease (300 s), Budget (2), Attempt-ID-Erzeugung.
- ACK-Verhalten: aktive Claims/Budget/terminal bleiben quittiert (Retry würde bei
  `maxReceiveCount=1` nur die DLQ füllen — keine Verbesserung).
- P02F (Delivery-Recovery) unangetastet.
- P02H-A-Autorisierung unangetastet.

---

## 6. Claim-Vertrag (unverändert, verifiziert)

```text
attribute_exists(pk)
AND attribute_exists(subjectId)
AND status <> CANCELLED
AND (state fehlt | pending | running mit abgelaufener Lease)
AND (processingAttempts < 2)
AND (version fehlt | version = gelesene Version)
→ SET state=running, attemptId=UUID, claimedAt=now, attempts+=1
```

| Vorzustand | Claim | Ergebnis |
|---|---|---|
| fehlt / `pending` | ja | `PROCESSING_CLAIMED` |
| `running`, Lease gültig | nein | `PROCESSING_ALREADY_RUNNING` (ACK) |
| `running`, Lease abgelaufen | ja | `PROCESSING_LEASE_EXPIRED` → `CLAIMED` |
| `failed` | nein | `PROCESSING_TERMINAL_FAILED` (ACK) |
| `succeeded` | nein | `NOOP` (ACK) |
| Budget erschöpft | nein | `PROCESSING_ATTEMPT_EXHAUSTED` (ACK) |
| `CANCELLED` / anonymisiert | nein | `PROCESSING_REJECTED` (ACK) |

---

## 7. Retry- und ACK-Semantik (dokumentiert, unverändert)

- Technischer Fehler/Timeout/ungültiges Ergebnis → Claim-Release (`pending`) + Batch-Failure.
- Bei `maxReceiveCount=1` folgt daraus **DLQ**, kein zweiter Verarbeitungsversuch.
- Aktive Claims, Budget, terminal `failed`, Storno, Anonymisierung → **ACK** (bewusst).
- **Keine** pauschale Umstellung von ACK auf RETRY (wäre ohne Infra-Änderung nur DLQ-Rauschen).

---

## 8. Versuchsbudget

| Frage | Antwort |
|---|---|
| Wann zählt ein Versuch? | beim erfolgreichen Claim (`attempts += 1`) |
| Wann wird er freigegeben? | nie zurückgesetzt; Release setzt nur `state=pending` |
| Zweiter Versuch zulässig? | ja, solange `attempts < 2` und eine neue Zustellung erfolgt |
| Budget erschöpft? | `attempts >= 2` → `PROCESSING_ATTEMPT_EXHAUSTED` |
| Worker-Reaktion | kein Handler, ACK, Ereignis-Log |
| Manuelle Intervention | erforderlich (Runbook §4/§5) |

---

## 9. Absturzmatrix (Auszug, mit neuem Logging)

| Szenario | Zustand | Ereignis | Automatische Wiederaufnahme |
|---|---|---|---|
| vor Claim | unverändert | `PROCESSING_REJECTED`/`STALE` | nein |
| nach Claim | `running` | `PROCESSING_CLAIMED`, bei Crash `TECHNICAL_ERROR`+`RETRY_RELEASED` | nur neue Zustellung |
| während Handler | `running` | `PROCESSING_TECHNICAL_ERROR` | nur neue Zustellung |
| nach Seiteneffekt, vor Abschluss | `running` | dito | **nein** (Seiteneffekt bleibt) |
| nach Abschluss, vor ACK | `succeeded` | `PROCESSING_SUCCEEDED` | ja (`NOOP` bei Duplikat) |
| fremder aktiver Claim | `running` | `PROCESSING_ALREADY_RUNNING` | nein |
| Budget erschöpft | `running`/`pending` | `PROCESSING_ATTEMPT_EXHAUSTED` | nein |
| Anonymize/Erase/Cancel | `running` | `PROCESSING_REJECTED` | nein (korrekt) |
| Konflikt beim Abschluss | `running` | `PROCESSING_RECOVERY_REQUIRED` | nein (sichtbar) |

---

## 10. Idempotenzvertrag

| Kennung | Bedeutung | Verwendung |
|---|---|---|
| `orderId` | stabile fachliche Identität | **externer Idempotency Key** |
| `processingAttemptId` | Identität eines Versuchs | Claim-Fencing, Ergebnisübernahme, Diagnose |

MO garantiert idempotente **Status-/Ergebnisübernahme** (Condition + Attempt-ID), **nicht**
idempotente externe Seiteneffekte. **Keine Exactly-once-Zusage.** Dokumentiert in
`order_handlers.py` (Modul-Docstring) und im Runbook.

---

## 11. Logging

`_log_event(event, **fields)` — nur `event`, `orderId`, `attemptId`, Zustand/Outcome.

| Ereignis | Auslöser |
|---|---|
| `PROCESSING_CLAIMED` | Claim erfolgreich |
| `PROCESSING_LEASE_EXPIRED` | Re-Claim nach abgelaufener Lease |
| `PROCESSING_ALREADY_RUNNING` | fremder aktiver Claim |
| `PROCESSING_TERMINAL_FAILED` | `state=failed` |
| `PROCESSING_ATTEMPT_EXHAUSTED` | Budget erschöpft |
| `PROCESSING_SUCCEEDED` / `FAILED` | Abschluss |
| `PROCESSING_REJECTED` | anonymisiert/storniert |
| `PROCESSING_RECOVERY_REQUIRED` | Abschlusskonflikt (Zustand bleibt ggf. `running`) |
| `PROCESSING_RETRY_RELEASED` / `TECHNICAL_ERROR` | technischer Fehler |

Keine Payloads, Ergebnisse, Kundendaten, Tokens, Exception-Texte. Keine neue
Logging-Bibliothek, keine CloudWatch-Ressource.

---

## 12. Operator-Runbook

`docs/runbooks/MO-PROCESSING-RECOVERY.md` (neu): Diagnose-Kommandos (read-only),
Fallmatrix, Voraussetzungen für autorisierte erneute Zustellung, DLQ-Verfahren,
Grenzen/Blocker. **Keine** ungültigen Schreibempfehlungen (kein Reset von
`processingAttempts`/`processingAttemptId`, kein blindes Redrive, keine Wiederbelebung
anonymisierter/gelöschter/stornierter Orders).

---

## 13. P02F-Kompatibilität

Unverändert: `deliveryState`, Delivery-Lease, GSI1-Fenster, `recovery_enabled=false`,
kein Processing-Anteil, kein Scheduler-Eingriff. Tests grün.

---

## 14. P02G-B-Kompatibilität

Claim/Completion/Conditions/Attempt-ID/Budget unverändert; nur Klassifikation und Logging
ergänzt. Alle bisherigen P02G-B-Tests bleiben grün (3 Expectations auf die neuen,
präziseren Outcomes angepasst).

---

## 15. P02H-A-Kompatibilität

GET/LIST/PATCH-Autorisierung, 401/404/409, Legacy-fail-closed und Worker-ohne-JWT
unverändert (Tests grün).

---

## 16. Testergebnisse

| Suite | Ergebnis |
|---|---|
| Lambda | **298/298 PASS** (+17) |
| Module Builder | **90/90 PASS** |
| Installer | **81/81 PASS** |
| Gesamt | **469 PASS** |
| `terraform validate` | PASS (keine Änderung) |
| `terraform fmt -check` | PASS |

Neue Tests decken: Outcome-Klassifikation, ACK-Matrix (positive/negative), Crash zwischen
Claim und Abschluss (Zustand bleibt `running`), Seiteneffekt-vor-Crash (kein Ergebnis),
technischer Fehler mit Claim-Release, Duplikat nach Erfolg, Lease-Ablauf-Ereignis,
`PROCESSING_RECOVERY_REQUIRED` bei Attempt-Konflikt, Log-Hygiene (kein PII/Ergebnis/
Exception-Text).

---

## 17. Offene Recovery-Lücken

| Lücke | Status |
|---|---|
| Kein automatischer Auslöser für abgelaufene Claims | **OPEN** |
| `maxReceiveCount=1` verhindert zweiten automatischen Versuch | **OPEN** |
| Kein `processingState`-Index (hängende Orders nur per ID findbar) | **OPEN** |
| Kein DLQ-Alarm | **OPEN** |
| Kein Operator-Vertrag (IAM/Freigabe/Audit) | **BLOCKED** |
| Handler-Seiteneffekte ohne stabile Idempotenz | **OPEN** (Handler-Verantwortung) |

---

## 18. Risiken

- Eine abgestürzte Verarbeitung bleibt bis zum manuellen Eingriff `running`.
- Manueller Re-Send kann externe Seiteneffekte duplizieren.
- DLQ wächst ohne Alarm unbemerkt (bis 14 Tage Retention).
- Logs sind unstrukturiert (Print-Zeilen), keine Metriken für Processing-Zustände.

---

## 19. Nächste empfohlene Maßnahmen (nicht implementiert)

1. **P02I-B** automatische Processing-Recovery (Auslöser + Suchindex + Scheduler-Reuse).
2. `maxReceiveCount` anheben (Infra-Freigabe), damit Budget 2 erreichbar wird.
3. DLQ-Alarm + `running`-Alter-Alarm.
4. Operator-Vertrag (IAM, Freigabe, Audit).
5. Strukturierte JSON-Logs / Metriken für `processingState`.

---

## 20. Commit

Commit-SHA: siehe Abschlussbericht (dieser Commit). Working Tree nach Commit CLEAN.
