# MO-AGENT-ORDER-OWNERSHIP-01 — Phase 1: Discovery & Ownership-Vertrag

**Datum:** 2026-11-13
**Typ:** READ-ONLY. Keine Änderung an Authentifizierung, Autorisierung oder Code.
**Basis:** `feature/mo-agent-order-body-01` @ `6369eb4` (Zielbasis `9627eb2`)
**Ergebnis:** Ist-Zustand belegt, Vertrag entschieden, Implementierungsplan liegt vor.

---

## 1. IST — was die Basis technisch wirklich macht

### 1.1 Authentifizierung (wer bist du?)

| Ebene | Befund | Beleg |
|---|---|---|
| API Gateway | HTTP API mit **JWT-Authorizer** | `terraform/modules/api/main.tf` |
| Issuer | `https://${cognito_user_pool_endpoint}` (eigener Pool) | ebd. |
| Audience | `[cognito_user_pool_client_id]` — genau **ein** Client | ebd. |
| Routen | 4, **alle** `authorization_type = "JWT"` | ebd. |
| Cognito-Client | **public client** (`generate_secret = false`), Gruppe `staff` | `terraform/modules/cognito/main.tf` |
| Lambda | liest **keine** Claims | `lambda/src/index.py` (kein `requestContext`/`authorizer`/`claims`) |

**Verifiziert durch die Infrastruktur:** Signatur, Ablauf, `iss`, `aud`.
Damit stehen im Lambda technisch zur Verfügung: `sub`, `iss`, `client_id`/`aud`,
`cognito:groups`, `token_use` — **sofern der Code sie liest**.

### 1.2 Autorisierung (was darfst du?)

| Pfad | Prüfung heute | Beleg |
|---|---|---|
| `POST /orders` | **keine** — `create_order(parse_body(event))`, `subject_id` wird nie übergeben | `index.py`, `order_service.py:139` |
| `GET /orders/{orderId}` | **keine** — `get_order(order_id)` ohne Identität | `order_service.py:get_order` |
| `GET /orders` | **keine** — `gsi1pk = "LIST"`, also **alle** Orders | `order_service.py:list_orders` |
| `PATCH /orders/{id}/status` | **keine** — `update_order_status` prüft nur den Statusübergang | `order_service.py:update_order_status` |
| Interner Privacy-Pfad | **ja**, aber separater Trust-Boundary: `event.authContext` + `PRIVACY_INTERNAL_SECRET`, fail-closed | `index._handle_internal`, `order_service._require_privacy_auth` |

**Kernaussage:** Authentifizierung ist vollständig vorhanden. Autorisierung
gegenüber dem Order-Eigentümer existiert **nicht**. Jeder gültige Cognito-Token
darf heute jede Order lesen und jeden Status setzen.

### 1.3 Dokumentierte Absicht vs. Implementierung

`security/authentication-decision.md` sagt:

> „API GW validiert Signatur + Ablauf → reicht Claims an Lambda weiter.
> Lambda nutzt Claims (`sub`, `cognito:username`, `groups`) für Authorization."

Der zweite Satz ist **nicht implementiert**. Das ist der zentrale GAP und
gleichzeitig der Beleg, dass die Zielrichtung bereits entschieden war.

### 1.4 Orders ohne `subjectId`

- `create_order(..., subject_id=None)` ist der einzige Aufruf; **kein** Aufrufer
  übergibt je einen Wert → **alle** Bestands-Orders haben kein `subjectId`.
- `subjectId` existiert im Modell und speist GSI2 (`SUBJECT#<sub>`), wird aber
  ausschließlich vom Privacy-Pfad genutzt.
- `INTERNAL_FIELDS` entfernt `subjectId` aus allen API-Antworten.
- Fazit: Es gibt heute **null** Eigentümerbindung, weder für Retail noch für
  Agent-Orders.

### 1.5 Agent-Order (A04)

`agentOrder` und `agentOrderFingerprint` sind persistiert und über
`INTERNAL_FIELDS` aus öffentlichen Antworten entfernt. Da es keine
Eigentümerprüfung gibt, ist diese Unsichtbarkeit der **einzige** Schutz — genau
deshalb ist A04.5 erfüllt, aber auch nicht mehr.

---

## 2. SOLL — Identitäts- und Ownership-Vertrag

### 2.1 Drei getrennte Identitäten (nicht vermischen)

| Rolle | Herkunft | Zweck | Darf Order lesen? |
|---|---|---|---|
| **Owner** | verifizierter JWT: `iss` + `sub` | wem gehört die Order | ja, nur eigene |
| **Actor** | derselbe oder delegierter Kontext | wer hat gehandelt | nein, außer er ist Owner |
| **Service/Consumer** | interner Trust-Boundary (kein Nutzer-JWT) | Result-/Privacy-Verarbeitung | nur über definierten internen Pfad |

**RIS-Key ist keine Identität für Orders.** Er authentifiziert gegen RIS, nicht
gegen Mays-Orders. Ein RIS-Key darf niemals eine Order „besitzen".

### 2.2 Gespeicherte Felder (Vorschlag)

| Feld | Inhalt | Zweck |
|---|---|---|
| `ownerIssuer` | `iss` (normalisiert, ohne Query/Fragment) | Mehr-Provider-Eindeutigkeit |
| `ownerSubject` | `sub` | Eigentümer |
| `ownerKey` | `sha256(iss + "\x00" + sub)` | konstanter Vergleich, indexfähig |
| `subjectId` | bleibt `sub` | Kompatibilität Privacy/GSI2 |
| `actorType` | `user` \| `service` \| `delegated` | Audit, Delegation sichtbar |
| `actorId` | `sub` oder Service-ID | „wer hat gehandelt" |
| `clientId` | `aud`/`client_id` | Consumer-/Partnerkontext |
| `tenantId` | optional, nur aus verifiziertem Kontext | Mehr-Mandanten |

Regeln:

- `iss` **und** `sub` zusammen, nie `sub` allein (mehrere Provider).
- Keine Übernahme aus Body/Query/Header. `sub` kommt ausschließlich aus
  `requestContext.authorizer.jwt.claims`.
- Kein `email` als Identität (änderbar, nicht eindeutig).
- `orderId` allein autorisiert nichts.

### 2.3 Delegierte Ausführung

Der Agent führt **nicht** als Eigentümer aus. Der Ergebnis-Rückweg (A06) ist
Service-zu-Service und nutzt einen internen Boundary wie der bestehende
Privacy-Pfad (`authContext` + Secret, fail-closed). Er darf **nur** Ergebnis-
felder schreiben, niemals `ownerIssuer`/`ownerSubject` ändern.

---

## 3. Legacy-Strategie (fail-closed)

| Fall | Verhalten |
|---|---|
| Order mit `ownerKey` | Zugriff nur bei Gleichheit |
| Order **ohne** `ownerKey` (alle Bestandsdaten) | **kein** Benutzerzugriff → `404 ORDER_NOT_FOUND` |
| Order existiert nicht | ebenfalls `404` (kein Existenz-Orakel) |
| Support/Operator | separater, auditierter Admin-Pfad (nicht Teil dieser Phase) |

Bewusst **nicht**:

- keine automatische Zuweisung anhand `customer.email`,
- keine Übernahme aus Request-Daten,
- keine „erste Anfrage gewinnt"-Heuristik,
- keine stille Massen-Migration.

Begründung: `customer.email` ist frei wählbar; eine darauf gestützte Zuweisung
wäre Identitätsdiebstahl per Eingabefeld.

**Konsequenz, die entschieden werden muss:** Mit Aktivierung werden alle
Bestands-Orders für Endnutzer unsichtbar. Das ist sicher, aber ein sichtbarer
Bruch. Optionen: (a) akzeptieren und kommunizieren, (b) einmalige, explizit
autorisierte Backfill-Aktion mit nachweisbarer Quelle, (c) Shadow-Mode
(Prüfung loggen, noch nicht durchsetzen) für einen begrenzten Zeitraum.

---

## 4. API-Zugriffsmatrix

| Route | Authn heute | Authz heute | SOLL |
|---|---|---|---|
| `POST /orders` | JWT | — | Owner aus Claims; `401` wenn Claims fehlen; Body darf keine Owner-Felder setzen |
| `GET /orders/{id}` | JWT | — | `ownerKey`-Gleichheit, sonst `404` |
| `GET /orders` | JWT | — | **nur eigene** Orders, cursor-basiert |
| `PATCH /orders/{id}/status` | JWT | — | Owner; `staff`/Admin separat zu entscheiden |
| interner Privacy-Pfad | Secret + authContext | vorhanden | unverändert |
| A06-Result-Rückweg | — | — | neuer interner Boundary, schreibt nur Ergebnis |

**Listen-Problem:** Heute listet `gsi1pk = "LIST"` alle Orders. Eine
eigentümerbezogene Liste braucht einen Index auf `ownerKey`.

- **Option A (Empfehlung):** neuer GSI3 `ownerKey` + `createdAt`. Saubere
  Trennung von Privacy (GSI2) und Ownership. Erfordert Terraform-Änderung.
- **Option B:** GSI2 wiederverwenden (`SUBJECT#<iss>#<sub>`). Kein Terraform,
  aber vermischt Ownership und Privacy-Schlüssel und ändert das Privacy-Format
  für neue Zeilen.

Option A ist die einzige Variante, die Privacy und Ownership nicht koppelt.
Die Terraform-Änderung wird **nicht** deployt, sondern nur vorbereitet.

---

## 5. Testpartner-Ablauf (Cognito + RIS-Key)

```
Partner A (Browser/Backend)
  1. Cognito Login (USER_PASSWORD_AUTH, public client)
     → Access/ID-Token mit iss=<pool>, sub=<userA>, aud=<client>
  2. POST /orders  (Authorization: Bearer <access token>)
     → Lambda liest iss+sub, setzt Owner, liefert 201 + orderId
  3. GET /orders/{orderId} (derselbe Token) → 200
  4. Partner B mit eigenem Token auf dieselbe orderId → 404

RIS-Key: ausschließlich für Aufrufe an RIS (M2M).
         niemals als Authorization gegenüber Mays-Orders.
```

Damit ist die Trennung erfüllt: Cognito identifiziert den Auftraggeber
gegenüber Orders, der RIS-Key autorisiert die Agentenausführung.

---

## 6. IST/SOLL/GAP-Matrix

| # | Baustein | SOLL | IST | GAP |
|---|---|---|---|---|
| 1 | JWT-Validierung | vorhanden | vorhanden (Gateway) | — |
| 2 | Claim-Auswertung im Lambda | `iss`+`sub` | keine | **GAP** |
| 3 | Owner beim Create | gesetzt | nicht gesetzt | **GAP** |
| 4 | Owner-Check Get | erzwungen | keiner | **GAP** |
| 5 | Owner-Check List | erzwungen | alle Orders | **GAP** |
| 6 | Owner-Check Patch | erzwungen | keiner | **GAP** |
| 7 | Legacy-Isolation | fail-closed | alle lesbar | **GAP** |
| 8 | Delegation/Service | getrennt | nicht definiert | **GAP** |
| 9 | Privacy-Boundary | vorhanden | vorhanden | OK |
| 10 | Retail-Verhalten | unverändert | unverändert | OK (nach Fix zu prüfen) |

---

## 7. Sicherheits- und Regressionstestmatrix

| # | Test | Erwartung |
|---|---|---|
| 1 | Create mit gültigem JWT | 201, `ownerKey` gesetzt, `iss`+`sub` korrekt |
| 2 | Create ohne Claims (direkter Invoke) | 401, nichts persistiert |
| 3 | Body mit `subjectId`/`ownerKey` | 400 (unbekanntes Feld) |
| 4 | Owner liest eigene Order | 200 |
| 5 | Fremder Nutzer liest Order | **404** |
| 6 | Fremder Nutzer listet | sieht nur eigene, Zähler stimmt |
| 7 | Fremder Nutzer patcht Status | 404, Status unverändert |
| 8 | Owner patcht gültigen Übergang | 200 |
| 9 | Owner patcht ungültigen Übergang | 409 unverändert |
| 10 | Legacy-Order (kein `ownerKey`) | 404 für Nutzer |
| 11 | Zwei Provider, gleicher `sub` | getrennte Owner |
| 12 | Gleicher `sub`, andere `iss` | kein Zugriff |
| 13 | Abgelaufener/fremder Token | 401 (Gateway) |
| 14 | Agent-Order: fremder Nutzer | 404, `agentOrder` nie sichtbar |
| 15 | Agent-Order: Owner | 200, `agentOrder` **weiterhin nicht** im Body |
| 16 | Result-Rückweg ohne Service-Boundary | abgelehnt |
| 17 | Retail-Regression | 76 Bestandstests grün |
| 18 | A04-Regression | 20 Tests grün |
| 19 | Keine Secrets in Logs/Fehlern | geprüft |

---

## 8. Minimaler Implementierungsplan (Phase 2, noch nicht freigegeben)

| Schritt | Inhalt | Risiko |
|---|---|---|
| S1 | `lambda/src/identity.py`: `extract_identity(event)` fail-closed; Tests mit synthetischen API-GW-v2-Events | klein |
| S2 | Create: Owner setzen; Body-Felder ablehnen | klein |
| S3 | Get/Patch: Owner-Check → 404 | **sichtbarer Bruch** für Altdaten |
| S4 | List: GSI3 (Option A) oder GSI2 (Option B) | Infra-Entscheidung |
| S5 | Legacy-Modus (durchsetzen vs. Shadow) | Produktentscheidung |
| S6 | Interner Result-Boundary (Vorbereitung A06) | mittel |

Reihenfolge bewusst: S1/S2 sind additiv und risikofrei. S3 ist der Bruch und
braucht die Legacy-Entscheidung. S4 braucht die Index-Entscheidung.

---

## 9. Offene Entscheidungen (vor Phase 2)

| # | Entscheidung | Auswirkung |
|---|---|---|
| O1 | Legacy: durchsetzen / Shadow-Mode / Backfill | sichtbar für alle Bestandsnutzer |
| O2 | Liste: GSI3 (sauber, TF) vs. GSI2 (kein TF) | Infra-Änderung |
| O3 | Dürfen `staff`/Admins fremde Orders lesen? | Support-Fähigkeit vs. Datenschutz |
| O4 | Wird der Result-Rückweg ein eigener interner Boundary? | Voraussetzung für A06 |

## 10. Abnahme Phase 1

- Keine Codeänderung an AuthN/AuthZ.
- Alle Aussagen mit Datei/Zeile belegt.
- Vertrag, Legacy-Strategie, Zugriffsmatrix und Testmatrix liegen vor.
- Keine AWS-Mutation, kein Deployment.
