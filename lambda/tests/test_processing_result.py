"""MO-RC4-P02G-A — Ergebnisvertrag: Struktur, Grenzen, Datenschutz-Zusammenfassung."""

import unittest

from errors import OrderError
from processing_result import (
    FIELD_COMPLETED_AT,
    FIELD_PROCESSING_ATTEMPT_ID,
    FIELD_PROCESSING_ERROR,
    FIELD_PROCESSING_STATE,
    FIELD_RESULT,
    PROCESSING_FIELDS,
    RESULT_MAX_BYTES,
    RESULT_MAX_DEPTH,
    RESULT_MAX_ITEMS_PER_CONTAINER,
    RESULT_WRITE_GUARD,
    processing_summary,
    validate_completed_at,
    validate_processing_attempt_id,
    validate_processing_error,
    validate_processing_result,
    validate_processing_state,
)


class TestProcessingState(unittest.TestCase):
    def test_valid_states(self):
        for state in ("pending", "running", "succeeded", "failed"):
            self.assertEqual(validate_processing_state(state), state)

    def test_invalid_states(self):
        for bad in ("", "DONE", "completed", None, 1):
            with self.subTest(value=bad):
                with self.assertRaises(OrderError):
                    validate_processing_state(bad)


class TestAttemptId(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate_processing_attempt_id("a1b2-c3:d4.e5_6"), "a1b2-c3:d4.e5_6")

    def test_invalid(self):
        for bad in ("", "with space", "x" * 129, None, "slash/here", "umlaut-ä"):
            with self.subTest(value=repr(bad)):
                with self.assertRaises(OrderError):
                    validate_processing_attempt_id(bad)


class TestCompletedAt(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate_completed_at("2026-11-01T12:00:00.000Z"),
                         "2026-11-01T12:00:00.000Z")
        self.assertEqual(validate_completed_at("2026-11-01T12:00:00Z"),
                         "2026-11-01T12:00:00Z")

    def test_invalid(self):
        for bad in ("", "2026-11-01", "2026-11-01T12:00:00+01:00", None):
            with self.subTest(value=bad):
                with self.assertRaises(OrderError):
                    validate_completed_at(bad)


class TestProcessingResult(unittest.TestCase):
    def test_accepts_json_values(self):
        for value in (None, True, 1, 1.5, "text", ["a", 1], {"a": [1, {"b": None}]}):
            with self.subTest(value=value):
                self.assertEqual(validate_processing_result(value), value)

    def test_rejects_non_json_types(self):
        for bad in (b"bytes", {1, 2}, object(), {"x": object()}):
            with self.subTest(value=type(bad).__name__):
                with self.assertRaises(OrderError):
                    validate_processing_result(bad)

    def test_rejects_too_deep(self):
        value = "leaf"
        for _ in range(RESULT_MAX_DEPTH + 1):
            value = [value]
        with self.assertRaises(OrderError):
            validate_processing_result(value)

    def test_rejects_too_many_items(self):
        with self.assertRaises(OrderError):
            validate_processing_result(list(range(RESULT_MAX_ITEMS_PER_CONTAINER + 1)))
        with self.assertRaises(OrderError):
            validate_processing_result({f"k{i}": 1 for i in range(RESULT_MAX_ITEMS_PER_CONTAINER + 1)})

    def test_rejects_invalid_keys(self):
        for key in ("with space", "1nicht-erlaubt!", "x" * 65, ""):
            with self.subTest(key=key):
                with self.assertRaises(OrderError):
                    validate_processing_result({key: 1})

    def test_rejects_oversized_payload(self):
        big = "x" * (RESULT_MAX_BYTES + 1)
        with self.assertRaises(OrderError):
            validate_processing_result({"blob": big})


class TestProcessingError(unittest.TestCase):
    def test_accepts_code_or_message(self):
        self.assertEqual(validate_processing_error({"code": "TIMEOUT"}), {"code": "TIMEOUT"})
        self.assertEqual(validate_processing_error({"message": "failed"}), {"message": "failed"})

    def test_rejects_invalid(self):
        for bad in ({}, {"other": 1}, {"code": ""}, {"code": "x" * 65},
                    {"message": 5}, {"message": "x" * 501}, "text", None):
            with self.subTest(value=repr(bad)):
                with self.assertRaises(OrderError):
                    validate_processing_error(bad)


class TestProcessingSummary(unittest.TestCase):
    def test_empty(self):
        summary = processing_summary([{"orderId": "ord_1"}])
        self.assertEqual(summary, {"hasProcessingResult": False,
                                   "hasProcessingError": False,
                                   "processingStates": []})

    def test_flags_without_content(self):
        items = [
            {"orderId": "ord_1", FIELD_RESULT: {"secret": "wert"},
             FIELD_PROCESSING_STATE: "succeeded"},
            {"orderId": "ord_2", FIELD_PROCESSING_ERROR: {"code": "X"},
             FIELD_PROCESSING_STATE: "failed"},
        ]
        summary = processing_summary(items)
        self.assertTrue(summary["hasProcessingResult"])
        self.assertTrue(summary["hasProcessingError"])
        self.assertEqual(summary["processingStates"], ["failed", "succeeded"])
        self.assertNotIn("wert", str(summary))
        self.assertNotIn("secret", str(summary))


class TestProcessingFieldContract(unittest.TestCase):
    def test_fields(self):
        self.assertEqual(set(PROCESSING_FIELDS), {
            FIELD_PROCESSING_STATE, FIELD_PROCESSING_ATTEMPT_ID,
            FIELD_RESULT, FIELD_COMPLETED_AT, FIELD_PROCESSING_ERROR,
        })

    def test_write_guard_requires_owner(self):
        self.assertEqual(RESULT_WRITE_GUARD, "attribute_exists(subjectId)")


if __name__ == "__main__":
    unittest.main()
