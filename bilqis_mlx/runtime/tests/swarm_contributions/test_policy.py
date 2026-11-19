from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.swarm_contributions import (
    ContributionClass, ContributionDisposition, IndependentEvaluation,
    DurableReplayStore, admit_remote_observation, dispatch_eligible_work,
)
from bilqis_mlx.runtime.tests.swarm_contributions.fixtures import manifest, receipt


class SwarmPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.replay_store = DurableReplayStore(Path(self.temp.name) / "replay")

    def test_worker_score_is_evidence_not_non_neural_authority(self):
        work = manifest()
        result = receipt(work, score=1.0)
        decision = admit_remote_observation(
            work, result, now=1_600, replay_store=self.replay_store,
            independent_evaluator=lambda *_: IndependentEvaluation(
                False, 0.25, "1" * 64, "retention:failed"))
        self.assertIs(decision.disposition, ContributionDisposition.REJECTED)
        self.assertEqual(result.claimed_score, 1.0)
        self.assertEqual(decision.canonical_evidence_digest, "1" * 64)

    def test_retention_requirement_cannot_be_bypassed_by_score(self):
        work = manifest()
        result = receipt(work)
        decision = admit_remote_observation(
            work, result, now=1_600, replay_store=self.replay_store,
            independent_evaluator=lambda *_: IndependentEvaluation(
                True, 1.0, "6" * 64, "retention:failed"))
        self.assertIs(decision.disposition, ContributionDisposition.REJECTED)

    def test_dense_updates_and_private_scope_fail_closed(self):
        with self.assertRaises(BilqisError):
            manifest(ContributionClass.DENSE_UPDATE)
        with self.assertRaises(BilqisError):
            manifest(rights_scope="PRIVATE_REAL")
        with self.assertRaises(BilqisError):
            manifest(rights_scope="UNCLASSIFIED")

    def test_public_derived_scope_is_explicitly_permitted(self):
        work = manifest(rights_scope="PUBLIC_DERIVED")
        self.assertEqual(work.rights_scope, "PUBLIC_DERIVED")

    def test_swarm_dispatch_is_optional_and_deterministic(self):
        first = manifest()
        second = replace(first, manifest_id="work:fixture-002", replay_id="replay:fixture-002")
        self.assertEqual(
            dispatch_eligible_work((first,), available_workers=()), ())
        result = dispatch_eligible_work(
            (second, first), available_workers=("worker:2", "worker:1"))
        self.assertEqual(tuple(item[1] for item in result),
                         tuple(sorted((first.digest, second.digest))))


if __name__ == "__main__":
    unittest.main()
