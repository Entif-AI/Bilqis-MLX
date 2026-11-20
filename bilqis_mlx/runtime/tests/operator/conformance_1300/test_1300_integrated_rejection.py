"""#1300 destructive-candidate rollback witness through the production root."""
from __future__ import annotations

from bilqis_mlx.runtime.atlas_flywheel_runtime import AcceptedAtlasFlywheelSupervisor
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation

from ..conformance_1300_support import Conformance1300RuntimeSupport, TARGET
from ..conformance_1300_support.rollback import (
    DestructiveCandidateCapture,
    assert_complete_rollback,
    parent_custody,
)
from ..conformance_1300_support.scenario import one_visit


BILQIS_LEAF_GATE_POLICY = "DETACHED_ONLY"


class IntegratedConformance1300RejectionTests(Conformance1300RuntimeSupport):
    def test_destructive_candidate_rejects_and_restores_complete_parent_custody(self):
        fixture = self._production_parameter_fixture()
        supervisor = AcceptedAtlasFlywheelSupervisor(
            self.run, self.parent_graph, reserve_gib=0.0
        )
        progress = []

        with self._operator_context(fixture):
            self._admit_target(supervisor, fixture)
            self._activate_current_generated_grade()
            self._credit_all_predecessor_learning(supervisor)
            baseline_start = len(progress)
            for _attempt in range(4):
                first = one_visit(self, progress)
                if (first.accepted
                        and "selected " + TARGET + " with "
                        in "\n".join(progress[baseline_start:])):
                    break
            else:
                self.fail(f"{TARGET} did not establish a retained baseline within 4 visits")
            self._credit_all_predecessor_learning(supervisor)
        first_accepted = load_accepted_generation(self.run)
        self.assertIsNotNone(first_accepted.baseline_evidence)

        before = parent_custody(first_accepted, self.run)
        destructive = DestructiveCandidateCapture()
        with self._operator_context(fixture), destructive.context():
            result = one_visit(self, progress)

        self.assertEqual(result.accepted, 0)
        self.assertEqual(result.rejected, 1)
        self.assertEqual(result.status, "VISIT_LIMIT")
        self.assertTrue(destructive.evaluations)
        self.assertIn(
            destructive.evaluations[-1].decision.reason,
            ("NO_MEASURABLE_TARGET_GAIN", "TARGET_BASELINE_REGRESSION"),
        )
        assert_complete_rollback(self, self.run, before, destructive)
