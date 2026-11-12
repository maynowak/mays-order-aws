# MO-RC3-RC4-G3-FIX-DEFECT-CORRECTION

**Targeted defect correction and local regression verification**

**Datum:** 2026-11-12
**Branch:** `test/mo-rc4-testsuite-hardening-10a`
**HEAD vor Fix:** `8f6dc8dd0915620fa6e45131797512c072df383d`
**Modus:** lokale Code-/Testkorrekturen; **keine AWS-Mutation, kein Terraform,
kein Deployment, kein Push/Merge**.

```text
STATUS: READY FOR G3-LIVE APPROVAL
G4 RELEASE: NOT READY (open scope/contract decisions)
```

---

## 1. Executive Summary

Die in G3-EXT bestätigten Implementierungsdefekte wurden reproduziert und
minimal korrigiert:

- **F-PRV-01:** Consumer-scoped Erase lädt nach der GSI2-Query das vollständige
  Item (inkl. `consumerId`) statt das nicht projizierte Feld aus dem Index zu
  lesen.
- **GSI3-GAP-01/02:** Recovery zählt übersprungene `CANCELLED`-/Budget-Einträge
  nicht mehr gegen das Kandidatenlimit; der Scan bleibt durch ein hartes
  Scan-Budget begrenzt.
- **GSI3-GAP-03:** Recovery sendet für bereits fortgeschrittene Status
  (`PROCESSING`/`SHIPPED`) den aktuellen Status statt immer `CONFIRMED`, damit
  der Processing-Pfad den Claim übernehmen kann, ohne einen Statusrücksprung
  zu erzeugen.
- **Artefakt:** `lambda/dist/lambda.zip` wurde nach den Produktänderungen
  neu gebaut; der Installer-Artefakt-Gate-Test ist wieder grün.

Es wurden **keine** AWS-/Terraform-Änderungen vorgenommen. Die lokale
Regression ist vollständig PASS.

---

## 2. Git-Baseline

| Feld | Wert |
|---|---|
| Branch | `test/mo-rc4-testsuite-hardening-10a` |
| HEAD vor Fix | `8f6dc8dd0915620fa6e45131797512c072df383d` |
| Working Tree vor Fix | CLEAN |
| Testbaseline | 1.153 PASS + 28 Seed |
| G3-Live-Basis | 4/4 PASS (bereits zuvor, nicht erneut ausgeführt) |

---

## 3. Agentenergebnisse / Umsetzung

| Agent | Ergebnis |
|---|---|
| A — DLQ/Retry | Read-only-Analyse; keine Produktänderung; Live-DLQ weiterhin offen |
| B — GSI3/Recovery | GAP-01/02/03 reproduziert; Fixes durch Commander umgesetzt |
| C — Privacy | F-PRV-01 reproduziert; Fix durch Commander umgesetzt |
| D — Compatibility/QA | Read-only; keine neuen Produktänderungen; offene Scope-/Releaseentscheidungen dokumentiert |

Die Agenten haben keine parallelen Schreibzugriffe ausgeführt. Alle
Produkt-/Teständerungen wurden seriell durch den Commander integriert.

---

## 4. F-PRV-01 — Consumer-scoped Erase

### Ursache

`erase_subject` verwendete:

```text
ProjectionExpression = "orderId,pk,sk,subjectId,version,createdAt"
```

Die GSI2-Projektion enthält `consumerId` nicht. Der optionale Consumer-Scope
las daher `consumerId=None` und verwarf alle Treffer; bei gesetztem Scope
erfolgte keine Löschung (fail-closed, aber funktional falsch).

### Fix

In `lambda/src/order_service.py`:

- GSI2-Query liest nur noch `orderId`.
- Pro Treffer wird das vollständige Item über `_load_order_item()` mit
  `ConsistentRead` geladen.
- Scope-/Owner-Prüfung und Delete/Anonymize verwenden anschließend die
  vollständigen Felder.

### Regressionstest

`lambda/tests/test_order_service.py::TestPrivacyConsumerScopeP02B.test_erase_with_scope_loads_full_item_after_gsi2_projection`

- Fake-Query liefert **nur** `orderId` (wie die reale GSI2-Projektion).
- Fake-GetItem liefert das vollständige Item inkl. `consumerId`.
- Erwartet: genau die eigene Order wird gelöscht, fremde Consumer bleiben
  unberührt.

Vor dem Fix: **FAIL** (`deletedRecords=0`). Nach dem Fix: **PASS**.

---

## 5. GSI3-GAP-01/02 — Kandidatenauswahl / Starvation

### Ursache

`run_processing_recovery` sammelte Kandidaten bis `len(order_ids) == limit`,
bevor `GetItem`/Skip-Klassifikation lief. Viele ältere `CANCELLED`- oder
Budget-Einträge konnten daher das Limit verbrauchen, ohne dass ein gültiger
Kandidat erreicht wurde.

### Fix

`lambda/src/recovery.py`:

- Query/GetItem/Filter laufen nun in einer begrenzten Scan-Schleife.
- Nur gültige Kandidaten zählen gegen `limit`.
- Skips (`cancelled`, `budget_exhausted`, `not_running`, `anonymized`,
  `order_missing`, `read_error`, `lease_not_expired`) werden gezählt, aber
  verdrängen keine gültigen Kandidaten.
- Hartes Scan-Budget `max(limit * 10, 100)` verhindert unbegrenzte Scans.
- Bei erreichter Scan-Grenze wird `scan_limit_reached` als Skip dokumentiert.
- Keine Writes; nur SQS-Sendungen.

### Regressionstests

`lambda/tests/test_processing_recovery.py`:

- `test_skipped_entries_do_not_starve_valid_candidate`
  - 2× `CANCELLED`, 2× Budget, danach 1 gültiger Kandidat.
  - Erwartet: gültiger Kandidat wird gesendet; `candidates=1`.
- `test_limit_bounds_run`, `test_pagination_across_pages`,
  `test_budget_exhausted_is_skipped_and_counted`,
  `test_cancelled_is_skipped` bleiben PASS.

Vor dem Fix: **FAIL** (`candidates=2`, gültiger Kandidat nicht erreicht).
Nach dem Fix: **PASS**.

---

## 6. GSI3-GAP-03 — Expired Claim bei PROCESSING/SHIPPED

### Ursache

Recovery sendete immer `status=CONFIRMED`. Bei einer Order, deren Status
bereits `PROCESSING`/`SHIPPED` war, klassifizierte der Worker die Nachricht als
`STALE`; der Processing-Claim wurde nicht übernommen und die Order konnte
stranden.

### Fix

- `lambda/src/recovery.py` wählt das Ziel:
  - `PENDING` → `CONFIRMED`,
  - bereits fortgeschrittene Prozess-Status → aktueller Status.
- `lambda/src/index.py::_send_processing_recovery(order_id, status=...)`
  übernimmt den Zielstatus in die SQS-Nachricht.
- Der Worker bleibt unverändert; der Processing-Pfad erkennt beim aktuellen
  Zielstatus `NOOP` als „weiter mit Claim“ und führt keinen Statusrücksprung
  aus.

### Regressionstests

- `test_expired_claim_sends_current_processing_status`
  - Status `PROCESSING`, expired Claim → SQS-Zielstatus `PROCESSING`.
- `test_processing_recovery_sender_preserves_target_status`
  - Message-Body enthält den Zielstatus.
- `test_processing_recovery_current_status_can_be_claimed`
  - Processing-Handler übernimmt den Claim bei Status `PROCESSING`; Ergebnis
    `processing_succeeded`, Status bleibt `PROCESSING`.

Vor dem Fix: **FAIL** (Status `None`/CONFIRMED, kein Claim). Nach dem Fix:
**PASS**.

---

## 7. RC3-/RC4-Kompatibilität

Agent D bestätigte read-only:

| Bereich | Ergebnis |
|---|---|
| RC3-Body ohne `orderType` | kompatibel; `generic` |
| RC4-`orderType` | additiv; unbekannter Typ fail-closed asynchron |
| JWT-Owner-/Consumer-Isolation | implementiert und lokal getestet |
| Statusmaschine | unverändert |
| SQS-/Worker-Vertrag | kompatibel, Batch-Failure gehärtet |
| Privacy | Teilfunktionen lokal; Live weiterhin Secret-/Invoke-blockiert |
| Recovery-Idempotenz | lokal getestet; Fixes oben |
| Builder/Installer | 128/669 PASS; Modulvertrag stabil |
| RC3-Bestandsdaten ohne Identität | bewusst 404/keine Staff-Liste; Migration offen |
| API-Idempotenz | API-Dedupe nicht implementiert |
| P00 KMS/Secrets/Retention | nicht implementiert/Scope offen |
| SEC-06 | Contract Gap / separate Entscheidung |

---

## 8. Vollständige lokale Regression

Nach den Fixes und dem Lambda-Artefakt-Rebuild:

```text
Installer:      669 PASS
Builder:        128 PASS
Lambda:         345 PASS
E2E-Harness:     16 PASS
Gesamt:       1.158 PASS
Seed-Tools:      28 PASS (separat)
Live-E2E:         4 BLOCKED/SKIP ohne Opt-in
```

Gegenüber Baseline: **+5 Lambda-Tests**, keine Regression.

Rebuild:

```text
Built lambda/dist/lambda.zip (36583 bytes,
sha256 1584ee0dcccd0b042277827184575a1876c159c75a7a0e95ccd29b4fe5a37e44)
```

Der Installer-Artefakt-Integritätstest ist nach dem Rebuild PASS.

---

## 9. Zusätzlicher Prüfpunkt — G3-EXT-Mutationsformulierung

Die Formulierung in der früheren Abschlussantwort:

> `Kleine produktive AWS-/Terraform-Mutation in G3-EXT`

ist **falsch** und nicht durch G3-EXT-Evidence belegt.

Geprüfte Fakten:

- G3-EXT-Orchestrierung und Agenten A–D waren **read-only**.
- G3-EXT hat **keine** AWS-Mutation, keine SQS-Nachricht, keinen
  Cognito-Benutzer, kein Terraform und kein Deployment ausgeführt.
- Die vorherige **G3**-Live-Suite hatte eine ausdrücklich freigegebene
  synthetische Testidentität und Test-Orders erzeugt; diese wurden
  vollständig bereinigt. Das war **G3**, nicht G3-EXT, und **kein Terraform**.
- G3-EXT-Report und Live-Manifest dokumentieren korrekt:
  `Gate B: BLOCKED — NEW APPROVAL REQUIRED`.

Es handelt sich um eine fehlerhafte Abschlusszeile, nicht um eine tatsächliche
Mutation.

---

## 10. Verbleibende Risiken

- **Privacy live** weiterhin durch fehlendes `PRIVACY_INTERNAL_SECRET` und
  fehlende Invoke-Rolle blockiert; F-PRV-01 ist lokal gefixt, Live-Nachweis
  offen.
- **DLQ** nur lokal/Konfiguration; keine absichtliche Live-Zustellung.
- **GSI3** Scan-Budget begrenzt; bei mehr als 100 übersprungenen Einträgen
  können gültige Kandidaten weiterhin außerhalb des Budgets liegen
  (dokumentierte Restgrenze).
- **Processing** produktiv nur `generic`; GSI3/Claim-Code ist vorbereitet,
  aber nicht produktiv aktiviert.
- **API-Idempotenz** fehlt.
- **RC3-Bestandsdaten** ohne Identität bleiben API-invisible; Migration offen.
- **P00 KMS/Secrets/Retention** nicht implementiert/entschieden.
- **SEC-06** Approval-Bindung separat offen.
- **RIS-/Main-Pipeline** unverändert; `directAWSGit` Auto-Apply bleibt
  eigener Releaseblocker.

---

## 11. G3-Live-Readiness

**READY FOR G3-LIVE APPROVAL** für die lokal korrigierten Defekte:

- F-PRV-01 reproduziert und lokal gefixt,
- GAP-01/02 reproduziert und lokal gefixt,
- GAP-03 reproduziert und lokal gefixt,
- Regression 1.158 PASS,
- Arbeitsbaum nach Commit CLEAN.

**Nicht G4-ready:** P00-Scope, RC3-Bestandsdaten, API-Idempotenz,
Processing-Aktivierung, DLQ-/Privacy-Live und SEC-06 bleiben offene
Entscheidungen. Keine neue AWS-Live-Ausführung in G3-FIX.

---

## 12. Auditlog

Vorgesehene Einträge:

- `MO-RC3-RC4-G3-FIX-DEFECT-CORRECTION` → dieser Bericht
- Agent A/B/C/D read-only entries aus G3-EXT bleiben referenziert
- keine AWS-/Terraform-Mutation in G3-FIX

---

## 13. Commits / CLEAN-Status

```text
Fix Privacy:  7d82ad42cffbac6f2a5ef59f763d61880e525bc2
Fix Recovery: 51094bf88ff2ece49ff29c63fefa70e2b43597d6
Build ZIP:    75a32fcf161dce6349406cda9e9b5e22c904a31a
Docs:         (dieser Commit)
```

Finaler Working Tree: CLEAN nach dem Doku-Commit. Kein Push, kein Merge.
