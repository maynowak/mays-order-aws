"""W03/W04 — static contract checks for the Orders agent transport Terraform."""

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODULE = os.path.join(ROOT, "terraform", "modules", "agent_transport")


def module_source():
    parts = []
    for name in sorted(os.listdir(MODULE)):
        if name.endswith(".tf"):
            with open(os.path.join(MODULE, name), encoding="utf-8") as handle:
                parts.append(handle.read())
    return "\n".join(parts)


def read(path):
    with open(os.path.join(ROOT, "terraform", path), encoding="utf-8") as f:
        return f.read()


class TestResultConsumerWiring(unittest.TestCase):
    def setUp(self):
        self.source = module_source()

    def test_expected_resources_exist(self):
        expected = {
            ("aws_sqs_queue", "results"),
            ("aws_sqs_queue", "results_dlq"),
            ("aws_sqs_queue_policy", "results"),
            ("aws_secretsmanager_secret", "result_hmac"),
            ("aws_secretsmanager_secret_policy", "result_hmac"),
            ("aws_cloudwatch_log_group", "result_consumer"),
            ("aws_iam_role", "result_consumer"),
            ("aws_iam_role_policy", "result_consumer"),
            ("aws_lambda_function", "result_consumer"),
            ("aws_lambda_event_source_mapping", "results"),
        }
        found = set(re.findall(r'resource "([a-z0-9_]+)" "([a-z0-9_]+)"', self.source))
        self.assertTrue(expected.issubset(found), expected - found)

    def test_handler_is_the_consumer_entrypoint(self):
        self.assertIn('handler       = "result_consumer.handler"', self.source)

    def test_event_source_mapping_reports_batch_failures(self):
        self.assertIn('function_response_types            = ["ReportBatchItemFailures"]',
                      self.source)

    def test_secret_has_no_value_in_code(self):
        self.assertNotIn("secret_string", self.source)
        self.assertNotIn("aws_secretsmanager_secret_version", self.source)

    def test_secret_policy_is_scoped_to_the_secret(self):
        self.assertIn("aws_secretsmanager_secret.result_hmac.arn", self.source)
        self.assertIn("var.ris_result_producer_role_arns", self.source)

    def test_kms_is_opt_in(self):
        self.assertIn('count = var.result_secret_kms_key_arn != "" ? 1 : 0',
                      self.source)

    def test_consumer_can_read_orders_table_but_not_write_new_orders(self):
        self.assertIn('"dynamodb:GetItem", "dynamodb:UpdateItem"', self.source)
        self.assertNotIn("dynamodb:PutItem", self.source)
        self.assertNotIn("dynamodb:DeleteItem", self.source)

    def test_no_api_route_is_added(self):
        self.assertNotIn('"aws_apigatewayv2_route"', self.source)

    def test_no_owner_rights_for_the_service_role(self):
        self.assertNotIn("cognito-idp", self.source)
        self.assertNotIn("AdministratorAccess", self.source)


class TestDefaultOff(unittest.TestCase):
    def test_flag_defaults_to_false(self):
        variables = read("variables.tf")
        start = variables.index('variable "enable_agent_transport"')
        self.assertIn("default     = false", variables[start:start + 300])

    def test_module_is_gated_by_the_flag(self):
        root = read("main.tf")
        self.assertIn('module "agent_transport"', root)
        self.assertIn("count  = var.enable_agent_transport ? 1 : 0", root)

    def test_module_uses_the_existing_orders_table(self):
        root = read("main.tf")
        self.assertIn("module.dynamodb.table_name", root)
        self.assertIn("module.dynamodb.table_arn", root)


if __name__ == "__main__":
    unittest.main()
