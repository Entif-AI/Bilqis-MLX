"""Operator policy text follows current assessment authority, preserving lineage."""
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.presentation.dashboard import _push_resource_and_contract
from bilqis_mlx.presentation.tests.test_bamf_metrics import board


class OperatorPolicyTests(unittest.TestCase):
    def test_factory_contract_does_not_advertise_fresh_generalization(self):
        view = board()
        with tempfile.TemporaryDirectory() as tmp:
            _push_resource_and_contract(view, Path(tmp),
                {'factory_release_sha256': 'a' * 64}, ('A', 'Z'), 'Z', reserve_gib=100)
        rendered = view.render(width=400, height=100)
        self.assertIn('fresh routine; fixed promotion; generalization inactive', rendered)
        self.assertNotIn('independent fresh generalization', rendered)

    def test_historical_policy_is_labeled_as_lineage_only(self):
        view = board()
        with tempfile.TemporaryDirectory() as tmp:
            _push_resource_and_contract(view, Path(tmp), None, (), 'NOT_ADMITTED', reserve_gib=100)
        self.assertIn('Historical policy (lineage only)', view.render(width=400, height=100))
