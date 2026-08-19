# DynamoDB Demo-Seed (50 Orders) — Finalisierungs-Report

> **Checkpoint:** T011-10 Finalisierung (F011, Branch `feature/dynamodb-seed-finalization`)
> **Zweck:** 50 kontrollierte, deterministische Demo-Orders als **opt-in** Seed
> (`seed_example_data=false`), Modell-konform (`version`, `isTestData`,
> `lineTotal`), boto3-**resource**-API (Marshalling wie Produktivpfad), sicheres
> Cleanup. **Kein `apply`, kein Live-Import.**

## 1. Ausgangslage & Ziel

Der 1.000er-Seed (`orders_seed_1000.jsonl`, `DYNAMODB-SEED-1000.md`) ist
funktional, aber seine Datei weicht an drei Stellen vom Item-Modell ab
(`lineTotal`/`version` fehlend, `items[].name` zusätzlich — erst beim Import
normalisiert). Für Demo-Präsentation und manuelle API-Tests wird eine **kleine,
modell-konforme, deterministische** Demo-Seed-Datei (50 Orders) bereitgestellt,
die **unverändert** in die Tabelle geschrieben wird (keine Import-Normalisierung
nötig).

## 2. Demo-Seed-Datei `database/seed/orders_seed_demo_50.json`

**50 Orders, JSON-Array, Top-Level-Felder (14):** `pk, sk, orderId, status,
customer, items, currency, totalAmount, createdAt, updatedAt, version,
isTestData, gsi1pk, gsi1sk`.

| Prüfung | Ergebnis |
|---------|----------|
| Anzahl Orders | 50 / 50 ✓ |
| `pk = ORDER#<orderId>`, `sk = #ORDER` | 50/50 ✓ |
| Eindeutige `pk`+`sk` (0 Duplikate) | ✓ |
| `gsi1pk = LIST`, `gsi1sk = createdAt` | 50/50 ✓ |
| Status-Verteilung | PENDING 12 · CONFIRMED 13 · SHIPPED 13 · CANCELLED 12 ✓ |
| `version = 1` | 50/50 ✓ |
| `isTestData = true` | 50/50 ✓ |
| `lineTotal == quantity × unitPrice` | alle ✓ |
| `totalAmount == Σ lineTotal` | alle ✓ |
| `createdAt`/`updatedAt` ISO-8601 UTC | 50/50 ✓ |
| Kunden | 10 verschiedene fiktive Personen ✓ |

Die Datei **entspricht bereits dem Storage-Modell** (`dynamodb-design.md` §2)
und wird **unverändert** importiert.

## 3. Datenmodell-Klärung (version / isTestData)

- **`version` = reguläres Order-Feld** (Optimistic-Locking): wird von `create_order`
  auf `1` gesetzt und bei Status-Updates (`#version = #version + :one`) per
  Conditional Write inkrementiert. Teil von `OrderDynamoItem`, in
  `INTERNAL_FIELDS` (aus API-Antworten gestrippt).
- **`isTestData` = reiner Testdaten-Marker**: wird von `create_order` **nie**
  gesetzt; `validate_create_order` weist unbekannte Felder ab (ein Client kann es
  nicht setzen). Nur der Demo-Seed trägt `isTestData=true`; `order_service`
  entfernt das Feld aus allen API-Antworten (`INTERNAL_FIELDS`).

## 4. Implementierung

| Komponente | Änderung |
|------------|----------|
| `scripts/seed_orders.py` | JSON-Array-**und** JSONL-Loader (Datei-Start `[` → Array), minimale Normalisierung (`lineTotal`/`version` ergänzen nur falls fehlend, `items[].name` entfernen), Validierung (`validate_seed_item`), boto3-**resource**-API (auto-Marshalling wie `order_service.py`), Default-Datei = demo-50, `--dry-run` |
| `scripts/delete_seed_orders.py` | Demo-Keys direkt aus der Seed-Datei (Single Source of Truth) + Sicherheitsbedingung **`isTestData == true`**; nur Items mit `isTestData=true` werden gelöscht, fehlende/Nicht-Testdaten-Items werden gezählt und übersprungen; `--dry-run` listet nur |
| `lambda/src/order_types.py` | `OrderDynamoItem.isTestData` (optional) + Kommentar (Seed-Marker, kein Produktfeld) |
| `lambda/src/order_service.py` | `INTERNAL_FIELDS` += `isTestData` → wird aus API-Antworten gestrippt |
| `terraform/variables.tf` | `seed_example_data` (bool, **Default `false`**) + `seed_file_path` (Default `database/seed/orders_seed_demo_50.json`) |
| `terraform/main.tf` | `terraform_data.seed_orders` (count = `seed_example_data`, Trigger = SHA256 der Seed-Datei + Tabellenname; `local-exec` → `seed_orders.py`) |

## 5. Tests

| Suite | Ergebnis |
|-------|----------|
| Seed-Tests (`scripts/tests`, TEST 1–12 + Demo-Daten/Import/Deletion) | **28/28 PASS** |
| Lambda-Tests (`lambda/tests`, u. a. `isTestData` wird nie gesetzt + aus Antworten gestrippt, Version-Inkrement) | **51/51 PASS** |
| `python3 -m compileall -q scripts lambda/src` | PASS |
| `python3 scripts/seed_orders.py --dry-run` | 50 validiert, 0 geschrieben |
| `python3 scripts/delete_seed_orders.py --dry-run` | 50 Keys gelistet, nichts gelöscht |

## 6. Terraform-Validierung

| Prüfung | Ergebnis |
|---------|----------|
| `terraform fmt -check` / `init` / `validate` | PASS |
| `terraform plan` (Default) | **16 to add**, 0 to change, 0 to destroy — kein Beispiel-Import |
| `terraform plan -var="seed_example_data=true"` | **17 to add** — nur `terraform_data.seed_orders[0]` zusätzlich, keine Replaces/Deletes |
| `terraform apply` | **NOT RUN** (Freigabe erforderlich) |
| `git diff --check` · Secret-Audit | PASS |

## 7. Kosten & Sicherheit

- Keine zusätzlichen AWS-Ressourcen (nur opt-in Import-Schritt; kein dauerhafter
  Dienst). Keine IAM-Erweiterung der Lambda-Role. Keine Secrets/PII.
- Cleanup nur über deterministische Demo-IDs **und** `isTestData==true` — echte
  Orders werden nie angetastet.

## 8. Status

- Demo-Seed-Datei, Importer, Cleanup, Lambda-Marker, Tests, Terraform-Opt-in,
  Doku: **COMPLETE**.
- AWS-Ressourcen: **NONE** (kein `apply`). Live-Import/`delete`: ⏳ PLANNED
  (nach Freigabe).
- `version` als reguläres Order-Feld bestätigt; `isTestData` nur Seed-Marker.
- 1.000er-Seed (`orders_seed_1000.jsonl`) bleibt als optionaler größerer
  Test-/Load-Seed erhalten.
