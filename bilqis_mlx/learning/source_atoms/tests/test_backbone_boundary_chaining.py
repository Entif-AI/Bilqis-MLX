"""B11 producer consumes only the immediate selected-state boundary."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
import bilqis_mlx.learning.source_atoms.backbone as backbone


class _Session:
    def __init__(self, completed):
        self.results = [object() for _ in range(completed)]
        self.next_inputs = []

    def advance(self, *, next_input=None):
        self.next_inputs.append(next_input)
        result = object()
        self.results.append(result)
        return result


class BoundaryChainingTests(unittest.TestCase):
    def producer(self, completed=2):
        producer = object.__new__(backbone._SourceBackboneProducerSession)
        producer._session = _Session(completed)
        producer._depth_inputs = ()
        producer._receipts = ()
        return producer

    def test_stale_boundary_fails_before_depth_selection_or_execution(self):
        producer = self.producer(completed=2)
        stale_features = SimpleNamespace(boundary_group=1)
        stale_view = SimpleNamespace(boundary_group=1)
        with patch.object(backbone, "depth_select") as select:
            with self.assertRaises(BilqisError):
                producer.advance(stale_features, stale_view)
        select.assert_not_called()
        self.assertEqual(producer._session.next_inputs, [])
        self.assertEqual(producer._depth_inputs, ())

    def test_exact_next_boundary_preserves_selected_input_and_receipt_order(self):
        producer = self.producer(completed=2)
        features = SimpleNamespace(boundary_group=2)
        view = SimpleNamespace(boundary_group=2)
        selected = object()
        receipt = object()
        with (patch.object(backbone, "depth_select", return_value=selected) as select,
              patch.object(backbone, "_issue_from_producer", return_value=receipt)):
            actual = producer.advance(features, view)
        select.assert_called_once_with(producer, features, view)
        self.assertIs(actual, receipt)
        self.assertEqual(producer._session.next_inputs, [selected])
        self.assertEqual(producer._depth_inputs, ((features, view),))
        self.assertEqual(producer._receipts, (receipt,))


if __name__ == "__main__":
    unittest.main()
