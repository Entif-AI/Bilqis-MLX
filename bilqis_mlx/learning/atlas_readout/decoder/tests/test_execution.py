"""Loss receipts must describe a causally executed legal committed prefix."""
from dataclasses import replace
import unittest
import mlx.core as mx
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_readout import predict_typed, DecisionKind, DecodeStatus
from bilqis_mlx.learning.atlas_readout.decoder.prediction import ModelOutput, DecisionLogits, ExecutionMode
from bilqis_mlx.learning.atlas_readout.decoder.tests.helpers import case


class ExecutionReceiptTests(unittest.TestCase):
    def test_nonexecuted_value_cannot_be_supervised(self):
        _, _, plan, _, _ = case()
        record = DecisionLogits('value', DecisionKind.VALUE, plan.decisions[1].legal_values,
                                mx.array([1., 2.]))
        with self.assertRaises(BilqisError):
            ModelOutput(plan, (record,), (), DecodeStatus.PARTIAL,
                        ExecutionMode.TEACHER_FORCED, None, True)

    def test_missing_reordered_or_truncated_candidate_receipts_reject(self):
        output = predict_typed(*case())
        with self.assertRaises(BilqisError):
            replace(output, decisions=output.decisions[1:])
        with self.assertRaises(BilqisError):
            replace(output, decisions=tuple(reversed(output.decisions)))
        record = output.decisions[1]
        with self.assertRaises(BilqisError):
            replace(output, decisions=(output.decisions[0],
                replace(record, candidates=record.candidates[:1], logits=record.logits[:1]),
                output.decisions[2]))
        with self.assertRaises(BilqisError):
            replace(output, status=DecodeStatus.PARTIAL, frame=None, fallback_requested=True)
