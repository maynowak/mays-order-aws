# Order-Erasure-Ledger V1 — Vertrag und Architektur (P3E-01)

**Status:** lokales Domainmodell + Reconciliation-Planer; **keine Persistenz, kein AWS,
keine Änderung am Erasure-Consumer**.
**Code:** `installer/core/order_erasure_ledger.py` · **Tests:** `installer/tests/test_order_erasure_ledger.py`
**Bericht:** `docs/reports/MO-ORDER-ERASURE-LEDGER-P3E-01.md`

---

## 1. Belegte Erasure-Semantik (Ist-Zustand)

Quelle: `lambda/src/order_service.py`, `lambda/src/identity.py`, Tests.

| Eigenschaft | Implementiert | Verifiziert | Offen |
|---|---|---|---|
| ERASE | `DeleteItem` mit `subjectId`/`version`-Condition | Ja (Unit + Fake-DB) | kein Tombstone, kein Ledger, kein Nachweis |
| ANONYMIZE | `customer.name/email = ANONYMIZED`, entfernt `subjectId`, GSI2, `result`, `processingError`, `processingAttemptId`, GSI3 | Ja | Order bleibt mit `orderId`/Betrag; kein Nachweis |
| RETAIN | zählt nur, keine Mutation | Ja | kein Nachweis; `RETAIN` ist **keine** Löschung |
| Idempotenz | `ConditionalCheckFailedException` → `skippedRecords`, kein Fehler | Ja | keine Wiederholungs-/Resume-Logik für `failedRecords` |
| Consumer-Isolation | optionaler `consumerId`-Scope filtert | Ja | ohne Scope deployment-weit; Legacy ohne `consumerId` wird nicht zugeordnet |
| Subject-Identifikation | `subjectId`/JWT-`sub`, GSI2 | Ja | keine pseudonymisierte Ledger-Referenz |
| Löschabschluss | Response `status=COMPLETED/PARTIALLY_COMPLETED/BLOCKED` | Ja | nicht persistent, nicht attestierbar |
| Restore-Schutz | — | — | **MISSING** |

### Wichtige Details

- **ERASE** löscht das Item hart. Es bleibt kein Löschmarker zurück; nach dem Löschen
  ist nicht mehr feststellbar, dass und wann gelöscht wurde.
- **ANONYMIZE** entfernt die Owner-Verknüpfung (`subjectId`, GSI2), setzt
  `customer.name/email` auf `ANONYMIZED`/`anonymized@example.com` und entfernt
  Ergebnis-/Fehlerfelder. Die Order selbst (inkl. `orderId`, Betrag, Zeitstempel)
  bleibt bestehen.
- **RETAIN** verändert keine Daten. Bei `retainedRecords > 0` lautet der Status
  `PARTIALLY_COMPLETED`; das ist **keine** Aussage „gelöscht“.
- **Teilfehler:** Die Schleife zählt `failedRecords` und macht weiter; es gibt keinen
  automatischen Retry und keinen persistenten Abschlussnachweis.
- **Idempotenz:** Ein bereits gelöschtes/parallel geändertes Item wird als `skipped`
  gewertet; das ist fachlich kein Fehler, aber auch kein Beleg für die Zielerreichung.
- **Auth:** `privacy/erase` ist nur intern (direkter Lambda-Invoke), mit Projekt-,
  Berechtigungs- und `PRIVACY_INTERNAL_SECRET`-Prüfung. Der Consumer-Scope stammt aus
  dem internen Auth-Kontext und ist optional.
- **Ausgabe:** Die Antwort enthält `subjectId` und Zähler; sie darf nicht in Logs oder
  Ledger übernommen werden.

**Fazit:** Es gibt heute **keine** Historie, die einen Restore überlebt, und **keinen**
Nachweis, welche Orders/Subjects von einer Löschung betroffen waren.

---

## 2. Vertrag `OrderErasureLedgerV1`

### 2.1 Ledger-Metadaten

| Feld | Typ | Pflicht | Zweck |
|---|---|---|---|
| `schemaVersion` | int | ja (1) | Fail-closed bei unbekannter Version |
| `ledgerId` | string | ja | Eindeutige Ledger-Instanz |
| `source` | string | ja | Revisionsquelle (Store/Region/Stream) |
| `completeHistory` | bool | ja | Nur `true` erlaubt Reconciliation |
| `coveredFrom` | ISO-8601 | ja | Beginn der nachgewiesenen Historie |
| `coveredUntil` | ISO-8601 | ja | Ende; muss Restore-Zeitpunkt abdecken |
| `createdAt` | ISO-8601 | optional | Erzeugungszeitpunkt |
| `events` | Liste | ja | Append-only Ereignisse |

### 2.2 Ereignis

| Feld | Typ | Pflicht | Anmerkung |
|---|---|---|---|
| `eventId` | string | ja | eindeutig; Dubletten mit gleichem Inhalt werden dedupliziert |
| `operationId` | string | ja | fachlicher Vorgang (eine Erase-Anforderung) |
| `operation` | enum | ja | `ERASE` / `ANONYMIZE` / `RETAIN` |
| `consumerId` | string | ja | Tenant-/Partner-Scope |
| `subjectRef` | string | ja | HMAC-pseudonymisiert, nie Roh-`sub` |
| `orderRefs` | string[] | ja | `ord_` + 24 Hex; keine Payloads |
| `decidedAt` | ISO-8601 | ja | fachliche Entscheidung |
| `appliedAt` | ISO-8601 | bei Anwendung | tatsächlicher Abschluss; `>= decidedAt` |
| `status` | enum | ja | `COMPLETED` / `PARTIALLY_COMPLETED` / `BLOCKED` / `FAILED` |
| `idempotencyKey` | string | ja | Dedupe; gleicher Key mit anderem Inhalt → Konflikt |
| `affectedRecords` | int | nein | Zähler aus der Response |
| `deletedRecords` | int | nein | Zähler |
| `anonymizedRecords` | int | nein | Zähler |
| `retainedRecords` | int | nein | Zähler (keine Löschung) |
| `skippedRecords` | int | nein | Idempotenz-/Conditional-Skip |
| `failedRecords` | int | nein | Teilfehler |
| `integritySha256` | hex | ja | SHA-256 über kanonisches Event-Payload |

`integritySha256` erkennt versehentliche/manipulative Änderungen, ist aber **keine
Signatur** und kein Ersatz für einen unabhängig geschützten Store.

### 2.3 Datensparsamkeit

Nicht im Ledger: Namen, E-Mail, Telefon, Anschrift, `customer`-Payload, `items`,
Beträge, Tokens, Secrets, vollständige Order-Objekte. Gespeichert werden nur
pseudonyme Subject-Referenz, Order-IDs und Zähler/Zeitpunkte.

### 2.4 Pseudonymisierung

- **Keyed HMAC-SHA256** über `subjectId`, Schlüssel ≥ 32 Byte, `keyId` im Klartext.
- Kein ungesalzener Hash niedrig-entropischer IDs (z. B. E-Mail) als „anonym“.
- Der Schlüssel wird **nie** im Ledger gespeichert; Produktion über
  Secrets Manager/KMS (noch nicht implementiert; ADR-008 D-5/D-6 PROPOSED).
- Rotation: neuer `keyId`, alter Schlüssel bleibt nur zur Verifikation alter
  Referenzen erhalten; Rotation ist ein eigener, freigegebener Vorgang.
- Eine pseudonymisierte Referenz ist **weiterhin personenbezogen**, solange eine
  Zuordnung möglich ist. Keine Anonymitätsbehauptung.

---

## 3. Speichervarianten

| Kriterium | A: Items in Order-Tabelle | B: Separate Ledger-Tabelle | C: Revisions-Event-Store |
|---|---|---|---|
| Restore-Isolation | **schlecht** (wird mitrestauriert/überschrieben) | gut | **sehr gut** |
| Zugriffsschutz | geteilt mit App-Rolle | eigene Rolle | eigene Rolle + Audit |
| Datenschutz | Ledger im selben Backup | separat löschbar | separat löschbar |
| Aufbewahrung | an Order-Retention gekoppelt | eigene Retention | eigene Retention |
| Kosten | gering | gering | höher |
| Wiederherstellbarkeit | mit Order | separat | separat, revisionsgeeignet |
| Konsistenz | gleiche Tabelle | eventual/dual-write | Event-Stream/Append |
| Komplexität | niedrig | mittel | hoch |

**Empfehlung (PROPOSED, nicht umgesetzt):** **Option C** für einen unabhängigen,
append-only Event-Store; **Option B** als pragmatische Zwischenstufe, wenn C nicht
freigegeben wird. **Option A ist für Restore-Schutz ungeeignet**, weil ein Restore
der Order-Tabelle die Historie zurücksetzen könnte.

In P3E-01 wird **keine** Ressource angelegt.

---

## 4. Reconciliation

```text
Restore-Kontext (Tabelle, ARN, Zeitpunkt, Backup-Zeitpunkt)
  → Ledger laden/validieren (Schema, Integrität, Vollständigkeit, Abdeckung)
  → Ereignisse nach appliedAt einordnen
  → ERASE/ANONYMIZE/RETAIN je Order auswerten
  → Konflikte/fehlende Voraussetzungen sammeln
  → Plan (DELETE/ANONYMIZE/RETAIN) — keine Ausführung
  → Readiness: REVIEW_REQUIRED/BLOCKED, Cutover immer BLOCKED
```

### Zeitlogik

- `appliedAt >= restoreAt`: Ereignis ist im Restore **nicht sicher** enthalten →
  Aktion einplanen (erneutes Löschen/Anonymisieren ist idempotent).
- `appliedAt < restoreAt`: Zustand muss im Restore bereits sichtbar sein; Abweichung
  ist ein Konflikt (z. B. Item trotz ERASE vorhanden).
- `decidedAt` allein reicht nicht; verspätete Anwendung wird über `appliedAt` erfasst.
- `RETAIN` wird nie in eine Löschung übersetzt.

### Fail-closed

| Code | Bedeutung |
|---|---|
| `ORDER_LEDGER_MISSING` | kein Ledger |
| `ORDER_LEDGER_SCHEMA_UNKNOWN` | unbekannte Version |
| `ORDER_LEDGER_INCOMPLETE` | `completeHistory=false` oder Abdeckung fehlt |
| `ORDER_LEDGER_MISSING_FIELD` | Pflichtfeld fehlt |
| `ORDER_LEDGER_INTEGRITY_MISSING` | Integritätsfeld fehlt |
| `ORDER_LEDGER_INTEGRITY_MISMATCH` | Event manipuliert |
| `ORDER_LEDGER_DUPLICATE_CONFLICT` | gleiche ID/Idempotenz, anderer Inhalt |
| `ORDER_LEDGER_CONFLICTING_EVENTS` | ERASE vs. RETAIN/ANONYMIZE o. ä. |
| `ORDER_LEDGER_INVALID_CHRONOLOGY` | Zeitreihenfolge ungültig |
| `ORDER_RESTORE_IDENTITY_MISMATCH` | Restore-Tabelle/ARN/Account/Region falsch |
| `ORDER_LEDGER_RESTORE_TIME_MISSING` | Restore-Zeitpunkt fehlt |
| `ORDER_LEDGER_CONSUMER_UNKNOWN` | Consumer-Scope fehlt |
| `ORDER_LEDGER_ORDER_KEY_UNKNOWN` | Order-Key entspricht nicht der Konvention |
| `ORDER_LEDGER_PARTIAL_APPLICATION` | Ereignis nicht vollständig angewendet |
| `ORDER_LEDGER_NO_HISTORY` | leere Historie ist kein Nachweis |
| `ORDER_RESTORE_CUTOVER_BLOCKED` | Cutover ohne Ausführungsnachweis |

Zusätzlich: keine automatische Freigabe bei leerer Restore-Menge oder ohne Aktionen;
ein vollständiger Plan ist nur `PLAN_VERIFIED`, **nicht** ausgeführt.

---

## 5. Grenzen

- Keine Persistenz, kein Store, keine AWS-Ressource.
- Kein Eingriff in `erase_subject`; der Consumer schreibt noch kein Ledger.
- Keine echte Order-Datenänderung; nur Plan.
- Kein Restore, kein Cutover, keine Migration.
- Kein Nachweis, dass die bestehende Löschung vollständig ist.
- Keine Rechtsgrundlage/Fristen festgelegt (siehe Retention-Entscheidungen).
