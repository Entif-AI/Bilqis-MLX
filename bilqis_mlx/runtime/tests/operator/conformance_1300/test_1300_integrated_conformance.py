"""#1300 root witness for create -> learn -> retain -> expand -> resume."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys

from bilqis_mlx.runtime.atlas_admission import read_accepted_atlas_factory_release
from bilqis_mlx.runtime.atlas_flywheel_runtime import AcceptedAtlasFlywheelSupervisor
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.runtime.bamf_operator.session import operate_bamf
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.runtime.tests.custody.bamf_bundle.cold_resume_probe import (
    retained_digest,
)
from bilqis_mlx.runtime.active_grade_cadence import read_current_cadence

from ..conformance_1300_support import (
    Conformance1300RuntimeSupport,
    TARGET,
)


BILQIS_LEAF_GATE_POLICY = "DETACHED_ONLY"
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
COLD_PROBE = (
    "bilqis_mlx.runtime.tests.operator.conformance_1300_support.cold_probe"
)


class IntegratedConformance1300Tests(Conformance1300RuntimeSupport):
    def test_c07_admission_seals_and_activates_target_without_learning(self):
        fixture = self._production_parameter_fixture()
        tail = fixture.snapshot.abi_entries[-2:]
        self.assertEqual(
            tuple(entry.index for entry in tail),
            tuple(range(len(fixture.snapshot.abi_entries) - 2,
                        len(fixture.snapshot.abi_entries))),
        )
        supervisor = AcceptedAtlasFlywheelSupervisor(
            self.run,
            self.parent_graph,
            reserve_gib=0.0,
        )
        with self._operator_context(fixture):
            before, before_release, after, after_release = self._admit_target(
                supervisor, fixture
            )
            active = self._activate_current_generated_grade()
        self.assertNotEqual(
            after_release.release_sha256,
            before_release.release_sha256,
        )
        self.assertIn(TARGET, after_release.execution_plan.capability_map)
        self.assertIn(TARGET, active.member_capability_ids)
        self.assertEqual(
            after.retained_state.optimizer_step,
            before.retained_state.optimizer_step,
        )
        self.assertEqual(after.baseline_evidence, before.baseline_evidence)

    def test_newly_admitted_semantic_trains_retains_and_reenters_from_cold_custody(
        self,
    ):
        fixture = self._production_parameter_fixture()
        supervisor = AcceptedAtlasFlywheelSupervisor(
            self.run,
            self.parent_graph,
            reserve_gib=0.0,
        )
        progress = []

        def observe(message):
            progress.append(message)
            print("BAMF1300_STAGE " + message, flush=True)

        with self._operator_context(fixture):
            before, before_release, admitted, admitted_release = self._admit_target(
                supervisor, fixture
            )
            activated = self._activate_current_generated_grade()
            self.assertIn(TARGET, activated.member_capability_ids)
            self._credit_all_predecessor_learning(supervisor)
            result = operate_bamf(
                self.run,
                minutes=1,
                max_visits=1,
                steps_per_visit=1,
                reserve_gib=0.0,
                source_prefetch_workers=0,
                parent_graph=self.parent_graph,
                progress=observe,
            )
            accepted = load_accepted_generation(self.run)
            accepted_release = read_accepted_atlas_factory_release(self.run)
            from bilqis_mlx.runtime.active_generated_grade import (
                read_active_generated_grade,
            )

            active = read_active_generated_grade(self.run)
            cold = AcceptedAtlasFlywheelSupervisor(
                self.run,
                self.parent_graph,
                reserve_gib=0.0,
            ).load_state()
            cadence = read_current_cadence(self.run)

        process = subprocess.run(
            [sys.executable, "-m", COLD_PROBE, str(self.run)],
            cwd=str(REPOSITORY_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        clean = json.loads(process.stdout.strip().splitlines()[-1])

        self.assertEqual(result.visits, 1)
        self.assertEqual(result.accepted, 1)
        self.assertEqual(result.rejected, 0)
        self.assertNotEqual(
            accepted_release.release_sha256,
            before_release.release_sha256,
        )
        self.assertIn(TARGET, accepted_release.execution_plan.capability_map)
        if result.admission_advances:
            self.assertNotEqual(
                accepted_release.release_sha256,
                admitted_release.release_sha256,
            )
        self.assertIn(TARGET, active.member_capability_ids)
        self.assertIn("selected " + TARGET + " with ", "\n".join(progress))
        self.assertIn("executing candidate step 1/1", progress)
        self.assertIn("evaluating retention evidence", progress)
        self.assertEqual(
            accepted.retained_state.optimizer_step,
            admitted.retained_state.optimizer_step + 1,
        )
        self.assertIsNotNone(accepted.baseline_evidence)
        self.assertEqual(
            cold.learner_evidence.optimizer_step,
            accepted.retained_state.optimizer_step,
        )
        self.assertEqual(
            cold.epoch.current_release.release_sha256,
            accepted_release.release_sha256,
        )
        self.assertEqual(clean["generation"], accepted.generation)
        self.assertEqual(
            clean["optimizer_step"],
            accepted.retained_state.optimizer_step,
        )
        self.assertEqual(
            clean["checkpoint_identity_sha256"],
            candidate_identity_digest(accepted.retained_state),
        )
        self.assertEqual(
            clean["retained_digest"],
            retained_digest(accepted.retained_state),
        )
        self.assertEqual(clean["baseline_evidence"], accepted.baseline_evidence)
        self.assertEqual(clean["teacher_state"], accepted.teacher_state)
        self.assertEqual(
            clean["factory_release_sha256"],
            accepted_release.release_sha256,
        )
        self.assertEqual(clean["active_grade"], active.to_record())
        self.assertIsNotNone(cadence)
        self.assertEqual(clean["cadence"], cadence.to_record())

if __name__ == "__main__":
    import unittest

    unittest.main()
