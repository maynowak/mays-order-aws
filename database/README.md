# May's Orders — Database

## DynamoDB (Single-Table, `mays-orders`)

- **Item-Modell:** `dynamodb-design.md` (Source of Truth)
- **Access Patterns:** `access-patterns.md` (AP1…AP4, Query statt Scan)
- **Infrastruktur:** `terraform/main.tf` → `aws_dynamodb_table.orders` (T011-02)

## Testdaten-Seed (opt-in)

**Bevorzugter Demo-Seed:** 50 deterministische Beispiel-Orders in
`seed/orders_seed_demo_50.json` (`ord_00001`…`ord_01000`, ausgewählte IDs).
Die Datei entspricht bereits dem Storage-Modell (inkl. `version = 1`,
`isTestData = true`, `lineTotal`) und wird unverändert importiert.

**Optionaler größerer Test-/Load-Seed:** `seed/orders_seed_1000.jsonl`
(1.000 deterministische Orders `ord_00001`…`ord_01000`); fehlende Modellfelder
werden beim Import normalisiert.

**Standardmäßig deaktiviert.** Der Seed läuft nur mit bewusster Aktivierung:

```bash
# 1) Infrastruktur anlegen + Demo-Seed beim apply ausführen (nach Freigabe):
terraform apply -var="seed_example_data=true"

# 2) Oder Seed manuell gegen die bereits bestehende Tabelle laufen lassen:
python3 scripts/seed_orders.py --table mays-orders \
    --file database/seed/orders_seed_demo_50.json
```

Der Importer ist **idempotent**: vorhandene `pk`+`sk` werden übersprungen,
ein zweiter Lauf erzeugt keine Duplikate. Das Marshalling läuft über die
boto3-**resource**-API (wie der produktive Lambda-Pfad) — plain Python-Dicts
werden automatisch in DynamoDB-AttributeValue-Maps umgesetzt. Details:
`docs/reports/DYNAMODB-SEED-DEMO-50.md`.

**Cleanup** (ausschließlich Demo-Seed-Keys mit `isTestData = true`, nicht bei
`terraform destroy`):

```bash
python3 scripts/delete_seed_orders.py --table mays-orders
```