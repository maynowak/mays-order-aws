from __future__ import annotations

"""Idempotenter DynamoDB-Seed-Importer für May's Orders.

Lädt deterministische Test-Orders (ord_00001 … ord_01000) aus einer JSONL-Datei
(database/seed/orders_seed_1000.jsonl) und schreibt sie in die bestehende
DynamoDB-Tabelle. Vorhandene Items (pk+sk) werden übersprungen — die Operation
ist dadurch idempotent und erzeugt keine Duplikate.

Normalisierung beim Import (dokumentiert, siehe DYNAMODB-SEED-1000.md):
- items[].lineTotal = quantity × unitPrice  (server-seitig, wie AP1)
- version = 1                                (Optimistic-Locking-Feld)
- items[].name wird NICHT gespeichert        (nicht Teil des Item-Modells)
Die Seed-Datei selbst bleibt unverändert.

Verwendung:
    python3 scripts/seed_orders.py --table mays-orders \
        --file database/seed/orders_seed_1000.jsonl
"""

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

ORDER_SK = "#ORDER"
GSI1_PK = "LIST"
ORDER_STATUSES = {"PENDING", "CONFIRMED", "PROCESSING", "SHIPPED", "DELIVERED", "CANCELLED"}

BATCH_GET_LIMIT = 100
BATCH_WRITE_LIMIT = 25
MAX_RETRIES = 8
BASE_BACKOFF_SECONDS = 0.2

_dynamodb_client = None


def _get_dynamodb_client():
    """Boto3-Client lazy erzeugen (lokal ist boto3 nicht installiert)."""
    global _dynamodb_client
    if _dynamodb_client is None:
        try:
            import boto3  # type: ignore[reportMissingImports]
        except ImportError as exc:  # pragma: no cover - nur bei echtem AWS-Import relevant
            raise SystemExit(
                "boto3 ist nicht installiert (pip install boto3). "
                "Die Unit-Tests injizieren einen Fake-Client und brauchen boto3 nicht."
            ) from exc
        _dynamodb_client = boto3.client("dynamodb", region_name=os.environ.get("AWS_REGION", "eu-central-1"))
    return _dynamodb_client


def normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Normalisiert ein Item auf das dokumentierte Item-Modell (dynamodb-design.md §2)."""
    normalized = dict(item)
    normalized["items"] = [
        {
            "sku": raw.get("sku"),
            "quantity": raw.get("quantity"),
            "unitPrice": raw.get("unitPrice"),
            "lineTotal": raw.get("quantity", 0) * raw.get("unitPrice", 0),
        }
        for raw in item.get("items", [])
    ]
    normalized["version"] = 1
    return normalized


def validate_seed_item(item: Dict[str, Any]) -> None:
    """Validiert ein geladenes Seed-Item gegen das dokumentierte Item-Modell.

    Bei Verstößen wird ValueError mit einer präzisen Meldung geworfen — das
    Modell (dynamodb-design.md §2) ist die Source of Truth, nicht die Datei.
    """
    required = {
        "pk", "sk", "orderId", "status", "customer", "items",
        "currency", "totalAmount", "createdAt", "updatedAt",
        "gsi1pk", "gsi1sk",
    }
    missing = required.difference(item)
    if missing:
        raise ValueError(f"Fehlende Pflichtfelder: {sorted(missing)}")

    if item["sk"] != ORDER_SK:
        raise ValueError(f"sk muss '{ORDER_SK}' sein, ist '{item['sk']}'")
    if item["gsi1pk"] != GSI1_PK:
        raise ValueError(f"gsi1pk muss '{GSI1_PK}' sein, ist '{item['gsi1pk']}'")
    if item["gsi1sk"] != item["createdAt"]:
        raise ValueError("gsi1sk muss identisch zu createdAt sein")

    if not str(item["pk"]).startswith("ORDER#"):
        raise ValueError(f"pk muss mit 'ORDER#' beginnen, ist '{item['pk']}'")
    if item["status"] not in ORDER_STATUSES:
        raise ValueError(f"Ungültiger Status '{item['status']}'")

    customer = item["customer"]
    if not isinstance(customer, dict) or not customer.get("name") or not customer.get("email"):
        raise ValueError("customer muss {name, email} enthalten")

    if not isinstance(item["items"], list) or len(item["items"]) < 1:
        raise ValueError("items muss eine nicht-leere Liste sein")
    for raw in item["items"]:
        if not isinstance(raw, dict):
            raise ValueError("Jedes Item muss ein Objekt sein")
        missing_item = {"sku", "quantity", "unitPrice"}.difference(raw)
        if missing_item:
            raise ValueError(f"Item-Felder fehlen: {sorted(missing_item)}")
        if not isinstance(raw.get("quantity"), int) or raw["quantity"] < 1:
            raise ValueError("quantity muss ein Integer >= 1 sein")
        if not isinstance(raw.get("unitPrice"), int) or raw["unitPrice"] < 1:
            raise ValueError("unitPrice muss ein Integer >= 1 sein")

    if not isinstance(item["totalAmount"], int) or item["totalAmount"] < 1:
        raise ValueError("totalAmount muss ein positiver Integer sein (Cent)")
    computed = sum(raw["quantity"] * raw["unitPrice"] for raw in item["items"])
    if computed != item["totalAmount"]:
        raise ValueError(
            f"totalAmount {item['totalAmount']} != Summe der Items {computed}"
        )


def load_seed_items(file_path: str) -> List[Dict[str, Any]]:
    """Lädt alle Zeilen der JSONL-Datei und validiert jedes Item."""
    items: List[Dict[str, Any]] = []
    with open(file_path, "r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Zeile {line_number}: kein gültiges JSON: {exc}") from exc
            if not isinstance(item, dict):
                raise ValueError(f"Zeile {line_number}: erwartet wurde ein JSON-Objekt")
            try:
                validate_seed_item(item)
            except ValueError as exc:
                raise ValueError(f"Zeile {line_number} ({item.get('orderId', '?')}): {exc}") from exc
            items.append(item)
    if not items:
        raise ValueError("Die Seed-Datei enthält keine Items")
    return items


def _chunks(items: List[Any], size: int) -> List[List[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def find_existing_keys(client: Any, table_name: str, items: List[Dict[str, Any]]) -> set:
    """Bestimmt per BatchGetItem, welche pk+sk bereits existieren (Idempotenz)."""
    existing: set = set()
    for chunk in _chunks(items, BATCH_GET_LIMIT):
        keys = [{"pk": item["pk"], "sk": item["sk"]} for item in chunk]
        request_items = {table_name: {"Keys": keys}}
        response = client.batch_get_item(RequestItems=request_items)
        for item in response.get("Responses", {}).get(table_name, []):
            existing.add((item["pk"], item["sk"]))
        # UnprocessedKeys mit Backoff nachziehen
        for attempt in range(MAX_RETRIES):
            unprocessed = response.get("UnprocessedKeys", {})
            if not unprocessed:
                break
            time.sleep(BASE_BACKOFF_SECONDS * (2 ** attempt))
            response = client.batch_get_item(RequestItems=unprocessed)
            for item in response.get("Responses", {}).get(table_name, []):
                existing.add((item["pk"], item["sk"]))
    return existing


def write_items(
    client: Any,
    table_name: str,
    items: List[Dict[str, Any]],
) -> Dict[str, int]:
    """Schreibt Items per BatchWriteItem und zieht UnprocessedItems mit Backoff nach."""
    stats = {"written": 0, "retries": 0}
    for chunk in _chunks(items, BATCH_WRITE_LIMIT):
        pending = [{"PutRequest": {"Item": item}} for item in chunk]
        while pending:
            response = client.batch_write_item(
                RequestItems={table_name: pending}
            )
            unprocessed = response.get("UnprocessedItems", {}).get(table_name, [])
            written = len(pending) - len(unprocessed)
            stats["written"] += written
            if unprocessed:
                stats["retries"] += 1
                pending = unprocessed
                time.sleep(BASE_BACKOFF_SECONDS * (2 ** stats["retries"]))
            else:
                pending = []
            if stats["retries"] >= MAX_RETRIES:
                raise RuntimeError(
                    f"BatchWriteItem nach {MAX_RETRIES} Versuchen nicht vollständig"
                )
    return stats


def import_orders(
    table_name: str,
    file_path: str,
    client: Any = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Führt den idempotenten Seed-Import durch und liefert Statistiken."""
    raw_items = load_seed_items(file_path)
    items = [normalize_item(item) for item in raw_items]

    if dry_run:
        return {
            "total": len(items),
            "written": 0,
            "skipped": len(items),
            "dry_run": True,
        }

    active_client = client if client is not None else _get_dynamodb_client()
    existing = find_existing_keys(active_client, table_name, items)

    to_write = [item for item in items if (item["pk"], item["sk"]) not in existing]
    stats = {"total": len(items), "skipped": len(items) - len(to_write), "dry_run": False}
    if to_write:
        stats.update(write_items(active_client, table_name, to_write))
    else:
        stats["written"] = 0
    return stats


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Idempotenter DynamoDB-Seed-Importer")
    parser.add_argument("--table", default=os.environ.get("ORDERS_TABLE", "mays-orders"))
    parser.add_argument(
        "--file",
        default="database/seed/orders_seed_1000.jsonl",
    )
    parser.add_argument("--dry-run", action="store_true", help="Nur validieren, nichts schreiben")
    args = parser.parse_args(argv)

    try:
        stats = import_orders(args.table, args.file, dry_run=args.dry_run)
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 1

    mode = "DRY-RUN (kein Schreiben)" if stats.get("dry_run") else "Import"
    print(f"{mode} auf Tabelle '{args.table}'")
    print(f"  gesamt:     {stats['total']}")
    print(f"  geschrieben: {stats['written']}")
    print(f"  übersprungen (existiert bereits): {stats['skipped']}")
    if not stats.get("dry_run") and stats["written"] > 0 and stats["skipped"] == 0:
        print(f"  OK — {stats['written']} Items geschrieben")
    elif not stats.get("dry_run"):
        print(f"  OK — idempotent, {stats['skipped']} bereits vorhandene übersprungen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
