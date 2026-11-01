"""Disposable curriculum changes retain the student's complete native state."""
from contextlib import redirect_stdout
import io
import json
from unittest.mock import patch

from bilqis_mlx import trainer as storage
from bilqis_mlx.state_dag import read_generation, _durable
from bilqis_mlx.compatibility.executable_projection import legacy_course_for_profile
from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
from bilqis_mlx.profiles.catalog import numeric_entry_transition, numeric_scope_profile
from bilqis_mlx.profiles.school import full_boolean_upgrade_profile
from tests.system import test_grade_c_trainer as fixtures


from tests.integration.numeric.profiles import NumericProfileFixture

class NumericStaircaseTests(NumericProfileFixture):
    def test_c_active_reduced_b_expands_to_full_b_without_neural_updates(self):
        _, record = self.start()
        release = storage._read_executable_factory_release_artifact(
            self.root, record)
        before_student = record['school']['current_student']
        before_step = int(self.optimizer.state['step'].item())
        target = full_boolean_upgrade_profile(release.profile)

        with redirect_stdout(io.StringIO()):
            changed, _, successor, program = storage._adopt_executable_profile(
                self.root, record, self.fixture.grade_a, fixtures.SOURCE,
                self.graph, target, invalidate_assessment_evidence=True)

        b_caps = tuple(cap.id for cap in program.grades[1].capabilities)
        self.assertEqual(b_caps, (
            'B.NOT', 'B.AND', 'B.OR', 'B.XOR', 'B.IMPLIES', 'B.IFF',
            'B.COMPOSITE', 'B.IDBOOLOPS'))
        self.assertTrue(
            {'B.NOT', 'B.OR', 'B.XOR', 'B.IMPLIES'} <=
            set(changed['school']['carried_mastery_debt']))
        self.assertEqual(changed['school']['current_student'], before_student)
        self.assertEqual(int(self.optimizer.state['step'].item()), before_step)
        self.assertEqual(changed['school']['active_grades'], ['A', 'B', 'C'])
        self.assertEqual(changed['school']['active_grades'][
            changed['school']['grade_index']], 'C')
        self.assertEqual(changed['school']['stage'], 'MAIN')
        self.assertIsNone(changed['last_exam'])
        self.assertEqual(successor.profile.profile_id,
                         'school/boolean/full/numeric-0-4')

    def test_staircase_entry_preserves_optimizer_teacher_and_admits_bounded_catalog(self):
        before = self.before_numeric
        prior_step = self.optimizer.state['step'].item()
        course, record = self.start()
        release = storage._read_executable_factory_release_artifact(
            self.root, record)
        program = schedule_program_from_executable_release(release)
        self.assertEqual(record['numeric_maximum'], 4)
        self.assertEqual(record['numeric_scope_final_maximum'], 10)
        self.assertEqual(release.profile.profile_id,
                         'school/boolean-kernel/and-iff/numeric-0-4')
        self.assertNotEqual(record['model_bundle'], before['model_bundle'])
        self.assertEqual(
            record['school']['current_student']['optimizer_step'],
            before['school']['current_student']['optimizer_step'])
        self.assertEqual(record['teacher'], before['teacher'])
        self.assertEqual(record['school']['champions'], before['school']['champions'])
        self.assertEqual(record['school']['queue'], ['C.COUNT'])
        self.assertEqual(
            [cap.id for cap in program.grades[-1].capabilities],
            ['C.COUNT', 'C.NUMBER', 'C.SUCCESSOR', 'C.ADD', 'C.SUB',
             'C.MUL', 'C.DIV'])
        self.assertEqual(record['last_exam']['exam_plane'],
                         'FIXED_FRONTIER_REBASELINE')
        self.assertNotIn('qualification_cohort_v2', record)
        self.assertEqual(self.optimizer.state['step'].item(), prior_step)
        with redirect_stdout(io.StringIO()):
            _, own, graph, again = storage._resume(
                self.root, self.fixture.manifest, course,
                self.fixture.policy_sha,
                grade_a_course=self.fixture.grade_a,
                source_root=fixtures.SOURCE)
        self.assertEqual(again, record)
        self.assertEqual(own.state['step'].item(), prior_step)
        self.assertEqual(graph, self.graph)

    def test_existing_wide_c_rebinds_to_small_staircase_without_neural_updates(self):
        prior_step = int(self.optimizer.state['step'].item())
        transition = numeric_entry_transition(
            self.boolean_release, self.graph, full_boolean=False, maximum=10)
        with redirect_stdout(io.StringIO()), patch(
                'bilqis_mlx.learning.student_ops._predictions',
                side_effect=lambda _m, _p, rows, *args:
                {row['id']: row['gold'] for row in rows}):
            self.params, self.optimizer, graph, wide, _ = (
                storage._adopt_catalog_profile(
                    self.mx, self.root, self.before_numeric,
                    self.fixture.grade_a, fixtures.SOURCE, self.graph,
                    self.params, self.optimizer, transition, reserve_gib=0.))
        self.assertEqual(wide['numeric_maximum'], 10)
        wide_student = wide['school']['current_student']
        wide = {**wide, 'school': {
            **wide['school'],
            'carried_mastery_debt': ['C.COUNT', 'C.MUL', 'C.DIV'],
            'debt_cadence_policy': {
                'bounded_debt_grade_id': 'B',
                'progression_priority_grade_id': 'C',
                'non_debt_turns_per_run': 4,
            },
        }}
        release = storage._read_executable_factory_release_artifact(
            self.root, wide)
        with redirect_stdout(io.StringIO()):
            changed, _, narrowed, program = storage._adopt_executable_profile(
                self.root,
                {**wide, 'numeric_scope_final_maximum': 10},
                self.fixture.grade_a, fixtures.SOURCE, graph,
                numeric_scope_profile(release, 4))
        self.assertEqual(changed['numeric_maximum'], 4)
        self.assertEqual(changed['numeric_scope_final_maximum'], 10)
        self.assertEqual(
            changed['school']['carried_mastery_debt'],
            ['C.COUNT', 'C.MUL', 'C.DIV'])
        self.assertEqual(changed['school']['current_student'], wide_student)
        self.assertEqual(
            changed['school']['debt_cadence_policy'],
            wide['school']['debt_cadence_policy'])
        self.assertEqual(int(self.optimizer.state['step'].item()), prior_step)
        self.assertEqual(
            [cap.id for cap in program.grades[-1].capabilities],
            ['C.COUNT', 'C.NUMBER', 'C.SUCCESSOR', 'C.ADD', 'C.SUB',
             'C.MUL', 'C.DIV'])
        self.assertEqual(
            narrowed.profile.profile_id.rsplit('-', 1)[-1], '4')
        self.assertTrue(storage._mentor_epoch_references(changed))
        school = storage._state_from_json(changed['school'], program)
        cleared, _, _ = storage._profile_transition(
            program, program, school, debt_cadence_policy=None)
        self.assertIsNone(cleared.debt_cadence_policy)
        malformed = {
            **changed,
            'championship_epoch_history': [
                *changed.get('championship_epoch_history', ()),
                {'kind': 'profile-revision-school-identity-reset', 'event': True},
                {'kind': 'unrelated-unknown-history-value'},
            ],
        }
        cleaned, removed = (
            storage._without_profile_revision_epoch_history_artifact(malformed))
        self.assertEqual(removed, 1)
        self.assertEqual(
            cleaned['championship_epoch_history'][-1],
            {'kind': 'unrelated-unknown-history-value'})
        with self.assertRaisesRegex(ValueError, 'MENTOR_EPOCH_UNKNOWN_SCHEMA'):
            storage._mentor_epoch_references(cleaned)

    def test_interrupted_enrollment_recovers_without_changing_student(self):
        original = _durable
        def interrupt(path, value, **kwargs):
            if (path == self.root/'state.json' and
                    json.loads(value).get('generation') == self.before_numeric['generation'] + 1):
                raise RuntimeError('enrollment pointer interrupted')
            return original(path,value,**kwargs)
        with patch('bilqis_mlx.state_dag._durable',side_effect=interrupt), redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError,'pointer interrupted'):
                self.start()
        transition = numeric_entry_transition(
            self.boolean_release, self.graph,
            full_boolean=False)
        course = legacy_course_for_profile(
            self.fixture.grade_a, fixtures.SOURCE, transition.profile)
        pending = read_generation(self.root, self.before_numeric['generation'] + 1)
        self.assertEqual(pending['numeric_maximum'], 4)
        self.assertEqual(
            pending['school']['current_student']['optimizer_step'],
            self.before_numeric['school']['current_student']['optimizer_step'])
        with storage.operator_lock(self.root), redirect_stdout(io.StringIO()):
            restored = storage._resume(self.root,self.fixture.manifest,
                course,self.fixture.policy_sha,
                grade_a_course=self.fixture.grade_a,
                source_root=fixtures.SOURCE)[3]
            again = storage._resume(self.root,self.fixture.manifest,course,
                self.fixture.policy_sha,
                grade_a_course=self.fixture.grade_a,
                source_root=fixtures.SOURCE)[3]
        self.assertEqual(restored,again)
        self.assertEqual(restored['model_bundle'], pending['model_bundle'])
        self.assertEqual(restored['teacher'], self.before_numeric['teacher'])
        self.assertEqual(
            restored['school']['current_student']['optimizer_step'],
            self.before_numeric['school']['current_student']['optimizer_step'])
