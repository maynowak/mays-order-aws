# May's Orders — Database

## DynamoDB (Single-Table, `mays-orders`)

- **Item-Modell:** `dynamodb-design.md` (Source of Truth)
- **Access Patterns:** `access-patterns.md` (AP1…AP4, Query statt Scan)
- **Infrastruktur:** `terraform/main.tf` → `aws_dynamodb_table.orders` (T011-02)

## Testdaten-Seed (opt-in)

Für Entwicklung und manuelle API-Tests liegen 1.000 deterministische
Beispiel-Orders in `seed/orders_seed_1000.jsonl` (`ord_00001`…`ord_01000`).

**Standardmäßig deaktiviert.** Der Seed läuft nur mit bewusster Aktivierung:

```bash
# 1) Infrastruktur anlegen + Seed beim apply ausführen (nach Freigabe):
terraform apply -var="seed_test_data=true"

# 2) Oder Seed manuell gegen die bereits bestehende Tabelle laufen lassen:
python3 scripts/seed_orders.py --table mays-orders \
    --file database/seed/orders_seed_1000.jsonl
```

Der Importer ist **idempotent**: vorhandene `pk`+`sk` werden übersprungen,
ein zweiter Lauf erzeugt keine Duplikate. Beim Import wird normalisiert
(`lineTotal = quantity × unitPrice`, `version = 1`); die Datei selbst bleibt
unverändert. Details: `docs/reports/DYNAMODB-SEED-1000.md`.

**Cleanup** (nur die deterministischen Seed-Keys, nicht bei `terraform destroy`):

```bash
python3 scripts/delete_seed_orders.py --table mays-orders
```