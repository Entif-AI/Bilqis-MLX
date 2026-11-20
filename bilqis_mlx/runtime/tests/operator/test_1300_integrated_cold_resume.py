"""#1300 focused cold-resume/legal-next witness after successor admission."""
from __future__ import annotations

from bilqis_mlx.runtime.atlas_admission import read_accepted_atlas_factory_release
from bilqis_mlx.runtime.active_generated_grade import read_active_generated_grade
from bilqis_mlx.runtime.atlas_flywheel_runtime import AcceptedAtlasFlywheelSupervisor
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation

from .conformance_1300_support import Conformance1300RuntimeSupport, SUCCESSOR
from .conformance_1300_support.cold_resume_assertions import (
    assert_cold_resume_legality,
)
from .conformance_1300_support.scenario import (
    one_visit,
    structural_certification_pass,
)


BILQIS_LEAF_GATE_POLICY = "DETACHED_ONLY"


class IntegratedConformance1300ColdResumeTests(Conformance1300RuntimeSupport):
    def test_successor_admitted_custody_cold_resumes_to_same_legal_next(self):
        fixture = self._production_parameter_fixture()
        supervisor = AcceptedAtlasFlywheelSupervisor(
            self.run, self.parent_graph, reserve_gib=0.0
        )
        progress = []

        with self._operator_context(fixture):
            self._admit_target(supervisor, fixture)
            self._activate_current_generated_grade()
            # The production successor path already has its own authoritative
            # #1300 witness.  This diagnostic needs only a lawful accepted
            # successor state so it can isolate cold-resume/legal-next behavior.
            # Close exact-checkpoint predecessor evidence structurally instead
            # of replaying another multi-minute learner visit.
            self._credit_all_predecessor_learning(
                supervisor, exclude=(SUCCESSOR,)
            )
            with structural_certification_pass():
                transition = one_visit(self, progress)
            self.assertEqual(transition.visits, 1)
            self.assertEqual((transition.accepted, transition.rejected), (0, 0))
            successor_release = read_accepted_atlas_factory_release(self.run)
            self.assertIn(
                SUCCESSOR, successor_release.execution_plan.capability_map
            )
            active = read_active_generated_grade(self.run)
            self.assertIn(SUCCESSOR, active.member_capability_ids)
            successor = load_accepted_generation(self.run)
            self._credit_all_predecessor_learning(
                supervisor, exclude=(SUCCESSOR,)
            )

        receipts = assert_cold_resume_legality(self, self.run, SUCCESSOR)

        self.assertEqual(
            receipts["accepted"]["generation"], successor.generation
        )
        self.assertEqual(
            receipts["accepted"]["optimizer_step"],
            successor.retained_state.optimizer_step,
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
