# MO-RC4-P02F-PENDING-RECOVERY

**PENDING-Recovery: Zustellvertrag, GSI1-Recovery und 5-Minuten-Scheduler**

**Datum:** 2026-11-01
**Branch:** `feature/mo-rc4-kms-privacy-retention`
**Basis:** `1aea2d6659483b7736f02c3936cf3a04cb02954b`
**Freigabe:** T1 (EventBridge Scheduler, 5 min) + A (bestehender GSI1)
**Typ:** Implementierung + Tests (lokal) — keine AWS-Operation, kein Push

---

## 1. Zustellvertrag (implementiert)

Additive Attribute am Order-Item; **keine** neuen fachlichen Statuswerte:

| Attribut | Werte | Bedeutung |
|---|---|---|
| `deliveryState` | `pending` (Anlage) → `sending` (Claim) → `sent` \| `failed` | Zustellzustand, unabhängig vom Order-Status |
| `deliveryAttempts` | Zahl | Sendeversuche (POST + Recovery) |
| `lastDeliveryAt` | ISO-8601 | letzter Sendeversuch |
| `deliveryClaimedAt` | ISO-8601 | Lease-Marke des aktiven Recovery-Laufs |

**Semantik:** `sent` heißt **nur**, dass SQS die Nachricht angenommen hat — **nicht**, dass
sie fachlich verarbeitet wurde (at-least-once). Fachlicher Status bleibt ausschließlich
`status` + State Machine.

### Änderungen im POST-Pfad (`lambda/src/index.py`)

```text
create_order → put_item(status=PENDING, deliveryState=pending)
  → _send_to_sqs(order_id)
      ├─ Erfolg → mark_delivery_state(order_id, "sent")
      └─ Fehler → mark_delivery_state(order_id, "failed")
  → 201 (unverändert)
```

- Markierung ist **best effort**; ein Fehler dabei ändert die API-Antwort nicht
  (Test `test_mark_failure_does_not_break_response`).
- Fehlt `SQS_QUEUE_URL`, wird `failed` vermerkt (nicht stillschweigend `sent`).
- `mark_delivery_state` erhöht `deliveryAttempts` atomar
  (`if_not_exists(deliveryAttempts, 0) + 1`).

---

## 2. Recovery-Mechanismus (`lambda/src/recovery.py`)

### 2.1 Ablauf

1. **GSI1-Range-Query** (kein Scan):
   `gsi1pk = "LIST" AND gsi1sk >= <now - window>`; `ScanIndexForward=True` (älteste zuerst),
   paginiert über `LastEvaluatedKey`, Abbruch bei `limit` Kandidaten.
2. **Filter:** nur `status == "PENDING"`, `createdAt <= now - min_age_seconds`.
3. **Re-Read** je Kandidat (`ConsistentRead`) → Skip bei `not_pending`, `already_sent`
   (`deliveryState == "sent"`), fehlender Order.
4. **Claim (atomar):**
   ```text
   Condition: #status = :pending
              AND (attribute_not_exists(deliveryClaimedAt) OR deliveryClaimedAt < :leaseExpiry)
              AND (attribute_not_exists(deliveryState) OR deliveryState <> :sent)
   Update:    deliveryState=sending, deliveryClaimedAt=now,
              lastDeliveryAt=now, deliveryAttempts += 1
   ```
5. **Zustellung** an die **bestehende** Queue mit dem **bestehenden** Nachrichtenformat
   (`{orderId, status:"CONFIRMED", metadata.reason}`) — gleicher Worker-/DLQ-Pfad.
6. **Abschluss:** Erfolg → `deliveryState=sent`, `REMOVE deliveryClaimedAt`
   (Condition `deliveryClaimedAt = :now`, damit kein fremder Claim überschrieben wird);
   Fehler → `deliveryState=failed`, `REMOVE deliveryClaimedAt`, Zähler `failed`.

### 2.2 Ungewisse Zustellung

Send erfolgreich, aber Bestätigung nicht schreibbar → Zähler `uncertain`; der Claim bleibt
stehen. Nach Ablauf der Lease (Default 300 s) darf erneut gesendet werden. Doppelte
Nachricht ist möglich; der Worker fängt den Statuswechsel über P02C ab (`noop`).
**Keine Exactly-once-Behauptung.**

### 2.3 DLQ-Abgrenzung

`deliveryState == "sent"` wird **niemals** erneut eingereiht. Eine im DLQ liegende
Nachricht (Worker/Hander-Fehler oder unbekannter `orderType`) bleibt dort — kein
automatisches DLQ-Redrive. Ein Recovery-Loop kann solche Orders daher nicht endlos
neu einreihen.

### 2.4 Grenzen pro Lauf

`window_minutes` (Default 60, max 1440), `limit` (Default 50, max 200),
`min_age_seconds` (Default 60), `lease_seconds` (Default 300, min 30). Ungültige Werte
fallen auf Defaults zurück (getestet).

---

## 3. Scheduler (Terraform)

Neues Modul `terraform/modules/recovery/`:

| Ressource | Zweck |
|---|---|
| `aws_scheduler_schedule.recovery` | `rate(5 minutes)`, `flexible_time_window = OFF`, Ziel = **bestehender** Handler (`module.lambda.function_arn`) |
| `aws_iam_role.scheduler` | Trust: `scheduler.amazonaws.com` |
| `aws_iam_role_policy.invoke_handler` | **nur** `lambda:InvokeFunction` auf genau diese Funktion |

Payload:

```json
{"internalAction":"recovery/scan",
 "options":{"windowMinutes":60,"minAgeSeconds":60,"limit":50,"leaseSeconds":300}}
```

- **Keine neue Lambda**, keine öffentliche Route.
- **Opt-in:** `recovery_enabled` Default **false** → bestehende Deployments erhalten ohne
  explizite Aktivierung keine neue Ressource.
- Aktivierung: `terraform apply -var recovery_enabled=true`
  (Installer: `./Mays-Order-AWS-installer plan --var recovery_enabled=true`, `--var` ist
  bereits vorhanden — **keine** Installer-Codeänderung nötig).
- Builder: Modul `recovery` im Katalog (`deps: ["lambda"]`), im Preset `complete`,
  Variablen `recovery_*` dem Modul zugeordnet. **`orders-service`-Vertrag unverändert.**
- Policy-Gate: `aws_scheduler_schedule` in die Allowlist aufgenommen (sonst würde der
  Gate-PASS für das neue Feature scheitern).

### IAM-Begründung

Der Scheduler-Payload enthält **kein Secret**. Die Autorisierung ist rein IAM-basiert:
nur die Scheduler-Rolle (und ein Operator mit `lambda:InvokeFunction`) kann den Lauf
auslösen. Der Handler nutzt für Tabellen-/Queue-Zugriff seine bestehende Rolle
(`dynamodb:Query` auf GSI1, `sqs:SendMessage` bereits vorhanden) — **keine IAM-Änderung
am Handler**.

---

## 4. Legacy-Verhalten

| Bestand | Verhalten |
|---|---|
| Order ohne `deliveryState` | gilt als „nicht bestätigt" → Recovery darf zustellen |
| Order mit `deliveryState=sent` | wird übersprungen (kein Re-Enqueue) |
| Order `CONFIRMED`/`PROCESSING`/… | wird übersprungen (`not_pending`) |
| Order `CANCELLED` | wird übersprungen |
| Order ohne GSI1-Eintrag | für GSI1-Recovery unsichtbar (Altbestand vor GSI1-Nutzung) — dokumentiert |

---

## 5. Tests

Neu: **24 Tests** (`lambda/tests/test_recovery.py` 15, `test_index.py` +6,
`test_order_service.py` +3).

Abgedeckt: Erfolg, Sendefehler, Retry im Folgelauf, Crash vor Versand (aktive Lease blockt),
Crash nach Versand (`uncertain`), abgelaufene Lease, zwei Läufe (nur ein Send), DLQ-Abgrenzung
(`sent` nie erneut), Storno/`CONFIRMED` skip, Legacy ohne Attribute, Pagination (5 über
mehrere Seiten), Limit (2 von 5), Zeitfenster, Ownership unverändert, POST-Markierung
sent/failed, Recovery-Action-Report, unbekannte Action abgelehnt, keine HTTP-Route.

| Suite | Ergebnis |
|---|---|
| Lambda | **204/204 PASS** (vorher 180) |
| Module Builder | **90/90 PASS** |
| Installer | **81/81 PASS** |
| `terraform validate` (Root) | PASS |
| `terraform fmt -check` | PASS |
| Generiertes Projekt (`complete`) | init 0 · validate PASS · fmt PASS · `recovery` enthalten |

---

## 6. Abschlusstabelle

| Prüfung | Ergebnis |
|---|---|
| Ausgangs-HEAD | `1aea2d6` |
| Zustelllücke | geschlossen für neue Orders (Zustellvermerk + Recovery); Altbestand ohne GSI1-Eintrag bleibt unsichtbar |
| Gewählte Strategie | **A** (GSI1-Range-Query) + Claim/Lease + **T1** (Scheduler 5 min) |
| Vorhandene Indizes | GSI1 (`LIST`/`createdAt`) — unverändert genutzt |
| Zusätzliche Attribute | `deliveryState`, `deliveryAttempts`, `lastDeliveryAt`, `deliveryClaimedAt` |
| Recovery-Ausführung | `internalAction: recovery/scan` im bestehenden Handler; Scheduler 5 min |
| Wiederholte Zustellung | Lease + `already_sent`-Skip; Duplikate möglich (at-least-once) |
| Parallele Recovery | Claim-Condition verhindert Doppelclaim |
| DLQ-Abgrenzung | `sent` wird nie neu eingereiht; kein Auto-Redrive |
| Stornierung | übersprungen |
| P02C-Kompatibilität | unverändert (Status-Write weiterhin bedingt) |
| P02E-Kompatibilität | unverändert (Routing bleibt im Worker) |
| Ownership unverändert | ja (nur `delivery*`-Attribute) |
| Lambda-Tests | 204/204 |
| Builder-Tests | 90/90 |
| Installer-Tests | 81/81 |
| Terraform-Validierung | PASS (Root + generiertes Projekt) |
| Commit | siehe Abschlussbericht (dieser Commit) |
| Working Tree | clean nach Commit |
| Offene Entscheidungen | Aktivierung von `recovery_enabled` in Zielumgebungen (opt-in) · Auto-DLQ-Redrive (bewusst aus) · Beobachtung/Alarm auf `failed`/`uncertain` (P02G) · Handler-Idempotenz bei künftigen Seiteneffekten |

---

## 7. Restrisiken

1. **Doppelzustellung** nach Lease-Ablauf (Crash nach Send) → Worker-`noop`, aber Handler
   mit künftigen **Seiteneffekten** brauchen eigene Idempotenz (P02G).
2. **Altbestand ohne GSI1-Eintrag** ist für die Recovery unsichtbar (kein Scan).
3. **`deliveryState=sent` + DLQ** = bewusst kein automatischer Retry; erfordert Betrieb.
4. **Scheduler ist opt-in** — ohne `recovery_enabled=true` bleibt die Lücke bestehen.
5. **Doppelte Sends** erhöhen kurzzeitig SQS-Kosten; begrenzt durch `limit`/Fenster.
