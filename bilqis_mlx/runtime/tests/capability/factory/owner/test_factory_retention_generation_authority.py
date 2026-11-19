"""Fail-closed C05 authority rebinding for final motif successor custody."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.learning.atlas_retention_decision import (
    _issued_decision_generation_authority,
    issue_factory_retention_decision,
)
from bilqis_mlx.learning.atlas_retention_generation_authority import (
    bind_factory_retention_generation_authority,
)

from .test_factory_retention_owner_adversarial import (
    _evaluate_foundation_owner,
    _foundation_owner_fixture,
)


class _FinalSuccessor:
    def __init__(self, retained_state, baseline):
        self.retained_state = retained_state
        self.baseline_evidence = baseline
        self.transition = {"kind": "MOTIF_ALLOCATION"}


class FactoryRetentionGenerationAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.evaluation = _evaluate_foundation_owner(*_foundation_owner_fixture())
        self.decision = issue_factory_retention_decision(self.evaluation)
        self.successor = _FinalSuccessor(
            self.evaluation.candidate_state,
            self.evaluation.baseline_ledger.to_record(),
        )

    def _owner_patches(self):
        return (
            patch(
                "bilqis_mlx.runtime.bamf_bundle.records.BamfBundleCandidate",
                _FinalSuccessor,
            ),
            patch(
                "bilqis_mlx.runtime.bamf_bundle.motif.transition."
                "is_motif_allocation_transition",
                return_value=True,
            ),
            patch(
                "bilqis_mlx.learning._atlas_candidate.identity_binding."
                "candidate_identity_for_canonical_consumer",
                return_value=self.evaluation.candidate_candidate_sha256,
            ),
            patch(
                "bilqis_mlx.runtime.bamf_bundle.genesis.records."
                "successor_candidate_identity_digest",
                return_value="9" * 64,
            ),
        )

    def test_rebind_advances_only_hidden_generation_authority(self):
        public_before = self.decision.to_record()
        patches = self._owner_patches()
        with patches[0], patches[1], patches[2], patches[3]:
            rebound = bind_factory_retention_generation_authority(
                self.decision, self.evaluation, self.successor)

        self.assertIs(rebound, self.decision)
        self.assertEqual(self.decision.to_record(), public_before)
        self.assertEqual(
            _issued_decision_generation_authority(self.decision), "9" * 64)

    def test_rebind_rejects_foreign_retained_state(self):
        self.successor.retained_state = SimpleNamespace()
        patches = self._owner_patches()
        with patches[0], patches[1], patches[2], patches[3]:
            with self.assertRaises(Exception):
                bind_factory_retention_generation_authority(
                    self.decision, self.evaluation, self.successor)


if __name__ == "__main__":
    unittest.main()
