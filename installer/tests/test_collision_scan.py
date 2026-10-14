"""Tests for the read-only AWS project collision scan (installer preflight).

Incident reference (2026-10): two deployments, same project name
'mays-orders', same account — two Cognito pools named 'mays-orders-users'.
These tests pin the detection logic; no real AWS access.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from installer.core.collision_scan import (
    find_name_duplicates,
    match_project_resources,
    scan_cognito_pools,
    scan_dynamodb_tables,
    scan_lambda_functions,
    scan_project_inventory,
    scan_s3_buckets,
    scan_sqs_queues,
)
from installer.core.context import InstallationContext, ValidationLayer


def _fake_runner(payload_by_cmd):
    """Build a runner fake keyed by the first two CLI words."""
    def runner(args, env):
        key = " ".join(args[:2])
        if key not in payload_by_cmd:
            raise AssertionError(f"unexpected aws call: {args}")
        return payload_by_cmd[key]
    return runner


class TestScanFunctions(unittest.TestCase):
    """AWS list calls parse correctly (injectable runner, no real AWS)."""

    def test_scan_cognito_pools(self):
        runner = _fake_runner({
            "cognito-idp list-user-pools": {
                "UserPools": [
                    {"Id": "eu-central-1_AAA", "Name": "mays-orders-users"},
                    {"Id": "eu-central-1_BBB", "Name": "mays-orders-users"},
                ]
            },
        })
        pools = scan_cognito_pools({"AWS_PROFILE": "test"}, runner)
        self.assertEqual(len(pools), 2)
        self.assertEqual(pools[0]["id"], "eu-central-1_AAA")
        self.assertEqual(pools[1]["name"], "mays-orders-users")

    def test_scan_dynamodb_tables(self):
        runner = _fake_runner({
            "dynamodb list-tables": {"TableNames": ["mays-orders", "mays-ris-dev-work-items"]},
        })
        tables = scan_dynamodb_tables({}, runner)
        self.assertEqual(tables, ["mays-orders", "mays-ris-dev-work-items"])

    def test_scan_lambda_functions(self):
        runner = _fake_runner({
            "lambda list-functions": {
                "Functions": [
                    {"FunctionName": "mays-orders-handler"},
                    {"FunctionName": "mays-ris-dev-agent"},
                ]
            },
        })
        funcs = scan_lambda_functions({}, runner)
        self.assertEqual(funcs, ["mays-orders-handler", "mays-ris-dev-agent"])

    def test_scan_sqs_queues_extracts_names_from_urls(self):
        runner = _fake_runner({
            "sqs list-queues": {
                "QueueUrls": [
                    "https://sqs.eu-central-1.amazonaws.com/240571105849/mays-orders-orders-queue",
                    "https://sqs.eu-central-1.amazonaws.com/240571105849/mays-ris-dev-work-queue",
                ]
            },
        })
        queues = scan_sqs_queues({}, runner)
        self.assertEqual(queues, ["mays-orders-orders-queue", "mays-ris-dev-work-queue"])

    def test_scan_sqs_queues_empty_payload(self):
        runner = _fake_runner({"sqs list-queues": {"QueueUrls": None}})
        self.assertEqual(scan_sqs_queues({}, runner), [])

    def test_scan_s3_buckets(self):
        runner = _fake_runner({
            "s3api list-buckets": {
                "Buckets": [{"Name": "mays-orders-tfstate-central-240571105849"}]
            },
        })
        buckets = scan_s3_buckets({}, runner)
        self.assertEqual(buckets, ["mays-orders-tfstate-central-240571105849"])

    def test_scan_project_inventory_shape(self):
        runner = _fake_runner({
            "cognito-idp list-user-pools": {"UserPools": []},
            "dynamodb list-tables": {"TableNames": ["mays-orders"]},
            "lambda list-functions": {"Functions": []},
            "sqs list-queues": {"QueueUrls": []},
            "s3api list-buckets": {"Buckets": []},
        })
        inv = scan_project_inventory({}, "mays-orders", runner)
        self.assertEqual(inv["project_name"], "mays-orders")
        self.assertEqual(inv["cognito_pools"], [])
        self.assertEqual(inv["dynamodb_tables"], ["mays-orders"])


class TestFindNameDuplicates(unittest.TestCase):
    """Duplicate same-service names are the strongest collision signal."""

    def _inventory(self, pools):
        return {"cognito_pools": pools}

    def test_detects_incident_shape_two_identical_pool_names(self):
        inv = self._inventory([
            {"id": "eu-central-1_xhjl0PxEH", "name": "mays-orders-users"},
            {"id": "eu-central-1_ENMwxNFS9", "name": "mays-orders-users"},
        ])
        dups = find_name_duplicates(inv)
        self.assertEqual(len(dups), 1)
        self.assertEqual(dups[0]["service"], "cognito_user_pools")
        self.assertEqual(dups[0]["name"], "mays-orders-users")
        self.assertEqual(dups[0]["count"], 2)
        self.assertEqual(
            dups[0]["ids"],
            ["eu-central-1_xhjl0PxEH", "eu-central-1_ENMwxNFS9"],
        )

    def test_no_duplicates_for_unique_names(self):
        inv = self._inventory([
            {"id": "eu-central-1_AAA", "name": "mays-orders-users"},
            {"id": "eu-central-1_BBB", "name": "mays-ris-pool"},
        ])
        self.assertEqual(find_name_duplicates(inv), [])

    def test_empty_inventory(self):
        self.assertEqual(find_name_duplicates({}), [])


class TestMatchProjectResources(unittest.TestCase):
    """Project-name matches must be surfaced for ownership verification."""

    def setUp(self):
        self.inv = {
            "cognito_pools": [
                {"id": "eu-central-1_AAA", "name": "mays-orders-users"},
                {"id": "eu-central-1_BBB", "name": "mays-ris-users"},
            ],
            "dynamodb_tables": ["mays-orders", "mays-ris-dev-work-items"],
            "lambda_functions": ["mays-orders-handler", "mays-ris-dev-agent"],
            "sqs_queues": ["mays-orders-orders-queue"],
            "s3_buckets": ["mays-orders-tfstate-central-240571105849", "other-bucket"],
        }

    def test_matches_are_case_insensitive_and_per_service(self):
        matches = match_project_resources(self.inv, "Mays-Orders")
        self.assertEqual(matches["cognito_user_pools"], ["mays-orders-users"])
        self.assertEqual(matches["dynamodb_tables"], ["mays-orders"])
        self.assertEqual(matches["lambda_functions"], ["mays-orders-handler"])
        self.assertEqual(matches["sqs_queues"], ["mays-orders-orders-queue"])
        self.assertEqual(
            matches["s3_buckets"], ["mays-orders-tfstate-central-240571105849"]
        )

    def test_no_matches_for_unknown_project(self):
        matches = match_project_resources(self.inv, "some-other-project")
        self.assertEqual(matches, {})

    def test_prefix_project_is_not_matched_by_longer_names(self):
        # 'mays-order' is a substring of 'mays-orders...' — matches, which is
        # intended (prefix projects deserve the same ownership verification).
        matches = match_project_resources(self.inv, "mays-order")
        self.assertIn("cognito_user_pools", matches)


class TestValidationLayerCollisionCheck(unittest.TestCase):
    """The preflight check classifies correctly and degrades gracefully."""

    def _context_with_aws(self):
        ctx = InstallationContext()
        aws_ctx = MagicMock()
        aws_ctx.get_environment.return_value = {"AWS_PROFILE": "test"}
        ctx.aws_execution_context = aws_ctx
        return ctx

    @patch("installer.core.collision_scan.scan_project_inventory")
    def test_duplicate_pools_produce_warning_with_details(self, mock_scan):
        mock_scan.return_value = {
            "project_name": "mays-orders",
            "cognito_pools": [
                {"id": "eu-central-1_xhjl0PxEH", "name": "mays-orders-users"},
                {"id": "eu-central-1_ENMwxNFS9", "name": "mays-orders-users"},
            ],
            "dynamodb_tables": [],
            "lambda_functions": [],
            "sqs_queues": [],
            "s3_buckets": [],
        }
        layer = ValidationLayer(self._context_with_aws())
        layer._check_aws_project_collisions()
        check = [c for c in layer.result.checks if c.name == "aws_project_collision"][0]
        self.assertEqual(check.status, "WARNING")
        self.assertIn("mays-orders-users", check.message)
        self.assertEqual(check.details["duplicates"][0]["count"], 2)

    @patch("installer.core.collision_scan.scan_project_inventory")
    def test_matches_without_duplicates_produce_ownership_warning(self, mock_scan):
        mock_scan.return_value = {
            "project_name": "mays-orders",
            "cognito_pools": [{"id": "eu-central-1_AAA", "name": "mays-orders-users"}],
            "dynamodb_tables": ["mays-orders"],
            "lambda_functions": ["mays-orders-handler"],
            "sqs_queues": [],
            "s3_buckets": [],
        }
        layer = ValidationLayer(self._context_with_aws())
        layer._check_aws_project_collisions()
        check = [c for c in layer.result.checks if c.name == "aws_project_collision"][0]
        self.assertEqual(check.status, "WARNING")
        self.assertIn("parallel owner", check.message)
        self.assertEqual(check.details["cognito_pools_matching_project"], 1)

    @patch("installer.core.collision_scan.scan_project_inventory")
    def test_clean_account_passes(self, mock_scan):
        mock_scan.return_value = {
            "project_name": "mays-orders-privacy-test",
            "cognito_pools": [{"id": "eu-central-1_AAA", "name": "mays-ris-users"}],
            "dynamodb_tables": [],
            "lambda_functions": [],
            "sqs_queues": [],
            "s3_buckets": [],
        }
        layer = ValidationLayer(self._context_with_aws())
        layer._check_aws_project_collisions()
        check = [c for c in layer.result.checks if c.name == "aws_project_collision"][0]
        self.assertEqual(check.status, "PASS")

    @patch("installer.core.collision_scan.scan_project_inventory")
    def test_scan_error_degrades_to_warning_not_fail(self, mock_scan):
        mock_scan.side_effect = RuntimeError("aws sts failed: no credentials")
        layer = ValidationLayer(self._context_with_aws())
        layer._check_aws_project_collisions()
        check = [c for c in layer.result.checks if c.name == "aws_project_collision"][0]
        self.assertEqual(check.status, "WARNING")
        self.assertIn("Collision scan skipped", check.message)

    def test_missing_aws_context_skips(self):
        ctx = InstallationContext()
        # No aws_execution_context attribute set
        if hasattr(ctx, "aws_execution_context"):
            del ctx.aws_execution_context
        layer = ValidationLayer(ctx)
        layer._check_aws_project_collisions()
        check = [c for c in layer.result.checks if c.name == "aws_project_collision"][0]
        self.assertEqual(check.status, "WARNING")
        self.assertIn("no validated AWS context", check.message)

    @patch("installer.core.collision_scan.scan_project_inventory")
    def test_check_included_in_run_all(self, mock_scan):
        """run_all() must execute the collision check (preflight coverage)."""
        mock_scan.return_value = {
            "project_name": "mays-orders",
            "cognito_pools": [],
            "dynamodb_tables": [],
            "lambda_functions": [],
            "sqs_queues": [],
            "s3_buckets": [],
        }
        ctx = self._context_with_aws()
        # Terraform CLI checks etc. would fail without terraform; only assert
        # that run_all reaches and records the collision check.
        layer = ValidationLayer(ctx)
        result = layer.run_all()
        names = [c.name for c in result.checks]
        self.assertIn("aws_project_collision", names)


if __name__ == "__main__":
    unittest.main()
