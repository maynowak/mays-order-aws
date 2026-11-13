# MO-RC4-P02G-B-PROCESSING-LIFECYCLE-AND-RESULT-PERSISTENCE

**Interner Processing-Lifecycle, atomare Ergebnisübernahme, Privacy-Race-Schutz**

**Datum:** 2026-11-01
**Branch:** `feature/mo-rc4-kms-privacy-retention`
**Basis:** `7471b26aadd8da94c132288de437eb8e8b5f4e68`
**Typ:** Implementierung + Tests (lokal) — keine AWS-Operation, kein Push

---

## 1. Git-Baseline

| Prüfung | Ergebnis |
|---|---|
| Branch | `feature/mo-rc4-kms-privacy-retention` ✔ |
| HEAD | `7471b26` ✔ |
| Working Tree | CLEAN ✔ |
| P02C/P02E/P02F/P02G-A | vorhanden (Worker-Condition, Registry, Delivery-Recovery, Result-Privacy-Vertrag) |
| Tests vorher | 233/233 |

---

## 2. Bestehende Architektur (erhalten)

```text
POST /orders → put_item(PENDING, deliveryState=pending) → SQS → Worker
  → Item lesen → Idempotenz/Stale/State-Machine → Handler wählen
  → [Status-Handler: Handler → bedingtes Statusupdate]
  → [Processing-Handler: Statusupdate → Claim → Handler → atomarer Abschluss]
```

- Keine neue Queue/Tabelle/Lambda, keine neue Route, keine Statusänderung.
- **Status-Handler (`generic`) unverändert**: Reihenfolge Idempotenz → Übergangsprüfung →
  Handler → bedingtes Update; Handler-Fehler hinterlässt **keinen** Statuswrite
  (bestehende Tests unverändert grün).

---

## 3. Processing-State-Vertrag (P02G-A, unverändert)

`processingState` ∈ `pending|running|succeeded|failed` · `processingAttemptId` ·
`result` · `completedAt` · `processingError`.

**Zusätzlich für den Claim (P02G-B):**

| Feld | Zweck |
|---|---|
| `processingClaimedAt` | Lease-Marke des aktiven Versuchs |
| `processingAttempts` | Versuchszähler (Budget `MAX_PROCESSING_ATTEMPTS = 2`) |

Übergänge: `missing|pending → running → succeeded|failed`.
**Kein Retry nach `failed`** (terminal bis Operator-Eingriff). Ein **abgelaufener
`running`-Claim** darf erneut versucht werden, solange das Budget reicht.

---

## 4. Claim-Mechanismus (atomar)

```text
Condition:
  attribute_exists(pk)
  AND attribute_exists(subjectId)          ← Datenschutz-Guard
  AND #status <> :cancelled
  AND (attribute_not_exists(processingState)
       OR processingState = :pending
       OR (processingState = :running AND claim abgelaufen))
  AND (attribute_not_exists(processingAttempts) OR processingAttempts < :maxAttempts)
  AND (attribute_not_exists(#version) OR #version = :version)
Update:
  SET processingState=running, processingAttemptId=:attempt,
      processingClaimedAt=:now, processingAttempts+=1
```

- **Guard im selben Update** (`attribute_exists(subjectId)`) → anonymisierte Orders
  können keinen Versuch starten.
- **Version** wird nur geprüft, wenn vorhanden (Legacy-kompatibel) und durch den
  Statuswechsel davor aktualisiert → Claim liest nach dem Statuswechsel frisch.
- **Lease** (`PROCESSING_LEASE_SECONDS = 300`) ist **nicht** identisch mit
  SQS-Visibility (60 s) oder P02F-Delivery-Lease (300 s, anderes Feld/Zweck).

---

## 5. Handler-Vertrag

Registry (`order_handlers.py`) additiv erweitert:

```python
@register("intern.report.generate", processing=True)
def handler(order, payload, context):      # context: attemptId, orderType
    return {"result": ...}                  # oder: {"processed": True}
    # raise ProcessingFailure("CODE", "message")  → kontrollierter Fehler
```

- **Explizite Fähigkeit** je Handler (`processing=False` ist Default) → `generic`
  bleibt Status-Handler; keine stillschweigende Änderung.
- Keine dynamischen Imports; Duplikate/invalide Typen abgelehnt.
- Handler schreiben **nie** Status, Ownership oder Ergebnis.
- `{"result": ...}`-Wrapper wird akzeptiert (Spec-Beispiel) und entpackt.

---

## 6. Ergebnisvalidierung

`validate_processing_result` (P02G-A): 16 KiB, Tiefe 5, 100 Elemente/Container,
Key-/Stringgrenzen, nur JSON-Typen. Ungültiges Ergebnis → **kein** Abschluss,
Claim wird freigegeben, Item-Failure → Retry → DLQ.

---

## 7. Atomare Ergebnisübernahme

Ein einziges bedingtes Update für Erfolg **und** Fehler:

```text
Condition: attribute_exists(pk) AND attribute_exists(subjectId)
           AND #status <> :cancelled
           AND processingState = :running AND processingAttemptId = :attempt
Erfolg:  SET processingState=succeeded, result=:result, completedAt=:now,
             updatedAt=:now, version+=1  REMOVE processingError, processingClaimedAt
Fehler:  SET processingState=failed, processingError=:error, completedAt=:now,
             updatedAt=:now, version+=1  REMOVE result, processingClaimedAt
```

- **Guard in derselben Bedingung** (nicht vorher geprüft).
- Konflikt → Klassifikation: `NOOP` (bereits erfolgreich), `PROCESSING_REJECTED`
  (storniert/anonymisiert), `PROCESSING_SKIPPED` (anderer Versuch/State), `MISSING`.
- Keine zweite Abschlussroutine; nutzt dieselbe Condition-Technik wie P02C.

---

## 8. Fehlerabschluss

| Fall | Verhalten |
|---|---|
| `ProcessingFailure(code, message)` | `processingState=failed`, validiertes `processingError`, `completedAt`; kein Stacktrace, keine Exception-Texte; Nachricht **quittiert** (kein Retry) |
| Technische Exception | Claim wird freigegeben (`processingState=pending`), Exception propagiert → **Item-Failure** → Retry (maxReceiveCount=1) → **DLQ** |
| Ungültiges Ergebnis | Claim freigegeben, `handler_failed` → Retry → DLQ |
| Completion-Konflikt | kein Retry (Work ist hinfällig oder bereits erledigt) |

**Technische Fehler werden nie als fachlich abgeschlossen gespeichert.**

---

## 9. Cancellation

- Claim-Bedingung: `status <> CANCELLED`.
- Abschluss-Bedingung: `status <> CANCELLED`.
- Storno während des Handlers → Abschluss wird abgelehnt (`PROCESSING_REJECTED`),
  kein Ergebnis, Status bleibt `CANCELLED`.
- **Dokumentiert:** Externe Seiteneffekte eines bereits gestarteten Handlers können
  nicht rückwirkend gestoppt werden (Handler-Verantwortung).

---

## 10. Idempotenzgrenzen

| Ebene | Garantie |
|---|---|
| SQS-Zustellung | at-least-once (P02F kann erneut senden) |
| Processing-Claim | genau ein aktiver Versuch (Lease, Attempt-Budget 2) |
| Ergebnisübernahme | genau einmal pro `processingAttemptId` (Condition) |
| Fachliche Seiteneffekte | **Handler-Verantwortung** (Attempt-ID im Kontext) |

**Keine Exactly-once-Zusage.** Ein Absturz zwischen Handler und Abschluss lässt
`processingState=running` stehen; nach Lease-Ablauf und erneuter Zustellung kann der
Handler erneut laufen (Duplicate möglich).

---

## 11. P02F-Kompatibilität

| Aspekt | Verhalten |
|---|---|
| Delivery-Recovery | unverändert (kein Scheduler-Eingriff) |
| Doppelte Zustellung | Claim verhindert parallele Verarbeitung; nach Abschluss `NOOP` |
| Aktiver Claim | zweiter Zustellversuch → `PROCESSING_SKIPPED` (quittiert, kein DLQ) |
| Abgelaufener Claim | neuer Versuch innerhalb des Budgets |
| Technischer Fehler | Claim freigegeben → Retry → DLQ |
| DLQ | unverändert, kein Auto-Redrive |

---

## 12. Privacy-Race-Schutz (hartes Abnahmekriterium)

Test `test_anonymize_during_processing_rejects_result`:

```text
Claim → Handler startet → Anonymize (subjectId entfernt) → Handler endet
→ Abschluss-Bedingung attribute_exists(subjectId) schlägt fehl
→ PROCESSING_REJECTED, KEIN result im Item
```

Ebenso getestet: **Erase** während des Handlers (`MISSING`), **Cancellation**
(`PROCESSING_REJECTED`), **fremder/gestohlener Attempt** (`PROCESSING_SKIPPED`).

---

## 13. Legacy-Kompatibilität

- Orders ohne `orderType`/`processingState`: `generic`-Pfad wie bisher.
- Legacy ohne `version`: Claim nutzt `attribute_not_exists(#version)`; Abschluss
  `if_not_exists(version, 0) + 1`.
- Öffentliche Antworten unverändert (interne Felder weiter gestrippt, P02G-A).
- Keine Pflichtfelder.

---

## 14. Tests

Neu: **22 Tests** (`test_processing_lifecycle.py` 18, `test_order_handlers.py` +4).

Abgedeckt: erfolgreicher Claim/Abschluss, Duplikat (`NOOP`), aktiver Claim blockt,
abgelaufener Claim, Versuchsbudget, fehlende Version, anonymisiert, storniert,
terminal `failed`, fachlicher Fehler (kontrolliert), technischer Fehler (Claim-Release
+ Retry), ungültiges Ergebnis, `generic` unverändert, Anonymize/Erase/Cancel während
Verarbeitung, fremder Attempt, Absturz vor Abschluss.

| Suite | Ergebnis |
|---|---|
| Lambda | **255/255 PASS** (vorher 233) |
| Module Builder | **90/90 PASS** |
| Installer | **81/81 PASS** |
| `terraform validate` | PASS (keine Infra-Änderung) |
| `terraform fmt -check` | PASS |

---

## 15. Abschlusstabelle

| Prüfung | Ergebnis |
|---|---|
| Git-Baseline | `7471b26`, clean |
| Processing-State-Vertrag | IMPLEMENTED (P02G-A-Werte + `processingClaimedAt`/`processingAttempts`) |
| Claim | IMPLEMENTED (atomar, Guard, Lease, Version, Budget) |
| Attempt-ID | IMPLEMENTED (UUID je Versuch, im Kontext) |
| Handler-Vertrag | IMPLEMENTED (explizite `processing=True`-Fähigkeit, `ProcessingFailure`) |
| Ergebnisvalidierung | VERIFIED (P02G-A-Grenzen) |
| Atomare Übernahme | IMPLEMENTED (ein bedingtes Update, Guard enthalten) |
| Fehlerabschluss | IMPLEMENTED (nur kontrollierte Fehler persistiert) |
| Cancellation | VERIFIED (Claim + Abschluss) |
| Idempotenz | VERIFIED (Status/Ergebnis idempotent; Seiteneffekte Handler) |
| P02F-Kompatibilität | VERIFIED (unverändert) |
| Privacy-Race | VERIFIED (Anonymize/Erase/Cancel blockieren Abschluss) |
| Legacy | VERIFIED (`generic`, fehlende Version/State) |
| Lambda-Tests | 255/255 |
| Builder / Installer | 90/90 · 81/81 |
| Terraform | validate/fmt PASS |
| Commit | siehe Abschlussbericht (dieser Commit) |
| Working Tree | clean nach Commit |

**Offene Risiken / Entscheidungen:**

| ID | Punkt | Status |
|---|---|---|
| R-11 | **Automatische Wiederaufnahme** abgestürzter `running`-Versuche: nur über erneute SQS-Zustellung innerhalb des Versuchsbudgets; **kein Processing-Scheduler** (bewusst, P02F-Scheduler unverändert) | **OPEN** |
| — | Fachlich terminale `failed`-Orders: kein automatischer Retry (Operator/Redrive) | **DESIGNED** |
| — | Fachliche Seiteneffekte: keine MO-Idempotenz; Handler muss `processingAttemptId` nutzen | **OPEN (Handler-Verantwortung)** |
| — | V-10 (Owner-Check beim Lesen) unverändert; Ergebnisse bleiben intern | **OPEN** |
| — | Lease-/Budgetwerte sind Konstanten (keine Terraform-Variablen) | **DESIGNED** |
