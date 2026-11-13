"""Explicit degraded-state and compatibility semantics for CP02."""
from dataclasses import FrozenInstanceError
import unittest

from bilqis_mlx.mission_control.codec import decode_record, encode_record
from bilqis_mlx.mission_control.envelopes import (
    EventEnvelope, PartialEnvelope, StaleEnvelope, UnavailableEnvelope,
    UnavailableReason,
)
from bilqis_mlx.mission_control.model import (
    AuthorityClass, ContractErrorCode, CoverageState, DataValue,
    MissionControlContractError, RecordMeta,
    ValueOrigin, ValueState,
)
from bilqis_mlx.mission_control.operator import (
    ActionReceiptState, OperatorActionReceipt,
)
from bilqis_mlx.mission_control.tests.samples import SAMPLES


class MissionControlStateTests(unittest.TestCase):
    def test_absent_values_are_explicit_states_not_zero_sentinels(self):
        for state in (
            ValueState.MISSING, ValueState.UNKNOWN,
            ValueState.DENIED, ValueState.UNAVAILABLE,
        ):
            with self.subTest(state=state):
                value = DataValue(state, None, None)
                self.assertIsNone(value.value)
                self.assertIsNone(value.origin)
        measured = DataValue(ValueState.PRESENT, ValueOrigin.MEASURED, 0, "count")
        derived = DataValue(ValueState.PRESENT, ValueOrigin.DERIVED, 0, "count")
        self.assertNotEqual(measured.origin, derived.origin)

    def test_degraded_envelopes_are_first_class_records(self):
        envelope_types = {type(sample) for sample in SAMPLES if type(sample) in (
            UnavailableEnvelope, StaleEnvelope, PartialEnvelope,
        )}
        self.assertEqual(envelope_types, {UnavailableEnvelope, StaleEnvelope, PartialEnvelope})

    def test_denied_envelope_carries_no_source_or_evidence_leakage(self):
        meta = RecordMeta(
            record_id="denied", run=None, materialized_at=120,
            observed_at=None, as_of=118, coverage=CoverageState.UNKNOWN,
            authority=AuthorityClass.DERIVED,
        )
        denied = UnavailableEnvelope(meta, "private-view", UnavailableReason.DENIED,
                                     "policy:mission-control")
        self.assertEqual(denied.meta.source_refs, ())
        self.assertEqual(denied.meta.evidence_refs, ())

    def test_action_acknowledgement_cannot_masquerade_as_completion(self):
        complete = next(sample for sample in SAMPLES if type(sample) is OperatorActionReceipt)
        self.assertEqual(complete.state, ActionReceiptState.COMPLETED)
        self.assertIsNotNone(complete.postcondition_ref)
        pending = OperatorActionReceipt(
            complete.meta, "request-2", "operation-2", ActionReceiptState.ACCEPTED,
            120, None, None,
        )
        self.assertIsNone(pending.postcondition_ref)
        with self.assertRaises(MissionControlContractError):
            OperatorActionReceipt(
                complete.meta, "request-3", "operation-3", ActionReceiptState.ACCEPTED,
                120, "postcondition:forbidden", None,
            )

    def test_event_cursor_is_order_metadata_not_event_identity(self):
        event = next(sample for sample in SAMPLES if type(sample) is EventEnvelope)
        self.assertEqual(event.event_id, "event-9")
        self.assertEqual(event.position.stream_id, "run-7:candidate")
        self.assertEqual(event.position.epoch_id, "epoch-1")
        self.assertEqual(event.position.ordinal, 9)
        self.assertEqual(event.position.cursor_sha256, "3" * 64)
        self.assertEqual(event.position.previous_cursor_sha256, "4" * 64)
        self.assertNotEqual(event.event_id, event.position.cursor_sha256)

    def test_unknown_and_missing_schema_errors_are_deterministic(self):
        for payload, code in (
            ({}, ContractErrorCode.SCHEMA_MISSING),
            ({"schema_version": "bilqis.bamf.mission-control.operator-view/v999"},
             ContractErrorCode.SCHEMA_UNSUPPORTED),
        ):
            with self.subTest(code=code):
                with self.assertRaises(MissionControlContractError) as raised:
                    decode_record(payload)
                self.assertEqual(raised.exception.code, code)
                self.assertTrue(str(raised.exception).startswith(code.value))

    def test_extra_wire_field_fails_closed_and_records_are_frozen(self):
        sample = SAMPLES[0]
        payload = encode_record(sample)
        payload["surprise"] = True
        with self.assertRaises(MissionControlContractError) as raised:
            decode_record(payload)
        self.assertEqual(raised.exception.code, ContractErrorCode.PAYLOAD_INVALID)
        with self.assertRaises(FrozenInstanceError):
            sample.stage = "MUTATED"


if __name__ == "__main__":
    unittest.main()
