# MO-AGENT-ORDER-PROJECTION-01 — Owner-only Agent Order Detail

**Datum:** 2026-11-13
**Typ:** Lokale Implementierung + Tests (kein Apply, kein Deployment)
**Ergebnis:** COMPLETE. Nur der verifizierte Eigentümer sieht den freigegebenen
`agentOrder` — und ausschließlich über den Detailabruf.

## 1. Baseline

| Feld | Wert |
|---|---|
| Branch | `feature/mo-agent-order-body-01` |
| Parent | `10f1aaa` |
| Tests vor Beginn | 128 OK |

## 2. Befund aus P00 (mitbehoben)

Die Ownership-Felder aus Phase 2 (`ownerIssuer`, `ownerSubject`, `ownerKey`,
`ownerClientId`, `actorType`, `actorId`, `gsi3pk`, `gsi3sk`) standen **nicht** in
`INTERNAL_FIELDS`. Sie wurden damit in **jeder** Detail- und Listenantwort
mitgeliefert — inklusive `ownerKey` und rohem `sub`.

Das ist ein Leak der Identitätsbindung, kein reines Kosmetikproblem: `ownerKey`
ist zwar gehasht, `ownerSubject` aber nicht. Die Projektionstests haben es
aufgedeckt; es ist in diesem Commit behoben.

## 3. Implementierung

### 3.1 `INTERNAL_FIELDS` erweitert
Alle Ownership-Felder sind jetzt intern. `to_public_order` entfernt sie.

### 3.2 Eigene Detailprojektion `to_public_agent_order`

Wird **nur** in `get_order` nach erfolgreicher Eigentümerprüfung angewendet.

Freigegeben:

| Feld | Begründung |
|---|---|
| `schemaVersion` | Vertragskennung |
| `target.{agentId, capability, agentVersion}` | fachlicher Auftrag |
| `input.{schemaVersion, data}` | fachliche Eingabe des Eigentümers |
| `metadata.{source, requestId}` | nicht-identifizierende Korrelation |
| `resultContract.*` | Liefervertrag, für den Partner relevant |

Zurückgehalten:

| Feld | Grund |
|---|---|
| `metadata.partnerApplicationRef` | Identitätskontext |
| `metadata.apiProfileRef` | Identitätskontext |
| `metadata.idempotencyKey` | technische Dedup-Info |
| `processing.*` | technischer Ausführungszustand (inkl. `parentWorkId`) |
| `agentOrderFingerprint` | internes Integritätsmerkmal |

### 3.3 Whitelist statt Blacklist

Die Projektion validiert den **gespeicherten** Body zuerst gegen den V1-Contract.
Schlägt die Validierung fehl (manipuliert, unbekannte Felder, Secret-Muster),
wird der Auftrag **vollständig zurückgehalten** (`{}`). Unbekannte Felder werden
niemals durchgereicht — auch nicht, wenn sie erst nach dem Create in die
Datenbank gelangt sind.

## 4. Wirkung nach Route

| Route | `agentOrder` sichtbar? |
|---|---|
| `GET /orders/{id}` (Eigentümer) | **ja**, freigegeben und sanitisiert |
| `GET /orders/{id}` (fremd) | nein — `404` |
| `GET /orders` (Liste) | nein |
| `POST /orders` | nein |
| `PATCH /orders/{id}/status` | nein |

## 5. Tests

`cd lambda && PYTHONPATH=src python -m unittest discover -s tests`
→ **144 Tests OK** (128 vorher + 16 neu), `compileall` sauber.

`lambda/tests/test_agent_order_projection.py`:

| # | Nachweis |
|---|---|
| 1 | Eigentümer liest `agentOrder` mit target/input/metadata/resultContract |
| 2 | Fremder Eigentümer → `404` |
| 3 | Legacy ohne Owner → `404` |
| 4 | Liste enthält kein `agentOrder` und keine Capability |
| 5 | Retail-Detail exakt unverändert (Schlüsselmenge geprüft) |
| 6 | Fremder Patch → `404`, Status unverändert |
| 7 | Identitätsreferenzen, `processing`, Fingerprint und Owner-Felder fehlen |
| 8 | Manipulierter Body wird nicht projiziert; Secret-Muster wird zurückgehalten |
| 9 | Ownership-Suite bleibt grün |
| 10 | Privacy-/Agent-Order-Regressionen bleiben grün |

Zusätzlich über HTTP: Eigentümer `200` mit sanitisiertem Body, Fremder `404`,
keine internen Felder in der Antwort.

## 6. Grenzen

- Kein neuer Lifecycle, kein neuer SQS-Vertrag, keine Änderung am RIS Transport V1.
- Retail-Create und Retail-Detail unverändert.
- Kein AWS-Aufruf, kein Apply, kein Deployment, kein Merge.

## 7. Offen

| Punkt | Status |
|---|---|
| Support-/Admin-Lesezugriff | separates Gate |
| Legacy-Backfill | separates Gate |
| A05 Dispatch / A06 Result | offen |
