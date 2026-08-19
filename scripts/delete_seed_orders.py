from __future__ import annotations

"""Entfernt ausschließlich Demo-Seed-Orders aus der DynamoDB-Tabelle.

Löscht NUR Items, deren (pk, sk) in der Demo-Seed-Datei
(database/seed/orders_seed_demo_50.json) definiert sind UND die aktuell
isTestData == true haben. Echte Orders (ohne isTestData=true) werden niemals
angetastet — die Sicherheitsbedingung ist: deterministische Seed-IDs UND
isTestData == true. Der Delete ist idempotent und wird NICHT automatisch bei
terraform destroy ausgeführt — dies ist ein bewusstes manuelles Cleanup-Skript.

Marshalling: wie der Importer nutzt das Skript die boto3-**resource**-API
(automatisches AttributeValue-Marshalling, identisch zum Lambda-Pfad).

Verwendung:
    python3 scripts/delete_seed_orders.py --table mays-orders
"""

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

ORDER_SK = "#ORDER"

BATCH_WRITE_LIMIT = 25
MAX_RETRIES = 8
BASE_BACKOFF_SECONDS = 0.2

DEFAULT_SEED_FILE = "database/seed/orders_seed_demo_50.json"

_dynamodb_resource = None


def _get_dynamodb_resource():
    global _dynamodb_resource
    if _dynamodb_resource is None:
        try:
            import boto3  # type: ignore[reportMissingImports]
        except ImportError as exc:  # pragma: no cover - nur bei echtem AWS-Import relevant
            raise SystemExit(
                "boto3 ist nicht installiert (pip install boto3)."
            ) from exc
        _dynamodb_resource = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "eu-central-1"))
    return _dynamodb_resource


def demo_seed_keys(file_path: str = DEFAULT_SEED_FILE) -> List[Dict[str, str]]:
    """Die deterministischen Demo-Seed-Keys direkt aus der Seed-Datei (Single Source of Truth)."""
    with open(file_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"{file_path}: erwartet wurde ein JSON-Array")
    keys: List[Dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict) or "pk" not in item or "sk" not in item:
            raise ValueError(f"{file_path}: ungültiges Item (pk/sk fehlen)")
        keys.append({"pk": item["pk"], "sk": item["sk"]})
    if not keys:
        raise ValueError(f"{file_path}: keine Demo-Seed-Keys gefunden")
    return keys


def _chunks(items: List[Any], size: int) -> List[List[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def find_existing_items(client: Any, table_name: str, keys: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Liest die vorhandenen Items zu den Demo-Keys per BatchGetItem."""
    existing: List[Dict[str, Any]] = []
    for chunk in _chunks(keys, 100):
        request_items = {table_name: {"Keys": chunk}}
        response = client.batch_get_item(RequestItems=request_items)
        existing.extend(response.get("Responses", {}).get(table_name, []))
        for attempt in range(MAX_RETRIES):
            unprocessed = response.get("UnprocessedKeys", {})
            if not unprocessed:
                break
            time.sleep(BASE_BACKOFF_SECONDS * (2 ** attempt))
            response = client.batch_get_item(RequestItems=unprocessed)
            existing.extend(response.get("Responses", {}).get(table_name, []))
    return existing


def delete_demo_orders(
    client: Any,
    table_name: str,
    file_path: str = DEFAULT_SEED_FILE,
) -> Dict[str, int]:
    """Löscht ausschließlich Demo-Seed-Items (deterministische IDs + isTestData == true)."""
    keys = demo_seed_keys(file_path)
    existing_items = find_existing_items(client, table_name, keys)
    existing_by_key = {(item["pk"], item["sk"]): item for item in existing_items}

    to_delete: List[Dict[str, str]] = []
    skipped_not_found = 0
    skipped_not_test_data = 0
    for key in keys:
        item = existing_by_key.get((key["pk"], key["sk"]))
        if item is None:
            skipped_not_found += 1
        elif item.get("isTestData") is not True:
            skipped_not_test_data += 1
        else:
            to_delete.append(key)

    stats = {
        "deleted": 0,
        "retries": 0,
        "skipped_not_found": skipped_not_found,
        "skipped_not_test_data": skipped_not_test_data,
    }

    for chunk in _chunks(to_delete, BATCH_WRITE_LIMIT):
        pending = [{"DeleteRequest": {"Key": key}} for key in chunk]
        while pending:
            response = client.batch_write_item(RequestItems={table_name: pending})
            unprocessed = response.get("UnprocessedItems", {}).get(table_name, [])
            stats["deleted"] += len(pending) - len(unprocessed)
            if unprocessed:
                stats["retries"] += 1
                pending = unprocessed
                time.sleep(BASE_BACKOFF_SECONDS * (2 ** stats["retries"]))
            else:
                pending = []
            if stats["retries"] >= MAX_RETRIES:
                raise RuntimeError(
                    f"BatchWriteItem (Delete) nach {MAX_RETRIES} Versuchen nicht vollständig"
                )
    return stats


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Entfernt Demo-Seed-Orders (isTestData=true) aus DynamoDB"
    )
    parser.add_argument("--table", default=os.environ.get("ORDERS_TABLE", "mays-orders"))
    parser.add_argument("--file", default=DEFAULT_SEED_FILE)
    parser.add_argument("--dry-run", action="store_true", help="Keys nur auflisten, nichts löschen")
    args = parser.parse_args(argv)

    try:
        keys = demo_seed_keys(args.file)
    except (ValueError, FileNotFoundError) as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"DRY-RUN: würde Demo-Seed-Orders löschen (Tabelle '{args.table}'):")
        for key in keys:
            print(f"  {key['pk']} / {key['sk']}")
        print(f"  ({len(keys)} Keys aus {args.file}; nur Items mit isTestData=true)")
        return 0

    try:
        active_client = _get_dynamodb_resource()
        stats = delete_demo_orders(active_client, args.table, args.file)
    except (RuntimeError, ValueError) as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 1

    print(f"Löschen abgeschlossen (Tabelle '{args.table}'):")
    print(f"  gelöscht:           {stats['deleted']}")
    print(f"  übersprungen (fehlt): {stats['skipped_not_found']}")
    print(f"  übersprungen (kein isTestData): {stats['skipped_not_test_data']}")
    print(f"  retries:            {stats['retries']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())