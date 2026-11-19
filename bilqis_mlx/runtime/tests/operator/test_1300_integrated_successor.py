"""#1300 append-only successor witness through accepted C07 and operate_bamf."""
from __future__ import annotations

from bilqis_mlx.runtime.atlas_admission import (
    read_accepted_atlas_factory_release,
    read_accepted_atlas_lease_v2,
)
from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.runtime.bamf_operator.session import operate_bamf

from .conformance_1300_support import (
    Conformance1300RuntimeSupport,
    SUCCESSOR,
    TARGET,
)
from .conformance_1300_support.lifecycle import (
    bootstrap_staged_generation_zero,
    enroll_prepared_lease,
)


BILQIS_LEAF_GATE_POLICY = "DETACHED_ONLY"


class IntegratedConformance1300SuccessorTests(Conformance1300RuntimeSupport):
    def test_append_only_successor_is_admitted_and_learned_under_same_v2_lease(self):
        fixture = self._production_parameter_fixture()
        progress = []

        def observe(message):
            progress.append(message)
            print("BAMF1300_SUCCESSOR " + message, flush=True)

        def one_visit():
            return operate_bamf(
                self.run, minutes=1, max_visits=1, steps_per_visit=16,
                reserve_gib=0.0, source_prefetch_workers=0,
                parent_graph=self.parent_graph, progress=observe)

        with self._operator_context(fixture):
            before, selected, foundation_grade, after = (
                bootstrap_staged_generation_zero(self.run))
            self.assertEqual(selected.status, "TEACHER_SELECTED")
            self.assertEqual(after.generation, before.generation)
            self.assertEqual(
                after.retained_state.optimizer_step,
                before.retained_state.optimizer_step,
            )
            self.assertEqual(foundation_grade.transition_kind, "BOOTSTRAP")
            self.assertEqual(
                foundation_grade.transition_reason,
                "DATA_DEFINED_INITIAL_GRADE_BOOTSTRAP",
            )
            self.assertEqual(
                tuple(dict.fromkeys(foundation_grade.member_capability_ids)),
                ("A.IDENTITY",),
            )

            with self.host_registry():
                enrolled = enroll_prepared_lease(
                    self.run,
                    fixture.lease,
                    source_authority=AcceptedRuntimeHost(self.run).source_authority(),
                )
            self.assertEqual(enrolled.digest(), fixture.lease.digest())

            foundation_start = len(progress)
            for _attempt in range(8):
                one_visit()
                event_release = read_accepted_atlas_factory_release(self.run)
                if TARGET in event_release.execution_plan.capability_map:
                    break
            else:
                self.fail("A.IDENTITY did not qualify TARGET for C07 within 8 visits")
            foundation_progress = progress[foundation_start:]
            self.assertIn("selected A.IDENTITY with ", "\n".join(foundation_progress))
            self.assertNotIn(
                "accepted learner evidence refresh:",
                "\n".join(foundation_progress),
            )
            foundation_boundary_refresh = next(
                index for index, message in enumerate(foundation_progress)
                if message.startswith("grade boundary learner evidence refresh:"))
            foundation_transition = foundation_progress.index(
                "grade certification succeeded; activated exact receipt-bound generated successor")
            self.assertLess(foundation_boundary_refresh, foundation_transition)
            admitted_event = load_accepted_generation(self.run)
            self.assertGreater(admitted_event.retained_state.optimizer_step, 0)

            target_start = len(progress)
            for _attempt in range(8):
                one_visit()
                successor_release = read_accepted_atlas_factory_release(self.run)
                if SUCCESSOR in successor_release.execution_plan.capability_map:
                    break
            else:
                self.fail(f"{TARGET} did not qualify {SUCCESSOR} within 8 visits")
            learned_event = load_accepted_generation(self.run)
            target_progress = progress[target_start:]
            self.assertIn("selected " + TARGET + " with ", "\n".join(target_progress))
            self.assertNotIn(
                "accepted learner evidence refresh:",
                "\n".join(target_progress),
            )
            target_boundary_refresh = next(
                index for index, message in enumerate(target_progress)
                if message.startswith("grade boundary learner evidence refresh:"))
            target_transition = target_progress.index(
                "grade certification succeeded; activated exact receipt-bound generated successor")
            self.assertLess(target_boundary_refresh, target_transition)
            self.assertGreater(
                learned_event.retained_state.optimizer_step,
                admitted_event.retained_state.optimizer_step,
            )

            with self.host_registry():
                accepted_lease = read_accepted_atlas_lease_v2(
                    self.run,
                    source_authority=AcceptedRuntimeHost(self.run).source_authority(),
                )
            self.assertIsNotNone(accepted_lease)
            self.assertEqual(accepted_lease.digest(), fixture.lease.digest())

            successor_start = len(progress)
            before_successor_learning = load_accepted_generation(self.run)
            for _attempt in range(8):
                result = one_visit()
                if (result.accepted
                        and "selected " + SUCCESSOR + " with "
                        in "\n".join(progress[successor_start:])):
                    break
            else:
                self.fail(f"{SUCCESSOR} did not retain within 8 visits")
            final = load_accepted_generation(self.run)
            final_release = read_accepted_atlas_factory_release(self.run)

        self.assertGreater(
            final.retained_state.optimizer_step,
            before_successor_learning.retained_state.optimizer_step,
        )
        self.assertEqual(final_release.release_sha256, successor_release.release_sha256)
        self.assertIn(TARGET, final_release.execution_plan.capability_map)
        self.assertIn(SUCCESSOR, final_release.execution_plan.capability_map)
