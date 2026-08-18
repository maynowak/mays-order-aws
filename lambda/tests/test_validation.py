import unittest

from errors import OrderError
from validation import (
    validate_create_order,
    validate_list_params,
    validate_order_id,
    validate_status,
    validate_status_update_body,
)

VALID_BODY = {
    "customer": {"name": "Max Mustermann", "email": "max@example.com"},
    "items": [{"sku": "SKU-1001", "quantity": 2, "unitPrice": 1999}],
    "currency": "EUR",
}


def expect_validation_error(func):
    try:
        func()
    except OrderError as error:
        assert error.code == "VALIDATION_ERROR", error.code
        assert error.http_status == 400, error.http_status
        return error
    raise AssertionError("expected validation error")


class TestValidateCreateOrder(unittest.TestCase):
    def test_accepts_valid_body(self):
        input_data = validate_create_order(VALID_BODY)
        self.assertEqual(input_data["customer"]["name"], "Max Mustermann")
        self.assertEqual(len(input_data["items"]), 1)
        self.assertEqual(input_data["currency"], "EUR")

    def test_rejects_missing_customer_name(self):
        body = dict(VALID_BODY, customer={"email": "max@example.com"})
        expect_validation_error(lambda: validate_create_order(body))

    def test_rejects_invalid_email(self):
        body = dict(VALID_BODY, customer={"name": "Max", "email": "not-an-email"})
        expect_validation_error(lambda: validate_create_order(body))

    def test_rejects_empty_items(self):
        body = dict(VALID_BODY, items=[])
        expect_validation_error(lambda: validate_create_order(body))

    def test_rejects_quantity_zero(self):
        body = dict(VALID_BODY, items=[{"sku": "SKU-1001", "quantity": 0, "unitPrice": 1999}])
        expect_validation_error(lambda: validate_create_order(body))

    def test_rejects_quantity_with_fraction(self):
        body = dict(VALID_BODY, items=[{"sku": "SKU-1001", "quantity": 1.5, "unitPrice": 1999}])
        expect_validation_error(lambda: validate_create_order(body))

    def test_rejects_float_unit_price(self):
        body = dict(VALID_BODY, items=[{"sku": "SKU-1001", "quantity": 1, "unitPrice": 19.99}])
        expect_validation_error(lambda: validate_create_order(body))

    def test_rejects_unknown_top_level_field(self):
        body = dict(VALID_BODY, extra=True)
        expect_validation_error(lambda: validate_create_order(body))

    def test_rejects_unknown_item_field(self):
        body = dict(
            VALID_BODY,
            items=[{"sku": "SKU-1001", "quantity": 1, "unitPrice": 100, "discount": 10}],
        )
        expect_validation_error(lambda: validate_create_order(body))

    def test_rejects_invalid_currency(self):
        body = dict(VALID_BODY, currency="EU")
        expect_validation_error(lambda: validate_create_order(body))

    def test_rejects_non_object_body(self):
        expect_validation_error(lambda: validate_create_order(None))
        expect_validation_error(lambda: validate_create_order("text"))


class TestValidateOrderId(unittest.TestCase):
    def test_accepts_ord_alphanumeric(self):
        self.assertEqual(
            validate_order_id("ord_2f4b1c9e0000000000000000"),
            "ord_2f4b1c9e0000000000000000",
        )

    def test_rejects_invalid_format(self):
        expect_validation_error(lambda: validate_order_id("order-123"))
        expect_validation_error(lambda: validate_order_id(""))
        expect_validation_error(lambda: validate_order_id(None))


class TestValidateStatus(unittest.TestCase):
    def test_accepts_valid_status(self):
        self.assertEqual(validate_status("CONFIRMED"), "CONFIRMED")
        self.assertEqual(validate_status_update_body({"status": "SHIPPED"}), "SHIPPED")

    def test_rejects_invalid_status(self):
        expect_validation_error(lambda: validate_status("READY"))
        expect_validation_error(lambda: validate_status_update_body({"status": "READY"}))
        expect_validation_error(lambda: validate_status_update_body({"status": "CONFIRMED", "extra": 1}))
        expect_validation_error(lambda: validate_status_update_body({}))


class TestValidateListParams(unittest.TestCase):
    def test_default_limit_20(self):
        self.assertEqual(validate_list_params(None), {"limit": 20})
        self.assertEqual(validate_list_params({}), {"limit": 20})

    def test_accepts_limit_range(self):
        self.assertEqual(validate_list_params({"limit": "1"})["limit"], 1)
        self.assertEqual(validate_list_params({"limit": "100"})["limit"], 100)

    def test_rejects_limit_out_of_range(self):
        expect_validation_error(lambda: validate_list_params({"limit": "0"}))
        expect_validation_error(lambda: validate_list_params({"limit": "101"}))
        expect_validation_error(lambda: validate_list_params({"limit": "abc"}))

    def test_passes_next_token_through(self):
        self.assertEqual(validate_list_params({"nextToken": "eyJ9"})["nextToken"], "eyJ9")


if __name__ == "__main__":
    unittest.main()
