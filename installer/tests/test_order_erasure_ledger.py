"""P3E-01: lokale Ledger-/Reconciliation-Tests (keine AWS-, keine Datenänderung)."""

from __future__ import annotations

import dataclasses
import json
import tempfile
import unittest
from pathlib import Path

from installer.core.order_erasure_ledger import (
    ACTION_ANONYMIZE,
    ACTION_DELETE,
    ACTION_RETAIN,
    CODE_CONSUMER_UNKNOWN,
    CODE_CUTOVER_BLOCKED,
    CODE_DUPLICATE_CONFLICT,
    CODE_INCOMPLETE,
    CODE_INTEGRITY_MISMATCH,
    CODE_INTEGRITY_MISSING,
    CODE_ORDER_KEY_UNKNOWN,
    CODE_PARTIAL_APPLICATION,
    CODE_SCHEMA_UNKNOWN,
    CODE_WEAK_KEY,
    CODE_LEDGER_MISSING,
    CUTOVER_BLOCKED,
    EXECUTION_NOT_VERIFIED,
    OP_ANONYMIZE,
    OP_ERASE,
    OP_RETAIN,
    PLAN_BLOCKED,
    PLAN_REVIEW_REQUIRED,
    PLAN_VERIFIED,
    READINESS_BLOCKED,
    READINESS_REVIEW_REQUIRED,
    RestoreContext,
    RestoredOrder,
    ErasureEvent,
    ErasureLedger,
    approve_cutover,
    build_privacy_readiness,
    load_ledger,
    plan_reconciliation,
    pseudonymize_subject,
    write_reconciliation_report,
)

KEY = b"k" * 32
KEY_ID = "test-key-1"
CONSUMER = "cognito:https://issuer.example#client-a"
OTHER_CONSUMER = "cognito:https://issuer.example#client-b"
SUBJECT_REF = pseudonymize_subject("user-1", key=KEY, key_id=KEY_ID)
ORDER_1 = "ord_" + "a" * 24
ORDER_2 = "ord_" + "b" * 24
ORDER_3 = "ord_" + "c" * 24
RESTORE_AT = "2026-11-03T00:00:00+00:00"
BACKUP_AT = "2026-11-02T00:00:00+00:00"
COVERED_FROM = "2026-10-01T00:00:00+00:00"
COVERED_UNTIL = "2026-11-04T00:00:00+00:00"


def make_event(
    event_id="evt-1",
    operation=OP_ERASE,
    order_refs=(ORDER_1,),
    applied_at="2026-11-03T12:00:00+00:00",
    decided_at="2026-11-03T11:00:00+00:00",
    consumer_id=CONSUMER,
    subject_ref=SUBJECT_REF,
    status="COMPLETED",
    idempotency_key=None,
    operation_id=None,
    **counts,
):
    values = dict(
        affected_records=len(order_refs),
        deleted_records=len(order_refs) if operation == OP_ERASE else 0,
        anonymized_records=len(order_refs) if operation == OP_ANONYMIZE else 0,
        retained_records=len(order_refs) if operation == OP_RETAIN else 0,
    )
    values.update(counts)
    event = ErasureEvent(
        event_id=event_id,
        operation_id=operation_id or f"op-{event_id}",
        operation=operation,
        consumer_id=consumer_id,
        subject_ref=subject_ref,
        order_refs=tuple(order_refs),
        decided_at=decided_at,
        applied_at=applied_at,
        status=status,
        idempotency_key=idempotency_key or f"idem-{event_id}",
        integrity_sha256="",
        **values,
    )
    return dataclasses.replace(event, integrity_sha256=event.compute_integrity()).to_dict()


def make_ledger(events=None, *, complete=True, covered_from=COVERED_FROM, covered_until=COVERED_UNTIL):
    return {
        "schemaVersion": 1,
        "ledgerId": "ledger-1",
        "source": "test-ledger",
        "completeHistory": complete,
        "coveredFrom": covered_from,
        "coveredUntil": covered_until,
        "createdAt": "2026-11-03T12:00:00+00:00",
        "events": events if events is not None else [make_event()],
    }


def make_restore(**overrides):
    values = dict(
        restore_table_name="mays-orders-restore-20261103",
        restore_table_arn="arn:aws:dynamodb:eu-central-1:123456789012:table/mays-orders-restore-20261103",
        aws_account="123456789012",
        region="eu-central-1",
        restore_at=RESTORE_AT,
        backup_created_at=BACKUP_AT,
        source_table_name="mays-orders",
    )
    values.update(overrides)
    return RestoreContext.create(**values)


def restored(order_ref=ORDER_1, **overrides):
    values = dict(
        order_ref=order_ref,
        consumer_id=CONSUMER,
        subject_ref=SUBJECT_REF,
        customer_anonymized=False,
        has_subject_link=True,
    )
    values.update(overrides)
    return RestoredOrder(**values)


def plan(ledger=None, restore=None, orders=None, **kwargs):
    return plan_reconciliation(
        ledger_data=ledger if ledger is not None else make_ledger(),
        restore_context=restore or make_restore(),
        restored_orders=orders if orders is not None else [restored()],
        **kwargs,
    )


class TestPseudonymization(unittest.TestCase):
    def test_hmac_is_stable_and_keyed(self) -> None:
        first = pseudonymize_subject("user-1", key=KEY, key_id=KEY_ID)
        second = pseudonymize_subject("user-1", key=KEY, key_id=KEY_ID)
        other_key = pseudonymize_subject("user-1", key=b"x" * 32, key_id=KEY_ID)
        self.assertEqual(first, second)
        self.assertNotEqual(first, other_key)
        self.assertNotIn("user-1", first)
        self.assertTrue(first.startswith("hmac-sha256:test-key-1:"))

    def test_short_key_is_rejected(self) -> None:
        with self.assertRaises(Exception) as ctx:
            pseudonymize_subject("user-1", key=b"short", key_id=KEY_ID)
        self.assertEqual(ctx.exception.code, CODE_WEAK_KEY)

    def test_subject_id_is_required(self) -> None:
        with self.assertRaises(Exception):
            pseudonymize_subject("", key=KEY, key_id=KEY_ID)


class TestLedgerContract(unittest.TestCase):
    def test_ledger_roundtrip_deduplicates_identical_events(self) -> None:
        event = make_event()
        duplicate = make_event(
            event_id="evt-duplicate", idempotency_key="idem-evt-1", operation_id="op-evt-1"
        )
        ledger = load_ledger(make_ledger([event, duplicate]))
        self.assertEqual(len(ledger.events), 1)

    def test_conflicting_duplicate_event_id_is_rejected(self) -> None:
        event = make_event()
        conflicting = make_event(operation=OP_ANONYMIZE, deleted_records=0)
        conflicting["eventId"] = event["eventId"]
        with self.assertRaises(Exception) as ctx:
            load_ledger(make_ledger([event, conflicting]))
        self.assertEqual(ctx.exception.code, CODE_DUPLICATE_CONFLICT)

    def test_missing_integrity_is_rejected(self) -> None:
        event = make_event()
        event.pop("integritySha256")
        with self.assertRaises(Exception) as ctx:
            load_ledger(make_ledger([event]))
        self.assertEqual(ctx.exception.code, CODE_INTEGRITY_MISSING)

    def test_tampered_integrity_is_rejected(self) -> None:
        event = make_event()
        event["deletedRecords"] = 99
        with self.assertRaises(Exception) as ctx:
            load_ledger(make_ledger([event]))
        self.assertEqual(ctx.exception.code, CODE_INTEGRITY_MISMATCH)

    def test_unknown_schema_is_rejected(self) -> None:
        ledger = make_ledger()
        ledger["schemaVersion"] = 99
        with self.assertRaises(Exception) as ctx:
            load_ledger(ledger)
        self.assertEqual(ctx.exception.code, CODE_SCHEMA_UNKNOWN)

    def test_missing_ledger_is_rejected(self) -> None:
        with self.assertRaises(Exception) as ctx:
            load_ledger(None)
        self.assertEqual(ctx.exception.code, CODE_LEDGER_MISSING)

    def test_missing_event_id_is_rejected(self) -> None:
        event = make_event()
        event["eventId"] = ""
        with self.assertRaises(Exception):
            load_ledger(make_ledger([event]))

    def test_missing_consumer_is_rejected(self) -> None:
        event = make_event()
        event["consumerId"] = ""
        with self.assertRaises(Exception):
            load_ledger(make_ledger([event]))

    def test_unknown_order_key_is_rejected(self) -> None:
        event = make_event(order_refs=("legacy-1",))
        with self.assertRaises(Exception) as ctx:
            load_ledger(make_ledger([event]))
        self.assertEqual(ctx.exception.code, CODE_ORDER_KEY_UNKNOWN)

    def test_invalid_chronology_is_rejected(self) -> None:
        event = make_event(
            decided_at="2026-11-03T13:00:00+00:00",
            applied_at="2026-11-03T12:00:00+00:00",
        )
        with self.assertRaises(Exception):
            load_ledger(make_ledger([event]))

    def test_ledger_json_contains_no_raw_subject(self) -> None:
        ledger = load_ledger(make_ledger())
        text = ledger.to_json()
        self.assertNotIn("user-1", text)
        self.assertIn("hmac-sha256:", text)
        self.assertNotIn(KEY.decode("latin-1"), text)


class TestReconciliationPositive(unittest.TestCase):
    def test_erase_after_restore_creates_delete_action(self) -> None:
        result = plan()
        self.assertEqual(result.plan_status, PLAN_VERIFIED)
        self.assertEqual(len(result.actions), 1)
        self.assertEqual(result.actions[0].action, ACTION_DELETE)
        self.assertEqual(result.execution_status, EXECUTION_NOT_VERIFIED)
        self.assertEqual(result.cutover_status, CUTOVER_BLOCKED)
        self.assertFalse(result.cutover_approved)

    def test_event_at_restore_time_is_scheduled_idempotently(self) -> None:
        event = make_event(
            applied_at=RESTORE_AT,
            decided_at="2026-11-02T23:00:00+00:00",
        )
        result = plan(ledger=make_ledger([event]))
        self.assertEqual(result.plan_status, PLAN_VERIFIED)
        self.assertEqual(result.actions[0].action, ACTION_DELETE)

    def test_anonymize_after_restore_creates_anonymize_action(self) -> None:
        result = plan(ledger=make_ledger([make_event(operation=OP_ANONYMIZE)]))
        self.assertEqual(result.plan_status, PLAN_VERIFIED)
        self.assertEqual(result.actions[0].action, ACTION_ANONYMIZE)

    def test_retain_after_restore_does_not_delete(self) -> None:
        result = plan(ledger=make_ledger([make_event(operation=OP_RETAIN)]))
        self.assertEqual(result.plan_status, PLAN_VERIFIED)
        self.assertEqual(result.actions[0].action, ACTION_RETAIN)
        self.assertEqual(result.actions[0].action, ACTION_RETAIN)
        self.assertNotEqual(result.actions[0].action, ACTION_DELETE)

    def test_multiple_orders_of_one_subject(self) -> None:
        event = make_event(order_refs=(ORDER_1, ORDER_2))
        result = plan(
            ledger=make_ledger([event]),
            orders=[restored(ORDER_1), restored(ORDER_2)],
        )
        self.assertEqual(result.plan_status, PLAN_VERIFIED)
        self.assertEqual({action.order_ref for action in result.actions}, {ORDER_1, ORDER_2})

    def test_repeated_identical_events_are_idempotent(self) -> None:
        first = make_event()
        duplicate = make_event(
            event_id="evt-2", idempotency_key="idem-evt-1", operation_id="op-evt-1"
        )
        result = plan(ledger=make_ledger([first, duplicate]))
        self.assertEqual(result.plan_status, PLAN_VERIFIED)
        self.assertEqual(len(result.actions), 1)

    def test_erase_before_restore_with_item_absent_is_ok(self) -> None:
        event = make_event(
            applied_at="2026-11-02T12:00:00+00:00",
            decided_at="2026-11-02T11:00:00+00:00",
        )
        # Ein weiteres Ereignis nach dem Restore sorgt fuer einen pruefbaren Plan.
        result = plan(
            ledger=make_ledger([event, make_event(event_id="evt-2", order_refs=(ORDER_2,))]),
            orders=[restored(ORDER_2)],
        )
        self.assertEqual(result.plan_status, PLAN_VERIFIED)
        self.assertEqual(result.actions[0].order_ref, ORDER_2)

    def test_anonymize_before_restore_and_already_anonymized_is_ok(self) -> None:
        event = make_event(
            operation=OP_ANONYMIZE,
            applied_at="2026-11-02T12:00:00+00:00",
            decided_at="2026-11-02T11:00:00+00:00",
        )
        pending = make_event(event_id="evt-2", order_refs=(ORDER_2,))
        result = plan(
            ledger=make_ledger([event, pending]),
            orders=[
                restored(ORDER_1, subject_ref=None, has_subject_link=False, customer_anonymized=True),
                restored(ORDER_2),
            ],
        )
        self.assertEqual(result.plan_status, PLAN_VERIFIED)

    def test_plan_does_not_mutate_restored_orders(self) -> None:
        orders = [restored()]
        before = list(orders)
        plan(orders=orders)
        self.assertEqual(orders, before)
        self.assertEqual(orders[0].subject_ref, SUBJECT_REF)

    def test_plan_has_no_subject_ref_or_pii(self) -> None:
        result = plan()
        text = result.to_json()
        self.assertNotIn("user-1", text)
        self.assertNotIn("subjectRef", text)
        self.assertNotIn("customer", text)
        self.assertIn(ORDER_1, text)


class TestReconciliationNegative(unittest.TestCase):
    def test_missing_ledger_blocks(self) -> None:
        result = plan(ledger={})
        self.assertEqual(result.plan_status, PLAN_BLOCKED)
        self.assertEqual(result.readiness_status, READINESS_BLOCKED)

    def test_missing_ledger_data_blocks(self) -> None:
        result = plan_reconciliation(
            ledger_data=None,
            restore_context=make_restore(),
            restored_orders=[restored()],
        )
        self.assertEqual(result.plan_status, PLAN_BLOCKED)
        self.assertTrue(any(CODE_LEDGER_MISSING in item for item in result.blockers))

    def test_erase_without_subject_link_blocks(self) -> None:
        result = plan(orders=[restored(subject_ref=None, has_subject_link=False)])
        self.assertEqual(result.plan_status, PLAN_BLOCKED)
        self.assertTrue(any("SUBJECT_REF_MISSING" in item for item in result.conflicts))

    def test_incomplete_history_blocks(self) -> None:
        result = plan(ledger=make_ledger(complete=False))
        self.assertEqual(result.plan_status, PLAN_BLOCKED)
        self.assertTrue(any(CODE_INCOMPLETE in item for item in result.blockers))

    def test_restore_outside_coverage_blocks(self) -> None:
        result = plan(ledger=make_ledger(covered_until="2026-11-02T00:00:00+00:00"))
        self.assertEqual(result.plan_status, PLAN_BLOCKED)
        self.assertTrue(any(CODE_INCOMPLETE in item for item in result.blockers))

    def test_unknown_schema_blocks(self) -> None:
        ledger = make_ledger()
        ledger["schemaVersion"] = 2
        result = plan(ledger=ledger)
        self.assertEqual(result.plan_status, PLAN_BLOCKED)
        self.assertTrue(any(CODE_SCHEMA_UNKNOWN in item for item in result.blockers))

    def test_missing_restore_time_is_blocked_or_rejected(self) -> None:
        with self.assertRaises(Exception):
            make_restore(restore_at=None)
        restore = make_restore()
        restore = dataclasses.replace(restore, restore_at="")
        result = plan(restore=restore)
        self.assertEqual(result.plan_status, PLAN_BLOCKED)

    def test_restore_identity_mismatch_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            make_restore(restore_table_arn="arn:aws:dynamodb:eu-central-1:999999999999:table/mays-orders-restore-20261103")

    def test_consumer_mismatch_blocks(self) -> None:
        result = plan(orders=[restored(consumer_id=OTHER_CONSUMER)])
        self.assertEqual(result.plan_status, PLAN_BLOCKED)
        self.assertTrue(any("CONSUMER_SCOPE_MISMATCH" in item for item in result.conflicts))

    def test_unknown_restored_consumer_blocks(self) -> None:
        result = plan(orders=[restored(consumer_id=None)])
        self.assertEqual(result.plan_status, PLAN_BLOCKED)
        self.assertTrue(any(CODE_CONSUMER_UNKNOWN in item for item in result.blockers))

    def test_conflicting_operations_block(self) -> None:
        ledger = make_ledger([
            make_event(operation=OP_ERASE),
            make_event(event_id="evt-2", operation=OP_RETAIN),
        ])
        result = plan(ledger=ledger)
        self.assertEqual(result.plan_status, PLAN_BLOCKED)
        self.assertTrue(any("CONFLICTING_OPERATIONS" in item for item in result.conflicts))

    def test_partial_application_blocks(self) -> None:
        event = make_event(status="PARTIALLY_COMPLETED", failed_records=1)
        result = plan(ledger=make_ledger([event]))
        self.assertEqual(result.plan_status, PLAN_BLOCKED)
        self.assertTrue(any(CODE_PARTIAL_APPLICATION in item for item in result.blockers))

    def test_failed_anonymize_blocks(self) -> None:
        event = make_event(operation=OP_ANONYMIZE, status="FAILED", failed_records=1)
        result = plan(ledger=make_ledger([event]))
        self.assertEqual(result.plan_status, PLAN_BLOCKED)

    def test_erase_applied_before_restore_but_item_present_blocks(self) -> None:
        event = make_event(
            applied_at="2026-11-02T12:00:00+00:00",
            decided_at="2026-11-02T11:00:00+00:00",
        )
        result = plan(ledger=make_ledger([event]))
        self.assertEqual(result.plan_status, PLAN_BLOCKED)
        self.assertTrue(any("ERASE_APPLIED_BUT_ITEM_PRESENT" in item for item in result.conflicts))

    def test_anonymize_applied_before_restore_but_pii_present_blocks(self) -> None:
        event = make_event(
            operation=OP_ANONYMIZE,
            applied_at="2026-11-02T12:00:00+00:00",
            decided_at="2026-11-02T11:00:00+00:00",
        )
        result = plan(ledger=make_ledger([event]))
        self.assertEqual(result.plan_status, PLAN_BLOCKED)
        self.assertTrue(any("ANONYMIZE_APPLIED_BUT_PII_PRESENT" in item for item in result.conflicts))

    def test_empty_restored_set_is_not_auto_verified(self) -> None:
        result = plan(orders=[])
        self.assertEqual(result.plan_status, PLAN_REVIEW_REQUIRED)
        self.assertNotEqual(result.plan_status, PLAN_VERIFIED)

    def test_no_actions_is_not_auto_verified(self) -> None:
        event = make_event(
            applied_at="2026-11-02T12:00:00+00:00",
            decided_at="2026-11-02T11:00:00+00:00",
        )
        result = plan(
            ledger=make_ledger([event]),
            orders=[restored(ORDER_2)],
        )
        self.assertEqual(result.plan_status, PLAN_REVIEW_REQUIRED)

    def test_cutover_cannot_be_approved(self) -> None:
        result = plan()
        self.assertEqual(result.plan_status, PLAN_VERIFIED)
        with self.assertRaises(Exception) as ctx:
            approve_cutover(result)
        self.assertEqual(ctx.exception.code, CODE_CUTOVER_BLOCKED)


class TestReadinessContract(unittest.TestCase):
    def test_verified_plan_is_only_review_required(self) -> None:
        readiness = build_privacy_readiness(plan())
        self.assertEqual(readiness["schemaVersion"], 1)
        self.assertEqual(readiness["planStatus"], PLAN_VERIFIED)
        self.assertEqual(readiness["status"], READINESS_REVIEW_REQUIRED)
        self.assertNotEqual(readiness["status"], "VERIFIED")
        self.assertEqual(readiness["executionStatus"], EXECUTION_NOT_VERIFIED)
        self.assertEqual(readiness["cutoverStatus"], CUTOVER_BLOCKED)
        self.assertFalse(readiness["cutoverApproved"])
        self.assertEqual(readiness["backupEvidence"], "NOT_PROVIDED")

    def test_blocked_plan_is_blocked_readiness(self) -> None:
        readiness = build_privacy_readiness(plan(ledger=make_ledger(complete=False)))
        self.assertEqual(readiness["status"], READINESS_BLOCKED)

    def test_blocked_plan_has_no_actions(self) -> None:
        result = plan(ledger=make_ledger(complete=False))
        self.assertEqual(result.actions, ())

    def test_report_written_without_pii(self) -> None:
        result = plan()
        with tempfile.TemporaryDirectory() as tmp:
            json_path, md_path = write_reconciliation_report(tmp, result)
            text = Path(json_path).read_text(encoding="utf-8")
            self.assertIn("PLAN_VERIFIED", text)
            self.assertNotIn("user-1", text)
            self.assertNotIn("subjectRef", text)
            self.assertIn("cutoverApproved", text)
            self.assertIn("CUTOVER_BLOCKED", text)
            self.assertIn("Order-Restore-Reconciliation", Path(md_path).read_text(encoding="utf-8"))


class TestDataMinimization(unittest.TestCase):
    def test_ledger_event_has_no_customer_payload(self) -> None:
        event = make_event()
        text = json.dumps(event)
        for forbidden in ("customer", "email", "phone", "address", "items", "totalAmount"):
            self.assertNotIn(forbidden, text)

    def test_consumer_is_not_a_subject_identifier(self) -> None:
        event = make_event()
        self.assertNotEqual(event["consumerId"], event["subjectRef"])
        self.assertIn("cognito:", event["consumerId"])

    def test_plan_json_does_not_contain_subject_ref(self) -> None:
        text = plan().to_json()
        self.assertNotIn("SUBJECT#", text)
        self.assertNotIn(SUBJECT_REF, text)


if __name__ == "__main__":
    unittest.main()
