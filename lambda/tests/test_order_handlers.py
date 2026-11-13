"""MO-RC4-P02E — interne Handler-Registry."""

import unittest

from errors import OrderError
from order_handlers import get_handler, is_registered, register, registered_types
from order_types import DEFAULT_ORDER_TYPE


class TestHandlerRegistry(unittest.TestCase):
    def test_generic_is_registered(self):
        self.assertTrue(is_registered(DEFAULT_ORDER_TYPE))
        self.assertIn(DEFAULT_ORDER_TYPE, registered_types())
        self.assertIsNotNone(get_handler(DEFAULT_ORDER_TYPE))

    def test_unknown_type_has_no_handler(self):
        self.assertIsNone(get_handler("never.registered.type"))

    def test_explicit_registration_and_lookup(self):
        calls = []

        @register("test.routing.example")
        def example(order, payload):
            calls.append((order, payload))

        self.assertIs(get_handler("test.routing.example"), example)
        example({"orderId": "ord_1"}, {})
        self.assertEqual(calls[0][0]["orderId"], "ord_1")

    def test_duplicate_registration_is_rejected(self):
        register("test.routing.duplicate", lambda order, payload: None)
        with self.assertRaises(ValueError):
            register("test.routing.duplicate", lambda order, payload: None)

    def test_invalid_type_names_are_rejected(self):
        for bad in ("", "   ", "Upper.Case", "with_underscore", "path/to/module",
                    "1leading", "trailing.", ".leading", "double..dot"):
            with self.subTest(name=bad):
                with self.assertRaises(OrderError):
                    register(bad, lambda order, payload: None)


if __name__ == "__main__":
    unittest.main()


class TestProcessingCapabilityP02GB(unittest.TestCase):
    """Handler deklarieren ihre Processing-Fähigkeit explizit."""

    def test_generic_is_status_handler(self):
        from order_handlers import get_handler_spec, is_processing_handler
        self.assertFalse(is_processing_handler("generic"))
        self.assertFalse(get_handler_spec("generic").processing)

    def test_processing_flag_is_explicit(self):
        from order_handlers import get_handler_spec, is_processing_handler, register

        @register("test.processing.flag", processing=True)
        def handler(order, payload, context):
            return {"ok": True}

        self.assertTrue(is_processing_handler("test.processing.flag"))
        self.assertTrue(get_handler_spec("test.processing.flag").processing)

    def test_processing_failure_carries_code_and_message(self):
        from order_handlers import ProcessingFailure
        failure = ProcessingFailure("UPSTREAM", "nope")
        self.assertEqual(failure.code, "UPSTREAM")
        self.assertEqual(failure.message, "nope")
        self.assertIsInstance(failure, Exception)

    def test_unknown_type_has_no_spec(self):
        from order_handlers import get_handler_spec
        self.assertIsNone(get_handler_spec("never.registered.processing"))
