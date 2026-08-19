# DynamoDB Testdaten-Seed (1.000 Orders) — Report

> **Checkpoint:** DynamoDB Seed 1000 (F011, Branch `feature/dynamodb-seed`)
> **Zweck:** Kontrollierter, idempotenter Import deterministischer Test-Orders
> (`ord_00001`…`ord_01000`) in die bestehende DynamoDB-Tabelle `mays-orders`.

## 1. Ausgangslage & Ziel

Die Lambda (AP1…AP4) und die Access Patterns (`database/access-patterns.md`)
sind implementiert, aber es gibt **noch keine Testdaten** in DynamoDB. Für
Entwicklung, manuelle API-Tests und die Woche-3-Verifikation werden 1.000
realistische Beispiel-Orders benötigt.

Ziel: ein **sicherer, idempotenter, opt-in** Seed-Mechanismus, der die
bereitgestellte Datei `orders_seed_1000.jsonl` unverändert ins Repo übernimmt,
die Items beim Import auf das dokumentierte Item-Modell normalisiert und
standardmäßig **deaktiviert** bleibt (kein automatischer Seed bei `apply`).

## 2. Seed-Datei & Schema-Konformität (Punkt „STOP & dokumentieren")

**Datei:** `database/seed/orders_seed_1000.jsonl` (1.000 Zeilen, 514 KB),
als Ausgangsdatei **unverändert** ins Repo übernommen.

### Verifikation gegen `database/dynamodb-design.md` §2 (automatisiert, 100 % der Zeilen)

| Prüfung | Ergebnis |
|---------|----------|
| Zeilen/Orders | 1.000 / 1.000 ✓ |
| `pk` = `ORDER#<orderId>` | 1.000/1.000 ✓ |
| `sk` = `#ORDER` | 1.000/1.000 ✓ |
| `orderId` Format `ord_[A-Za-z0-9]+` | 1.000/1.000 ✓ |
| Eindeutige `pk`+`sk` (keine Duplikate) | ✓ |
| `gsi1pk` = `LIST` | 1.000/1.000 ✓ |
| `gsi1sk` = `createdAt` | 1.000/1.000 ✓ |
| `status` ∈ gültige Statusmenge | 1.000/1.000 ✓ (250/250/250/250) |
| `currency` = EUR | 1.000/1.000 ✓ |
| `totalAmount` Integer (Cent) | 1.000/1.000 ✓ |
| `totalAmount` == Σ `quantity × unitPrice` | 1.000/1.000 ✓ |
| `createdAt`/`updatedAt` ISO-8601 UTC | 1.000/1.000 ✓ |
| `customer` = `{ name, email }` | 1.000/1.000 ✓ |

**Keine doppelten `orderId`**, keine `CANCELLED`-Pfad-Verletzungen, keine
Betrags-/Zeitstempel-Anomalien.

### Dokumentierte Abweichungen vom Item-Modell (bewusst, nicht schema-kritisch)

Die Datei enthält drei Punkte, die vom strikten Item-Modell abweichen.
Das Datenmodell ist die Source of Truth (`dynamodb-design.md` §2); die Datei
**wird nicht verändert**. Stattdessen normalisiert der Importer **beim Schreiben**:

| Punkt | Datei | Item-Modell | Behandlung beim Import |
|-------|-------|-------------|------------------------|
| `items[].lineTotal` | fehlt | dokumentiert (`quantity × unitPrice`) | wird berechnet (`normalize_item`) |
| `items[].name` | vorhanden (Buchtitel) | **nicht** im Modell | wird **nicht** gespeichert (kein zusätzliches Feld) |
| `version` | fehlt | dokumentiert (Optimistic-Locking, `1`) | wird auf `1` gesetzt (`normalize_item`) |

Begründung: `lineTotal`/`version` werden auch im Normalbetrieb server-seitig
von AP1 gesetzt (`order_service.create_order`); der Seed-Import gleicht die
Testdaten damit exakt dem dokumentierten Modell an. Die Datei bleibt als
Ausgangsdokument erhalten (Determinismus, Nachvollziehbarkeit).

## 3. Implementierung

### `scripts/seed_orders.py` — idempotenter Importer

- **CLI:** `python3 scripts/seed_orders.py --table mays-orders --file database/seed/orders_seed_1000.jsonl [--dry-run]`
- **Laden & Validieren:** JSONL zeilenweise, jedes Item gegen das Modell
  validiert (`validate_seed_item`); Abbruch mit klarer Fehlermeldung bei
  Verstößen (Datei ist nicht die Source of Truth).
- **Normalisierung:** `lineTotal = quantity × unitPrice`, `version = 1`,
  `items[].name` wird nicht übernommen.
- **Idempotenz:** vor dem Schreiben per `batch_get_item` (Chunks à 100)
  ermittelt der Importer existierende `pk`+`sk` und **überspringt** diese.
  Ein zweiter Lauf schreibt 0 Items (TEST 9). Deterministische Keys
  (`ord_00001`…`ord_01000`) garantieren Eindeutigkeit.
- **Schreiben:** `batch_write_item` (Chunks à 25), `UnprocessedItems` werden
  mit exponentiell ansteigendem Backoff nachgezogen (max. 8 Versuche).
- **Statistik:** gesamt / geschrieben / übersprungen; `--dry-run` validiert
  nur, ohne zu schreiben.

### `scripts/delete_seed_orders.py` — kontrolliertes Cleanup

- Löscht **ausschließlich** die deterministischen Seed-Keys
  `ORDER#ord_00001`…`ORDER#ord_01000` (`sk` = `#ORDER`).
- **Nicht** automatisch bei `terraform destroy` — bewusst manuelles Skript.
- `--dry-run` listet die betroffenen Keys nur auf (Audit-Trail).

### `terraform/` — opt-in Integration

- `variables.tf`: `seed_test_data` (`bool`, **Default `false`**) +
  `seed_file_path` (Default `database/seed/orders_seed_1000.jsonl`).
- `main.tf`: `terraform_data.seed_orders` mit `count = var.seed_test_data ? 1 : 0`.
  - Trigger = SHA256 der Seed-Datei + Tabellenname → **kein Re-Run bei jedem
    apply**, nur bei geänderter Datei (oder neuem `seed_test_data=true`).
  - Der Importer ist zusätzlich idempotent (Doppel-Schutz).
  - `local-exec` führt `scripts/seed_orders.py` aus.
- **Kein automatischer Seed** im Standard-`apply`: Plan bleibt bei
  `16 to add` (identisch zu T011-07). Mit `-var="seed_test_data=true"`
  wird zusätzlich die Seed-Ressource geplant (`17 to add`).

## 4. IAM / Sicherheit (Least Privilege)

- Der Seed läuft **lokal** mit den AWS-Credentials des Entwicklers (Standard-
  boto3-Credential-Chain) — **keine** Erweiterung der Lambda-Execution-Role.
- Benötigte Berechtigungen (nur für die Seed-Ausführung, nicht Teil der
  Terraform-Policy): `dynamodb:BatchWriteItem`, `dynamodb:BatchGetItem` auf
  die Tabelle `mays-orders`. Der Seeder braucht **kein** `Scan`, kein
  `DeleteItem` (das macht das separate Cleanup-Skript).
- Keine Secrets, keine echten PII (fiktive Beispiel-Kunden), keine
  Zugriffsschlüssel im Repo.

## 5. Tests (automatisiert, `scripts/tests/test_seed_orders.py`)

Lauf: `PYTHONPATH=scripts python3 -m unittest discover -s scripts/tests -v`

| Test | Prüfung | Ergebnis |
|------|---------|----------|
| TEST 1 | exakt 1.000 Orders in der Datei | PASS |
| TEST 2 | `pk`/`sk`-Felder korrekt (`ORDER#ord_…`, `#ORDER`) | PASS |
| TEST 3 | keine doppelten `pk`+`sk` | PASS |
| TEST 4 | GSI-Felder korrekt (`gsi1pk=LIST`, `gsi1sk=createdAt`) | PASS |
| TEST 5 | Statuswerte gültig | PASS |
| TEST 6 | Beträge valide (int, Cent, Summeninvariante) | PASS |
| TEST 7 | Zeitstempel valide ISO-8601 UTC | PASS |
| TEST 8 | Import schreibt 1.000 Items (Fake-Client) | PASS |
| TEST 9 | zweiter Lauf idempotent — 0 neu, 0 Duplikate | PASS |
| TEST 10 | Item-Count = 1.000 nach Import | PASS |
| – | Normalisierung (`lineTotal`, `version`, `name`-Entfernung) | PASS |
| – | `dry-run` schreibt nichts | PASS |
| – | Delete-Skript löscht nur Seed-Range (Nicht-Seed-Item bleibt) | PASS |

**Ergebnis: 14/14 PASS.** Real-AWS-Import ist erst nach `apply` möglich
(TEST 8–10 gegen Fake-Client; Live-Verifizierung ⏳ PLANNED / nach Freigabe).

## 6. Access-Pattern-Bezug

- AP2 (`GetItem`), AP3 (GSI1-`Query`, absteigend) und AP4 (`UpdateItem`
  conditional) arbeiten unverändert auf den Seed-Daten — der Seed erzeugt
  **keine** neuen Access Patterns und **keinen** `Scan` im Seeder.
- GSI1 (`LIST`) bleibt konsistent: `gsi1sk = createdAt` ermöglicht das
  Listen „neueste zuerst" auch für die Testdaten.

## 7. Kosten

- 1.000 kleine Items in On-Demand-DynamoDB (Free-Tier-freundlich); keine
  zusätzlichen AWS-Ressourcen, kein dauerhaft laufender Dienst, kein
  Event-Loop/Seeder-Service. Nur ein einmaliger Batch-Import.

## 8. Validierung (dieser Checkpoint)

| Prüfung | Ergebnis |
|---------|----------|
| `python3 -m compileall -q scripts` | PASS |
| `PYTHONPATH=scripts python3 -m unittest discover -s scripts/tests -v` | PASS (14/14) |
| `python3 scripts/seed_orders.py --dry-run` | PASS (1.000 validiert, 0 geschrieben) |
| `terraform fmt -check` / `init` / `validate` | PASS |
| `terraform plan` (Default) | `16 to add` — unverändert, kein Seed |
| `terraform plan -var="seed_test_data=true"` | `17 to add` — nur Seed-Ressource zusätzlich |
| `terraform apply` | **NOT RUN** — Freigabe erforderlich (T011-08) |
| `git diff --check` · Secret-Audit | PASS |

## 9. Aktivierung (nur nach menschlicher Freigabe)

```bash
terraform apply -var="seed_test_data=true"   # Opt-in: Seed läuft beim apply
python3 scripts/delete_seed_orders.py --table mays-orders   # Cleanup (manuell)
```

## 10. Status

- Seed-Datei, Importer, Cleanup, Tests, Terraform-Opt-in und Doku:
  **COMPLETE**.
- AWS-Ressourcen: **NONE** (kein `apply`). Live-Seed: ⏳ PLANNED
  (nach Freigabe, T011-08).
- Keine Datenmodell-Änderung; keine IAM-Erweiterung der Lambda-Role.