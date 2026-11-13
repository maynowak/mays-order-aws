# MO-RC4-P02B-RIS-COMPATIBILITY

**RIS-Schreibpfad, verfügbare Identitäten und minimaler Vertragszusatz**

**Datum:** 2026-11-01
**Quellen:** MO-Dokumentation + **read-only** RIS-Clone (`73965e3`), keine RIS-Änderung
**Ergebnis:** RIS-Eigentümerbindung **BLOCKED** (kein verifizierter Kontext, kein Transportweg)

---

## 1. Wo RIS Bestellungen tatsächlich erstellt

| Schritt | Ort | Beleg (RIS-Code) |
|---|---|---|
| Agent ruft Port auf | `agents/orders/function.py` → `OrdersPort.submit_order(work_item, capability, payload, tenant_id, actor_id, idempotency_key)` | `agents/orders/adapter.py:65-67` |
| Real-Adapter spricht **RIS-eigene API** | `agents/orders/real.py` (`DEFAULT_BASE_URL` = `mays-ris-dev-api`) | `real.py:99-110` |
| Bestellung wird **direkt in der MO-Tabelle** angelegt | `lambda/orders_reader.py` → `_create_order()` → `table.put_item(..., ConditionExpression="attribute_not_exists(pk)")` | `orders_reader.py:227-256` |
| MO-Tabelle/Queue | `ORDERS_TABLE`, `ORDERS_SQS_QUEUE_URL` | `orders_reader.py` Env |

## 2. Tatsächliche IAM-Rechte von `orders_reader` (verifiziert)

`terraform/modules/orders_reader/main.tf` Z. 38–60:

```text
dynamodb:GetItem, Query, UpdateItem, PutItem
  Resource: var.orders_table_arn, "${var.orders_table_arn}/index/*"
sqs:SendMessage
  Resource: var.orders_queue_arn
```

**Fazit:** Der Name täuscht — `orders_reader` ist ein **Schreiber** (Create + Status-Update)
mit Tabellen- und Indexzugriff. MO hat auf diesem Pfad **keine** Validierungsinstanz.

## 3. Welche Identitäten RIS hat und was sie verifiziert

| Identität | Vorhanden in RIS? | Verifiziert durch | Wird an MO übergeben? |
|---|---|---|---|
| RIS-Benutzer (`sub`) | ja (eigenes Cognito, JWT) | RIS API-Gateway-Authorizer | **nein** |
| `tenant_id` | ja (Work Item / `custom:tenant_id`) | RIS (Tenant-Isolation im Code) | **nein** (nur Log/Context) |
| `actor_id` | ja (Port-Parameter) | RIS (Work Item) | **nein** |
| Consumer-Kennung für MO | **nein** (kein Konzept) | — | **nein** |

Belege: `adapter.py:65-67,76-78` (Parameter), `real.py:160-162` (nur Logging),
`orders_reader.py` (kein `subjectId`/`tenant` im Item — `grep` ohne Treffer).

## 4. Kann der bestehende MO-Vertrag diese Informationen transportieren?

| Kanal | Geeignet? | Begründung |
|---|---|---|
| MO-Modul-Inputs (6) | **nein** | Deployment-Parameter, nicht pro Bestellung |
| MO-Modul-Outputs (20) | **nein** | Ausgaben, kein Transport |
| SQS-Nachricht an MO-Worker | **nein** | Worker ändert nur Status (`sqs_handler.py`), legt nichts an |
| MO-API `POST /orders` | **ja** | aber RIS nutzt sie nicht (Architekturentscheidung) |
| Direktschreiben in die Tabelle | technisch möglich | **keine** MO-Validierung, daher kein Sicherheitsgewinn |

## 5. Minimaler Vertragszusatz (Vorschlag, **nicht** implementiert)

Damit RIS eine **verifizierte** Bindung schreiben kann, braucht es **beides**:

### 5.1 Transport (RIS → MO-Daten)

Neue, **optionale** Item-Attribute beim Anlegen (gleiche Namen wie MO):

```text
subjectId            # Owner-Identität im MO-Namensraum
consumerId           # z. B. "ris:<tenant_id>" (abgestimmter Namensraum)
ownerType            # "user" (heute einziger zugelassener Wert)
ownerId              # == subjectId
actorType            # "user" | "agent" | "service"
actorId              # ausführender Akteur
identityVersion      # 1
identityVerification # "verified_internal_signed" (erst nach V-1)
```

**Kritisch:** `subjectId` muss im **MO-Namensraum** eindeutig sein. RIS-`sub`/`tenant_id`
sind **fremde** Namensräume. Ohne Consumer-Trennung würden gleiche IDs kollidieren
(siehe Privacy-Isolation). Zulässige Varianten:

| Variante | Beispiel | Bewertung |
|---|---|---|
| A — RIS schreibt MO-`sub` (Mapping-Tabelle) | MO-User-UUID | sauber, braucht Mapping (neue Datenhaltung → nicht erlaubt) |
| B — Composite-Owner `consumerId#ownerId` in `subjectId` | `ris:tenant-1#user-42` | kompatibel ohne neue Tabelle, **ändert GSI2-Semantik für neue Items** (Migrationsthema) |
| C — RIS schreibt weiter ohne Owner | — | Status quo, keine Privacy-Fähigkeit |

### 5.2 Verifikation (Warum darf RIS das?)

Ohne Nachweis ist jede RIS-Identität **unverifiziert**. Erforderlich (V-1):

- signierter, kurzlebiger Kontext (z. B. JWT mit `iss=ris`, `aud=mays-orders`, `owner`
  + `tenant` + `iat/exp`), **oder**
- beidseitig vereinbarte Service-Rolle mit expliziter Erlaubnisliste **und** Nachweis
  pro Bestellung (kein Blanko-Recht).

**Nicht ausreichend:** Existenz einer IAM-Rolle, `consumerId` im Body, `agentId`-String.

## 6. Was MO heute durchsetzt (und was nicht)

| Eigenschaft | MO-API | RIS-Direktschreiben |
|---|---|---|
| Consumer verifiziert | ✅ (JWT `iss`+`client`) | ❌ |
| Owner verifiziert | ✅ (`sub`) | ❌ |
| Actor getrennt | ✅ (Feld, heute = Owner) | ❌ |
| Bindung erzwungen | ✅ | ❌ (nur RIS könnte es) |
| Privacy-Auffindbarkeit | ✅ | ❌ (kein `subjectId`) |

## 7. Abwärtskompatibilität

| Aspekt | Status |
|---|---|
| RIS ruft MO-API nicht auf → P02/P02A/P02B brechen RIS nicht | ✅ bestätigt |
| MO liest RIS-Bestellungen weiterhin (GET/Liste) | ✅ unverändert |
| MO-Worker verarbeitet RIS-erzeugte `PENDING`-Bestellungen | ✅ unverändert (Status-Matrix) |
| RIS-Schreibformat (`pk` mit Doppelpräfix, kein `subjectId`) | ✅ weiterhin gültig |
| MO-Privacy findet RIS-Bestellungen | ❌ (unverändert; bewusst) |
| Neue Pflichtfelder | **keine** |

## 8. Erforderliche RIS-Anpassungen (separat, nicht durchgeführt)

1. **Entscheidung** V-1/V-3 (Delegationsformat + Owner-Namensraum).
2. RIS: Identität beim Anlegen mitgeben (Body-Erweiterung der RIS-eigenen API +
   `orders_reader` schreibt die Felder).
3. RIS: Mapping/Composite-Regel für `subjectId` umsetzen (Variante A oder B).
4. RIS: Tests für „Bestellung mit Owner“ und „Bestellung ohne Owner“.
5. Beide Seiten: Abnahme, dass Privacy-Erase die neuen Bestellungen findet.

**Aufwandsschätzung:** RIS-Seite ~1–2 PT nach Entscheidung; MO-Seite nur Doku/Test,
sofern Variante B gewählt wird (kein MO-Code nötig, da Felder bereits definiert sind).

## 9. Status

| Element | Status |
|---|---|
| RIS-Schreibpfad analysiert | ✅ VERIFIED (Code + IAM) |
| Risiko dokumentiert | ✅ |
| MO-seitiger Schutz des Direktschreibpfads | **nicht möglich** (architektonisch) |
| RIS-Eigentümerbindung | **BLOCKED** — wartet auf V-1/V-3 und RIS-Umsetzung |
| Rückwärtskompatibilität | ✅ (keine Änderung an RIS nötig) |
