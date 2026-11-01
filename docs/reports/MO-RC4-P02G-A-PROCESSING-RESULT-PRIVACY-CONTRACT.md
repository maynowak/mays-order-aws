# MO-RC4-P02G-A-PROCESSING-RESULT-PRIVACY-CONTRACT

**Ergebnis-Datenvertrag + vollständige Privacy-Integration (ohne Ergebnis-Schreibpfad)**

**Datum:** 2026-11-01
**Branch:** `feature/mo-rc4-kms-privacy-retention`
**Basis:** `5af53dc7aec2b6ae01295eb48e54e3d1379141b8`
**Typ:** Implementierung + Tests (lokal) — keine AWS-Operation, kein Push

---

## 1. Git-Baseline

| Prüfung | Ergebnis |
|---|---|
| Branch | `feature/mo-rc4-kms-privacy-retention` ✔ |
| HEAD | `5af53dc` ✔ |
| Working Tree | CLEAN ✔ |
| P02–P02F | vorhanden |
| Tests vorher | 204/204 |

---

## 2. Bestehende Privacy-Semantik (vor Änderung, verifiziert)

| Funktion | Verhalten | Evidence |
|---|---|---|
| `inspect_subject` | GSI2-Query (`gsi2pk=SUBJECT#…`), liefert `orderReferences`, `dataCategories`; paginiert seit P02 | `order_service.py:311-378` |
| `export_subject` | GSI2-Query paginiert, baut Export-Items (orderId/status/createdAt/customer/totalAmount/currency) | ebd. `:380-450` |
| `erase_subject` | **PREVIEW/EXECUTE** mit Policy `ERASE`/`ANONYMIZE`/`RETAIN`; ohne Policy `BLOCKED` | `:452-600` |
| **ERASE** | `delete_item` mit `ConditionExpression subjectId=:sid [AND version=:ver]` | `:578-583` |
| **ANONYMIZE** | `update_item`: setzt `customer.name/email` auf `ANONYMIZED`, **entfernt** `subjectId`, `gsi2pk`, `gsi2sk` | `:584-597` |
| Auth | `_require_privacy_auth` (Projekt, `authorized`, Berechtigungsflag, Secret, `compare_digest`) | `:101-124` |
| Scope | optionaler `consumerId`-Scope (P02B, nur einschränkend) | `identity.py` |
| Konkurrenz | `subjectId` + `version` in der Bedingung; `ConditionalCheckFailed` → `skipped` | P02C |

**ERASE und ANONYMIZE sind unterschiedliche Operationen**, teilen aber denselben Query-/Loop-Rahmen.

### 2.1 Korrigierter Befund: GSI2 projiziert nicht alle abgefragten Felder

`terraform/modules/dynamodb/main.tf:66` projiziert:
`orderId, subjectId, version, createdAt, status, updatedAt, customer, totalAmount, currency`.
**Nicht** projiziert: `consumerId` (seit P02B in `ProjectionExpression`!) und alle
Verarbeitungsfelder.

DynamoDB erlaubt bei einer GSI-Query **nur projizierte** Attribute in der
`ProjectionExpression` — die bisherige Abfrage wäre in AWS mit `ValidationException`
gescheitert (Tests nutzen Fakes, daher lokal unentdeckt). **P02G-A korrigiert das ohne
Schemaänderung:**

- Query projiziert nur `orderId` (garantiert projiziert),
- danach `get_item(ConsistentRead=True)` je Order → vollständiges Item (Scope, customer,
  Verarbeitungsfelder).
- Kosten: +1 Read je gefundener Order (bei Auskunft/Löschung vertretbar); dokumentiert.

---

## 3. Ergebnis-Datenvertrag (vorbereitet, **nicht** schreibend)

Modul: `lambda/src/processing_result.py`

| Feld | Typ | Optional | Bedeutung |
|---|---|---|---|
| `processingState` | `pending`/`running`/`succeeded`/`failed` | ja | Zustand der Fachverarbeitung (kein Order-Status!) |
| `processingAttemptId` | String `[A-Za-z0-9._:-]{1,128}` | ja | Idempotenzschlüssel je Versuch |
| `result` | JSON-kompatibel, ≤ 16 KiB serialisiert | ja | kleines strukturiertes Ergebnis |
| `completedAt` | ISO-8601 UTC | ja | fachlicher Abschlusszeitpunkt |
| `processingError` | `{code?, message?}` | ja | kontrollierte Fehlerinfo |

- **Kein Feld wird initialisiert**; Bestandsdaten bleiben unverändert.
- **Kein Schreibpfad** in P02G-A (`RESULT_WRITE_GUARD` nur als Vertragskonstante).
- `resultRef` bewusst **nicht** aktiviert.

### Validierungsgrenzen (konservativ)

| Grenze | Wert |
|---|---|
| Serialisierte Größe | **16 KiB** (UTF-8 JSON) |
| Verschachtelungstiefe | **5** |
| Elemente pro Container | **100** |
| Schlüssellänge / Muster | ≤ 64, `^[A-Za-z0-9_.-]+$` |
| Stringlänge | ≤ 2 000 |
| `processingError.code` / `.message` | ≤ 64 / ≤ 500, **nur** diese zwei Felder |
| Nicht-JSON-Typen | abgelehnt (bytes, set, Objekte, Decimal erlaubt) |

**Wichtig:** Die Strukturvalidierung ist **keine** PII-Erkennung. `result` gilt
grundsätzlich als potenziell personenbezogen.

---

## 4. Privacy-Integration

### 4.1 Inspect (datensparsam)

Neu im Ergebnis:

```json
{"hasProcessingResult": true, "hasProcessingError": false, "processingStates": ["succeeded"]}
```

- **Keine Inhalte** aus `result`/`processingError` (Test: Secret-String taucht nirgends auf).
- `dataCategories` ergänzt um `processing.result` / `processing.error`.
- Scope- und Pagination-Regeln unverändert.

### 4.2 Export (vollständige Auskunft)

Übernimmt vorhandene Felder `processingState`, `processingAttemptId`, `result`,
`completedAt`, `processingError` **vollständig** (nur wenn vorhanden). Owner-/Scope-Filter
und Pagination unverändert. Legacy-Orders ohne Felder bleiben unverändert.

### 4.3 Anonymize (vollständige Entfernung)

`REMOVE subjectId, gsi2pk, gsi2sk, #result, #perr, #patt` — d. h.
**`result`, `processingError`, `processingAttemptId` werden komplett entfernt**
(keine selektive PII-Bereinigung). `processingState`/`completedAt` bleiben (technisch,
nicht personenbezogen). Bedingung (`subjectId` + `version`) unverändert.

### 4.4 Erase

Unverändert: das gesamte Item wird gelöscht — damit auch alle Ergebnisfelder.

### 4.5 Idempotenz / Konkurrenz

- Wiederholtes Anonymize: Query liefert nichts mehr (subjectId entfernt) bzw.
  `ConditionalCheckFailed` → `skipped`, Status `COMPLETED` (Test).
- Bedingung schützt vor gleichzeitigen Änderungen; ein Race kann weiterhin dazu führen,
  dass ein *später* geschriebenes Ergebnis die Anonymisierung „überholt" — siehe §7
  (Schutzbedingung für P02G-B).

---

## 5. API-Projektion (keine Offenlegung)

- Alle fünf Felder stehen in `INTERNAL_FIELDS` (`order_service.py`) → `to_public_order`
  entfernt sie in **POST/GET/PATCH**-Antworten (Tests).
- `POST`-Body akzeptiert sie **nicht** (Validator lehnt unbekannte Felder mit 400 ab).
- `to_list_item` listet sie nicht.
- Keine neue Route, keine Erweiterung bestehender Zugriffe.
- **V-10 bleibt offen** (Listen-/Owner-Checks) — P02G-A verschärft sie nicht, weil keine
  neuen Daten öffentlich werden.

---

## 6. Ownership

`subjectId`, `consumerId`, `ownerType`, `ownerId`, `actorType`, `actorId` werden weder
gesetzt noch gelesen für Ergebnisfelder; Ergebnisfelder sind keine Identitätsquelle
(Test: Anonymize behält Bedingung, Export nutzt weiterhin GSI2/Scope).

---

## 7. Voraussetzungen für P02G-B (dokumentiert, **nicht** implementiert)

1. **Schreibpfad nur intern** (nie API), atomar mit Status-/Processing-State.
2. **Guard:** `RESULT_WRITE_GUARD = "attribute_exists(subjectId)"` in die Bedingung
   aufnehmen → nach ANONYMIZE (subjectId entfernt) ist ein Ergebnis-Schreiben unmöglich.
   Nach ERASE existiert das Item nicht mehr.
3. **Bedingung zusätzlich** auf `processingState`/`processingAttemptId` (Idempotenz,
   Konflikt bei unterschiedlichen Ergebnissen).
4. **Storno:** Status `CANCELLED` ⇒ kein Ergebnis.
5. **Idempotenz:** gleicher `attemptId` + gleiches Ergebnis ⇒ `noop`; anderer Inhalt ⇒
   Konflikt (kein Überschreiben).
6. **Keine öffentliche Ausgabe** von `result` bis V-10 entschieden.

**BLOCKED für P02G-B, falls** ein Ergebnis nach ANONYMIZE ohne `subjectId`-Bedingung
geschrieben würde — der Guard ist deshalb verbindlicher Teil des Vertrags.

---

## 8. Tests

Neu: **29 Tests**

| Bereich | Anzahl | Inhalt |
|---|---|---|
| `test_processing_result.py` | 18 | State/AttemptId/completedAt/Error/Result-Grenzen (Tiefe, Items, Keys, Größe, Nicht-JSON), Summary ohne Inhalte, Feldvertrag, Guard |
| `test_order_service.py::TestProcessingResultPrivacyP02GA` | 9 | Inspect-Flags ohne Inhalt, Scope-Isolation, Export vollständig/legacy, Anonymize entfernt Ergebnis+Fehler+Attempt, Bedingung unverändert, Wiederholung sicher, öffentliche Projektion (GET/PATCH) |
| `test_index.py::TestProcessingFieldsNotPublicP02GA` | 2 | Body-Felder abgelehnt, GET ohne interne Felder |

Zusätzlich angepasst: GSI2-Query fakest jetzt nur `orderId` (projiziert); Test-Fixtures
liefern `get_item` aus dem Query-Store; zwei Legacy-Tests prüfen die **sichere** Projektion.

| Suite | Ergebnis |
|---|---|
| Lambda | **233/233 PASS** (vorher 204) |
| Module Builder | **90/90 PASS** |
| Installer | **81/81 PASS** |
| `terraform validate` | PASS (keine Schemaänderung) |
| `terraform fmt -check` | PASS |

---

## 9. Abschlusstabelle

| Prüfung | Ergebnis |
|---|---|
| Git-Baseline | `5af53dc`, clean |
| Privacy-Semantik vorher verstanden | ja (ERASE ≠ ANONYMIZE, Scope, Pagination, Conditions) |
| Ergebnis-Datenvertrag | IMPLEMENTED (Felder + Validierung, **ohne** Schreibpfad) |
| Validierungsgrenzen | IMPLEMENTED (16 KiB, Tiefe 5, 100 Items, Key-/Stringlimits) |
| Inspect | IMPLEMENTED (nur Flags/States, keine Inhalte) |
| Export | IMPLEMENTED (vollständig, nur vorhandene Felder) |
| Erase | unverändert (Item-Löschung umfasst Ergebnisse) |
| Anonymize | IMPLEMENTED (`result`, `processingError`, `processingAttemptId` entfernt) |
| API-Projektion | IMPLEMENTED (alle 5 Felder intern, Body abgelehnt) |
| Ownership / Scope | VERIFIED unverändert |
| Legacy-Kompatibilität | VERIFIED (keine Initialisierung, keine Felder in Antworten) |
| Konkurrenzschutz | VERIFIED (Condition unverändert; `skipped`-Pfad) |
| GSI2-Projektionsfehler | **BEHOBEN** (Query nur `orderId` + GetItem je Order) |
| Testergebnisse | 233/233 · 90/90 · 81/81 · validate/fmt PASS |
| Offene Risiken | Ergebnis-Race nach Anonymize (nur mit Guard in P02G-B lösbar) · V-10 · N Reads je Auskunft |
| Commit | siehe Abschlussbericht (dieser Commit) |
| Working Tree | clean nach Commit |

**Status:** Daten- und Datenschutzvertrag **IMPLEMENTED/VERIFIED**; Ergebnisübernahme
**OPEN (P02G-B)**; Agenten-Callbacks **BLOCKED**.
