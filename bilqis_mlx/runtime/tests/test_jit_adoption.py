from dataclasses import replace
import unittest

from bilqis_mlx.factory.autonomy import compile_autonomy_plan, initial_evidence_ledger
from bilqis_mlx.factory.jit_curriculum import propose_curriculum_delta
from bilqis_mlx.factory.tests.test_candidate_staging import CandidateStagingFixture
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime.jit_adoption import resolve_ready_candidate


class JitAdoptionTests(CandidateStagingFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.staged = self.stage()
        self.plan = compile_autonomy_plan(self.current)
        self.ledger = initial_evidence_ledger(self.current, plan=self.plan)
        self.checkpoint = Checkpoint("e" * 64, "bundles/fixture", 0, True)
        self.proposal = propose_curriculum_delta(self.frontier, self.current,
            self.ledger, self.plan, self.checkpoint.sha256, self.checkpoint.optimizer_step,
            candidate_bindings=(self.staged.binding,))

    def resolve(self, **overrides):
        arguments = dict(frontier=self.frontier, current=self.current,
            ledger=self.ledger, plan=self.plan, checkpoint=self.checkpoint,
            proposal=self.proposal, staged=(self.staged,))
        arguments.update(overrides)
        return resolve_ready_candidate(**arguments)

    def test_exact_current_proposal_resolves_without_mutating_learner(self):
        self.assertEqual(self.resolve(), self.staged)
        self.assertEqual(self.checkpoint.optimizer_step, 0)
        self.assertEqual(self.ledger.receipts, ())

    def test_checkpoint_or_optimizer_drift_prevents_adoption(self):
        for checkpoint in (replace(self.checkpoint, sha256="f" * 64),
                           replace(self.checkpoint, optimizer_step=1)):
            with self.assertRaisesRegex(ValueError, "PROPOSAL_CONTEXT_CHANGED"):
                self.resolve(checkpoint=checkpoint)

    def test_new_evidence_and_missing_package_require_a_new_proposal(self):
        with self.assertRaisesRegex(ValueError, "PROPOSAL_CONTEXT_CHANGED"):
            self.resolve(staged=())
        from bilqis_mlx.factory.autonomy import EvidenceReceipt, record_evidence, obligations_for_capability
        obligation = obligations_for_capability(self.current, "Z.C0", plan=self.plan)[0]
        ledger = record_evidence(self.current, self.ledger, EvidenceReceipt(
            obligation.obligation_id, "new-evidence", "e" * 64, 0,
            "d" * 64, obligation.minimum_specimens, True), plan=self.plan)
        with self.assertRaisesRegex(ValueError, "PROPOSAL_CONTEXT_CHANGED"):
            self.resolve(ledger=ledger)
