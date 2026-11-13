# MO-RC4-P02-ORDER-OWNERSHIP

**Order Ownership & Privacy Consistency — Abschlussbericht**

**Datum:** 2026-11-01
**Branch:** `feature/mo-rc4-kms-privacy-retention`
**Basis:** `62f6b195bba9b4f0998f5ab3e2c0e450766753a3` (P01)
**Scope:** lokale Implementierung + Tests, **keine** AWS-Operation, **kein** Push

---

## 1. Ausgangslage (aus P01 bestätigt)

- `POST /orders` rief `create_order(body)` **ohne** `subject_id` (`index.py:143`) → keine
  `subjectId`, keine GSI2-Einträge → Privacy-Funktionen fanden API-Bestellungen nicht.
- Kein `userId`/`ownerId`/`tenantId`, keine Retention-Felder.
- `inspect_subject` las nur die **erste** DynamoDB-Seite.
- `erase_subject` zählte „Datensatz bereits weg" als **Fehler**.

## 2. P02-A — Ownership-Vertrag

| Aspekt | Umsetzung |
|---|---|
| Identitätsquelle | `extract_subject_id(event)` liest `requestContext.authorizer.jwt.claims.sub` (HTTP API v2). Defensiv zusätzlich flaches `authorizer.sub` (REST-Stil). |
| Keine Client-Kontrolle | Body-Feld `subjectId` bleibt unbekanntes Feld → 400 `VALIDATION_ERROR`; der Handler übergibt ausschließlich den JWT-Wert. |
| Fehlende Identität | **401 `UNAUTHORIZED`** (`errors.unauthorized_error`), kein Ersatz-Eigentümer. |
| Ungültige Identität | leer/Whitespace, > 256 Zeichen, Steuerzeichen → 401. Service prüft zusätzlich (Defense in Depth) → `VALIDATION_ERROR`. |
| Reihenfolge | Identität **vor** Body-Validierung (fail-closed). |
| Bestehende Verträge | `orderId`-Format, Statuswerte, Antwortstruktur unverändert. |

**Dateien:** `lambda/src/index.py` (`extract_subject_id`, POST-Route), `lambda/src/errors.py`
(`UNAUTHORIZED`), `lambda/src/order_service.py` (`_require_valid_subject_id`).

## 3. RIS-Consumer / Delegation — **STOP (blockiert)**

Die Aufgabe verlangt ausdrücklich: „Die aufrufende technische Identität darf nicht
automatisch mit dem fachlichen Eigentümer gleichgesetzt werden.“

**Befund:** Es existiert **kein** sicherer Delegationsvertrag für MO:

- Kein Feld/Claim für „handelt im Auftrag von" (`actor`, `on_behalf_of`, `tenantId`).
- Kein signierter Delegationsnachweis (Token-Assertion/Audience/Scope) im MO-Vertrag.
- RIS ruft die MO-API **nicht** auf (bestätigt in
  `MAYS-ORDERS-MODULARIZATION-01-B-…EXECUTION_LOG.md` §2): der Real-Adapter nutzt die
  RIS-eigene API; geschrieben wird direkt über `orders_reader` in die MO-Tabelle.
- Für diese Direktschreibungen setzt RIS **kein** `subjectId` und übergibt keine Identität.

**Entscheidung:** Es wurde **keine** Delegationslogik improvisiert. Der technische
Consumer-Pfad bleibt ungelöst und wird als eigene Vertragsentscheidung geführt
(siehe `MO-RC4-P01-OPEN-QUESTIONS.md` Q-06 und unten §9). Konsequenz: RIS-erzeugte
Bestellungen bleiben **eigentümerlos** und damit für Privacy unauffindbar — das ist
dokumentiert, nicht behoben.

**Wichtig:** Die Änderung bricht RIS nicht, weil RIS die MO-API nicht nutzt. Ein künftiger
technischer Consumer, der `POST /orders` aufruft, müsste einen Benutzerkontext
(JWT mit `sub` des Nutzers) mitbringen oder einen noch zu definierenden
Delegationsmechanismus verwenden.

## 4. P02-B — DynamoDB-Konsistenz

- `subjectId`, `gsi2pk` (`SUBJECT#<sub>`) und `gsi2sk` (`ord_<id>#<createdAt>`) werden jetzt
  **immer** geschrieben (vorher nur bei gesetztem Parameter).
- Statuswechsel (`PATCH`) ändern ausschließlich `status`, `updatedAt`, `version` —
  `subjectId`/GSI2 bleiben unangetastet (Test belegt: Update-Expression enthält sie nicht).
- **Keine** neue Tabelle, **keine** GSI-Änderung. Bestehende GSI2-Projektion enthielt
  `subjectId` bereits (`terraform/modules/dynamodb/main.tf`).

## 5. P02-C — Privacy-Konsistenz

| Aspekt | Vorher | Nachher |
|---|---|---|
| Bestellungen eines Benutzers auffindbar | nur wenn `subjectId` gesetzt (faktisch nie) | ja, für alle ab P02 erzeugten |
| `inspect` Pagination | nur erste Seite | vollständig paginiert (`LastEvaluatedKey`-Schleife) |
| `export` Pagination | vorhanden | unverändert (bereits korrekt) |
| Fremde Daten | GSI2-Query nach `subjectId` | unverändert; zusätzlich Bedingung `subjectId = :sid` + `version` |
| Fehlende Identität | `validation_error("Invalid subjectId")` | unverändert (weiterhin 400, keine Löschung) |
| Wiederholte Löschung | „bereits gelöscht" → `failedRecords > 0`, `PARTIALLY_COMPLETED` | `ConditionalCheckFailed` → `skippedRecords`, Status bleibt `COMPLETED` |
| Autorisierung | Projekt + `authorized` + Berechtigungsflag + Secret | **unverändert** (`_require_privacy_auth`) |

**Additives Feld:** `skippedRecords` im Erase-Ergebnis (und `0` im BLOCKED-Fall). Rein
additiv, keine Umbenennung, keine Entfernung.

## 6. P02-D — Bestandsdaten (keine Migration)

| Frage | Ergebnis |
|---|---|
| Wie viele Datensätze betroffen? | **Ohne AWS-Zugriff nicht bestimmbar.** Statische Belege: Demo-Seed enthält **0** `subjectId` (`grep -c` = 0); jede über die MO-API vor P02 erzeugte Bestellung hat keins; RIS-Direktschreibungen ebenfalls nicht. |
| Automatische Zuordnung? | **Nein** — es gibt keine verlässliche Quelle für die Nutzerzuordnung (kein `sub` gespeichert, keine Cognito-Verknüpfung). |
| Pauschale Löschung? | **Nein** — ausdrücklich ausgeschlossen. |
| Migrationsoptionen | (a) Bestand bleibt eigentümerlos und wird dokumentiert; (b) Consumer/Betreiber ordnet manuell zu (nur mit Nachweis); (c) Bestand wird nach einer Aufbewahrungsfrist archiviert/gelöscht — braucht Rechtsgrundlage und Freigabe. |
| Nicht auflösbar | Alle Datensätze ohne `subjectId`; RIS-Schreibungen (auch künftig, solange kein Delegationsvertrag existiert). |

**Keine Migration ausgeführt.**

## 7. P02-E — Tests

| Bereich | Neu |
|---|---|
| Handler: 401 ohne/bei leerer/malformierter Identität | 3 Tests (mit Subtests) |
| Handler: Body-`subjectId` überschreibt JWT nicht | 1 |
| Handler: flache Authorizer-Claims | 1 |
| Handler: lesende Routen unverändert | 1 |
| Service: Persistenz `subjectId`/GSI2 | 1 |
| Service: Owner-Pflicht (5 ungültige Varianten) | 1 (Subtest-Matrix) |
| Service: Body-Smuggling `subjectId` | 1 |
| Service: Statuswechsel erhält Owner | 1 |
| Service: zwei Benutzer → getrennte Partitionen | 1 |
| Privacy: `inspect`-Pagination über 3 Seiten | 1 |
| Privacy: idempotentes Erase (`skippedRecords`) | 1 |
| Privacy: Bedingung bindet `subjectId` + `version` | 1 |
| Privacy: nur eigene Datensätze | 1 |
| Privacy: Anonymize entfernt Owner-Link | 1 |
| Privacy: Erase ohne Policy bleibt BLOCKED | 1 |

**Ergebnis:** `93/93 PASS` (vorher 76; +17). Zusätzlich unverändert: Builder 90/90,
Installer 81/81.

Bestehende Tests wurden **angepasst, nicht abgeschwächt**: POST-Tests führen jetzt einen
JWT-Kontext mit; die Ablehnung ohne Identität ist durch neue Tests abgedeckt.

## 8. API-Kompatibilität

| Element | Änderung | Bewertung |
|---|---|---|
| Request-Body `POST /orders` | unverändert (weiterhin nur `customer`, `items`, `currency`) | kompatibel |
| Response `POST /orders` | unverändert (kein `subjectId` in der Antwort — `INTERNAL_FIELDS`) | kompatibel |
| `GET /orders`, `GET /orders/{id}` | unverändert, **kein** Auth-Zwang im Handler | kompatibel |
| `PATCH` | unverändert | kompatibel |
| Neuer Fehlerfall | 401 `UNAUTHORIZED` bei fehlender Identität — **bereits im Fehlerkatalog** (`api/endpoints.md` §3) | dokumentiert |
| Privacy-Erase-Antwort | + `skippedRecords` | additiv |
| Privacy-Inspect | vollständigere Ergebnisse (Pagination) | korrigierend |

**Verhaltensänderung:** Ein Aufruf von `POST /orders` ohne verifizierten JWT-Kontext wird
jetzt abgelehnt (vorher 201 ohne Eigentümer). Das ist die beabsichtigte Schließung der
P01-Lücke.

## 9. Security-Regression-Bewertung

| Prüfung | Ergebnis |
|---|---|
| Auth-Boundary `_require_privacy_auth` | unverändert (Projekt, `authorized`, Flag, Secret, `compare_digest`) |
| Cross-User-Schutz | verbessert (Bedingung `subjectId = :sid` + `version`; Query bleibt GSI2) |
| Kein Ersatz-Eigentümer | bestätigt (kein Default, kein Fallback) |
| Secret-Handling | unverändert (weiterhin Env; RC4-P03-Thema) |
| Logs | keine PII/Secrets hinzugefügt |
| Neue Rechte | keine |
| Abschwächung bestehender Checks | **keine** |

## 10. Offene Risiken

| Risiko | Status |
|---|---|
| Kein Delegationsvertrag für technische Consumer (RIS) | **OPEN** (blockiert, §3) |
| RIS-Direktschreibungen ohne `subjectId` | **OPEN** (Daten bleiben unauffindbar) |
| Bestandsdaten ohne Eigentümer | **OPEN** (dokumentiert, keine Migration) |
| Worker-Race (`CANCELLED→CONFIRMED` möglich) | **OPEN** (P01-Befund, nicht Teil von P02) |
| Kein DLQ/Retry | **OPEN** (separates Paket) |
| Retention-Fristen | **OPEN** (P03/P04) |

## 11. Akzeptanzkriterien

- [x] Neue Bestellungen sind zuverlässig einem verifizierten Benutzer zugeordnet.
- [x] Fremde/fehlende Identität führt zu kontrollierter Ablehnung, nie zu Fremdzuordnung.
- [x] Privacy-Inspect/Export/Erase finden API-Bestellungen vollständig (inkl. Pagination).
- [x] Keine fremden Daten werden zurückgegeben oder gelöscht.
- [x] Wiederholte Löschung ist sicher und meldet keinen Fehler.
- [x] Bestehende Autorisierung unverändert, keine Abschwächung.
- [x] Keine AWS-Operation, keine Migration, keine neue Tabelle/GSI.
