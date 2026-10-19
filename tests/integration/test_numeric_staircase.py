"""Disposable curriculum changes retain the student's complete native state."""
from contextlib import redirect_stdout
from dataclasses import asdict, replace
import io
import json
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx import trainer as storage
from bilqis_mlx.grade_transition import activate_numeric_grade
from bilqis_mlx.live_grade_c import draw, prepare_course, RELEASE as OLD_RELEASE
from bilqis_mlx.numeric_staircase import (
    RELEASE, build_course, enroll, advance_scope, scope_advance_due, row_in_scope)
from tests.system import test_grade_c_trainer as fixtures


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

    def _id_parent_fixture(self, root):
        from bilqis_mlx.boolean_composite import build_course as build_composite
        from bilqis_mlx.boolean_identification import (
            RELEASE as ID_RELEASE, answer_heads as id_answer_heads,
            build_course as build_id,
        )
        from bilqis_mlx.curriculum.scheduler import (
            Assessment, Score, assess, next_capability, start_new, visit,
        )

        identified = build_id(
            build_composite(self.fixture.previous, fixtures.SOURCE), fixtures.SOURCE)
        successor, _ = prepare_course(identified, maximum=10)
        mx, params, opt = self.fixture.toy()
        pointer = storage._bundle_pointer(
            root, 'id-parent', params, opt, self.fixture.parent_graph, reserve_gib=0.)
        school = start_new(identified, pointer)
        for grade in ('A', 'B', 'A', 'B'):
            while next_capability(school):
                school = visit(identified, school, next_capability(school), pointer)
            scores = {
                cap.id: Score(12, 12)
                for admitted in identified.grades
                if admitted.id in school.champions or admitted.id == grade
                for cap in admitted.capabilities
            }
            rubric = identified.grades[
                1 if any(cap.startswith('B.') for cap in scores) else 0
            ].assessment_sha256
            school = assess(identified, school, Assessment(
                pointer.sha256, pointer.optimizer_step, identified.digest(),
                rubric, scores, 'id-parent-pass'))
        receipt = self.fixture.receipt(school, pointer, params)
        receipt['curriculum_mode'] = ID_RELEASE
        receipt['config']['answer_heads'] = id_answer_heads(self.fixture.parent_graph)
        receipt['live_rubric_sha256'] = identified.grades[-1].assessment_sha256
        receipt['last_exam'] = {
            'student_sha256': pointer.sha256,
            'optimizer_step': pointer.optimizer_step,
            'cohort_sha256': 'd' * 64,
            'exam_rubric_sha256': identified.grades[-1].assessment_sha256,
            'scores': {
                cap.id: {'correct': count, 'total': count}
                for admitted in identified.grades
                for cap in admitted.capabilities
                for count in (dict(admitted.exam_item_counts)[cap.id],)
            },
        }
        return identified, successor, id_answer_heads, mx, params, opt, receipt

    def _numeric_staircase_preview(self, root):
        from bilqis_mlx.cli import main
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main([
                'train', '--dry-run', '--resume', '--numeric-staircase',
                '--run-dir', str(root), '--legacy-code-root', str(fixtures.SOURCE),
            ]), 0)
        return json.loads(output.getvalue())['numeric_staircase']

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

    def test_question_inventory_change_globally_resets_live_champions_and_soups(self):
        seeded = deepcopy(self.old)
        epoch = seeded["mentor_epoch"]
        pointer = seeded["school"]["current_student"]
        epoch["active_roles"] = {
            "C.COUNT": {
                "capability": "C.COUNT", "origin_grade": "C",
                "checkpoint": pointer, "correct": 12, "total": 12,
            }}
        epoch["active_grade_soups"] = {"C": {"grade": "C", "vote_count": 1}}
        match_key = "C.COUNT|" + "a" * 64 + "|" + "b" * 64
        epoch["settled_matchups"] = {
            match_key: {"decision": "TITLE_DEFENDED", "winner_sha256": "a" * 64}}
        self.old = seeded
        prior_identity = epoch["championship_school_identity"]["sha256"]
        prior_step = self.optimizer.state["step"].item()

        course, record = self.start()
        successor = record["mentor_epoch"]
        self.assertNotEqual(record["championship_school_identity"]["sha256"], prior_identity)
        self.assertEqual(successor["active_roles"], {})
        self.assertEqual(successor["active_grade_soups"], {})
        self.assertEqual(successor["settled_matchups"], epoch["settled_matchups"])
        self.assertEqual(successor["administrative_empty_reset"]["old_active_role_count"], 1)
        self.assertEqual(successor["administrative_empty_reset"]["old_active_soup_grades"], ["C"])
        self.assertEqual(successor["administrative_empty_reset"]["training_or_optimizer_updates"], 0)
        self.assertEqual(record["school"]["current_student"], seeded["school"]["current_student"])
        self.assertEqual(self.optimizer.state["step"].item(), prior_step)

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

    def test_id_parent_preview_and_answer_head_custody_survive_c_and_staircase(self):
        with tempfile.TemporaryDirectory() as temp, redirect_stdout(io.StringIO()):
            root = Path(temp)
            identified, successor, id_answer_heads, mx, params, opt, receipt = (
                self._id_parent_fixture(root))
            receipt = storage._persist(root, receipt)
            grown, own, graph, c_record = activate_numeric_grade(
                mx, root, receipt, identified, successor,
                params, opt, self.fixture.parent_graph, reserve_gib=0.)

            operator_head = id_answer_heads(graph)['boolean_operator']
            self.assertEqual(c_record['config']['answer_heads']['boolean_operator'],
                             operator_head)
            self.assertEqual(int(own.state['step'].item()), int(opt.state['step'].item()))
            preview = self._numeric_staircase_preview(root)
            self.assertEqual(preview['parent_course_sha256'], identified.digest())
            self.assertEqual(preview['grade_b_capabilities'], [
                'B.NOT', 'B.AND', 'B.OR', 'B.XOR', 'B.IMPLIES', 'B.IFF',
                'B.COMPOSITE', 'B.IDBOOLOPS',
            ])

            staircase, staircase_record = enroll(
                root, c_record, successor, identified, graph)
            self.assertEqual(
                staircase_record['config']['answer_heads']['boolean_operator'],
                operator_head)
            self.assertEqual(
                [cap.id for cap in staircase.grades[1].capabilities],
                preview['grade_b_capabilities'])

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
