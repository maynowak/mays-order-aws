# Test Results — May's Orders

> Zentrale Ergebnis-Datei. **Stand Woche 2:** Lambda-Unit-Tests (Python 3.14)
> ausgeführt. Keine erfundenen Ergebnisse; Live-Tests erst nach Deployment.

| Ebene | Status | Datum | Hinweis |
|-------|--------|-------|---------|
| Python-Tests (unittest) | ✅ PASS (49/49) | 2026-08-18 | `lambda/` · `PYTHONPATH=src python3 -m unittest discover -s tests -v` |
| Python-Syntax (`compileall`) | ✅ PASS | 2026-08-18 | `python3 -m compileall -q src tests` |
| ZIP-Build + Integrität | ✅ PASS | 2026-08-18 | `python3 build_zip.py` → `dist/lambda.zip` (6 Module) · `unzip -t` PASS |
| Seed-Tests (scripts) | ✅ PASS (14/14) | 2026-08-19 | `scripts/` · `PYTHONPATH=scripts python3 -m unittest discover -s scripts/tests -v` (TEST 1-10 + Normalisierung + dry-run + Delete-Range) |
| Seed-Data-Schema-Prüfung | ✅ PASS | 2026-08-19 | `database/seed/orders_seed_1000.jsonl` — 1.000 Zeilen: Keys, GSI, Status, Beträge, Zeitstempel |
| Integration-Tests | NOT RUN | – | Lambda gegen echte DynamoDB erst nach apply |
| Terraform validate | validate ✅ | 2026-08-18 | plan zu T011-07 |
| Terraform plan (seed opt-in) | plan ✅ | 2026-08-19 | default 16 add; `-var="seed_test_data=true"` → 17 add (nur Seed-Ressource) |
| Live-API-Tests | NOT RUN | – | Keine Ressourcen deployed |

> Historische Node.js/TypeScript-Baseline (T011-04, Vitest 45/45, `npm run build`):
> aus dem aktiven Repo entfernt (Cleanup T011-04-CLEANUP); nachvollziehbar über
> Git-Historie (Commit `449cdd7`) und `docs/reports/LAMBDA-PYTHON-3.14-MIGRATION.md`.

## Detaillierte Einzelprüfungen

Ergebnisse werden ab Woche 2 hier tabellarisch eingetragen (IDs gemäß `api/test-cases.md`).

### State-Machine-Unit-Tests (`lambda/tests/test_state_machine.py`) — 4 PASS

- Erlaubte Übergänge (6), verbotene Übergänge (6), Endzustand (12), Idempotenz (6) —
  parametrisiert über `can_transition`.

### Validierungs-Unit-Tests (`lambda/tests/test_validation.py`) — 19 PASS

- POST /orders: gültiger Body; fehlendes `customer.name` (T-02); ungültige E-Mail (T-03);
  leere `items` (T-04); `quantity=0` (T-05); unbekannte Felder (T-06, strikt);
  `unitPrice`-Float (Cent-Konvention); ungültige `currency`; Nicht-Objekt-Body.
- GET /orders/{id}: ID-Format (T-09).
- PATCH status: gültiger/ungültiger Status (T-15), strikte Body-Prüfung.
- GET /orders: `limit`-Bereich 1..100, Default 20, `nextToken`-Durchreichung.

### Order-Service-Unit-Tests (`lambda/tests/test_order_service.py`) — 12 PASS

- AP1 Create: `totalAmount`/`lineTotal` server-seitig (T-01), Status PENDING, GSI1-/version-Felder,
  Validierung vor Write.
- AP2 Get: Order-Objekt ohne interne Felder (T-07); nicht vorhandene ID → ORDER_NOT_FOUND (T-08).
- AP3 List: GSI1-Query (absteigend), kompakte Items (T-10), `nextToken`-Encode/Decode (T-11/T-12),
  ungültiger Token → VALIDATION_ERROR.
- AP4 Status: gültiger Übergang mit Conditional Write (T-13); ungültiger Übergang →
  INVALID_TRANSITION mit Details (T-14); fehlende ID → ORDER_NOT_FOUND (T-16);
  ConditionalCheckFailed → CONFLICTED_UPDATE (R-01).

### Handler-Verhalten (`lambda/tests/test_index.py`) — 14 PASS

- Routing über `routeKey` für alle vier Routen, Body-Parsing inkl. Base64, Fehler-Mapping,
  `ORDERS_TABLE`-Check, unbekannte Route → 400.