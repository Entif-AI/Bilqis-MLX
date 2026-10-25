"""A source/teaching revision need not change the scheduler projection."""
from dataclasses import replace
from types import SimpleNamespace
import unittest

from bilqis_mlx.boolean_identification import (
    CAPABILITY as IDBOOLOPS_CAPABILITY,
    GENERATOR as IDBOOLOPS_GENERATOR,
    ORACLE as IDBOOLOPS_ORACLE,
    REPRESENTATION_VARIATION,
)
from bilqis_mlx.boolean_composite import (
    CAPABILITY as COMPOSITE_CAPABILITY,
    REPRESENTATION_VARIATION as COMPOSITE_REPRESENTATION_VARIATION,
)
from bilqis_mlx.curriculum.scheduler import start_new
from bilqis_mlx.factory.schedule import ScheduleCapability, ScheduleGrade, ScheduleProgram
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.live_grade_b import OUTER_LANDMARK_VARIATION
from bilqis_mlx.runtime.release_adoption import (
    _atomic_boolean_landmark_revision_required,
    _composite_landmark_revision_required,
    _idboolops_landmark_revision_required,
    _source_presentation_revision_required,
    _profile_transition,
)
from bilqis_mlx.source_adapters.school import live_source_registry


class TeachingOnlyTransitionTests(unittest.TestCase):
    def setUp(self):
        self.program = ScheduleProgram('a' * 64, (
            ScheduleGrade('D', (ScheduleCapability('D.EVENT_OCCURRENCE', 12),),
                          (('D.EVENT_OCCURRENCE',),), 'b' * 64),), False)
        self.school = start_new(self.program, Checkpoint('c' * 64, 'bundles/fixture', 10, True))

    def test_identical_scheduler_projection_preserves_current_work(self):
        state, revised_grade, appended = _profile_transition(
            self.program, self.program, self.school)
        self.assertIs(state, self.school)
        self.assertIsNone(revised_grade)
        self.assertFalse(appended)

    def test_changed_program_identity_still_requires_a_supported_revision(self):
        changed = replace(self.program, program_digest='d' * 64)
        with self.assertRaisesRegex(ValueError, 'FACTORY_SCHEDULE_REVISION_INVALID'):
            _profile_transition(self.program, changed, self.school)

    def test_source_revision_history_keeps_valid_epoch_custody_records(self):
        from dataclasses import asdict
        from types import SimpleNamespace
        from bilqis_mlx.learning.mentor_epoch import begin_initial_epoch, reference_checkpoints
        from bilqis_mlx.runtime.release_adoption import _profile_championship_state

        epoch = begin_initial_epoch(student=asdict(self.school.current_student),
            introduced_grade='D', source_graph_sha256='e' * 64, frontier={}, soups={})
        receipt = dict(generation=1, semantic_graph_sha256='e' * 64,
            parameter_shapes={'weight': [3, 4]}, mentor_epoch=epoch)
        successor = SimpleNamespace(release_sha256='f' * 64,
            execution_plan=SimpleNamespace(curriculum_sha256='a' * 64))
        identity, updated, history = _profile_championship_state(
            receipt, None, successor, self.school, self.school, appended=False)
        self.assertEqual(history, [epoch])
        self.assertEqual(updated['active_roles'], {})
        self.assertEqual(updated['active_grade_soups'], {})
        for item in (*history, updated):
            self.assertTrue(reference_checkpoints(item))
        unchanged = {**receipt, 'mentor_epoch': updated, 'championship_epoch_history': history}
        _, _, repeated_history = _profile_championship_state(
            unchanged, None, successor, self.school, self.school, appended=False)
        self.assertEqual(repeated_history, history)

    def test_named_idboolops_landmarks_require_one_explicit_source_revision(self):
        registry = live_source_registry()
        current = registry.require(
            IDBOOLOPS_GENERATOR, IDBOOLOPS_ORACLE).descriptor
        historical = replace(
            current,
            variation_axes=tuple(
                axis for axis in current.variation_axes
                if axis != REPRESENTATION_VARIATION),
        )
        binding = SimpleNamespace(
            generator_id=IDBOOLOPS_GENERATOR,
            oracle_id=IDBOOLOPS_ORACLE,
        )

        def release(provider):
            return SimpleNamespace(
                execution_plan=SimpleNamespace(capability_map={
                    IDBOOLOPS_CAPABILITY: SimpleNamespace(
                        provider_id=provider.adapter_id),
                }),
                source_bindings=SimpleNamespace(by_capability={
                    IDBOOLOPS_CAPABILITY: binding,
                }),
                source_adapters=(provider,),
            )

        self.assertTrue(_idboolops_landmark_revision_required(
            release(historical), registry))
        self.assertFalse(_idboolops_landmark_revision_required(
            release(current), registry))

    def test_named_and_implies_landmarks_require_one_explicit_source_revision(self):
        registry = live_source_registry()
        generator = IDBOOLOPS_GENERATOR
        current = registry.require(
            generator, "bilqis.mlx.grade-b-connective-record-oracle/v1"
        ).descriptor
        historical = replace(
            current,
            variation_axes=tuple(
                axis for axis in current.variation_axes
                if axis != OUTER_LANDMARK_VARIATION),
        )
        binding = SimpleNamespace(
            generator_id=generator,
            oracle_id="bilqis.mlx.grade-b-connective-record-oracle/v1",
        )

        def release(provider):
            capabilities = {
                capability: SimpleNamespace(provider_id=provider.adapter_id)
                for capability in ("B.AND", "B.IMPLIES")
            }
            bindings = {
                capability: binding
                for capability in capabilities
            }
            return SimpleNamespace(
                execution_plan=SimpleNamespace(capability_map=capabilities),
                source_bindings=SimpleNamespace(by_capability=bindings),
                source_adapters=(provider,),
            )

        self.assertTrue(_atomic_boolean_landmark_revision_required(
            release(historical), registry))
        self.assertFalse(_atomic_boolean_landmark_revision_required(
            release(current), registry))
        self.assertTrue(_source_presentation_revision_required(
            release(historical), registry))

    def test_composite_landmarks_require_one_explicit_source_revision(self):
        registry = live_source_registry()
        generator = IDBOOLOPS_GENERATOR
        current = registry.require(
            generator, "bilqis.mlx.grade-b-composite-record-oracle/v1"
        ).descriptor
        historical = replace(
            current,
            variation_axes=tuple(
                axis for axis in current.variation_axes
                if axis != COMPOSITE_REPRESENTATION_VARIATION),
        )
        binding = SimpleNamespace(
            generator_id=generator,
            oracle_id="bilqis.mlx.grade-b-composite-record-oracle/v1",
        )

        def release(provider):
            return SimpleNamespace(
                execution_plan=SimpleNamespace(capability_map={
                    COMPOSITE_CAPABILITY: SimpleNamespace(
                        provider_id=provider.adapter_id),
                }),
                source_bindings=SimpleNamespace(by_capability={
                    COMPOSITE_CAPABILITY: binding,
                }),
                source_adapters=(provider,),
            )

        self.assertTrue(_composite_landmark_revision_required(
            release(historical), registry))
        self.assertFalse(_composite_landmark_revision_required(
            release(current), registry))
        self.assertTrue(_source_presentation_revision_required(
            release(historical), registry))


class ExplicitProfileDebtTests(unittest.TestCase):
    def setUp(self):
        self.previous = ScheduleProgram('a' * 64, (
            ScheduleGrade('A', (ScheduleCapability('A.IDENTITY', 12),), (), 'b' * 64),), False)
        self.successor = ScheduleProgram('c' * 64, (*self.previous.grades,
            ScheduleGrade('B', (ScheduleCapability('B.NOT', 12),), (), 'd' * 64)), False)
        self.school = start_new(self.previous, Checkpoint('e' * 64, 'bundles/student', 10, True))

    def test_explicit_debt_admits_a_same_abi_next_grade_without_fabricating_mastery(self):
        state, revised, appended = _profile_transition(
            self.previous, self.successor, self.school, mastery_debt=('A.IDENTITY',))
        self.assertTrue(appended)
        self.assertIsNone(revised)
        self.assertEqual(state.grade, 'B')
        self.assertEqual(state.carried_mastery_debt, ('A.IDENTITY',))
        self.assertEqual(state.current_student, self.school.current_student)
        self.assertEqual(state.champions, {})

    def test_ordinary_append_still_requires_the_graduated_boundary(self):
        with self.assertRaises(ValueError):
            _profile_transition(self.previous, self.successor, self.school)


class EarlierGradeExpansionTests(unittest.TestCase):
    def setUp(self):
        student = Checkpoint('f' * 64, 'bundles/student', 42, True)
        self.previous = ScheduleProgram('1' * 64, (
            ScheduleGrade('A', (ScheduleCapability('A.IDENTITY', 12),), (), '2' * 64),
            ScheduleGrade('B', (ScheduleCapability('B.AND', 12), ScheduleCapability('B.IFF', 12)), (), '3' * 64),
            ScheduleGrade('C', (ScheduleCapability('C.COUNT', 12), ScheduleCapability('C.NUMBER', 12)), (), '4' * 64),
        ), False)
        self.successor = ScheduleProgram('5' * 64, (
            self.previous.grades[0],
            ScheduleGrade('B', tuple(ScheduleCapability(cap, 12) for cap in (
                'B.NOT', 'B.AND', 'B.OR', 'B.XOR', 'B.IMPLIES', 'B.IFF', 'B.COMPOSITE', 'B.IDBOOLOPS')), (), '6' * 64),
            self.previous.grades[2],
        ), False)
        base = start_new(self.previous, student)
        self.school = replace(base, active_grades=('A', 'B', 'C'), grade_index=2,
            stage='RECOVERY_1', queue=('C.NUMBER', 'B.AND'), visits=123,
            carried_mastery_debt=('B.AND', 'C.COUNT'),
            frontier_priority_visits=17, nongating_b_visits=4)

    def test_additive_prior_grade_revision_preserves_frontier_and_adds_debt(self):
        state, revised, appended = _profile_transition(self.previous, self.successor, self.school)
        self.assertFalse(appended)
        self.assertEqual(revised, 'B')
        self.assertEqual((state.grade, state.stage, state.queue), ('C', 'RECOVERY_1', ('C.NUMBER', 'B.AND')))
        self.assertEqual(state.current_student, self.school.current_student)
        self.assertEqual((state.visits, state.frontier_priority_visits, state.nongating_b_visits), (123, 17, 4))
        self.assertEqual(state.carried_mastery_debt, ('B.AND', 'C.COUNT', 'B.NOT', 'B.OR', 'B.XOR', 'B.IMPLIES', 'B.COMPOSITE', 'B.IDBOOLOPS'))
        self.assertEqual(state.course_digest, self.successor.digest())
