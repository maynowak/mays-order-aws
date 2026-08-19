# T011-10 SEED-FINALIZATION — Execution Log

> **Task:** T011-10 DynamoDB Seed-Daten Finalisierung — 50 Demo-Orders, `version`, `isTestData`, `seed_example_data`-Opt-In.
> **Auftrag:** Kein `terraform apply`, kein Live-Seed. Marshalling-Punkt vor Live-Import technisch klären.
> **Datum:** 2026-08-19

---

## 2026-08-19 12:53 — Schritt 1

### Aktion
Repository Recovery / Ist-Stand (Abschnitt 1) — git-Status, Branch, HEAD, Demo-Datei-Lage.

### Command
git status / git status -sb / git branch --show-current / git rev-parse HEAD / git log --oneline --decorate -20
ls database/seed/
unzip -l docs.zip / docsMaysOrdersAws.zip (Suche nach Seed-Datei)

### Ergebnis
PASS

### Evidenz
- Branch `main`, HEAD `e1d80e6` (merge feature/dynamodb-seed → main); `origin/main` auf gleicher Höhe.
- Untracked: `database/seed/orders_seed_demo_50.json`, `docs.zip`, `docs/reports/NORMALIZATION-AUDIT-EXECUTION-LOG.md`.
- `database/seed/` enthält `orders_seed_1000.jsonl` (514 KB) und **bereits bereitgestellt** `orders_seed_demo_50.json` (35 KB, Aug 19 12:52).

### Auswirkungen
Keine (read-only). Execution-Log angelegt.

### Nächster Schritt
Demo-Datei-Inhalt validieren + aktuellen Code lesen.

---

## 2026-08-19 12:54 — Schritt 2

### Aktion
Demo-Datei `orders_seed_demo_50.json` (bereits in `database/seed/`) per Python validiert: Struktur, Invarianten, Variation.

### Command
python3 <<EOF (JSON-Load, Checks: Anzahl, Felder, Duplikate, pk/sk, GSI, Status, version, isTestData, lineTotal, totalAmount)
Read: database/seed/orders_seed_demo_50.json (1602 Zeilen)

### Ergebnis
PASS

### Evidenz
- 50 Orders; Top-Level-Felder: `pk, sk, orderId, status, customer, items, currency, totalAmount, createdAt, updatedAt, version, isTestData, gsi1pk, gsi1sk` (14).
- Item-Felder: `sku, quantity, unitPrice, lineTotal` (4; kein `name`).
- 0 Duplikate pk/sk; `pk=ORDER#<orderId>`, `sk=#ORDER`; `gsi1pk=LIST`, `gsi1sk=createdAt`.
- Status-Verteilung: PENDING 12, CONFIRMED 13, SHIPPED 13, CANCELLED 12.
- `version` überall 1; `isTestData` überall true.
- `lineTotal == quantity × unitPrice` (alle); `totalAmount == Σ lineTotal` (alle).
- Kunden 8 verschiedene (Anna Müller, Peter Schmidt, Laura Weber, Jonas Fischer, Sophie Wagner, Mila Becker, Paul Hoffmann, Emma Schäfer, Clara Bauer, Leon Koch); verschiedene Mengen/Beträge/createdAt.

### Auswirkungen
Keine (read-only). Datei bleibt unverändert.

### Nächster Schritt
Aktuellen Code lesen (Terraform, Lambda, delete-Skript, Access Patterns) — kein Vertrauen in alte Reports.

---

## 2026-08-19 12:55 — Schritt 3

### Aktion
Aktuellen Code und Doku gelesen (Ist-Stand, Abschnitt 1).

### Command
Read: terraform/variables.tf, terraform/main.tf, terraform/outputs.tf
Read: scripts/delete_seed_orders.py
Read: lambda/src/state_machine.py, lambda/src/order_types.py, lambda/src/order_service.py
Read: lambda/tests/test_order_service.py
Read: database/access-patterns.md
(scripts/seed_orders.py + tests zuvor im NORMALIZATION-AUDIT gelesen; unverändert, git clean)

### Ergebnis
PASS

### Evidenz
- Terraform: `variable "seed_test_data"` (default false) + `seed_file_path` (JSONL) + `terraform_data.seed_orders` (count = seed_test_data, local-exec → seed_orders.py). Aktueller Importpfad = 1.000er JSONL.
- `seed_orders.py`: low-level `boto3.client` mit plain dicts (`batch_get_item`/`batch_write_item`) → Marshalling-Risiko (Audit-Punkt §9).
- `delete_seed_orders.py`: löscht Bereich `ord_00001..ord_01000` (1.000er), low-level client, KEIN isTestData-Check.
- Lambda: `create_order` setzt `version=1` (order_service.py:120), berechnet `lineTotal` (Z. 104), nutzt `boto3.resource(...).Table.put_item` (auto-Marshalling). `version` in `INTERNAL_FIELDS` (aus API-Antworten gestrippt). `update_order_status` inkrementiert `version` (Z. 176-184), Conditional Write auf `status`.
- `order_types.py`: `OrderItem` = {sku, quantity, unitPrice, lineTotal}; `OrderDynamoItem` enthält version, KEIN isTestData.
- Access Patterns AP1..AP4 dokumentiert (PutItem / GetItem / GSI1-Query / UpdateItem+Condition); kein Scan.
- Tests: lambda-Tests decken version=1 beim Create und version-Inkrement ab; Seed-Tests 14/14 (Fake-Client).

### Auswirkungen
Keine (read-only).

### Nächster Schritt
Model-Frage version/isTestData verifizieren (validation.py, index.py) + boto3-resource-Marshalling belegen.

---

## 2026-08-19 12:56 — Schritt 4

### Aktion
Datenmodell-Frage verifiziert (Abschnitt 4/5/11): Ist `version` Teil des normalen Order-Modells? Ist `isTestData` produktiv oder nur Testdaten?

### Command
Read: lambda/src/validation.py, lambda/src/index.py
Grep: version/isTestData in lambda/src/*, lambda/tests/*, database/dynamodb-design.md

### Ergebnis
PASS

### Evidenz
- **version = reguläres Order-Feld** (bereits verankert):
  - `order_types.OrderDynamoItem.version` (order_types.py:53), `dynamodb-design.md` §2.
  - `create_order` setzt `version = 1` (order_service.py:120); `update_order_status` inkrementiert `#version = #version + :one` (Z. 176-184) bei Conditional Write auf `status` (AP4, access-patterns.md §2.4).
  - `version` in `INTERNAL_FIELDS` → wird aus API-Antworten gestrippt (order_service.py:15, 46).
  - Kein neues Concurrency-Design nötig — bestehende Update-Logik (Conditional Write) bleibt Source of Truth.
- **isTestData = NICHT Teil des produktiven Modells**:
  - Nicht in TypedDicts (nur optional neu zu dokumentieren, s. u.), nicht von `create_order` gesetzt.
  - `validate_create_order` weist unbekannte Felder per `reject_unknown_keys` ab (validation.py:44, 49, 68) → ein Client kann `isTestData` im Create-Payload NICHT setzen. Normale echte Orders werden dadurch niemals Testdaten.
  - Demo-Seed setzt `isTestData = true` ausschließlich in der Datei; Importer übernimmt das Feld unverändert.

### Auswirkungen
Keine (read-only).

### Nächster Schritt
Marshalling-Punkt (Abschnitt 9) mit autoritativer Quelle belegen.

---

## 2026-08-19 12:57 — Schritt 5

### Aktion
Audit-Punkt §9 „Marshalling" technisch geklärt: `boto3.client` vs. `boto3.resource`, korrektes Marshalling nachweisen.

### Command
WebSearch/WebFetch: AWS-Doku „Programming DynamoDB with Python and Boto3" + boto3-Quellcode (boto3/dynamodb/transform.py, types.py)

### Ergebnis
PASS (Klärt den Befund; Lokale Ausführung mangels boto3/pip nicht möglich — BLOCKED für empirischen Live-Beweis)

### Evidenz (autoritative Quellen)
- AWS-Doku (programming-with-python.html): Die **Client**-Schnittstelle verlangt DynamoDB-JSON (AttributeValue-Maps: `{'pk': {'S': ...}}`); die **Resource**-Schnittstelle hat „data typing is implicit" (plain Python).
- boto3-Quellcode `boto3/dynamodb/transform.py`: die Resource-API registriert Handler `inject_attribute_value_input` (TypeSerializer beim Request) und `inject_attribute_value_output` (TypeDeserializer bei der Response).
- boto3 `types.py`: TypeSerializer bildet plain Python (str/int/bool/list/dict) → DynamoDB-Typen ab.
- Bestätigtes Fehlerbild bei Client + plain dicts: `ParamValidationError: Invalid type for parameter ..., type: <class 'str'>, valid types: <class 'dict'>`.
- **Produktiver Präzedenzfall im Repo:** `order_service.py` nutzt bereits `boto3.resource(...).Table(...).put_item(Item=plain dict)` (Z. 30-33, 96, 125) — geprüfter Produktivpfad (49/49 Tests).

### Auswirkungen
Keine (read-only). Ergebnis fließt in die Implementierung ein: Importer + Cleanup auf **resource**-API umstellen (identische Signaturen `batch_get_item`/`batch_write_item`), damit das Marshalling automatisch erfolgt — wie im Produktivpfad.

### Nächster Schritt
Implementierung: seed_orders.py (Loader JSON+JSONL, Normalisierung minimal, resource-API, Default demo-50).

---

## 2026-08-19 13:02 — Schritt 6

### Aktion
Implementierung: `scripts/seed_orders.py` (Abschnitt 2/9/10) — JSON-Array- UND JSONL-Loader, minimale Normalisierung, resource-API, Default-Datei demo-50.

### Command
Edit: scripts/seed_orders.py (Docstring, _get_dynamodb_resource, normalize_item, validate_seed_item, _load_json_array/_load_jsonl/load_seed_items, import_orders, main --file)

### Ergebnis
PASS

### Evidenz
- `_get_dynamodb_resource()` → `boto3.resource` (auto-Marshalling, wie order_service.py). Signatur `batch_get_item`/`batch_write_item` bleibt identisch → Fake-Client-Tests unverändert lauffähig.
- Loader erkennt `[`-Start → JSON-Array (demo-50), sonst JSONL (1.000er).
- `normalize_item` minimal: übernimmt vorhandene `lineTotal`/`version`/`isTestData`, ergänzt nur fehlende abgeleitete Felder, entfernt `items[].name`.
- `validate_seed_item` + optional: `version` int ≥ 1, `isTestData` bool, `lineTotal == quantity × unitPrice`.
- `--file` Default = `database/seed/orders_seed_demo_50.json`.

### Auswirkungen
Geändert: scripts/seed_orders.py.

### Nächster Schritt
Implementierung: delete_seed_orders.py (Demo-Keys, isTestData-Sicherheitscheck, resource-API).

---

## 2026-08-19 13:03 — Schritt 7

### Aktion
Implementierung: `scripts/delete_seed_orders.py` (Abschnitt 18) — Cleanup ausschließlich Demo-Seed mit Sicherheitsbedingung `isTestData == true`.

### Command
Write: scripts/delete_seed_orders.py (demo_seed_keys aus Datei, find_existing_items, delete_demo_orders mit isTestData-Check, resource-API, --dry-run)

### Ergebnis
PASS

### Evidenz
- Keys werden aus der Demo-Datei gelesen (Single Source of Truth, deterministische IDs).
- Vor dem Delete BatchGetItem; nur Items mit `isTestData is True` werden gelöscht; fehlende/nicht-Testdaten-Items werden gezählt und übersprungen.
- boto3-resource-API (Marshalling korrekt-by-Konstruktion).
- `--dry-run` listet die 50 Keys auf, ohne zu löschen.

### Auswirkungen
Geändert: scripts/delete_seed_orders.py.

### Nächster Schritt
Lambda: isTestData als Storage-Marker dokumentieren + aus API-Antworten strippen.

---

## 2026-08-19 13:03 — Schritt 8

### Aktion
Lambda-Anpassung (Abschnitt 11): `isTestData` optional im Storage-Typ; aus API-Antworten entfernt; Tests TEST 13/14 ergänzt.

### Command
Edit: lambda/src/order_types.py (OrderDynamoItem.isTestData optional + Kommentar)
Edit: lambda/src/order_service.py (INTERNAL_FIELDS += "isTestData")
Edit: lambda/tests/test_order_service.py (+test_create_order_does_not_set_is_test_data, +test_returns_order_without_is_test_data_marker, Version-Inkrement-Assertion)

### Ergebnis
PASS

### Evidenz
- Normale Create-Orders setzen `isTestData` NICHT (Test 13, neu); zusätzlich weist `validation.py` unbekannte Felder im Create-Payload ab.
- Demo-Seed-Items tragen `isTestData=true` in DynamoDB, API-Antworten strippen es (Test neu).
- version-Inkrement (`#version = #version + :one`) im Status-Update-Assertion nachgezogen (Test 14).

### Auswirkungen
Geändert: lambda/src/order_types.py, lambda/src/order_service.py, lambda/tests/test_order_service.py.

### Nächster Schritt
Seed-Tests erweitern (TEST 1-12 + Demo-Deletion) und ausführen.

---

## 2026-08-19 13:04 — Schritt 9

### Aktion
Seed-Tests erweitert (Abschnitt 14, TEST 1-12 + Demo-Cleanup) und alle Tests ausgeführt.

### Command
Edit: scripts/tests/test_seed_orders.py (TestDemoSeedData TEST 1-9, TestDemoSeedImport TEST 10-12, TestDemoSeedDeletion)
python3 -m compileall -q scripts lambda/src
PYTHONPATH=scripts python3 -m unittest discover -s scripts/tests -v
PYTHONPATH=lambda/src python3 -m unittest discover -s lambda/tests -v
python3 scripts/seed_orders.py --dry-run
python3 scripts/delete_seed_orders.py --dry-run

### Ergebnis
PASS

### Evidenz
- Seed-Tests: **28/28 PASS** (bisher 14/14 + 14 neue Demo-Tests).
- Lambda-Tests: **51/51 PASS** (bisher 49/49 + 2 neue; Version-Assertion erweitert).
- `seed_orders.py --dry-run`: 50 validiert, 0 geschrieben.
- `delete_seed_orders.py --dry-run`: 50 Keys gelistet, nichts gelöscht.

### Auswirkungen
Geändert: scripts/tests/test_seed_orders.py.

### Nächster Schritt
Terraform: variable `seed_example_data` + main.tf anpassen, fmt/init/validate/plan.

---

## 2026-08-19 13:05 — Schritt 10

### Aktion
Terraform (Abschnitt 6/7/15): Variable `seed_example_data` (default false), `seed_file_path` → demo-50, `terraform_data.seed_orders` count umgestellt.

### Command
Edit: terraform/variables.tf, terraform/main.tf
terraform fmt -check terraform/
terraform init -input=false -backend=false
terraform validate
terraform plan (default)
terraform plan -var="seed_example_data=true"

### Ergebnis
PASS

### Evidenz
- `fmt -check` PASS · `init` PASS · `validate` PASS.
- Plan Default: **16 to add, 0 to change, 0 to destroy** — kein Beispiel-Import.
- Plan `-var="seed_example_data=true"`: **17 to add, 0 to change, 0 to destroy** — nur `terraform_data.seed_orders[0]` zusätzlich. Keine Replaces, keine Deletes.

### Auswirkungen
Geändert: terraform/variables.tf, terraform/main.tf.

### Nächster Schritt
Dokumentation aktualisieren (design.md, access-patterns, READMEs, PROJECT_STATUS, F011, WEEK-02, CHANGELOG) + Report DEMO-50.

---