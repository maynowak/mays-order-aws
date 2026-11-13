# MO-RC4-P02A-LEGACY-COMPATIBILITY

**Abwärtskompatibilität, Bestandsdaten und RIS-Realität**

**Datum:** 2026-11-01
**Basis:** `766f56e` (P02), P02A-Implementierung
**Typ:** Analyse + dokumentiertes Verhalten (keine Migration)

---

## 1. Ausgangsbeobachtung: `orders_reader` liest **und schreibt**

Auftrag: „Nicht voraussetzen, dass `orders_reader` ausschließlich liest.“

**Verifiziert am RIS-Code** (read-only Clone, Commit `73965e3`,
`terraform/modules/orders_reader/main.tf` Z. 38–60; `lambda/orders_reader.py`):

| Recht | Vorhanden | Beleg |
|---|---|---|
| `dynamodb:GetItem` | ja | IAM-Statement |
| `dynamodb:Query` | ja | IAM-Statement |
| `dynamodb:UpdateItem` | **ja** | IAM-Statement |
| `dynamodb:PutItem` | **ja** | IAM-Statement (`orders_reader.py:244`, `ConditionExpression="attribute_not_exists(pk)"`) |
| `sqs:SendMessage` | ja | IAM-Statement (Queue des MO-Projekts) |
| Ressourcen | `orders_table_arn` + `/index/*` | IAM-Statement |

**Folge:** RIS erzeugt Bestellungen **direkt in der MO-Tabelle**, ohne MO-API und ohne
`subjectId`/Identity-Felder. Solche Datensätze sind für MO **nicht** als „verwaist“
erkennbar (siehe P01-Orphan-Design) und bleiben eigentümerlos.

## 2. Kompatibilitätsfälle

### Fall A — Neue API-Bestellungen (JWT)

| Garantie | Status |
|---|---|
| `subjectId` aus verifiziertem JWT | ✅ unverändert (P02) |
| Keine Body-Identität | ✅ 400 `VALIDATION_ERROR` |
| Fehlende Identität → Ablehnung | ✅ 401 `UNAUTHORIZED` |
| Antwortstruktur unverändert | ✅ Identity-Felder sind in `INTERNAL_FIELDS` |
| Zusätzlich (P02A) | `consumerId`/`ownerType`/`ownerId`/`actorType`/`actorId`/`identityVersion` gespeichert |

**Verhaltensänderung gegenüber P02:** Ein Aufruf mit `sub`, aber **ohne** `iss`/`client_id`
(oder `aud`) wird jetzt mit 401 abgelehnt. Grund: ohne Consumer ist die Identität nicht
abgrenzbar. Bei echten Cognito-Token sind beide Claims immer vorhanden.

### Fall B — Bestehende RIS-Integration

| Aspekt | Befund |
|---|---|
| Ruft RIS die MO-API auf? | **Nein** — RIS nutzt die eigene API; der Real-Adapter spricht `mays-ris-dev-api` an |
| Schreibt RIS in die MO-Tabelle? | **Ja** — `orders_reader` (Put/Update) |
| Setzt RIS `subjectId`? | **Nein** (kein Treffer in `orders_reader.py`) |
| Bricht P02/P02A RIS? | **Nein** — RIS nutzt die geänderten Pfade nicht |
| RIS-Bestellungen erhalten Owner? | **Nein** — sie bleiben `legacy_unowned` |

**Vertragsentscheidung erforderlich (nicht improvisiert):** Wenn RIS-Bestellungen einem
Benutzer zugeordnet werden sollen, braucht es einen **verifizierbaren Delegationskontext**
(z. B. signiertes `ownerAssertion`/Token mit Audience + Berechtigungsscope) **oder** die
Umstellung von RIS auf die MO-API mit Benutzer-JWT. Beides ist eine Entscheidung
(Q-06 in `MO-RC4-P01-OPEN-QUESTIONS.md`), keine Implementierungsfreiheit.

### Fall C — Bestehende Bestellungen **mit** `subjectId`

| Verhalten | Status |
|---|---|
| Zuordnung bleibt erhalten | ✅ (keine Mutation) |
| Neue Identity-Felder werden **nicht** nachgetragen | ✅ (keine Migration) |
| Klassifikation | `legacy_subject` → `ownerType=user`, `ownerId=subjectId`, `consumerId=null` |
| Privacy inspect/export/erase | ✅ unverändert (GSI2 `SUBJECT#<subjectId>`) |
| Automatische Neuzuordnung zu anderem Consumer/Typ | ❌ ausgeschlossen |

Begründung der `ownerType=user`-Ableitung: `subjectId` wurde ab P02 ausschließlich aus dem
verifizierten JWT-`sub` geschrieben (Vertrag), nicht aus Client-Daten.

### Fall D — Bestellungen **ohne** `subjectId`

| Verhalten | Status |
|---|---|
| Bestand bleibt erhalten | ✅ |
| Automatische Eigentümerzuweisung | ❌ (kein Nachweis möglich) |
| Pauschale Löschung | ❌ |
| Automatische Migration | ❌ |
| Klassifikation | `legacy_unowned` (ownerType/OwnerId/consumerId = null) |
| Privacy-Funktionen | finden sie **nicht** (korrekt: keine nachgewiesene Beziehung) |

**Quantifizierung ohne AWS:** nicht möglich. Statisch belegbar:
- Demo-Seed: **0** Datensätze mit `subjectId` (`grep -c` = 0).
- Alle über die MO-API **vor** P02 erzeugten Bestellungen: ohne `subjectId`.
- Alle RIS-Direktschreibungen: ohne `subjectId`.
Eine belastbare Zahl erfordert einen read-only AWS-Zugriff (nicht Teil dieses Auftrags).

### Fall E — Neue Agenten-/Service-Identitäten

| Aspekt | Status |
|---|---|
| Modell (Dataclass) kann Agent/Service als Owner und getrennten Actor abbilden | ✅ (`test_agent_can_act_for_user_without_becoming_owner`) |
| Auflösung über den HTTP-Pfad | **BLOCKED** — `resolve_order_identity(delegated=…)` → 400 mit klarer Meldung |
| Automatische Gleichsetzung Actor = Owner | ❌ (nie) |
| Ersatzidentität bei fehlendem Vertrag | ❌ (nie) |

## 3. Bestehende DynamoDB-Schlüssel

**Unverändert:**

```text
pk       = "ord_<id>"
sk       = "#ORDER"
gsi1pk   = "LIST"          (Listing)
gsi2pk   = "SUBJECT#<subjectId>"   (Privacy)
gsi2sk   = "ord_<id>#<createdAt>"
```

**Neu (nur Attribute, keine Schlüssel):** `consumerId`, `ownerType`, `ownerId`,
`actorType`, `actorId`, `identityVersion`.

Konsequenz: Kein Item verliert seine Auffindbarkeit; keine Reindexierung; kein Backfill.

## 4. Auswirkung auf GSI2 und Privacy

| Prüfung | Ergebnis |
|---|---|
| GSI2-Definition geändert? | **Nein** (`terraform/modules/dynamodb/main.tf` unberührt) |
| Bestehende Items weiterhin auffindbar? | **Ja** — Partitionsschlüssel identisch (`SUBJECT#<subjectId>`) |
| Neue Items auffindbar? | **Ja** — `subjectId` wird weiterhin geschrieben |
| Privacy-Inspect/Export/Erase geändert? | **Nein** (nur P02-Fixes: Pagination, idempotentes Erase) |
| Cross-Owner-Zugriff möglich? | **Nein** — Query nur eigene Partition + Bedingung `subjectId`/`version` |
| `consumerId` im Privacy-Pfad genutzt? | **Nein** (bewusst; Änderung wäre ein eigener Vertrag) |

## 5. Rückwärtskompatibilität der Service-Schnittstelle

| Aufruf | Verhalten |
|---|---|
| `create_order(body, subject_id="x")` | wie P02: `subjectId`/GSI2, **keine** Identity-Felder (keine erfundene Identität) |
| `create_order(body, identity=OrderIdentity(...))` | `subjectId` = `identity.owner_id`, Identity-Felder gespeichert |
| `create_order(body, subject_id="y", identity=owner "x")` | 400 (Mismatch) |
| `create_order(body)` | 400 (Owner fehlt) |
| `create_order(body, identity=… ownerType="service")` | 400 (nicht unterstützt) |

## 6. Teststrategie / Nachweise

| Nachweis | Test |
|---|---|
| JWT-POST unverändert (201, Felder versteckt) | `TestOrderOwnershipPersistence` + `TestIdentityPersistenceP02A` |
| Legacy nur `subjectId` | `test_legacy_subject_only_call_remains_supported` |
| Legacy ohne `subjectId` klassifiziert, nicht zugeordnet | `test_legacy_unowned_item_invents_nothing` |
| Keine GSI2-Änderung | `test_identity_fields_are_persisted_and_hidden` (prüft `gsi2pk`) |
| Privacy nutzt weiterhin `SUBJECT#…` | `TestPrivacyConsistency` (unverändert grün) |

## 7. Offene Punkte

1. RIS-Bestellungen bleiben eigentümerlos (Vertrag fehlt).
2. Bestandsdaten ohne `subjectId` bleiben unzugeordnet (kein Backfill).
3. Einmalige Erhebung der betroffenen Anzahl benötigt read-only AWS-Zugriff.
4. `consumerId` ist noch kein Privacy-Filter (bewusst).
