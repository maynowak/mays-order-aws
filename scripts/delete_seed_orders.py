from __future__ import annotations

"""Entfernt deterministische Seed-Test-Orders aus der DynamoDB-Tabelle.

Löscht ausschließlich die Items mit pk = ORDER#ord_00001 … ORDER#ord_01000
(sk = #ORDER). Andere Keys werden niemals angefasst. Der Delete ist idempotent
und wird NICHT automatisch bei terraform destroy ausgeführt — dies ist ein
bewusstes manuelles Cleanup-Skript.

Verwendung:
    python3 scripts/delete_seed_orders.py --table mays-orders
"""

import argparse
import os
import sys
import time
from typing import Any, Dict, List, Optional

ORDER_SK = "#ORDER"
FIRST_ID = 1
LAST_ID = 1000

BATCH_WRITE_LIMIT = 25
MAX_RETRIES = 8
BASE_BACKOFF_SECONDS = 0.2

_dynamodb_client = None


def _get_dynamodb_client():
    global _dynamodb_client
    if _dynamodb_client is None:
        try:
            import boto3  # type: ignore[reportMissingImports]
        except ImportError as exc:  # pragma: no cover - nur bei echtem AWS-Import relevant
            raise SystemExit(
                "boto3 ist nicht installiert (pip install boto3)."
            ) from exc
        _dynamodb_client = boto3.client("dynamodb", region_name=os.environ.get("AWS_REGION", "eu-central-1"))
    return _dynamodb_client


def seed_keys() -> List[Dict[str, str]]:
    """Die deterministischen Seed-Keys ord_00001 … ord_01000."""
    return [
        {"pk": f"ORDER#ord_{order_id:05d}", "sk": ORDER_SK}
        for order_id in range(FIRST_ID, LAST_ID + 1)
    ]


def _chunks(items: List[Any], size: int) -> List[List[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def delete_seed_orders(client: Any, table_name: str) -> Dict[str, int]:
    """Löscht alle Seed-Orders per BatchWriteItem (DeleteRequest)."""
    keys = seed_keys()
    stats = {"deleted": 0, "retries": 0}
    for chunk in _chunks(keys, BATCH_WRITE_LIMIT):
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
        description="Entfernt Seed-Test-Orders (ord_00001..ord_01000) aus DynamoDB"
    )
    parser.add_argument("--table", default=os.environ.get("ORDERS_TABLE", "mays-orders"))
    parser.add_argument("--dry-run", action="store_true", help="Keys nur auflisten, nichts löschen")
    args = parser.parse_args(argv)

    keys = seed_keys()
    if args.dry_run:
        print(f"DRY-RUN: würde {len(keys)} Seed-Orders löschen (Tabelle '{args.table}'):")
        for key in keys:
            print(f"  {key['pk']} / {key['sk']}")
        return 0

    try:
        active_client = _get_dynamodb_client()
        stats = delete_seed_orders(active_client, args.table)
    except (RuntimeError,) as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 1

    print(f"Löschen abgeschlossen (Tabelle '{args.table}'): {stats['deleted']} Items, "
          f"{stats['retries']} Retries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
