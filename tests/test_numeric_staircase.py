"""Disposable curriculum changes retain the student's complete native state."""
from contextlib import redirect_stdout
from dataclasses import asdict, replace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx import trainer as storage
from bilqis_mlx.grade_transition import activate_numeric_grade
from bilqis_mlx.live_grade_c import draw, RELEASE as OLD_RELEASE
from bilqis_mlx.numeric_staircase import (
    RELEASE, build_course, enroll, advance_scope, scope_advance_due, row_in_scope)
from tests import test_grade_c_trainer as fixtures


class NumericStaircaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.GradeCTrainerTests.setUpClass()

    def setUp(self):
        self.fixture = fixtures.GradeCTrainerTests()
        self.mx, self.params, self.optimizer = self.fixture.toy()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        with redirect_stdout(io.StringIO()):
            pointer = storage._bundle_pointer(self.root, 'initial', self.params,
                self.optimizer, self.fixture.parent_graph, reserve_gib=0.)
            record = storage._persist(self.root, self.fixture.receipt(
                self.fixture.graduated(pointer), pointer, self.params))
            self.params, self.optimizer, self.graph, self.old = activate_numeric_grade(
                self.mx, self.root, record, self.fixture.previous, self.fixture.course,
                self.params, self.optimizer, self.fixture.parent_graph, reserve_gib=0.)

    def start(self):
        with redirect_stdout(io.StringIO()):
            return enroll(self.root, self.old, self.fixture.course,
                          self.fixture.previous, self.graph)

    def test_enrollment_reuses_latest_bundle_optimizer_teacher_and_catalog(self):
        course, record = self.start()
        self.assertEqual(course.version, RELEASE)
        self.assertEqual(record['numeric_maximum'], 3)
        self.assertEqual(record['model_bundle'], self.old['model_bundle'])
        self.assertEqual(record['school']['current_student'], self.old['school']['current_student'])
        self.assertEqual(record['teacher'], self.old['teacher'])
        self.assertEqual(record['school']['champions'], self.old['school']['champions'])
        self.assertEqual(record['school']['queue'], ['C.COUNT'])
        self.assertIsNone(record['last_exam'])
        self.assertNotIn('qualification_cohort', record)
        self.assertEqual(record['curriculum_parent'], self.old['school']['current_student'])
        self.assertEqual(self.optimizer.state['step'].item(), 1)
        with redirect_stdout(io.StringIO()):
            _, own, graph, again = storage._resume(self.root, self.fixture.manifest,
                course, self.fixture.policy_sha, admitted_courses={RELEASE: course})
        self.assertEqual(again, record)
        self.assertEqual(own.state['step'].item(), 1)
        self.assertEqual(graph, self.graph)

    def test_opt_in_preview_and_repeated_preview_do_not_enroll_or_train(self):
        from bilqis_mlx.cli import main
        original = (self.root/'state.json').read_bytes()
        for enrolled in (False, True):
            if enrolled:
                self.start()
                original = (self.root/'state.json').read_bytes()
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(['train', '--dry-run', '--resume',
                    '--numeric-staircase', '--run-dir', str(self.root),
                    '--legacy-code-root', str(fixtures.SOURCE)]), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report['numeric_staircase']['resume_maximum'], 3)
            self.assertEqual(report['numeric_staircase']['final_maximum'], 6)
            self.assertFalse(report['neural_training_started_by_this_command'])
            self.assertEqual((self.root/'state.json').read_bytes(), original)

    def test_missing_or_old_checkpoint_scores_cannot_advance_scope(self):
        course, record = self.start()
        self.assertFalse(scope_advance_due(record, course))
        record['school'].update(introduction_stage=5, stage='MAIN', queue=['C.MUL'])
        exam = {'student_sha256': record['school']['current_student']['sha256'],
                'optimizer_step': record['school']['current_student']['optimizer_step'],
                'scores': {c: {'correct': n, 'total': n} for c,n in
                    course.grades[-1].exam_item_counts if c != 'C.SUB'}}
        record['last_exam'] = exam
        self.assertFalse(scope_advance_due(record, course))
        exam['scores']['C.SUB'] = {'correct': 12, 'total': 12}
        self.assertTrue(scope_advance_due(record, course))
        exam['optimizer_step'] -= 1
        self.assertFalse(scope_advance_due(record, course))

    def test_scopes_advance_individually_then_allow_multiply_and_divide(self):
        course, record = self.start()
        for maximum in (4, 5, 6):
            school = storage._state_from_json(record['school'], course)
            school = replace(school, introduction_stage=5, stage='MAIN', queue=('C.MUL',))
            record = storage._persist(self.root, {**record, 'generation': record['generation']+1, 'school': asdict(school),
                'last_exam': {'student_sha256': school.current_student.sha256,
                    'optimizer_step': school.current_student.optimizer_step,
                    'scores': {cap: {'correct': n, 'total': n} for cap,n in
                        course.grades[-1].exam_item_counts if cap in
                        ('C.COUNT','C.NUMBER','C.SUCCESSOR','C.ADD','C.SUB')}}})
            self.assertTrue(scope_advance_due(record, course))
            with redirect_stdout(io.StringIO()):
                course, changed = advance_scope(self.root, record, course,
                    self.fixture.previous, self.graph)
            self.assertEqual(changed['numeric_maximum'], maximum)
            self.assertEqual(changed['school']['introduction_stage'], 4)
            self.assertEqual(changed['school']['queue'],
                ['C.COUNT','C.NUMBER','C.SUCCESSOR','C.ADD','C.SUB'])
            self.assertEqual(changed['model_bundle'], record['model_bundle'])
            self.assertEqual(changed['teacher'], record['teacher'])
            self.assertGreater(changed['school']['grade_exam_epoch'],
                               record['school']['grade_exam_epoch'])
            self.assertNotEqual(course.digest(), record['school']['course_digest'])
            record = changed
        school = storage._state_from_json(record['school'], course)
        record = {**record, 'school': asdict(replace(school, introduction_stage=5,
                    stage='MAIN', queue=('C.MUL',)))}
        self.assertFalse(scope_advance_due(record, course))

    def test_wide_old_mistakes_are_deferred_without_being_discarded(self):
        course, record = self.start()
        rows = draw(self.graph, seed=17, maximum=10, capability='C.COUNT')
        wide = next(r for r in rows if r['answer_kind']=='numeric_active' and r['gold']=='10')
        small = next(r for r in rows if r['answer_kind']=='numeric_active' and r['gold']=='2')
        self.assertFalse(row_in_scope(wide, 3))
        self.assertTrue(row_in_scope(small, 3))
        record = {**record, 'teacher_misses': [wide], 'teacher_miss_exposures': {wide['id']: 2}}
        with redirect_stdout(io.StringIO()):
            changed = storage._take_visit(self.mx, self.root, record,
                self.fixture.manifest, course, self.fixture.engine, self.params,
                self.optimizer, self.graph, steps_per_visit=1, batch_size=6,
                reserve_gib=0., source_root=fixtures.SOURCE)
        self.assertIn(wide, changed['teacher_misses'])
        self.assertEqual(changed['teacher_miss_exposures'][wide['id']], 2)

    def test_full_staircase_redraws_routine_test_at_every_evaluation(self):
        course, record = self.start()
        observed = []
        cohorts = []
        with redirect_stdout(io.StringIO()):
            while record['school']['active_grades'][record['school']['grade_index']] == 'C':
                maximum = record['numeric_maximum']
                while record['school']['queue']:
                    cap = record['school']['queue'][0]
                    self.assertTrue(cap not in ('C.MUL','C.DIV') or maximum == 6)
                    observed.append((maximum, cap))
                    record = storage._take_visit(self.mx, self.root, record,
                        self.fixture.manifest, course, self.fixture.engine, self.params,
                        self.optimizer, self.graph, steps_per_visit=1, batch_size=6,
                        reserve_gib=0., source_root=fixtures.SOURCE)
                # Source-gold predictions test transitions, not learned mastery.
                with patch.object(storage, '_predictions', side_effect=lambda _m,_p,rows,*a:
                                  {r['id']:r['gold'] for r in rows}):
                    record = storage._take_exam(self.mx,self.root,record,
                        self.fixture.manifest,course,fixtures.SOURCE,fixtures.PARENT,
                        self.params,self.optimizer,self.graph,reserve_gib=0.)
                cohort = record['last_exam']['routine_cohort_sha256']
                self.assertNotIn(cohort, cohorts)
                cohorts.append(cohort)
                if scope_advance_due(record, course):
                    course, record = advance_scope(self.root,record,course,
                        self.fixture.previous,self.graph)
            self.assertEqual(record['school']['revalidation_target_grade'], 'C')
            self.assertEqual(len(set(cohorts)), len(cohorts))
            self.assertEqual(observed, [(n,c) for n in (3,4,5,6) for c in
                ('C.COUNT','C.NUMBER','C.SUCCESSOR','C.ADD','C.SUB')] +
                [(6,'C.MUL'),(6,'C.DIV')])
            self.assertTrue((self.root/record['curriculum_parent']['filename']).is_dir())

    def test_interrupted_enrollment_recovers_without_changing_student(self):
        original = storage._durable_json
        def interrupt(path, value, **kwargs):
            if path == self.root/'state.json' and value.get('curriculum_mode') == RELEASE:
                raise RuntimeError('enrollment pointer interrupted')
            return original(path,value,**kwargs)
        with patch.object(storage,'_durable_json',side_effect=interrupt), redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError,'pointer interrupted'):
                self.start()
        course = build_course(self.fixture.previous,self.graph)
        with storage.operator_lock(self.root), redirect_stdout(io.StringIO()):
            restored = storage._resume(self.root,self.fixture.manifest,
                self.fixture.course,self.fixture.policy_sha,
                admitted_courses={OLD_RELEASE:self.fixture.course,RELEASE:course})[3]
            again = storage._resume(self.root,self.fixture.manifest,course,
                self.fixture.policy_sha,admitted_courses={RELEASE:course})[3]
        self.assertEqual(restored,again)
        self.assertEqual(restored['model_bundle'], self.old['model_bundle'])
        self.assertEqual(restored['teacher'], self.old['teacher'])
