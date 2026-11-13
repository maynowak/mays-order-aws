# MO-AGENT-ORDER-OWNERSHIP-02 — Phase 2: Verified Owner Enforcement

**Datum:** 2026-11-13
**Typ:** Lokale Implementierung + Tests (kein Apply, kein Deployment, kein Merge)
**Ergebnis:** COMPLETE für S1–S6. Eigentümerbindung wird auf Create, Get, List und Patch durchgesetzt.

## 1. Ausgangslage

| Feld | Wert |
|---|---|
| Branch | `feature/mo-agent-order-body-01` |
| Parent | `3ca1730` (Phase 1) |
| Zielbasis | `9627eb2` (RC2-/Modul-Contract-Linie, kein RC4) |

Umgesetzte Entscheidungen: **O1** fail-closed, **O2** eigener Index, **O3** kein
Gruppen-Bypass, **O4** interner Result-Boundary erst in A06.

## 2. S1 — Identity

`lambda/src/identity.py` (neu):

- liest **nur** `requestContext.authorizer.jwt.claims`;
- verlangt `iss` **und** `sub`; `sub` allein genügt nicht;
- prüft `iss` gegen den konfigurierten Issuer, wenn gesetzt;
- prüft `aud`/`client_id` gegen den konfigurierten Client, wenn gesetzt;
- akzeptiert nur `token_use` ∈ {`id`, `access`} (wenn vorhanden);
- `OwnerIdentity.owner_key = sha256(iss + "\x00" + sub)`;
- keine Identität aus Header, Query, Pfad oder Body.

**Fail-closed auch bei Konfigurationsfehlern:** Fehlen `ORDERS_COGNITO_ISSUER`
oder `ORDERS_COGNITO_CLIENT_ID`, antwortet der Dienst `503 SERVICE_UNAVAILABLE`
statt ungeprüft weiterzulaufen.

## 3. S2 — Create

- Owner wird serverseitig gesetzt: `ownerIssuer`, `ownerSubject`, `ownerKey`,
  `actorType="user"`, `actorId`, `ownerClientId`.
- Retail **und** Agent-Orders nutzen exakt dieselbe Bindung.
- Body kann keine Owner-Felder setzen: die strikte Allowlist lehnt sie mit
  `400 VALIDATION_ERROR` ab (Test).
- Keine stille Delegation: `actorType` ist explizit, kein Default „service".

## 4. S3 — Get / Patch

- `get_order(order_id, identity)` und `update_order_status(order_id, status, identity)`.
- Fremde Order → `404 ORDER_NOT_FOUND`, identisch zu „existiert nicht".
- Order ohne `ownerKey` (Bestand) → `404`.
- Prüfung erfolgt **vor** jeder Ausgabe und vor jedem Update.
- `agentOrder`/`agentOrderFingerprint` bleiben in `INTERNAL_FIELDS`.

## 5. S4 — List

- Vorhandene Indizes geprüft: **gsi1** (global `LIST`) und **gsi2** (Privacy
  `SUBJECT#…`) sind belegt; **gsi3 war frei**.
- Neue Abfrage läuft ausschließlich über `gsi3` (`gsi3pk = ownerKey`,
  `gsi3sk = createdAt#orderId`).
- **Kein Fallback auf gsi1.** Fehlt der Index, wird `503 SERVICE_UNAVAILABLE`
  geliefert; die globale Liste ist für normale Aufrufer nicht erreichbar.
- Terraform: `gsi3` in `modules/dynamodb` ergänzt (Code/Plan, kein Apply).

## 6. S5 — Legacy und Privacy

| Bereich | Verhalten |
|---|---|
| Bestands-Orders ohne `ownerKey` | unverändert gespeichert, für normale Aufrufer `404` |
| Automatische Zuweisung | **keine** (kein E-Mail-, Kunden- oder Metadaten-Matching) |
| `subjectId` / gsi2 | **unverändert**: wird weiterhin nur gesetzt, wenn explizit übergeben (nie im API-Pfad) |
| Privacy-Funktionen | unverändert, weiter auf gsi2 und mit eigenem `authContext`+Secret |
| Öffentliche Erreichbarkeit Privacy | unverändert intern (direkter Invoke, keine Route) |

Damit wird kein bestehender Retail- oder Privacy-Ablauf still umgedeutet.

## 7. S6 — Tests

`cd lambda && PYTHONPATH=src python -m unittest discover -s tests`
→ **128 Tests, OK** (96 bestehend + 32 neu), `compileall` sauber.

Neue Datei `lambda/tests/test_ownership.py` deckt die geforderten Punkte ab:

| # | Nachweis | Test |
|---|---|---|
| 1 | eigene Order lesen/ändern | `test_owner_can_read`, `test_owner_patch_succeeds` |
| 2 | fremde Order nicht lesen | `test_foreign_reader_gets_404` |
| 3 | fremde Order nicht ändern | `test_foreign_patch_is_rejected_and_changes_nothing` |
| 4 | fremde Orders nicht auflisten | `test_foreign_orders_are_not_listed` |
| 5 | Legacy → 404 | `test_legacy_order_without_owner_is_inaccessible` |
| 6 | fehlender JWT-Kontext | `test_missing_claims_get_401`, `test_missing_authorizer_context_is_rejected` |
| 7 | falscher Issuer | `test_wrong_issuer_is_rejected` |
| 8 | manipuliertes `sub` | `test_body_cannot_inject_owner_fields`, `test_manipulated_sub_in_body_is_ignored` |
| 9 | `staff` kein Pauschalzugriff | `test_staff_group_grants_no_implicit_access` |
| 10 | Agent-Order geschützt | `test_agent_order_body_is_not_exposed`, `test_foreign_user_cannot_see_agent_order` |
| 11 | Retail-Regression | bestehende Suiten grün |
| 12 | Privacy-Regression | `test_privacy_path_still_uses_its_own_index` + bestehende Privacy-Tests |
| 13 | keine Secrets | `test_no_secret_in_error_bodies` |
| 14 | RIS-Vertrag kompatibel | A04-Tests unverändert grün |

Zusätzlich: gleicher `sub` mit anderem `iss` ist ein anderer Eigentümer; fremd und
nicht vorhanden sind ununterscheidbar; fehlender Index → `503` ohne Fallback.

## 8. Terraform (Code, kein Apply)

| Datei | Änderung |
|---|---|
| `terraform/modules/dynamodb/main.tf` | `gsi3` (`gsi3pk`/`gsi3sk`) + Attribute |
| `terraform/modules/lambda/variables.tf` | `cognito_issuer`, `cognito_client_id` |
| `terraform/modules/lambda/main.tf` | Env `ORDERS_COGNITO_ISSUER`/`ORDERS_COGNITO_CLIENT_ID` |
| `terraform/main.tf` | Durchreichen aus `module.cognito` |

**Betriebshinweis:** Nach einem Deployment müssen diese beiden Env-Variablen
gesetzt sein. Fehlen sie, antwortet die API fail-closed mit `503` — das ist
beabsichtigt und darf nicht als „Bypass" umgangen werden.

## 9. Verhaltensänderung (bewusst)

Alle Bestands-Orders werden für Endnutzer unsichtbar (`404`). Das ist O1.
Es gibt **keine** Migration in diesem Gate; sie bleibt ein separater,
ausdrücklich genehmigter Auftrag.

## 10. Offen

| Punkt | Status |
|---|---|
| Support-/Admin-Lesezugriff | nicht Teil dieses Gates (O3) |
| Legacy-Backfill | separater Auftrag |
| Autorisiertes `agentOrder`-Projektionsfeld | nach diesem Gate |
| A05 Dispatch / A06 Result | offen |

Kein AWS-Aufruf, kein Apply, kein Deployment, kein Merge.
