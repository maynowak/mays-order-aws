# MO-RIS-AGENT-RESULT-BOUNDARY-01 — A06 Secure SQS Result Handoff

**Datum:** 2026-11-13
**Typ:** Lokale Implementierung + Tests (kein Apply, kein Deployment)
**Ergebnis:** COMPLETE lokal. Ein gültiges `ORDER_RESULT` mit `42` wird genau
einmal der richtigen Order zugeordnet und ist für den Eigentümer abrufbar.

## 1. A06.0 — IST / SOLL / GAP

| # | Baustein | SOLL | IST vor A06 | Status |
|---|---|---|---|---|
| 1 | SQS-Consumer | interner Result-Consumer | nur status-only Retail-Worker, eine Queue | **GAP** |
| 2 | `ORDER_RESULT`-Vertrag | vorhanden (RIS V1) | vorhanden, eingefroren | OK (RIS) |
| 3 | Orders-Result-Persistenz | Feld + atomare Übernahme | keine | **GAP** |
| 4 | Idempotenz | genau einmal | keine Result-Semantik | **GAP** |
| 5 | Service-Identität | verifizierbar | keine | **GAP** |
| 6 | Owner-Projektion | Ergebnis sichtbar | `agentOrder` ja, Ergebnis nein | **GAP** |
| 7 | Statusmodell | unverändert | 6-Werte-Lifecycle | OK (nicht angefasst) |
| 8 | Fingerprint | unverändert | vorhanden | OK |

## 2. A06.2 — Service-Boundary

**Kein JSON-Feld als Vertrauensbasis.** Der Consumer verlangt ein SQS-Attribut
`serviceSignature`:

```
HMAC-SHA256(ORDER_RESULT_SERVICE_SECRET, messageId + "\n" + body)
```

- konstanter Vergleich (`hmac.compare_digest`),
- fehlt Secret oder Signatur → **drop**, kein Schreiben,
- manipulierter Body → Signatur ungültig → **drop**.

`signature` beweist Integrität und Herkunft nur gegenüber dem geteilten Secret;
die eigentliche Zustellberechtigung bleibt Infrastruktur (siehe §6).

Zusätzlich: der gespeicherte Auftrag ist die autoritative Quelle. `orderId`,
`correlationId` und — sobald der Dispatch eine hinterlegt — `expectedWorkId`
müssen übereinstimmen.

## 3. A06.3 — Ergebnisübernahme

Neue Methode `OrderService.apply_result(envelope)`:

| Regel | Umsetzung |
|---|---|
| Nur Agent-Orders | `orderType == agent.execution`, sonst `not_agent_order` |
| Korrelation | `agentOrder.metadata.requestId` == `correlationId`, sonst `correlation_mismatch` |
| Keine Korrelation gespeichert | `missing_correlation` (fail-closed) |
| Work-ID | falls `expectedWorkId` gesetzt: muss passen, sonst `work_mismatch` |
| Storniert | `status == CANCELLED` → `order_cancelled` |
| Doppelte Zustellung | gleicher `idempotencyKey` → unverändertes Ergebnis, keine zweite Wirkung |
| Abweichende Execution bei gleichem Key | `execution_mismatch` |
| Bereits abgeschlossen | anderer Key → `already_finalised` |
| Stale Attempt | `attempt` älter als gespeichert → `stale_attempt` |
| Nebenläufigkeit | Conditional Write `attribute_not_exists(processing)`; Verlierer liest nach und ist idempotent |
| Lifecycle | `status` wird **nicht** verändert; Ergebnis lebt in `processing` |

## 4. A06.4 — Projektion

`processing` erscheint ausschließlich in der Eigentümer-Detailantwort:

| Feld | freigegeben |
|---|---|
| `status`, `attempt`, `completedAt` | ja |
| `result` (bei COMPLETED) | ja |
| `error.message` (bei FAILED, gekürzt) | ja |
| `workId`, `executionId`, `messageId`, `idempotencyKey` | **nein** |

Owner-Identity-Interna, Service-Credentials und Queue-Metadaten bleiben intern.

## 5. A06.5 — Tests

`cd lambda && PYTHONPATH=src python -m unittest discover -s tests`
→ **175 Tests OK** (144 bestehend + 31 neu), `compileall` sauber.

Die geforderten 20 Punkte sind abgedeckt, u. a.: gültiges `ORDER_RESULT` mit 42,
`ORDER_FAILED`, Duplikat, unbekannte Order, falsche Work-ID, falsche
Execution-ID, stale Attempt, manipuliertes Ergebnis, unbekannte Version, falscher
Message-Type, fehlende Service-Berechtigung, fremde Korrelation, stornierte Order,
bereits abgeschlossen, ungültiger Body, Größenlimit, keine Secrets,
Owner liest, Owner B `404`, Retail-/Ownership-Regression.

## 6. Infrastruktur-Anforderungen (nicht deployed)

Für den echten Betrieb fehlen — bewusst außerhalb dieses Gates:

1. **Queue** `<project>-processing-results` mit DLQ (eigene Queue, nicht die
   Retail-Queue — deren Consumer deutet `status` als Übergang).
2. **IAM**: nur die RIS-Result-Producer-Rolle darf `sqs:SendMessage`; der
   Consumer darf nur diese Queue lesen.
3. **Secret**: `ORDER_RESULT_SERVICE_SECRET` in beiden Laufzeiten, Rotation
   vorgesehen.
4. **Lambda**: eigener Consumer mit `result_handler.handler`, Batch/Visibility
   passend, DLQ nach N Versuchen.

Bis dahin ist der AWS-Pfad ausdrücklich **nicht** live verifiziert.

## 7. Grenzen

- Keine öffentliche Result-Write-Route.
- Kein direkter RIS-Zugriff auf Orders-DynamoDB.
- Kein RIS-Key als Order-Identität.
- Kein RC-Upgrade, kein Apply, kein Deployment, keine Cognito-/CloudFront-/DNS-Änderung.
- RIS Generic Transport V1 unverändert.

## 8. Offen

| Punkt | Status |
|---|---|
| A05 Dispatch (Orders → RIS) | offen |
| A07 Voll-E2E | offen |
| Infra-Apply (Queue/IAM/Lambda) | separater freigegebener Schritt |
