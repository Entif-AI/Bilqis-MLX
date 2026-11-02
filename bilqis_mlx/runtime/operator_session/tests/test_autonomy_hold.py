"""A source-frontier hold reports proposal evidence without a learner update."""
from types import SimpleNamespace
from unittest import TestCase

from bilqis_mlx.runtime.operator_session.autonomy_hold import _hold_autonomy


class AutonomyHoldTests(TestCase):
    def test_source_development_preserves_proposal_and_checkpoint_identity(self):
        proposal = SimpleNamespace(disposition=SimpleNamespace(value="SOURCE_DEVELOPMENT"),
            proposal_sha256="proposal", frontier_sha256="frontier",
            candidate_gates=("gate",), selected_candidate_ids=("candidate",))
        session = SimpleNamespace(propose_source_frontier_work=lambda *args: (proposal, "proposal.json"))
        school = SimpleNamespace(grade="Z", current_student=SimpleNamespace(sha256="student", optimizer_step=7))
        events = []
        reason = _hold_autonomy(autonomy_session=session, school=school, graph=None,
            receipt={"generation": 8}, run_dir="unused", action=SimpleNamespace(deferred_obligation_ids=("debt",)),
            record=lambda run_dir, event: events.append(event))
        self.assertEqual(reason, "AUTONOMY_SOURCE_DEVELOPMENT_REQUIRED")
        self.assertEqual(events, [{"event": "SCHOOL_AUTONOMY_SOURCE_DEVELOPMENT_REQUIRED",
            "generation": 8, "grade": "Z", "deferred_obligations": ["debt"],
            "proposal_sha256": "proposal", "proposal_file": "proposal.json",
            "frontier_sha256": "frontier", "candidate_gate_count": 1,
            "selected_candidate_ids": ["candidate"], "student_sha256": "student",
            "optimizer_step": 7, "model_and_optimizer_unchanged": True}])
