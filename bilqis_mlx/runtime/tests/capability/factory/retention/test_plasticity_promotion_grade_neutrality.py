"""Real persisted grade-label neutrality for B09.3 promotion authority."""
from dataclasses import asdict, replace
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from bilqis_mlx import state_dag
from bilqis_mlx.curriculum.scheduler import Assessment, Score, assess, start_new, visit
from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.factory.executable_release import compile_executable_factory_release
from bilqis_mlx.factory.execution import CurriculumProfile, GradeProfile
from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
from bilqis_mlx.factory.tests.test_executable_release import _boolean_answers
from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_boolean_course
from bilqis_mlx.generated_assessment import PROMOTION_ATTEMPT_LIFECYCLE
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.atlas_candidate import (
    CandidateCustodyIdentity, CandidateState, issue_promotion_transition_state,
)
from bilqis_mlx.learning.atlas_plasticity import PlasticityPolicy
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime.admission import _persist_executable_factory_release
from bilqis_mlx.runtime.plasticity_promotion import issue_accepted_promotion_transition
from bilqis_mlx.runtime.state import _fingerprint
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    accepted_state, parent_state, retention_decision,
)


def _graph():
    return {
        "tokens": [
            "fixture.padding", "cogal.value.false", "cogal.value.true",
            "cogal.operator.NOT", "cogal.operator.AND", "cogal.operator.OR",
            "cogal.operator.XOR", "cogal.operator.IMPLIES", "cogal.operator.IFF",
        ],
    }


class PlasticityPromotionGradeNeutralityTests(TestCase):
    def setUp(self):
        fixture_parent = parent_state()
        self.parent_state = CandidateState(
            fixture_parent.optimizer,
            PlasticityPolicy(row_ages=fixture_parent.policy.row_ages),
            fixture_parent.allocations, fixture_parent.optimizer_step,
            fixture_parent.custody, fixture_parent.step_proofs)
        retained = accepted_state(self.parent_state)
        self.retained = CandidateState(
            retained.optimizer, retained.policy, retained.allocations,
            retained.optimizer_step,
            CandidateCustodyIdentity(
                "fixture-run", 4, "3" * 64,
                retained.custody.topology_digest, retained.custody.extents_digest),
            retained.step_proofs)
        self.identity = candidate_identity_digest(self.retained)
        self.decision = retention_decision(
            parent=self.parent_state, retained=self.retained)

        course, self.registry = _synthetic_boolean_course()
        self.course = course
        curriculum, bindings = from_legacy_course(course)
        self.initial_release = compile_executable_factory_release(
            curriculum, bindings,
            CurriculumProfile("foundation-only", (
                GradeProfile("B", enabled_capabilities=()),)),
            self.registry, _boolean_answers(), source_root=None, graph=_graph(),
            verification_seed=91)
        self.foundation = tuple(
            item.capability_id
            for item in self.initial_release.execution_plan.capabilities)

    def _runtime_release(self, next_grade_id: str):
        grade = replace(self.course.grades[1], id=next_grade_id)
        course = replace(self.course, grades=(self.course.grades[0], grade))
        curriculum, bindings = from_legacy_course(course)
        return compile_executable_factory_release(
            curriculum, bindings, CurriculumProfile.full(),
            self.registry, _boolean_answers(), source_root=None, graph=_graph(),
            verification_seed=97)

    def _issue(self, runtime_release):
        with tempfile.TemporaryDirectory(prefix="b09-948-grade-neutral-") as temp:
            root = Path(temp)
            _persist_executable_factory_release(root, self.initial_release)
            _persist_executable_factory_release(root, runtime_release)
            program = schedule_program_from_executable_release(runtime_release)
            student = Checkpoint(
                self.identity, "bundles/fixture", self.retained.optimizer_step, True)
            state = start_new(program, student)
            for capability in tuple(state.queue):
                state = visit(program, state, capability, student)
            grade = program.grades[0]
            scores = {
                capability.id: Score(
                    capability.exam_item_count, capability.exam_item_count)
                for capability in grade.capabilities
            }
            snapshot = Assessment(
                student.sha256, student.optimizer_step, program.digest(),
                grade.assessment_sha256, scores,
                evaluation_id="b09-948-grade-neutral")
            state = assess(program, state, snapshot)
            states = [state]
            while state.stage == "PROMOTION_SWEEP":
                state = visit(program, state, state.queue[0], student)
                states.append(state)
                state = assess(program, state, snapshot)
                states.append(state)

            for generation, saved in enumerate(states):
                receipt = {
                    "run_id": "fixture-run",
                    "generation": generation,
                    "factory_release_sha256": runtime_release.release_sha256,
                    "school": asdict(saved),
                }
                if generation == len(states) - 1:
                    receipt["last_exam"] = {
                        "student_sha256": student.sha256,
                        "optimizer_step": student.optimizer_step,
                        "grade_test_lifecycle": PROMOTION_ATTEMPT_LIFECYCLE,
                        "assessment_scope_sha256": _fingerprint(self.foundation),
                        "scores": {
                            capability: {
                                "correct": scores[capability].correct,
                                "total": scores[capability].total,
                            }
                            for capability in self.foundation
                        },
                    }
                state_dag.persist(root, receipt)

            parent = SimpleNamespace(
                run_id="fixture-run", generation=4,
                retained_state=self.parent_state,
                run_identity=SimpleNamespace(
                    factory_release_sha256=self.initial_release.release_sha256))
            cache = SimpleNamespace(
                run_id="fixture-run", generation=4,
                accepted_manifest_sha256="3" * 64)
            with (
                patch(
                    "bilqis_mlx.runtime.bamf_bundle.accepted_runtime."
                    "load_accepted_generation", return_value=parent),
                patch(
                    "bilqis_mlx.runtime.bamf_bundle.accepted_runtime."
                    "bind_accepted_execution_cache", return_value=cache),
            ):
                receipt = issue_accepted_promotion_transition(
                    root, self.retained, self.decision)
            transitioned = issue_promotion_transition_state(self.retained, receipt)
            return receipt, transitioned.policy.mode_transition, asdict(states[-1])

    def test_real_future_grade_relabel_does_not_change_transition_authority(self):
        baseline_receipt, baseline_transition, baseline_final = self._issue(
            self._runtime_release("B"))
        relabeled_receipt, relabeled_transition, relabeled_final = self._issue(
            self._runtime_release("Z"))

        self.assertNotEqual(
            baseline_final["course_digest"], relabeled_final["course_digest"])
        self.assertNotEqual(
            baseline_final["active_grades"], relabeled_final["active_grades"])
        self.assertEqual(
            baseline_receipt.promotion_evidence_sha256,
            relabeled_receipt.promotion_evidence_sha256)
        self.assertEqual(baseline_transition, relabeled_transition)
