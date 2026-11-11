# MO-RC4-TESTSUITE-HARDENING-10C

**Isolation, Auth-Grenzen, Fixtures, Cleanup und Diagnostik der RC4-Live-E2E-Suite**

**Datum:** 2026-11-11
**Referenz:** `test/mo-rc4-testsuite-hardening-10a` @ `7922bae9e1e0ac05f0b9786aaa976e5b408f1e41`
**Arbeitsbranch:** `test/mo-rc4-testsuite-hardening-10a`
**Modus:** ausschließlich lokale Testentwicklung und lokale Validierung;
keine Live-Requests, keine AWS-Schreiboperation, keine Cognito-Anlage,
kein Tokenabruf, kein Terraform, kein Backup/Restore, kein Push/Merge.

```text
MO-RC4-TESTSUITE-HARDENING-10C — VERIFIED
```

---

## 1. Git-Ausgangsbasis

| Feld | Wert |
|---|---|
| Referenzbranch | `test/mo-rc4-testsuite-hardening-10a` |
| Referenz-HEAD | `7922bae9e1e0ac05f0b9786aaa976e5b408f1e41` |
| 10A im Verlauf | `e703f96` |
| 10B im Verlauf | `7922bae` |
| Ausgangs-Working-Tree | CLEAN |
| Baseline | Installer 621, Builder 128, Lambda 337 = **1.086 PASS** |

---

## 2. Bestehende E2E-Architektur — Ist-Zustand

`tests/test_e2e_async_order.py` enthielt vier Live-Tests:

| Test | Problem |
|---|---|
| `TestAsyncOrderFlow.test_01_post_order_sends_to_sqs` | erzeugte `self.order_id` |
| `test_02_order_eventually_confirmed` | verwendete `self.order_id` aus Test 01; `skipTest`, wenn nicht vorhanden |
| `test_03_verify_order_data_integrity` | verwendete ebenfalls `self.order_id` aus Test 01 |
| `TestWorkerIntegration.test_sqs_message_processed` | prüfte global `ApproximateNumberOfMessages` der Queue, ohne Run-/Order-Bezug |

Weitere Befunde:

- `TestAsyncOrderFlow.setUpClass` beschaffte den Token zentral und übersprang bei
  fehlendem `TEST_USER_PASSWORD` die gesamte Klasse.
- `get_access_token()` rief `cognito.initiate_auth(...USER_PASSWORD_AUTH...)`
  auf; das ist Token-Erzeugung über eine echte Cognito-API.
- Die Suite hatte **keinen** Cleanup-Pfad und keine Eigentumszuordnung.
- Test 02/03 konnten ohne Test 01 nicht sinnvoll laufen.
- Der Default `API_BASE_URL` zeigte auf eine reale API; ein versehentlicher
  Lauf war nicht durch einen expliziten Opt-in geschützt.
- Der Worker-Test war nicht run-scoped und konnte fremde Queue-Zustände
  interpretieren.
- Fehlerausgaben enthielten keine strukturierte Test-/Run-/Cleanup-Diagnostik.

Es wurden keine Live-Aufrufe ausgeführt.

---

## 3. Implementierte Änderungen

### 3.1 Neue lokale Harness

`tests/e2e_harness.py` enthält:

- `resolve_auth()` — expliziter Live-Opt-in (`MO_E2E_LIVE=1`), `API_BASE_URL`
  und **vorab bereitgestellter** `ACCESS_TOKEN`; kein Cognito-Passwort-Flow,
  keine Token-Erzeugung.
- `AuthContext` — `PASS`/`BLOCKED` plus Blocked-Grund; Token wird nicht in
  `repr()` ausgegeben.
- `SyntheticOrder` / `build_synthetic_order()` — run-scoped, deterministische
  Testdaten mit `.invalid`-E-Mail und eindeutigem SKU-Marker.
- `E2ERun` — eigene Run-ID, eigene Order-Liste, eigener Cleanup-Ledger.
- `OwnedOrder` / `CleanupLedger` — Eigentumsprüfung, Cleanup-Erfolg/-Fehler,
  keine fremden Orders.
- `run_with_cleanup()` — Cleanup wird auch ausgeführt, wenn der Testkörper
  eine Exception wirft.
- `ApiClient` / `FakeTransport` / `Urllib3Transport` — lokal wird ausschließlich
  `FakeTransport` verwendet; `Urllib3Transport` wird nur von explizit
  freigegebenen Live-Tests konstruiert.
- `Diagnostic` / `redact()` — strukturierte Diagnostik und zentrale
  Secret-Redaktion.

### 3.2 Lokale Tests

`tests/test_e2e_harness.py` enthält 16 Tests:

- unabhängiger unauthentifizierter 401-Test mit Fake-Transport,
- Auth-Trennung ohne/mit Token,
- BLOCKED-/NOT-EXECUTED-/PASS-/FAIL-Klassifikation,
- run-scoped synthetische Fixtures,
- Cleanup bei Erfolg, Fehler und Testabbruch,
- Ablehnung fremder Orders,
- expliziter Cleanup-Unavailable-Blocker,
- Diagnostikfelder und Secret-Redaktion.

`tests/__init__.py` macht die lokalen E2E-Helfer als Paket importierbar.

### 3.3 Überarbeitete Live-Suite

`tests/test_e2e_async_order.py` enthält jetzt:

- `LiveE2EBase` mit eigener `E2ERun` pro Test,
- drei voneinander unabhängige authentifizierte Tests:
  - `test_post_order_creates_pending_order`
  - `test_order_transitions_to_confirmed_independently`
  - `test_order_data_integrity_independently`
- `TestLiveUnauthenticatedEndpoint.test_unauthenticated_get_orders_returns_401`
  ohne Token-Abhängigkeit,
- keinen globalen SQS-Queue-Count-Test mehr,
- **keinen** Live-Lauf ohne `MO_E2E_LIVE=1`, `API_BASE_URL`, Token und
  verfügbare sichere Cleanup-Fähigkeit.

Die authentifizierten Live-Tests sind aktuell absichtlich **BLOCKED**:
Es existiert keine sichere, eigentümergebundene Order-Löschoperation. Der
Cleanup-Guard verhindert jede Live-Order-Erzeugung, bevor Daten entstehen.

---

## 4. Testisolation

Jeder Live-Test:

1. erzeugt in `setUp()` seine eigene `E2ERun` mit eigener Run-ID,
2. ruft `_create_order()` selbst auf,
3. registriert die serverseitig erzeugte Order im eigenen Cleanup-Ledger,
4. verwendet kein `self.order_id` aus einer anderen Testmethode,
5. hat einen eigenen `tearDown`-Pfad.

Damit sind Test 02/03 nicht mehr von Test 01 abhängig. Der alte
`hasattr(self, "order_id")`-Skip ist entfernt.

---

## 5. Authentifizierungs- und Statusmodell

| Situation | Ergebnis |
|---|---|
| Kein Live-Opt-in | `BLOCKED` mit Opt-in-Grund |
| `MO_E2E_LIVE=1`, aber `API_BASE_URL` fehlt | `BLOCKED` |
| `MO_E2E_LIVE=1`, aber kein `ACCESS_TOKEN` | `BLOCKED` |
| Token vorhanden, aber keine sichere Cleanup-Fähigkeit | `BLOCKED` |
| Test ausgeführt und erfolgreich | `PASS` |
| Test ausgeführt und fehlgeschlagen | `FAIL` |
| Test nicht ausgeführt | `NOT EXECUTED` |

`unittest`-Skips werden für die Live-Tests verwendet, aber der Skip-Text beginnt
ausdrücklich mit `BLOCKED:` und nennt den konkreten Grund. Es gibt keinen
Cognito-Passwort-Flow und keine Token-Erzeugung.

---

## 6. Testdaten und Cleanup

### Synthetische Daten

Jede Order enthält:

- Run-ID im Customer-Namen und SKU-Marker,
- `.invalid`-E-Mail-Adresse,
- keine echten Kundendaten,
- keine festen produktiven Order-IDs.

### Cleanup-Regeln

`CleanupLedger` löscht nur, wenn:

- `order.run_id == current_run_id`,
- `order.owner_run_id == current_run_id`,
- eine Order-ID vorhanden ist,
- eine explizite Cleanup-Funktion übergeben wurde.

Fremde Orders werden mit `CleanupOwnershipError` abgelehnt; die Delete-Funktion
wird nicht aufgerufen. Cleanup-Fehler werden als `FAIL` im Ledger gespeichert
und als `CleanupError` weitergereicht — keine stille Unterdrückung.

### Live-Cleanup

Die RC4-API besitzt **keine** sichere, öffentliche Order-Delete-Route. Eine
direkte DynamoDB-Löschung ist ausdrücklich nicht implementiert. Deshalb gilt:

```text
LIVE CLEANUP — BLOCKED
```

Die authentifizierten Live-Tests erzeugen daher aktuell keine Orders. Eine
spätere Freigabe benötigt eine eigene, eigentümergebundene Cleanup-Schnittstelle
(z. B. einen autorisierten Test-Admin-Endpunkt mit Run-ID und Nachweis der
Zugehörigkeit) oder eine ausdrücklich freigegebene, auditierte
DynamoDB-Cleanup-Prozedur.

---

## 7. Testmatrix — lokale Validierung

| ID | Prüfung | Test | Ergebnis |
|---|---|---|---|
| T10C-01 | Unabhängige Live-Testfälle | `tests/test_e2e_async_order.py` (3 eigene Orders) | **PASS** (Struktur; Live BLOCKED) |
| T10C-02 | Auth-Trennung / fehlende Credentials | `TestUnauthenticatedBoundary`, `TestAuthClassification` | **PASS** |
| T10C-03 | Unabhängiger 401-Test | `test_unauthenticated_get_orders_is_independent_401` | **PASS** |
| T10C-04 | Synthetische Fixtures | `TestSyntheticData` | **PASS** |
| T10C-05 | Cleanup Erfolg/Fehler/Testabbruch/fremde Daten/unavailable | `TestCleanupSafety` | **PASS** |
| T10C-06 | Diagnostik und Redaktion | `TestDiagnostics` | **PASS** |
| T10C-02 | Live-Tests ohne Credentials | Live-Suite | **BLOCKED / SKIP** |

---

## 8. Fokussierte Testergebnisse

```bash
cd /tmp/opencode/rc4-upgrade-plan
python3 -m unittest discover -s tests -p 'test_e2e_harness.py'
```

```text
Ran 16 tests in 0.004s
OK
```

Live-Suite ohne Opt-in:

```bash
env -u MO_E2E_LIVE -u ACCESS_TOKEN -u API_BASE_URL \
  python3 -m unittest tests.test_e2e_async_order
```

```text
Ran 4 tests in 0.001s
OK (skipped=4)
```

Alle vier Skips sind mit `BLOCKED:` begründet; es wurde kein HTTP-Request
ausgeführt.

---

## 9. Regression

```bash
python3 -m unittest discover -s installer/tests
python3 -m unittest discover -s module_builder/tests
cd lambda && PYTHONPATH=src python3 -m unittest discover -s tests
```

```text
Installer:  Ran 621 tests — OK
Builder:    Ran 128 tests — OK
Lambda:     Ran 337 tests — OK
Gesamt:     1.086 PASS
```

Zusätzlich:

```text
Lokale E2E-Harness-Tests: 16 PASS (separat)
Live-E2E-Suite:           4 SKIP/BLOCKED (kein Live-Lauf)
```

---

## 10. Mutationstests

Mutationen wurden ausschließlich in temporären Kopien außerhalb des
Repositories durchgeführt.

### Mutation A — Eigentumsprüfung entfernt

`CleanupLedger.owns()` wurde auf `bool(order.order_id)` reduziert. Danach:

```text
FAIL: test_foreign_order_is_never_deleted
AssertionError: CleanupOwnershipError not raised
Ran 1 test — FAILED (failures=1)
```

Der Cleanup-Sicherheitstest erkennt die fehlende Eigentumsprüfung.

### Mutation B — Auth-Grenze entfernt

Die Prüfung

```python
if authenticated and not self.access_token:
    raise AuthUnavailable(...)
```

wurde aus `ApiClient.request()` entfernt. Danach:

```text
FAIL: test_authenticated_request_without_token_is_rejected
AssertionError: FakeTransport has no queued response
Ran 1 test — FAILED (failures=1)
```

Der Test erkennt, dass ein authentifizierter Request ohne Token nicht mehr
fail-closed abgewiesen wird.

---

## 11. Sicherheitsnachweise

| Prüfung | Ergebnis |
|---|---|
| Produktcode geändert | **NEIN** |
| Live-HTTP-Request | **NEIN** |
| AWS-API-Aufruf | **NEIN** |
| Cognito-Benutzer/Token erzeugt | **NEIN** |
| DynamoDB-Schreiboperation | **NEIN** |
| SQS-Nachricht | **NEIN** |
| Terraform-Mutation | **NEIN** |
| IAM-/CloudFront-/RIS-Änderung | **NEIN** |
| Backup/Restore | **NEIN** |
| Credentials in Diagnostik | **NEIN** — zentrale Redaktion |
| Fremde Orders gelöscht | **NEIN** — Ownership-Guard |

---

## 12. Verbleibende AWS-Live-Blocker

- Kein pre-provisioned Token in der Umgebung.
- Keine sichere, eigentümergebundene Order-Cleanup-Route.
- Live-Order-Erzeugung ist deshalb deaktiviert.
- Der 401-Test kann später unabhängig live ausgeführt werden, sobald
  `MO_E2E_LIVE=1` und `API_BASE_URL` freigegeben sind; im lokalen Lauf wird
  der Transport gemockt.
- Ein späterer Live-Lauf benötigt ausdrücklich eine neue Freigabe; dieser
  Auftrag führt keinen aus.

---

## 13. Git-Abschluss

Geplant:

```text
Branch:  test/mo-rc4-testsuite-hardening-10a
Commit:  test(rc4): isolate live e2e tests and harden cleanup
```

Kein Push, kein Merge. Der Commit-SHA und der CLEAN-Status werden nach dem
Commit verifiziert.
