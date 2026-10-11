# MAYS-ORDERS-PRIVACY-E2E-VERIFY-01

## Baseline
`e11badd`. Kein `apply`/`destroy` ausgeführt. Nur synthetische Testdaten.
Testinstallation bleibt bestehen. Tabelle und Test-User nach Tests bereinigt.

## 1. Smoke-Tests (alle VERIFIED, außer Privacy-Route wie erwartet)
- **API Gateway** (`d4y53tocmk`, eu-central-1): erreichbar. Unauthentifiziert →
  401 (Auth erzwungen). Cognito `USER_PASSWORD_AUTH` + `admin-create-user`:
  synthetischer User, IdToken erhalten.
- **Cognito/JWT**: VERIFIED (Login, JWT akzeptiert, 401 ohne Token).
- **Lambda handler**: VERIFIED aktiv (CloudWatch-Logs, INIT/START/REPORT).
- **DynamoDB** (`mays-orders-privacy-test`): ACTIVE, GSI1 + GSI2 ACTIVE.
- **SQS/Worker**: VERIFIED — Handler legte Order in Queue, Worker
  `PENDING → CONFIRMED` (Worker-Logs), Queue danach leer (0 Nachrichten).
- **CloudWatch Logs**: VERIFIED (Handler- + Worker-Log-Groups schreiben).
- **IAM**: Handler-Rolle arbeitet (Put/Query/Update gegen Tabelle belegt).

## 2. Orders-Regression (gemischt)
- `POST /orders` → 201 (totalAmount serverseitig): VERIFIED.
- `PATCH /status` (PENDING→CONFIRMED via Worker bestätigt, Doppel-PATCH →
  409 INVALID_TRANSITION, PENDING-Revert → 409): VERIFIED.
- `GET /orders/{id}` und `GET /orders` → 500: **FAILED**. Ursache in
  CloudWatch-Logs: `Unexpected error: Object of type Decimal is not JSON
  serializable`. Lesepfade serialisieren DynamoDB-`Decimal` direkt; POST/PATCH
  antworten aus lokal gebauten Ints und sind nicht betroffen. Lambda-Codefehler
  (`lambda/src/`), keine Infrastrukturfrage. Kein Fix deployed (no-apply-Regel).

## 3. Privacy-Funktionen (interne Service-Funktionen, keine öffentlichen Routen)
- Deployed Lambda: keine Privacy-Route in `src/index.py`, und
  `PRIVACY_INTERNAL_SECRET` ist in `terraform/modules/lambda/main.tf` nicht
  gesetzt → `_require_privacy_auth` fällt live immer auf
  `Internal secret not configured`. Lokal gegen echte Tabelle reproduziert.
  **Deployed Privacy-Ops: BLOCKED (Konfigurationslücke, kein Code-Deploy
  ohne Freigabe vorgenommen).**
- Gegen echte Tabelle (lokaler Prozess, interner Aufrufweg, Test-Secret):
  - `inspect_subject`/`export_subject` → **FAILED (Codefehler)**: GSI2-Query
    nutzt `ProjectionExpression` mit unmaskiertem reserviertem Wort `status`
    → `ValidationException: reserved keyword: status` → als BLOCKED
    zurückgegeben. Direkt-Query mit Alias (`#s`) liefert 2/2 Items — GSI2 und
    Datenmodell sind korrekt, nur die Projektion ist fehlerhaft
    (`src/order_service.py:237-239,296`).
  - Auth-Negativpfade → VERIFIED (fail-closed): ohne Kontext, falsches Projekt,
    falscher Token, fehlendes Secret — jeweils Fehler, kein Datenzugriff.
  - Tenant-Isolation der Datenschicht: per Direkt-Query belegt (A=2, B=1,
    disjunkt).
  - `erase_subject` (mode EXECUTE, policy ERASE) → **VERIFIED**: A=2 Deletes,
    danach `get_order` → NOT_FOUND; B=1 Delete. Tatsächliche Löschung belegt.
  - Hinweis: erster Erase-Versuch mit `policy=EXECUTE` → `Invalid policy`
    (korrekte Parameter: `mode=EXECUTE` + `policy=ERASE`).

## 4. Statusmatrix
- IMPLEMENTED: Smoke, Regression POST/PATCH, Worker, Erase-Pfad, Negativpfade.
- VERIFIED: API/Cognito/Lambda/DynamoDB/SQS/Logs, POST, PATCH-Transitionsregeln,
  Worker-Transition, erase (echte Löschung), Auth-fail-closed.
- FAILED: GET/LIST (Decimal-Serialisierung), inspect/export (reserviertes Wort
  `status` in Projektion). Zwei konkrete Lambda-Codefehler, gleiche Datei.
- NOT TESTED: nichts offen außer Behebung der zwei Fehler nach Fix-Deploy.
- BLOCKED: Privacy-Ops im deployed Lambda (Secret nicht provisioniert, keine Route).

## 5. Nächste Schritte (Freigabe erforderlich)
1. `Decimal`-JSON-Serialisierung in Lesepfaden fixen.
2. `status` in GSI2-Projektionen aliasen (`#s`).
3. `PRIVACY_INTERNAL_SECRET` provisionieren (Secrets Manager, nie in Code/Logs)
   + internen Aufrufweg definieren.
4. Danach E2E-Verify wiederholen. Betrifft nur `lambda/src/`, kein Terraform.
