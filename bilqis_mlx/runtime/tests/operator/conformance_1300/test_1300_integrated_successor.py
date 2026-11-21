"""#1300 append-only successor-admission witness through accepted C07."""
from __future__ import annotations

from bilqis_mlx.runtime.atlas_admission import (
    read_accepted_atlas_factory_release,
    read_accepted_atlas_lease_v2,
)
from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
from bilqis_mlx.runtime.atlas_flywheel_runtime import AcceptedAtlasFlywheelSupervisor
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.runtime.bamf_operator.session import operate_bamf

from ..conformance_1300_support import (
    Conformance1300RuntimeSupport,
    SUCCESSOR,
    TARGET,
)
from ..conformance_1300_support.lifecycle import (
    bootstrap_staged_generation_zero,
    enroll_prepared_lease,
)
from ..conformance_1300_support.scenario import (
    advance_until_admitted,
    assert_structural_admission_transition,
    structural_certification_pass,
)


BILQIS_LEAF_GATE_POLICY = "DETACHED_ONLY"


class IntegratedConformance1300SuccessorTests(Conformance1300RuntimeSupport):
    def _bootstrap_foundation(self, fixture, progress):
        before, selected, foundation_grade, after = bootstrap_staged_generation_zero(
            self.run)
        self.assertEqual(selected.status, "TEACHER_SELECTED")
        self.assertEqual(after.generation, before.generation)
        self.assertEqual(
            after.retained_state.optimizer_step, before.retained_state.optimizer_step)
        self.assertEqual(foundation_grade.transition_kind, "BOOTSTRAP")
        self.assertEqual(
            foundation_grade.transition_reason, "DATA_DEFINED_INITIAL_GRADE_BOOTSTRAP")
        self.assertEqual(
            tuple(dict.fromkeys(foundation_grade.member_capability_ids)),
            ("A.IDENTITY",))
        with self.host_registry():
            enrolled = enroll_prepared_lease(
                self.run, fixture.lease,
                source_authority=AcceptedRuntimeHost(self.run).source_authority())
        self.assertEqual(enrolled.digest(), fixture.lease.digest())
        supervisor = AcceptedAtlasFlywheelSupervisor(
            self.run, self.parent_graph, reserve_gib=0.0)
        start = len(progress)
        with structural_certification_pass():
            advance_until_admitted(self, progress, TARGET)
        messages = progress[start:]
        self.assertIn("selected A.IDENTITY with ", "\n".join(messages))
        self.assertNotIn("accepted learner evidence refresh:", "\n".join(messages))
        boundary = next(i for i, message in enumerate(messages)
                        if message.startswith("grade boundary learner evidence refresh:"))
        transition = messages.index(
            "grade certification succeeded; activated exact receipt-bound generated successor")
        self.assertLess(boundary, transition)
        self.assertGreater(
            load_accepted_generation(self.run).retained_state.optimizer_step,
            before.retained_state.optimizer_step)
        return supervisor

    def _learn_target(self, supervisor, progress, observe):
        self._credit_all_predecessor_learning(supervisor)
        start = len(progress)
        before = load_accepted_generation(self.run)
        for _attempt in range(4):
            result = operate_bamf(
                self.run, minutes=1, max_visits=1, steps_per_visit=1,
                reserve_gib=0.0, source_prefetch_workers=0,
                parent_graph=self.parent_graph, progress=observe)
            if result.accepted and "selected " + TARGET + " with " in "\n".join(
                    progress[start:]):
                break
        else:
            self.fail(f"{TARGET} did not retain within 4 visits")
        learned = load_accepted_generation(self.run)
        self.assertGreater(
            learned.retained_state.optimizer_step, before.retained_state.optimizer_step)
        self._credit_all_predecessor_learning(supervisor)
        return learned

    def _admit_successor(self, target_learned, progress):
        start = len(progress)
        with structural_certification_pass():
            _, successor_release, _ = advance_until_admitted(
                self, progress, SUCCESSOR)
        transitioned = load_accepted_generation(self.run)
        messages = progress[start:]
        self.assertIn("selected " + TARGET + " with ", "\n".join(messages))
        self.assertNotIn("accepted learner evidence refresh:", "\n".join(messages))
        boundary = next(i for i, message in enumerate(messages)
                        if message.startswith("grade boundary learner evidence refresh:"))
        transition = messages.index(
            "grade certification succeeded; activated exact receipt-bound generated successor")
        self.assertLess(boundary, transition)
        assert_structural_admission_transition(self, target_learned, transitioned)
        return successor_release, transitioned

    def test_append_only_successor_is_admitted_under_same_v2_lease(self):
        fixture = self._production_parameter_fixture()
        progress = []
        def observe(message):
            progress.append(message)
            print("BAMF1300_SUCCESSOR " + message, flush=True)

        with self._operator_context(fixture):
            supervisor = self._bootstrap_foundation(fixture, progress)
            target_learned = self._learn_target(supervisor, progress, observe)
            successor_release, transitioned_event = self._admit_successor(
                target_learned, progress)
            with self.host_registry():
                accepted_lease = read_accepted_atlas_lease_v2(
                    self.run,
                    source_authority=AcceptedRuntimeHost(self.run).source_authority())
            self.assertIsNotNone(accepted_lease)
            self.assertEqual(accepted_lease.digest(), fixture.lease.digest())
            final = load_accepted_generation(self.run)
            final_release = read_accepted_atlas_factory_release(self.run)

        self.assertEqual(
            final.retained_state.optimizer_step,
            transitioned_event.retained_state.optimizer_step,
        )
        self.assertEqual(final_release.release_sha256, successor_release.release_sha256)
        self.assertIn(TARGET, final_release.execution_plan.capability_map)
        self.assertIn(SUCCESSOR, final_release.execution_plan.capability_map)
