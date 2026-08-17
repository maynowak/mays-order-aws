# Test Results — May's Orders

> Zentrale Ergebnis-Datei. **Stand Woche 2 (T011-04):** Lambda-Unit-Tests ausgeführt.
> Keine erfundenen Ergebnisse; Live-Tests erst nach Deployment.

| Ebene | Status | Datum | Hinweis |
|-------|--------|-------|---------|
| Build / Type-Check | ✅ PASS | 2026-08-17 | `lambda/` · `npm run build` (tsc --noEmit + esbuild) |
| Unit-Tests | ✅ PASS (45/45) | 2026-08-17 | Vitest: stateMachine 14, validation 19, orderService 12 |
| Integration-Tests | NOT RUN | – | Lambda gegen echte DynamoDB erst nach apply |
| Terraform validate/plan | validate ✅ / plan NOT RUN | 2026-08-17 | plan zu T011-07 |
| Live-API-Tests | NOT RUN | – | Keine Ressourcen deployed |

## Detaillierte Einzelprüfungen

Ergebnisse werden ab Woche 2 hier tabellarisch eingetragen (IDs gemäß `api/test-cases.md`).

### State-Machine-Unit-Tests (`lambda/tests/stateMachine.test.ts`) — 14 PASS

- SM-01…SM-06 (gültige Übergänge): PASS
- SM-07…SM-18 (ungültige Übergänge inkl. Endzustände + Idempotenz → 409): PASS

### Validierungs-Unit-Tests (`lambda/tests/validation.test.ts`) — 19 PASS

- POST /orders: gültiger Body; fehlendes `customer.name` (T-02); ungültige E-Mail (T-03);
  leere `items` (T-04); `quantity=0` (T-05); unbekannte Felder (T-06, strikt);
  `unitPrice`-Float (Cent-Konvention); ungültige `currency`; Nicht-Objekt-Body.
- GET /orders/{id}: ID-Format (T-09).
- PATCH status: gültiger/ungültiger Status (T-15), strikte Body-Prüfung.
- GET /orders: `limit`-Bereich 1..100, Default 20, `nextToken`-Durchreichung.

### Order-Service-Unit-Tests (`lambda/tests/orderService.test.ts`) — 12 PASS

- AP1 Create: `totalAmount`/`lineTotal` server-seitig (T-01), Status PENDING, GSI1-/version-Felder,
  Validierung vor Write.
- AP2 Get: Order-Objekt ohne interne Felder (T-07); nicht vorhandene ID → ORDER_NOT_FOUND (T-08).
- AP3 List: GSI1-Query (absteigend), kompakte Items (T-10), `nextToken`-Encode/Decode (T-11/T-12),
  ungültiger Token → VALIDATION_ERROR.
- AP4 Status: gültiger Übergang mit Conditional Write (T-13); ungültiger Übergang →
  INVALID_TRANSITION mit Details (T-14); fehlende ID → ORDER_NOT_FOUND (T-16);
  ConditionalCheckFailed → CONFLICTED_UPDATE (R-01).
