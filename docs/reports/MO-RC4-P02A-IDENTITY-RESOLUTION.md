# MO-RC4-P02A-IDENTITY-RESOLUTION

**Zentrale Identitätsauflösung für Bestellungen**

**Datum:** 2026-11-01
**Branch:** `feature/mo-rc4-kms-privacy-retention`
**Basis:** `766f56e6e6625ac7607cba26371d098f61e89432` (P02)
**Typ:** interne Komponente (kein öffentlicher API-Vertrag)

---

## 1. Umsetzung (Dateien)

| Datei | Inhalt |
|---|---|
| `lambda/src/identity.py` (**neu**) | `OrderIdentity`, `resolve_order_identity`, `derive_consumer_id`, `canonical_key`, `classify_ownership` |
| `lambda/src/index.py` | `POST /orders` löst Identität zuerst auf (fail-closed), übergibt `identity` + `owner_id`; `extract_subject_id` bleibt als dünne Hülle |
| `lambda/src/order_service.py` | `create_order(..., identity=None)`; Identity-Felder in `INTERNAL_FIELDS`; Guard gegen Owner-Mismatch/nicht-User-Owner |
| `lambda/tests/test_identity.py` (**neu**) | 18 Tests: Namensräume, Kollisionen, Owner/Actor, Legacy-Klassifikation |
| `lambda/tests/test_index.py`, `test_order_service.py` | +9 Tests für Handler/Service-Integration |

## 2. Identitätsmodell

### 2.1 Real implementiert (persistiert)

| Feld | Typ | Quelle | Bedeutung |
|---|---|---|---|
| `consumerId` | string | verifiziert: `iss` + `client_id`/`aud` | Consumer-Namensraum, z. B. `cognito:cognito-idp.eu-central-1.amazonaws.com/eu-central-1_ABC#client-1` |
| `ownerType` | string | aufgelöst (`user`) | Eigentümer-Kategorie |
| `ownerId` | string | JWT `sub` | Eigentümer |
| `actorType` | string | aufgelöst (`user`) | ausführender Akteur |
| `actorId` | string | JWT `sub` | ausführender Akteur |
| `identityVersion` | number | `1` (aufgelöst) | Schema-Version der Zuordnung |

Zusätzlich unverändert bestehend: `subjectId` (= `ownerId` bei Benutzerbestellungen),
`gsi2pk`/`gsi2sk` (Privacy-Lookup).

### 2.2 Nur konzeptionell / nicht implementiert

| Element | Status | Grund |
|---|---|---|
| `ownerType = "agent"` bei Auflösung | **BLOCKED** | kein verifizierter Delegationsvertrag |
| `ownerType = "service"` bei Auflösung | **BLOCKED** | dito |
| Owner ≠ Actor in der API-Auflösung | **nicht erzeugbar** | `resolve_order_identity` liefert immer `user`/`user`; die Dataclass kann die Trennung abbilden (Test), der Aufrufpfad tut es nicht |
| Verifizierter Delegationsnachweis (signierter Kontext) | **nicht vorhanden** | Vertragsentscheidung offen (Q-06) |
| `tenantId` | **nicht vorhanden** | MO hat kein Tenant-Feld (P01) |

**Wichtig:** Ein Agent kann im Modell Owner sein oder für einen Owner handeln — beides ist
**modelliert**, aber **nicht aktiviert**, weil kein Vertrauensvertrag existiert. Es wurde
bewusst keine Ersatzidentität erfunden.

## 3. Vertrauensgrenzen

| Quelle | Vertrauenswürdig? | Verhalten |
|---|---|---|
| JWT-Claims des API-Gateway-Authorizers (`requestContext.authorizer.jwt.claims`) | **ja** (Gateway prüft Signatur/Audience) | einzige Identitätsquelle |
| Request-Body (`subjectId`, `ownerId`, `tenantId`, …) | **nein** | unbekannte Felder → 400 `VALIDATION_ERROR` |
| Header (z. B. `X-User-Id`) | **nein** | wird nicht gelesen |
| Fehlende Claims | — | 401 `UNAUTHORIZED`, kein Fallback |
| Fehlender Consumer (`iss` oder Client) | — | 401 `UNAUTHORIZED`, kein Fallback |

**Keine implizite Berechtigung** aus `consumerId`, `agentId` oder einer übermittelten
`ownerId`: Der Consumer bestimmt nur den Namensraum, nie die Berechtigung.

## 4. Kanonischer Schlüssel (Kollisionsprävention)

```text
v1|<len>:<consumerId>|<ownerType>|<len>:<ownerId>
```

Beispiel: `v1|52:cognito:cognito-idp…/eu-central-1_ABC#client-1|user|8:user-123`

- **Längenpräfixe** machen Trennzeichen in Komponenten unwirksam (Test mit `a|b`, `b|c`).
- **Consumer** trennt verschiedene Pools/Clients; **ownerType** trennt Benutzer/Agent/Dienst.
- **Stabil** bei wiederholten Aufrufen (Test: 5 Aufrufe → identischer Schlüssel).
- Ungültige Komponenten (leer, > 256 Zeichen, Steuerzeichen, Nicht-String) → Fehler.

**Nicht** verwendet: der Schlüssel wird **nicht** als DynamoDB-Partition/GSI-Wert
eingeführt (siehe Legacy-Bericht §4) — er dient der internen Eindeutigkeitsprüfung und
künftigen Verwendung.

## 5. Aufrufkette

```text
API Gateway (JWT-Autorizer, Payload 2.0)
  └─ index.handler
       └─ identity.resolve_order_identity_from_event(event)
            ├─ claims extrahieren (jwt.claims | REST-Stil)
            ├─ Consumer ableiten (iss + client_id/aud)  → 401 wenn unvollständig
            ├─ Owner/Actor = sub                        → 401 wenn unbrauchbar
            └─ OrderIdentity(version=1)
       └─ order_service.create_order(body, subject_id=owner, identity=identity)
            ├─ Guard: ownerType == user, subject == owner
            ├─ validate_create_order(body)              → 400 bei Fremdfeldern
            ├─ item.subjectId/gsi2pk/gsi2sk (unverändert)
            └─ item.consumerId/ownerType/ownerId/actorType/actorId/identityVersion
```

## 6. Tests (Auszug)

| Testfall | Ergebnis |
|---|---|
| Gleicher Owner, gleicher Consumer → stabil | ✅ |
| Gleiche Owner-ID, unterschiedliche Consumer → keine Kollision | ✅ |
| Gleiche ID, unterschiedliche Owner-Typen → keine Kollision | ✅ |
| Trennzeichen-Injektion → keine Vermischung | ✅ |
| Benutzer als Owner | ✅ |
| Agent als Owner (Modell) / Auflösung | ✅ Modell / **blockiert** in Auflösung |
| Agent handelt für Benutzer (Owner/Actor getrennt) | ✅ Modell, Pfad blockiert |
| Fehlende Consumer-Identität | ✅ 401 |
| Ungültige Owner-ID (leer/zu lang/Steuerzeichen/Nicht-String) | ✅ 401/400 |
| Wiederholte Auflösung | ✅ stabil |
| Legacy-Klassifikation (api_v1 / legacy_subject / legacy_unowned) | ✅ |

## 7. Risiken

| Risiko | Bewertung |
|---|---|
| Zwei Consumer im selben Deployment/Table | derzeit ausgeschlossen (ein Cognito-Pool je Deployment); `consumerId` macht es künftig erkennbar |
| `subjectId`-Kollision über Consumer hinweg | durch Consumer-Namensraum im Item erkennbar; GSI2 bewusst unverändert |
| Delegation ohne Vertrag | **blockiert**, kein Workaround |
| Modell „Agent als Owner" ungetestet gegen echte Verträge | dokumentiert, nicht aktiviert |

## 8. Akzeptanzkriterien

- [x] Zentrale Komponente statt verstreuter Claim-Leser.
- [x] Consumer, Owner und Actor sind getrennte Konzepte.
- [x] Keine implizite Berechtigung aus übermittelten IDs.
- [x] Kollisionsfreier Schlüssel mit Tests.
- [x] Bestehende API-Antworten unverändert (Identity-Felder sind intern).
- [x] Keine neue Benutzerverwaltung, keine neue Tabelle/GSI, keine AWS-Operation.
