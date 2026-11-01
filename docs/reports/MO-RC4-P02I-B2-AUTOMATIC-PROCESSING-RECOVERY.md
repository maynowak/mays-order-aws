# MO-RC4-P02I-B2-AUTOMATIC-PROCESSING-RECOVERY

**Automatische Wiederaufnahme abgelaufener Processing-Claims (GSI3 + separater Schedule)**

**Datum:** 2026-11-01
**Branch:** `feature/mo-rc4-kms-privacy-retention`
**Basis:** `852da917159efe8b29d697674b9fefcb8c7765c4`
**Typ:** Implementierung + Tests (lokal) — **kein Deployment**, keine AWS-Operation, kein Push

---

## 1. Git-Baseline

| Prüfung | Ergebnis |
|---|---|
| Branch | `feature/mo-rc4-kms-privacy-retention` ✔ |
| HEAD | `852da91` ✔ |
| Working Tree | CLEAN ✔ |
| Ausgangstests | Lambda 298 · Builder 90 · Installer 81 = 469 |

---

## 2. Implementierte Architektur

```text
EventBridge Scheduler
  ├─ recovery/scan    (P02F, unverändert, Flag recovery_enabled)
  └─ processing/scan  (NEU, Flag processing_recovery_enabled, default false)
        └─ bestehende Handler-Lambda (keine zweite Lambda)
             ├─ GSI3-Query (running, claimedAt <= now−360 s)
             ├─ GetItem-Recheck (ConsistentRead)
             └─ SQS SendMessage (bestehende Queue, bestehendes Format)
                  └─ Worker: atomarer Claim (unverändert) → Handler → Completion
```

**Prinzip:** Recovery findet und stellt erneut zu; der **Worker** entscheidet atomar.

---

## 3. GSI3

`terraform/modules/dynamodb/main.tf`:

| Element | Wert |
|---|---|
| Name | `gsi3` |
| Hash Key | `gsi3pk` (S) |
| Range Key | `gsi3sk` (S, ISO-8601 → lexikografisch sortierbar) |
| Projektion | **KEYS_ONLY** (keine PII) |
| Ausgabe | `gsi3_name`, `gsi3_arn` |

Neue Attribute `gsi3pk`/`gsi3sk` (Typ `S`) im Table-Schema.

**Kein Backfill**, keine Änderung bestehender Attribute.

---

## 4. Indexpflege (IMPLEMENTED)

| Übergang | Ort | Verhalten |
|---|---|---|
| Claim (`pending|fehlend|abgelaufen → running`) | `sqs_handler._claim_processing` | `SET gsi3pk="PROCESSING#RUNNING", gsi3sk=:now` |
| Re-Claim nach Lease-Ablauf | dito | `gsi3sk` wird auf den neuen Claim-Zeitwert gesetzt |
| `running → succeeded` | `_complete_processing` | `REMOVE gsi3pk, gsi3sk` |
| `running → failed` | dito | `REMOVE gsi3pk, gsi3sk` |
| Release nach technischem Fehler | `_release_claim` | `REMOVE processingClaimedAt, gsi3pk, gsi3sk` |
| Erase | Item-Löschung | Indexeintrag verschwindet mit dem Item |
| Anonymize | `order_service` Update | `REMOVE … gsi3pk, gsi3sk` (Privacy-Pfad, additiv) |
| Cancel | Status-Update | Index bleibt; Recovery-GetItem erkennt `CANCELLED` und überspringt |

Damit enthält der Index **nur aktive Claims**.

---

## 5. Recovery-Handler

`lambda/src/recovery.py::run_processing_recovery(table, send_message, *, now, limit, safety_margin_seconds)`

1. **Query:** `IndexName=gsi3`, `gsi3pk = PROCESSING#RUNNING AND gsi3sk <= cutoff`,
   `Limit=limit`, paginiert (Cursor), Abbruch bei `limit`.
2. **Cutoff:** `now − (PROCESSING_LEASE_SECONDS + safety_margin)` — Werte aus
   `sqs_handler` importiert (keine doppelten Konstanten).
3. **GetItem-Recheck** (ConsistentRead), Skip-Gründe:
   `order_missing`, `not_running`, `lease_not_expired`, `budget_exhausted`,
   `anonymized`, `cancelled`, `read_error`.
4. **Send** über Callback; Fehler → `failed` + `send_failed` (kein Abbruch des Laufs).
5. **Kein Write:** die Funktion besitzt keinerlei `update_item`-Aufruf (Test erzwingt das).

Report: `scanned`, `candidates`, `checked`, `sent`, `failed`, `budgetExhausted`, `skipped{...}`.

---

## 6. Scheduler

`terraform/modules/recovery/main.tf`: `aws_scheduler_schedule.processing_recovery`
(**unabhängig** von `enabled`/P02F; nur `processing_enabled` entscheidet), gleiche Lambda,
gemeinsame Scheduler-Rolle (Rolle wird erstellt, sobald **einer** der beiden Schedules aktiv
ist), Payload `{"internalAction":"processing/scan","options":{limit, safetyMarginSeconds}}`.
Eigene Variablen und eigener Output `processing_schedule_name`.

**P02F-Schedule unverändert.**

---

## 7. Feature Flags (Default = AUS, wirksam)

| Variable | Default | Wirkung |
|---|---|---|
| `processing_recovery_enabled` | **false** | Ohne diesen Flag entsteht **keine** Schedule-Ressource (count=0) → kein automatischer Lauf; unabhängig von `recovery_enabled` |
| `processing_recovery_schedule_expression` | `rate(5 minutes)` | Takt |
| `processing_recovery_limit` | 20 | Kandidaten pro Lauf |
| `processing_recovery_safety_margin_seconds` | 60 | Puffer über der Lease |
| `recovery_enabled` (P02F) | false | unabhängig |

---

## 8. IAM

| Aktion | Vorher | Neu |
|---|---|---|
| Query GSI1/GSI2 | ja | unverändert |
| **Query GSI3** | nein | **ergänzt** (`dynamodb_gsi3_arn` → IAM-Policy, Root-Wiring) |
| GetItem / SendMessage / Logs | ja | unverändert |
| UpdateItem in Recovery | — | **nicht verwendet** |
| Scan / Purge / Delete / Redrive | nein | **nicht ergänzt** |

Worker-Rolle unverändert.

---

## 9. SQS-Zustellung

Unverändertes Nachrichtenformat:

```json
{"orderId":"ord_...","status":"CONFIRMED","metadata":{"reason":"processing_recovery"}}
```

`metadata.reason` ist **nur Diagnose** und begründet keine Berechtigung; der Worker prüft
Zustand, Budget, Privacy und Status erneut.

Send-Fehler → Zähler, kein Zustandswechsel; Kandidat bleibt für den nächsten Lauf sichtbar.
Erfolgreicher Send + späterer Fehler → mögliche Doppelzustellung (at-least-once).

---

## 10. Duplikatbehandlung

- Mehrere Läufe können dieselbe Order erneut senden (at-least-once).
- Der atomare Worker-Claim verhindert Doppelverarbeitung; Duplikate enden als
  `PROCESSING_ALREADY_RUNNING` bzw. `NOOP`.
- Kein zusätzlicher Recovery-Claim (bewusste Entscheidung P02I-B1, Strategie A).
- **Keine Exactly-once-Garantie.**

---

## 11. Privacy

- GSI3 ist **KEYS_ONLY** (keine personenbezogenen Daten im Index).
- Recovery prüft `subjectId` und `status` per GetItem; anonymisierte/gelöschte/stornierte
  Orders werden übersprungen.
- Anonymize entfernt `gsi3pk`/`gsi3sk`; Erase entfernt das Item.
- Abschluss bleibt atomar im Worker geschützt (`subjectId`-Guard, `status≠CANCELLED`,
  Attempt-ID) — ein veralteter Indexeintrag begründet keine Berechtigung.

---

## 12. Cancellation

`CANCELLED` wird von der Recovery übersprungen **und** vom Worker beim Claim/Abschluss
abgelehnt. Keine Wiederaufnahme.

---

## 13. Budget-Erschöpfung (verbindliche Entscheidung: keine Terminalisierung)

`attempts >= 2` + Lease abgelaufen → **keine** Zustellung, Zähler `budgetExhausted`,
kein `failed`, kein Reset. Die Order bleibt `running`; Dokumentation im Runbook und
Report. Terminalisierung bleibt einem späteren Operator-Vertrag vorbehalten.

---

## 14. Legacy-Verhalten

`processingState=running` ohne `gsi3pk`/`gsi3sk` wird **nicht** gefunden (kein Backfill,
kein Scan, keine Ableitung). Dokumentiert als Grenze.

---

## 15. DLQ-Alarm

`terraform/modules/monitoring`: `aws_cloudwatch_metric_alarm.dlq_messages`

| Feld | Wert |
|---|---|
| Name | `${project}-dlq-messages` |
| Namespace/Metrik | `AWS/SQS` / `ApproximateNumberOfMessagesVisible` |
| Dimension | `QueueName = ${project}-orders-queue-dlq` |
| Statistik/Periode | Maximum / 300 s |
| Schwelle | `>= 1`, 1 Evaluation |
| `treat_missing_data` | `notBreaching` |
| Aktivierung | `monitoring_enabled && dlq_name != null` (unabhängig von Recovery-Flags) |
| Aktionen | **keine** (kein SNS-Kanal im Stack → **OPEN**) |

---

## 16. Monitoring

Recovery-Report-Zähler + strukturierte Ereignisse (P02I-A-Konventionen), keine Payloads/PII.
Neue Ereignisnamen: `PROCESSING_RECOVERY_SCAN_*` sind als Report-Felder abgebildet
(`kind=processing`, `sent`, `failed`, `budgetExhausted`, `skipped`).

---

## 17. Terraform-Validierung

| Prüfung | Ergebnis |
|---|---|
| `terraform init -backend=false` | 0 |
| `terraform validate` | **PASS** |
| `terraform fmt -check -recursive` | **PASS** |
| Generiertes `complete`-Projekt (Builder) | init 0 · validate PASS · fmt PASS · GSI3/Flags vorhanden |

**Nicht ausgeführt:** plan/apply/destroy (keine AWS-Operation).

---

## 18. Testergebnisse

| Suite | Ergebnis |
|---|---|
| Lambda | **321/321 PASS** (+23) |
| Module Builder | **90/90 PASS** |
| Installer | **81/81 PASS** |
| Gesamt | **492 PASS** |

Neue Tests: Auswahl (abgelaufen/aktiv/Puffer/Budget/Cancelled/Anonymisiert/gelöscht/legacy),
Puffer-Grenze, Limit, Pagination, Sende-Fehler, **keine Writes**, At-least-once-Wiederholung,
interne Aktion (`processing/scan`, P02F weiterhin, unbekannte Aktion), GSI3-Pflege
(Claim/Erfolg/Fehler/Release), Anonymize entfernt Indexattribute.

---

## 19. Deployment-Reihenfolge (dokumentiert, **nicht ausgeführt**)

1. GSI3 erstellen (`terraform apply` nach Freigabe), Status `ACTIVE` abwarten.
2. IAM-Erweiterung (GSI3-ARN) ausrollen.
3. Lambda-Code mit Indexpflege ausrollen.
4. Recovery-Code (Funktion + `processing/scan`) ausrollen.
5. Tests/Betriebsprüfung (manueller Lauf mit `limit=1`).
6. `processing_recovery_enabled=true` separat freigeben und aktivieren.
7. DLQ-Alarm (`monitoring_enabled=true`) ist unabhängig aktiv, sobald monitoring an ist.

**Terraform-Abhängigkeiten unterstützen diese Reihenfolge** (GSI im Table-Ressource,
IAM referenziert `module.dynamodb.gsi3_arn`, Lambda-Code ist separat).

---

## 20. Rollback

- `processing_recovery_enabled=false` → Schedule wird entfernt (count=0), Code bleibt inert.
- GSI3 kann bestehen bleiben (keine Reads, minimale Storage-Kosten) oder in einem eigenen
  Plan entfernt werden (Rückbau braucht Freigabe).
- DLQ-Alarm über `monitoring_enabled=false` bzw. `dlq_name=null` deaktivierbar.

---

## 21. Offene Risiken

| Risiko | Status |
|---|---|
| GSI3 eventual consistent → einzelne Kandidaten kurzfristig verpasst | **OPEN** (Puffer 60 s + GetItem-Recheck) |
| Alt-`running` ohne Indexattribute | **OPEN** (kein Backfill) |
| Budget erschöpft → Order bleibt `running` | **OPEN** (bewusst, Operator) |
| Kein Benachrichtigungskanal für Alarme | **OPEN** |
| Doppelte Zustellung nach Re-Claim/Lease-Ablauf | **dokumentiert** (at-least-once) |
| Kosten bei sehr hoher Order-Rate | **INFERRED** gering (Index nur aktive Claims) |

---

## 22. Commit

Commit-SHA: siehe Abschlussbericht (dieser Commit). Working Tree nach Commit CLEAN.

**Status:** IMPLEMENTED / VERIFIED (lokal) · **NOT DEPLOYED** (keine AWS-Operation).
