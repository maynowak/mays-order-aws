# MO-RC4-P02H-A-ORDER-OWNER-CONSUMER-AUTHORIZATION

**V-10 Fix: Owner-/Consumer-Autorisierung der öffentlichen Order-API**

**Datum:** 2026-11-01
**Branch:** `feature/mo-rc4-kms-privacy-retention`
**Basis:** `796e97fe958a5db5a814e4a5f3537c0f487f9b53`
**Architekturentscheidung:** Variante D (gemeinsamer Helper + atomare DynamoDB-Bedingungen)
**Typ:** Implementierung + Tests (lokal) — keine AWS-Operation, kein Push

---

## 1. Git-Baseline

| Prüfung | Ergebnis |
|---|---|
| Branch | `feature/mo-rc4-kms-privacy-retention` ✔ |
| HEAD | `796e97f` ✔ |
| Working Tree | CLEAN ✔ |
| Tests vorher | 255/255 |

---

## 2. V-10-Ausgangslage (verifiziert)

| Lücke | Vorher | Evidence |
|---|---|---|
| **L-1 LIST** | GSI1 `LIST` ohne Filter → alle Orders | `order_service.py:259-286` (vorher) |
| **L-2 GET** | `get_item` per `pk`, keine Prüfung | `:250-257` (vorher) |
| **L-3 PATCH** | Condition nur `status`, keine Identität | `:288-311` (vorher) |
| L-4 Consumer | kein Scope in der API | `api/main.tf:31-34` |
| L-5 `staff` | Gruppe dokumentiert, ungenutzt | `cognito/main.tf:47-52` |
| L-6 Cancel | fremder Storno blockierte Processing | P02G-B-Bedingung |

---

## 3. Authorization Helper (implementiert)

`lambda/src/identity.py::authorize_order_access(item, identity)`:

```text
True  ⇔  identity vorhanden
      ∧  item.subjectId  vorhanden und == identity.owner_id
      ∧  item.consumerId vorhanden und == identity.consumer_id
```

- **Fail-closed:** fehlendes `subjectId` **oder** `consumerId` → `False` (Legacy).
- Reine Prüffunktion, keine Mutation, keine Ableitung aus `customer`/`actorId`/`ownerId`.
- Wird von GET, LIST und PATCH verwendet (eine Semantik, keine Duplikate).

---

## 4. Identitätsquellen (unverändert)

| Wert | Quelle | Vertrauensgrenze |
|---|---|---|
| `owner_id` (`sub`) | JWT-Authorizer-Claims | API Gateway prüft Signatur/Audience/Issuer |
| `consumer_id` | `iss` + `client_id`/`aud` | Authorizer pinnt Pool+Client |
| Body/Query/Header | **nicht** verwendet | Validator lehnt Fremdfelder ab (400) |
| `isAdmin`/`isSystem` | **nicht vorhanden** | keine Ausnahme implementiert |

`index.py` löst die Identität jetzt für **alle** öffentlichen Routen auf
(`:228`, `:233`, `:239`) → fehlende Claims ⇒ **401**.

---

## 5. LIST (`GET /orders`)

```text
identity = resolve(...)
limit/nextToken validieren
GSI2-Query: gsi2pk = SUBJECT#<owner_id>, Projection "orderId"
je Kandidat: GetItem (ConsistentRead) → authorize_order_access()
Stop bei limit, MAX_LIST_PAGES=10
Sortierung der Seite: createdAt absteigend
Cursor: GSI2-LastEvaluatedKey (base64 wie bisher)
```

- **Kein** GSI1-Fallback, **kein** Scan.
- Fremde Orders und Legacy-Orders werden verworfen.
- Dedupe über `orderId` (verhindert Doppel-Einträge bei Cursor-Wiederholung).
- Response-Format unverändert (`orders`/`count`/`nextToken`); interne Felder bleiben verborgen.
- Alte GSI1-Token → `ValidationException` → **400** (dokumentiert).

---

## 6. GET (`GET /orders/{orderId}`)

`_get_raw_order` (ConsistentRead) → `authorize_order_access` → `to_public_order`.
Fremd/fehlend/Legacy ⇒ `order_not_found` (**404**), keine Unterscheidung in der Antwort.

---

## 7. PATCH (`PATCH /orders/{orderId}/status`)

**Atomar** in derselben Conditional-Expression:

```text
Condition:
  attribute_exists(pk)
  AND #status = :currentStatus
  AND #subjectId = :owner
  AND #consumerId = :consumer
Update:
  SET status, updatedAt, version = if_not_exists(version, 0) + 1
```

- Kein TOCTOU, kein ungeschützter Fallback-Write.
- `if_not_exists` behebt zugleich den Legacy-`version`-Fehler aus dem P02H-Spike.
- Conflict-Behandlung: Re-Read → fremd/verschwunden = **404**, sonst **409**.
- Fremder Storno schlägt fehl (Test) und beeinflusst den Processing-Claim nicht.

---

## 8. Legacy-Verhalten

| Persistierte Identität | Zugriff |
|---|---|
| `subjectId` + `consumerId` passend | ALLOW |
| `subjectId` fehlt | **404** |
| `consumerId` fehlt | **404** |
| eines abweichend | **404** |

Keine Migration, keine Ableitung, keine Sonderregel.

---

## 9. Consumer-Isolation

- Beide Bedingungen sind Pflicht: gleiche `sub` mit anderem Consumer → **404**
  (Test `test_same_subject_other_consumer_is_404`).
- Der Authorizer pinnt Pool+Client zusätzlich; die Code-Prüfung ist Defense in Depth.
- Keine consumer-übergreifende Freigabe ohne Vertrag.

---

## 10. Fehlersemantik

| Situation | HTTP |
|---|---|
| Fehlende/ungültige Identität | 401 |
| Eigene Order gelesen | 200 |
| Eigene Order geändert | 200 (unverändert) |
| Nicht vorhanden | 404 |
| Fremd | 404 |
| Legacy ohne vollständige Identität | 404 |
| Eigener Konflikt | 409 |
| Ungültiger Request | 400 |

Bestehende Helfer (`unauthorized_error`, `order_not_found`, `conflicted_update`,
`validation_error`) wiederverwendet; keine neuen Detailmeldungen.

---

## 11. Worker-Kompatibilität

- Worker nutzt **keine** HTTP-Route; IAM-Zugriff (GetItem/UpdateItem) unverändert.
- P02C-Conditions, P02E-Routing, P02F-Recovery, P02G-B-Claims unberührt.
- Test `test_worker_runs_without_identity_context` belegt: kein Cognito-Kontext nötig.
- **Keine** `isSystem`/`isAdmin`-Flags eingeführt.

---

## 12. Privacy-Kompatibilität

Inspect/Export/Erase/Anonymize unverändert (interne Auth via Secret, GSI2, Scope).
P02G-A/B-Ergebnisbehandlung unverändert. Keine neue öffentliche Route.

---

## 13. Pagination

- Cursor = GSI2-`LastEvaluatedKey`; `ExclusiveStartKey` wird korrekt weitergeführt.
- Seiten mit herausgefilterten Orders: Schleife lädt bis `limit` oder Seitenende
  (Test mit 6 Orders, 3 fremd → 2 + 1, keine Verluste/Duplikate).
- `MAX_LIST_PAGES = 10` verhindert unbegrenzte Schleifen; der Cursor bleibt gültig.
- Sortierung je Seite nach `createdAt` absteigend (globale Sortierung über Seitengrenzen
  ist bei GSI2 nicht garantiert — dokumentierte Änderung gegenüber GSI1).

---

## 14. IAM-Befund

Handler-Rolle hat bereits `dynamodb:GetItem`, `dynamodb:Query` auf Tabelle **und**
GSI1/GSI2 (`terraform/modules/iam/main.tf:26-52`). Die neue GetItem/GSI2-Nutzung ist damit
**ohne IAM-Änderung** abgedeckt. **Keine IAM-Erweiterung vorgenommen.**

---

## 15. Tests

Neu: **26 Tests** (`test_order_access_authorization.py`).

| Bereich | Inhalt |
|---|---|
| Helper | beide Bedingungen, fehlende Felder, None |
| GET | eigen 200, fremd 404, anderer Consumer 404, Legacy 404, fehlend 404 |
| LIST | nur eigene, GSI2 statt GSI1, Consumer-Filter, Legacy-Filter, Pagination mit Filterung, keine internen Felder, ungültiger Cursor 400 |
| PATCH | atomare Bedingung (Owner+Consumer), fremd 404 ohne Write, fremder Storno, anderer Consumer, Legacy, Konflikt 409 ohne Fallback-Write, Konflikt+unlesbar 404 |
| Handler | GET/PATCH/LIST ohne Identität 401, mit Identität 200, Body-Override 400 |
| Worker | läuft ohne Cognito-Kontext |

Angepasst: bestehende Service-/Handler-Tests auf die neuen Signaturen und
`make_order`-Defaults (`subjectId`/`consumerId`), LIST auf GSI2.

| Suite | Ergebnis |
|---|---|
| Lambda | **281/281 PASS** (vorher 255) |
| Module Builder | **90/90 PASS** |
| Installer | **81/81 PASS** |
| `terraform validate` | PASS (keine Infra-Änderung) |
| `terraform fmt -check` | PASS |

---

## 16. Breaking Changes (bewusst, dokumentiert)

1. **Lesende Routen brauchen jetzt eine Identität** (401 ohne Claims).
2. **LIST zeigt nur eigene Orders** — die bisherige Staff-Sicht auf alle Orders entfällt.
3. **Legacy-Orders ohne `subjectId`+`consumerId` sind über die API unsichtbar** (404).
4. **Alte GSI1-`nextToken` werden mit 400 abgelehnt.**
5. **Sortierung** der Owner-Liste je Seite nach `createdAt` (nicht global über Seiten).
6. **+1 ConsistentRead** je gelesener/gelisteter Order (Kosten, Latenz minimal).

API-Doku `api/endpoints.md` (2.2–2.4) entsprechend aktualisiert.

---

## 17. Offene Risiken

| Risiko | Status |
|---|---|
| Legacy-Bestand ohne Identität ist per API unzugänglich (Backfill/Migration nötig) | **OPEN** (V-05) |
| Staff-/Admin-Sicht fehlt (kein verifizierter Vertrag) | **BLOCKED** |
| GSI2 ist eventual consistent (Query), GetItem konsistent → keine falsch-negativen Reads, aber kurzzeitig fehlende Listeneinträge möglich | **dokumentiert** |
| Sortierung über Seitengrenzen nicht global garantiert | **dokumentiert** |
| `MAX_LIST_PAGES` kann bei extrem vielen unberechtigten Einträgen früher stoppen (Cursor bleibt gültig) | **dokumentiert** |
| Externe Agenten/Delegation | **BLOCKED** (V-1/V-9) |

---

## 18. Commit

Commit-SHA: siehe Abschlussbericht (dieser Commit). Working Tree nach Commit CLEAN.
