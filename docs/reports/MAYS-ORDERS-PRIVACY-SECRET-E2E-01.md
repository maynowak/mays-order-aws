# MAYS-ORDERS-PRIVACY-SECRET-E2E-01

## Phase 1 — Security Review (Befund)
- Einziger Secret-Lesepfad: `order_service.py:114`
  (`os.environ["PRIVACY_INTERNAL_SECRET"]`, Konstantzeit-Vergleich mit
  `internal_token`, fail-closed ohne Secret). Keine weitere Secret-Ladung.
- IAM: keine neuen Rechte nötig (Env-Lesung implizit, DynamoDB-Rechte
  vorhanden). Invoke-Recht `lambda:InvokeFunction` für Testidentität belegt.
- Interne Aufrufwege: **keiner vorhanden** (keine Route, kein Dispatch).
  Daher minimaler Dispatch `_handle_internal` in `index.py` für Aktionen
  `privacy/inspect|export|erase`, ausschließlich per direktem Lambda-Invoke
  erreichbar — **keine öffentliche API-Route** hinzugefügt, jede Aktion durch
  `_require_privacy_auth`.
- Integrationsentscheidung (statt Secrets Manager/SSM): Secret **ephemer** per
  `update-function-configuration` gesetzt und nach Tests wieder entfernt —
  nie in Git/State/Plan/Doku/Logs/History (0600-Dateien + `--cli-input-json
  file://`, danach geschreddert). Secrets Manager hätte nicht-allowlistete
  Ressourcentypen + neue IAM-Pfade erfordert (Policy RED); als Follow-up
  dokumentiert, nicht eingeführt.

## Phase 2/3 — Provisionierung + Deployment
- Secret kryptografisch sicher generiert (`secrets.token_urlsafe(32)`),
  gesetzt ohne Klartext in argv/History; Lambda danach ACTIVE.
- Code-Deploy `deploy-0009` (nur 2 Lambda-Updates): Policy PASSED, applied,
  Post-Verify OK. `validate` + 76 Unit-Tests GREEN, Artefakt-Check PASS.

## Phase 4 — Privacy AWS E2E (synthetisch, via deployed Lambda)
- P-01 inspect: 200 COMPLETED, affected=2, Kategorien
  customer.name/email, Y-isoliert (1 eigener Record). VERIFIED.
- P-02 export: 200 COMPLETED, 2 Orders, operationId, JSON/Decimal ok. VERIFIED.
- P-03 erase: COMPLETED; danach affected=0, Refs leer; Y separat gelöscht
  (deleted=1); Wiederhol-Löschung sicher (COMPLETED, 0). VERIFIED.

## Phase 5 — Negativtests (alle fail-closed)
Falscher Token, falsches Projekt, fehlender Kontext, `authorized=false` →
jeweils 400 VALIDATION_ERROR, kein Datenzugriff. Nach Secret-Entfernung:
Invoke mit beliebigem Token → 400 (fail-closed Endzustand). VERIFIED.

## Phase 6 — Cleanup (VERIFIED)
Tabelle `Count=0`, Secret per CLI aus Lambda-Env entfernt (Keys danach ohne
Secret), 0600-Dateien geschreddert, keine Test-User angelegt. Installation
besteht, **kein Destroy**.

## Status: GREEN
Offen/Follow-up: dauerhafte Secret-Haltung (Secrets Manager + Rotation) und
produktiver interner Aufrufweg — Governance-Entscheidung, kein Blocker für
Testinstallation. Destroy-Bereitschaft: Plan `destroy-0001` (37 deletes,
projektrein) liegt vor, Ausführung separat freizugeben.
