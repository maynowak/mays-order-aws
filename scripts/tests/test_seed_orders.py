import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from delete_seed_orders import demo_seed_keys, delete_demo_orders
from seed_orders import (
    GSI1_PK,
    ORDER_SK,
    import_orders,
    load_seed_items,
    normalize_item,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_FILE = REPO_ROOT / "database" / "seed" / "orders_seed_1000.jsonl"
DEMO_FILE = REPO_ROOT / "database" / "seed" / "orders_seed_demo_50.json"

VALID_STATUSES = {"PENDING", "CONFIRMED", "PROCESSING", "SHIPPED", "DELIVERED", "CANCELLED"}


class FakeDynamoClient:
    """In-Memory-Fake für dynamodb client batch_get_item / batch_write_item."""

    def __init__(self):
        self.items = {}

    def batch_get_item(self, RequestItems=None):
        response = {}
        for table_name, spec in (RequestItems or {}).items():
            found = []
            for key in spec["Keys"]:
                item = self.items.get((key["pk"], key["sk"]))
                if item is not None:
                    found.append(item)
            response[table_name] = found
        return {"Responses": response, "UnprocessedKeys": {}}

    def batch_write_item(self, RequestItems=None):
        for table_name, requests in (RequestItems or {}).items():
            for request in requests:
                if "PutRequest" in request:
                    item = request["PutRequest"]["Item"]
                    self.items[(item["pk"], item["sk"])] = item
                elif "DeleteRequest" in request:
                    key = request["DeleteRequest"]["Key"]
                    self.items.pop((key["pk"], key["sk"]), None)
        return {"UnprocessedItems": {}}


def parse_iso(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class TestSeedData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items = load_seed_items(str(SEED_FILE))

    def test_t01_has_exactly_1000_orders(self):
        self.assertEqual(len(self.items), 1000)

    def test_t02_pk_and_sk_fields(self):
        for item in self.items:
            self.assertTrue(item["pk"].startswith("ORDER#"), item)
            self.assertEqual(item["sk"], ORDER_SK)
            self.assertEqual(item["pk"], f"ORDER#{item['orderId']}", item)
            self.assertRegex(item["orderId"], r"^ord_[A-Za-z0-9]+$")

    def test_t03_no_duplicate_pk_sk(self):
        keys = [(item["pk"], item["sk"]) for item in self.items]
        self.assertEqual(len(keys), len(set(keys)))

    def test_t04_gsi_fields_correct(self):
        for item in self.items:
            self.assertEqual(item["gsi1pk"], GSI1_PK, item)
            self.assertEqual(item["gsi1sk"], item["createdAt"], item)

    def test_t05_statuses_valid(self):
        for item in self.items:
            self.assertIn(item["status"], VALID_STATUSES, item)

    def test_t06_amounts_valid(self):
        for item in self.items:
            self.assertIsInstance(item["totalAmount"], int)
            self.assertGreater(item["totalAmount"], 0)
            for raw in item["items"]:
                self.assertIsInstance(raw["quantity"], int)
                self.assertIsInstance(raw["unitPrice"], int)
                self.assertGreaterEqual(raw["quantity"], 1)
                self.assertGreaterEqual(raw["unitPrice"], 1)

    def test_t07_timestamps_valid_iso8601(self):
        for item in self.items:
            created = parse_iso(item["createdAt"])
            updated = parse_iso(item["updatedAt"])
            self.assertEqual(created.tzinfo, timezone.utc)
            self.assertEqual(updated.tzinfo, timezone.utc)


class TestSeedImport(unittest.TestCase):
    def test_t08_import_writes_1000_items(self):
        client = FakeDynamoClient()
        stats = import_orders("mays-orders", str(SEED_FILE), client=client)
        self.assertEqual(stats["total"], 1000)
        self.assertEqual(stats["written"], 1000)
        self.assertEqual(stats["skipped"], 0)
        self.assertEqual(len(client.items), 1000)

    def test_t09_second_run_is_idempotent_no_extra_items(self):
        client = FakeDynamoClient()
        import_orders("mays-orders", str(SEED_FILE), client=client)
        before = len(client.items)
        stats = import_orders("mays-orders", str(SEED_FILE), client=client)
        self.assertEqual(stats["written"], 0)
        self.assertEqual(stats["skipped"], 1000)
        self.assertEqual(len(client.items), before)

    def test_t10_item_count_is_1000_after_import(self):
        client = FakeDynamoClient()
        import_orders("mays-orders", str(SEED_FILE), client=client)
        self.assertEqual(len(client.items), 1000)

    def test_normalize_sets_line_total_and_version(self):
        raw = json.loads(SEED_FILE.read_text(encoding="utf-8").splitlines()[0])
        normalized = normalize_item(raw)
        for raw_item, norm_item in zip(raw["items"], normalized["items"]):
            self.assertEqual(
                norm_item["lineTotal"],
                norm_item["quantity"] * norm_item["unitPrice"],
            )
            self.assertNotIn("name", norm_item)
        self.assertEqual(normalized["version"], 1)

    def test_dry_run_writes_nothing(self):
        client = FakeDynamoClient()
        stats = import_orders("mays-orders", str(SEED_FILE), client=client, dry_run=True)
        self.assertTrue(stats["dry_run"])
        self.assertEqual(stats["written"], 0)
        self.assertEqual(len(client.items), 0)


class TestDemoSeedData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items = load_seed_items(str(DEMO_FILE))

    def test_t01_has_exactly_50_orders(self):
        self.assertEqual(len(self.items), 50)

    def test_t02_no_duplicate_pk_sk(self):
        keys = [(item["pk"], item["sk"]) for item in self.items]
        self.assertEqual(len(keys), len(set(keys)))

    def test_t03_primary_keys_correct(self):
        for item in self.items:
            self.assertTrue(item["pk"].startswith("ORDER#"), item)
            self.assertEqual(item["sk"], ORDER_SK)
            self.assertEqual(item["pk"], f"ORDER#{item['orderId']}", item)
            self.assertRegex(item["orderId"], r"^ord_[A-Za-z0-9]+$")

    def test_t04_gsi_fields_correct(self):
        for item in self.items:
            self.assertEqual(item["gsi1pk"], GSI1_PK, item)
            self.assertEqual(item["gsi1sk"], item["createdAt"], item)

    def test_t05_statuses_valid(self):
        for item in self.items:
            self.assertIn(item["status"], VALID_STATUSES, item)

    def test_t06_version_present_and_numeric(self):
        for item in self.items:
            self.assertIn("version", item, item)
            self.assertIsInstance(item["version"], int)
            self.assertGreaterEqual(item["version"], 1)
            self.assertEqual(item["version"], 1)

    def test_t07_is_test_data_true(self):
        for item in self.items:
            self.assertIs(item.get("isTestData"), True, item)

    def test_t08_line_total_correct(self):
        for item in self.items:
            for raw in item["items"]:
                self.assertEqual(raw["lineTotal"], raw["quantity"] * raw["unitPrice"], item)

    def test_t09_total_amount_equals_sum_line_total(self):
        for item in self.items:
            self.assertEqual(item["totalAmount"], sum(i["lineTotal"] for i in item["items"]), item)


class TestDemoSeedImport(unittest.TestCase):
    def test_t10_importer_validates_all_50(self):
        client = FakeDynamoClient()
        stats = import_orders("mays-orders", str(DEMO_FILE), client=client, dry_run=True)
        self.assertTrue(stats["dry_run"])
        self.assertEqual(stats["total"], 50)

    def test_t11_dry_run_writes_nothing(self):
        client = FakeDynamoClient()
        stats = import_orders("mays-orders", str(DEMO_FILE), client=client, dry_run=True)
        self.assertEqual(stats["written"], 0)
        self.assertEqual(len(client.items), 0)

    def test_t12_second_seed_run_creates_no_duplicates(self):
        client = FakeDynamoClient()
        first = import_orders("mays-orders", str(DEMO_FILE), client=client)
        self.assertEqual(first["written"], 50)
        second = import_orders("mays-orders", str(DEMO_FILE), client=client)
        self.assertEqual(second["written"], 0)
        self.assertEqual(second["skipped"], 50)
        self.assertEqual(len(client.items), 50)

    def test_demo_normalization_preserves_is_test_data_and_version(self):
        raw = json.loads(DEMO_FILE.read_text(encoding="utf-8"))[0]
        normalized = normalize_item(raw)
        self.assertEqual(normalized["version"], 1)
        self.assertIs(normalized["isTestData"], True)
        for raw_item, norm_item in zip(raw["items"], normalized["items"]):
            self.assertEqual(norm_item["lineTotal"], raw_item["lineTotal"])
            self.assertNotIn("name", norm_item)


class TestDemoSeedDeletion(unittest.TestCase):
    def test_delete_removes_only_demo_seed_items_with_is_test_data(self):
        client = FakeDynamoClient()
        import_orders("mays-orders", str(DEMO_FILE), client=client)
        client.items[("ORDER#ord_99999", ORDER_SK)] = {
            "pk": "ORDER#ord_99999",
            "sk": ORDER_SK,
            "isTestData": False,
        }

        stats = delete_demo_orders(client, "mays-orders", str(DEMO_FILE))
        self.assertEqual(stats["deleted"], 50)
        self.assertIn(("ORDER#ord_99999", ORDER_SK), client.items)
        self.assertEqual(len(client.items), 1)

    def test_delete_skips_demo_key_without_is_test_data(self):
        client = FakeDynamoClient()
        import_orders("mays-orders", str(DEMO_FILE), client=client)
        first_key = list(client.items)[0]
        client.items[first_key] = dict(client.items[first_key], isTestData=False)

        stats = delete_demo_orders(client, "mays-orders", str(DEMO_FILE))
        self.assertEqual(stats["deleted"], 49)
        self.assertEqual(stats["skipped_not_test_data"], 1)
        self.assertIn(first_key, client.items)

    def test_demo_keys_are_exactly_50_from_file(self):
        keys = demo_seed_keys(str(DEMO_FILE))
        self.assertEqual(len(keys), 50)
        for key in keys:
            self.assertEqual(key["sk"], ORDER_SK)


if __name__ == "__main__":
    unittest.main()
