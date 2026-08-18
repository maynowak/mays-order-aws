import unittest

from state_machine import can_transition
from order_types import ORDER_STATUSES

ALLOWED = [
    ("PENDING", "CONFIRMED"),
    ("PENDING", "CANCELLED"),
    ("CONFIRMED", "PROCESSING"),
    ("CONFIRMED", "CANCELLED"),
    ("PROCESSING", "SHIPPED"),
    ("SHIPPED", "DELIVERED"),
]

DISALLOWED = [
    ("PENDING", "PROCESSING"),
    ("PENDING", "SHIPPED"),
    ("PENDING", "DELIVERED"),
    ("CONFIRMED", "DELIVERED"),
    ("PROCESSING", "CANCELLED"),
    ("SHIPPED", "CANCELLED"),
]


class TestAllowedTransitions(unittest.TestCase):
    def test_allowed_transitions(self):
        for from_status, to_status in ALLOWED:
            with self.subTest(from_status=from_status, to_status=to_status):
                self.assertTrue(can_transition(from_status, to_status))


class TestDisallowedTransitions(unittest.TestCase):
    def test_disallowed_transitions(self):
        for from_status, to_status in DISALLOWED:
            with self.subTest(from_status=from_status, to_status=to_status):
                self.assertFalse(can_transition(from_status, to_status))

    def test_terminal_states_reject_all(self):
        for terminal in ("DELIVERED", "CANCELLED"):
            for target in ORDER_STATUSES:
                with self.subTest(terminal=terminal, target=target):
                    self.assertFalse(can_transition(terminal, target))

    def test_same_status_rejected(self):
        for status in ORDER_STATUSES:
            with self.subTest(status=status):
                self.assertFalse(can_transition(status, status))


if __name__ == "__main__":
    unittest.main()
