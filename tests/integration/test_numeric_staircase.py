"""Disposable curriculum changes retain the student's complete native state."""
from contextlib import redirect_stdout
from dataclasses import asdict
import io
import json
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx import trainer as storage
from bilqis_mlx.compatibility.executable_projection import (
    compile_projected_executable_release, legacy_course_for_profile)
from bilqis_mlx.curriculum.scheduler import (
    Assessment, Score, assess, assessment_capabilities, next_capability,
    start_new, visit)
from bilqis_mlx.factory.executable_release import (
    answer_heads_from_executable_release, compile_successor_profile_release)
from bilqis_mlx.factory.live_answers import live_answer_registry
from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
from bilqis_mlx.generated_assessment import score
from bilqis_mlx.learning.championship_identity import build_school_identity
from bilqis_mlx.live_grade_c import draw
from bilqis_mlx.profiles.catalog import (
    next_numeric_scope_profile, numeric_entry_transition, numeric_row_in_scope,
    numeric_scope_profile)
from bilqis_mlx.profiles.school import (
    boolean_entry_profile, with_disabled_future_grades)
from bilqis_mlx.source_adapters.school import live_source_registry
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
        self.graph = self.fixture.parent_graph
        with redirect_stdout(io.StringIO()):
            pointer = storage._bundle_pointer(self.root, 'initial', self.params,
                self.optimizer, self.graph, reserve_gib=0.)
            base_release, _, _ = compile_projected_executable_release(
                self.fixture.previous, self.fixture.grade_a,
                fixtures.SOURCE, self.graph)
            boolean_profile = with_disabled_future_grades(
                boolean_entry_profile(full=False),
                tuple(grade.grade_id for grade in base_release.curriculum.grades[2:]))
            boolean_course = legacy_course_for_profile(
                self.fixture.grade_a, fixtures.SOURCE, boolean_profile)
            boolean_release = compile_successor_profile_release(
                base_release, boolean_profile, live_source_registry(),
                live_answer_registry(), source_root=fixtures.SOURCE,
                graph=self.graph, verification_seed=2026102101,
                legacy_course=boolean_course)
            boolean_program = schedule_program_from_executable_release(
                boolean_release)
            school = self._perfect_to_boundary(
                boolean_program, start_new(boolean_program, pointer))
            _, release_file, admission = storage._executable_factory_admission(
                self.root, boolean_release, pointer,
                storage._fingerprint(self.graph), self.graph)
            base = self.fixture.receipt(
                self.fixture.graduated(pointer), pointer, self.params)
            parameter_shapes = {
                name: list(value.shape) for name, value in self.params.items()}
            record = storage._persist(self.root, {
                **base,
                'school': asdict(school),
                'curriculum_mode': boolean_course.version,
                'factory_release_sha256': boolean_release.release_sha256,
                'factory_release_file': release_file,
                'factory_release_schema': boolean_release.schema,
                'factory_admission_v2': asdict(admission),
                'config': {
                    **base['config'],
                    'vocab_size': len(self.graph['tokens']),
                    'answer_heads': answer_heads_from_executable_release(
                        boolean_release, self.graph),
                },
                'parameter_shapes': parameter_shapes,
                'semantic_graph_sha256': storage._fingerprint(self.graph),
                'championship_school_identity': build_school_identity(
                    course_sha256=boolean_release.execution_plan.curriculum_sha256,
                    semantic_graph_sha256=storage._fingerprint(self.graph),
                    parameter_shapes=parameter_shapes,
                    factory_release_sha256=boolean_release.release_sha256),
                'live_rubric_sha256':
                    boolean_program.grades[-1].assessment_sha256,
                'result': storage._school_result_label(school),
                'last_exam': None,
            })
            record = self._bind_perfect_boundary(
                record, boolean_release, boolean_course, boolean_program)
        self.before_numeric = record
        self.boolean_release = boolean_release
        self.boolean_course = boolean_course
        self.boolean_program = boolean_program

    def start(self):
        with redirect_stdout(io.StringIO()):
            transition = numeric_entry_transition(
                self.boolean_release, self.graph,
                full_boolean=False, maximum=3)
            with patch('bilqis_mlx.learning.student_ops._predictions',
                    side_effect=lambda _m, _p, rows, *args:
                    {row['id']: row['gold'] for row in rows}):
                self.params, self.optimizer, self.graph, record, course = (
                    storage._adopt_catalog_profile(
                        self.mx, self.root, self.before_numeric,
                        self.fixture.grade_a, fixtures.SOURCE, self.graph,
                        self.params, self.optimizer, transition,
                        reserve_gib=0.))
        return course, record

    @staticmethod
    def _perfect_to_boundary(program, school):
        for index in range(32):
            if school.stage == 'AWAITING_NEXT_GRADE':
                return school
            while next_capability(school):
                school = visit(
                    program, school, next_capability(school),
                    school.current_student)
            scope = assessment_capabilities(program, school)
            scores = {
                capability: Score(
                    program.capability_map[capability].exam_item_count,
                    program.capability_map[capability].exam_item_count)
                for capability in scope
            }
            rubric = program.exact_scope_rubric(scope)
            school = assess(program, school, Assessment(
                school.current_student.sha256,
                school.current_student.optimizer_step,
                program.digest(), rubric, scores,
                f'fixture-perfect-{index}'))
        raise AssertionError('fixture did not reach AWAITING_NEXT_GRADE')

    def _bind_perfect_boundary(
            self, record, release, course, program, *, run_dir=None, graph=None):
        run_dir = self.root if run_dir is None else run_dir
        graph = self.graph if graph is None else graph
        school = storage._state_from_json(record['school'], program)
        capabilities = tuple(
            item.capability_id for item in release.execution_plan.capabilities)
        cohort, pointer = storage._routine_executable_cohort(
            run_dir, record, self.fixture.manifest, release,
            live_source_registry(), fixtures.SOURCE, graph,
            capabilities=capabilities,
            assessment_epoch=school.grade_exam_epoch,
            legacy_course=course)
        measured = score(
            cohort, {row['id']: row['gold'] for row in cohort.rows},
            asdict(school.current_student))
        exam = {
            **pointer,
            'student_sha256': school.current_student.sha256,
            'optimizer_step': school.current_student.optimizer_step,
            'exam_rubric_sha256': pointer['rubric_sha256'],
            'scores': measured['scores'],
            'misses_for_teacher': [],
        }
        return storage._advance(
            run_dir, record, school, last_exam=exam)

    def _advance_scope(self, course, record):
        release = storage._read_executable_factory_release_artifact(
            self.root, record)
        program = schedule_program_from_executable_release(release)
        school = self._perfect_to_boundary(
            program, storage._state_from_json(record['school'], program))
        if asdict(school) != record['school']:
            record = storage._advance(self.root, record, school)
        profile = next_numeric_scope_profile(
            release, final_maximum=record['numeric_scope_final_maximum'])
        self.assertIsNotNone(profile)
        with redirect_stdout(io.StringIO()):
            changed, course, successor, successor_program = (
                storage._adopt_executable_profile(
                    self.root, record, self.fixture.grade_a,
                    fixtures.SOURCE, self.graph, profile))
        return course, changed, successor, successor_program

    def _id_parent_fixture(self, root):
        from bilqis_mlx.boolean_composite import build_course as build_composite
        from bilqis_mlx.boolean_identification import (
            answer_heads as id_answer_heads, build_course as build_id,
        )

        identified = build_id(
            build_composite(self.fixture.previous, fixtures.SOURCE), fixtures.SOURCE)
        mx, params, opt = self.fixture.toy()
        pointer = storage._bundle_pointer(
            root, 'id-parent', params, opt, self.fixture.parent_graph, reserve_gib=0.)
        base_release, _, _ = compile_projected_executable_release(
            identified, self.fixture.grade_a, fixtures.SOURCE,
            self.fixture.parent_graph)
        profile = with_disabled_future_grades(
            boolean_entry_profile(full=True),
            tuple(grade.grade_id for grade in base_release.curriculum.grades[2:]))
        compatibility = legacy_course_for_profile(
            self.fixture.grade_a, fixtures.SOURCE, profile)
        release = compile_successor_profile_release(
            base_release, profile, live_source_registry(),
            live_answer_registry(), source_root=fixtures.SOURCE,
            graph=self.fixture.parent_graph, verification_seed=2026102102,
            legacy_course=compatibility)
        program = schedule_program_from_executable_release(release)
        school = self._perfect_to_boundary(
            program, start_new(program, pointer))
        _, release_file, admission = storage._executable_factory_admission(
            root, release, pointer,
            storage._fingerprint(self.fixture.parent_graph),
            self.fixture.parent_graph)
        base = self.fixture.receipt(
            self.fixture.graduated(pointer), pointer, params)
        parameter_shapes = {name: list(value.shape) for name, value in params.items()}
        receipt = storage._persist(root, {
            **base,
            'school': asdict(school),
            'curriculum_mode': compatibility.version,
            'factory_release_sha256': release.release_sha256,
            'factory_release_file': release_file,
            'factory_release_schema': release.schema,
            'factory_admission_v2': asdict(admission),
            'config': {
                **base['config'],
                'vocab_size': len(self.fixture.parent_graph['tokens']),
                'answer_heads': answer_heads_from_executable_release(
                    release, self.fixture.parent_graph),
            },
            'parameter_shapes': parameter_shapes,
            'semantic_graph_sha256': storage._fingerprint(
                self.fixture.parent_graph),
            'championship_school_identity': build_school_identity(
                course_sha256=release.execution_plan.curriculum_sha256,
                semantic_graph_sha256=storage._fingerprint(
                    self.fixture.parent_graph),
                parameter_shapes=parameter_shapes,
                factory_release_sha256=release.release_sha256),
            'live_rubric_sha256': program.grades[-1].assessment_sha256,
            'result': storage._school_result_label(school),
            'last_exam': None,
        })
        receipt = self._bind_perfect_boundary(
            receipt, release, compatibility, program,
            run_dir=root, graph=self.fixture.parent_graph)
        return (identified, compatibility, release, id_answer_heads,
                mx, params, opt, receipt)

    def _numeric_staircase_preview(self, root):
        from bilqis_mlx.cli import main
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main([
                'train', '--dry-run', '--resume', '--numeric-staircase',
                '--run-dir', str(root), '--legacy-code-root', str(fixtures.SOURCE),
            ]), 0)
        return json.loads(output.getvalue())['numeric_staircase']

    def test_staircase_entry_preserves_optimizer_teacher_and_admits_bounded_catalog(self):
        before = self.before_numeric
        prior_step = self.optimizer.state['step'].item()
        course, record = self.start()
        release = storage._read_executable_factory_release_artifact(
            self.root, record)
        program = schedule_program_from_executable_release(release)
        self.assertEqual(record['numeric_maximum'], 3)
        self.assertEqual(record['numeric_scope_final_maximum'], 4)
        self.assertEqual(release.profile.profile_id,
                         'school/boolean-kernel/and-iff/numeric-0-3')
        self.assertNotEqual(record['model_bundle'], before['model_bundle'])
        self.assertEqual(
            record['school']['current_student']['optimizer_step'],
            before['school']['current_student']['optimizer_step'])
        self.assertEqual(record['teacher'], before['teacher'])
        self.assertEqual(record['school']['champions'], before['school']['champions'])
        self.assertEqual(record['school']['queue'], ['C.COUNT'])
        self.assertEqual(
            [cap.id for cap in program.grades[-1].capabilities],
            ['C.COUNT', 'C.NUMBER', 'C.SUCCESSOR', 'C.ADD', 'C.SUB'])
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

    def test_rebaselined_predecessor_v2_pointer_is_bound_and_tamper_rejected(self):
        # The pre-growth Boolean exam is a normal same-current v2 cohort.
        self.assertIsNotNone(storage._verify_saved_cohort(
            self.root, self.before_numeric, self.boolean_course))

        course, record = self.start()
        exam = record['last_exam']
        predecessor = self.boolean_release
        expected_capabilities = tuple(
            item.capability_id for item in predecessor.execution_plan.capabilities)
        self.assertEqual(exam['schema'], 'bilqis.mlx.generated-cohort/v2')
        self.assertEqual(
            exam['factory_release_sha256'], predecessor.release_sha256)
        self.assertEqual(tuple(exam['capabilities']), expected_capabilities)
        self.assertEqual(
            exam['rubric_sha256'],
            self.before_numeric['last_exam']['rubric_sha256'])
        self.assertEqual(
            exam['source_sha256'],
            self.before_numeric['last_exam']['source_sha256'])
        self.assertEqual(
            exam['student_sha256'], record['school']['current_student']['sha256'])
        self.assertEqual(
            exam['optimizer_step'],
            record['school']['current_student']['optimizer_step'])
        self.assertIsNotNone(storage._verify_saved_cohort(
            self.root, record, course))

        arbitrary_release = deepcopy(record)
        arbitrary_release['last_exam']['factory_release_sha256'] = 'a' * 64
        with self.assertRaisesRegex(
                ValueError,
                'FACTORY_EXECUTABLE_SAVED_COHORT_PREDECESSOR_UNAUTHORIZED'):
            storage._verify_saved_cohort(self.root, arbitrary_release, course)

        for field, value in (
                ('rubric_sha256', 'b' * 64),
                ('source_sha256', 'c' * 64),
                ('capabilities', list(expected_capabilities[:-1]))):
            tampered = deepcopy(record)
            tampered['last_exam'][field] = value
            with self.assertRaisesRegex(
                    ValueError, 'FACTORY_EXECUTABLE_COHORT_SCOPE_DRIFT'):
                storage._verify_saved_cohort(self.root, tampered, course)

        wrong_student = deepcopy(record)
        wrong_student['last_exam']['student_sha256'] = 'd' * 64
        with self.assertRaisesRegex(
                ValueError,
                'FACTORY_EXECUTABLE_SAVED_COHORT_PREDECESSOR_STUDENT_DRIFT'):
            storage._verify_saved_cohort(self.root, wrong_student, course)

        wrong_provenance = deepcopy(record)
        wrong_provenance['factory_admission_v2']['semantic_graph_sha256'] = 'e' * 64
        with self.assertRaisesRegex(
                ValueError,
                'FACTORY_EXECUTABLE_SAVED_COHORT_CURRENT_ADMISSION_DRIFT'):
            storage._verify_saved_cohort(self.root, wrong_provenance, course)

        wrong_manifest = deepcopy(record)
        wrong_manifest['source_manifest_sha256'] = 'f' * 64
        with self.assertRaisesRegex(
                ValueError, 'FACTORY_EXECUTABLE_COHORT_METADATA_DRIFT'):
            storage._verify_saved_cohort(self.root, wrong_manifest, course)

    def test_question_inventory_change_globally_resets_live_champions_and_soups(self):
        course, record = self.start()
        seeded = deepcopy(record)
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
        program = schedule_program_from_executable_release(
            storage._read_executable_factory_release_artifact(self.root, seeded))
        school = storage._state_from_json(seeded['school'], program)
        seeded = storage._advance(
            self.root, {**seeded, 'mentor_epoch': epoch}, school)
        prior_identity = epoch["championship_school_identity"]["sha256"]
        prior_step = self.optimizer.state["step"].item()

        course, changed, _, _ = self._advance_scope(course, seeded)
        successor = changed["mentor_epoch"]
        self.assertNotEqual(changed["championship_school_identity"]["sha256"], prior_identity)
        self.assertEqual(successor["active_roles"], {})
        self.assertEqual(successor["active_grade_soups"], {})
        self.assertEqual(successor["settled_matchups"], epoch["settled_matchups"])
        self.assertEqual(successor["administrative_empty_reset"]["old_active_role_count"], 1)
        self.assertEqual(successor["administrative_empty_reset"]["old_active_soup_grades"], ["C"])
        self.assertEqual(successor["administrative_empty_reset"]["training_or_optimizer_updates"], 0)
        self.assertEqual(changed["school"]["current_student"],
                         seeded["school"]["current_student"])
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
            self.assertEqual(report['numeric_staircase']['final_maximum'], 4)
            self.assertFalse(report['neural_training_started_by_this_command'])
            self.assertEqual((self.root/'state.json').read_bytes(), original)

    def test_id_parent_preview_and_answer_head_custody_survive_c_and_staircase(self):
        with tempfile.TemporaryDirectory() as temp, redirect_stdout(io.StringIO()):
            root = Path(temp)
            (identified, compatibility, release, id_answer_heads,
             mx, params, opt, receipt) = (
                self._id_parent_fixture(root))
            preview = self._numeric_staircase_preview(root)
            self.assertEqual(preview['resume_maximum'], 3)
            self.assertEqual(preview['profile_id'], release.profile.profile_id)
            transition = numeric_entry_transition(
                release, self.fixture.parent_graph,
                full_boolean=True, maximum=3)
            with patch('bilqis_mlx.learning.student_ops._predictions',
                    side_effect=lambda _m, _p, rows, *args:
                    {row['id']: row['gold'] for row in rows}):
                grown, own, graph, c_record, staircase = (
                    storage._adopt_catalog_profile(
                        mx, root, receipt, self.fixture.grade_a,
                        fixtures.SOURCE, self.fixture.parent_graph,
                        params, opt, transition, reserve_gib=0.))

            operator_head = id_answer_heads(graph)['boolean_operator']
            admitted_operator_head = c_record['config']['answer_heads'][
                'boolean_operator']
            self.assertEqual(admitted_operator_head['values'],
                             operator_head['values'])
            self.assertEqual(admitted_operator_head['token_ids'],
                             operator_head['token_ids'])
            self.assertEqual(admitted_operator_head['modality_id'],
                             'answer.boolean-operator/v1')
            self.assertEqual(len(admitted_operator_head['implementation_sha256']),
                             64)
            self.assertEqual(int(own.state['step'].item()), int(opt.state['step'].item()))
            admitted = storage._read_executable_factory_release_artifact(
                root, c_record)
            program = schedule_program_from_executable_release(admitted)
            self.assertEqual(
                [cap.id for cap in program.grades[1].capabilities], [
                'B.NOT', 'B.AND', 'B.OR', 'B.XOR', 'B.IMPLIES', 'B.IFF',
                'B.COMPOSITE', 'B.IDBOOLOPS',
            ])
            self.assertEqual(
                c_record['config']['answer_heads']['boolean_operator'],
                admitted_operator_head)
            self.assertEqual(c_record['numeric_maximum'], 3)
            self.assertEqual(staircase.grades[1], identified.grades[1])
            self.assertEqual(
                [cap.id for cap in program.grades[-1].capabilities],
                ['C.COUNT', 'C.NUMBER', 'C.SUCCESSOR', 'C.ADD', 'C.SUB'])

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
        }}
        release = storage._read_executable_factory_release_artifact(
            self.root, wide)
        with redirect_stdout(io.StringIO()):
            changed, _, narrowed, program = storage._adopt_executable_profile(
                self.root,
                {**wide, 'numeric_scope_final_maximum': 4},
                self.fixture.grade_a, fixtures.SOURCE, graph,
                numeric_scope_profile(release, 3))
        self.assertEqual(changed['numeric_maximum'], 3)
        self.assertEqual(changed['numeric_scope_final_maximum'], 4)
        self.assertEqual(changed['school']['carried_mastery_debt'], ['C.COUNT'])
        self.assertEqual(changed['school']['current_student'], wide_student)
        self.assertEqual(int(self.optimizer.state['step'].item()), prior_step)
        self.assertEqual(
            [cap.id for cap in program.grades[-1].capabilities],
            ['C.COUNT', 'C.NUMBER', 'C.SUCCESSOR', 'C.ADD', 'C.SUB'])
        self.assertEqual(
            narrowed.profile.profile_id.rsplit('-', 1)[-1], '3')
        self.assertTrue(storage._mentor_epoch_references(changed))
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

    def test_numeric_profile_sequence_cannot_skip_or_exceed_final_maximum(self):
        course, record = self.start()
        observed = [record['numeric_maximum']]
        release = storage._read_executable_factory_release_artifact(
            self.root, record)
        while record['numeric_maximum'] < record['numeric_scope_final_maximum']:
            course, record, release, _ = self._advance_scope(course, record)
            observed.append(record['numeric_maximum'])
        self.assertEqual(observed, [3, 4])
        self.assertIsNone(next_numeric_scope_profile(
            release, final_maximum=record['numeric_scope_final_maximum']))

    def test_final_scope_four_adds_multiply_and_divide_without_widening_numbers(self):
        course, record = self.start()
        entry_bundle = record['model_bundle']
        prior_step = self.optimizer.state['step'].item()
        prior_epoch = record['school']['grade_exam_epoch']
        course, changed, release, program = self._advance_scope(course, record)
        self.assertEqual(changed['numeric_maximum'], 4)
        self.assertEqual(changed['school']['introduction_stage'], 0)
        self.assertEqual(changed['school']['queue'], ['C.COUNT'])
        self.assertEqual(changed['model_bundle'], record['model_bundle'])
        self.assertEqual(changed['teacher'], record['teacher'])
        self.assertGreater(changed['school']['grade_exam_epoch'], prior_epoch)
        self.assertEqual(
            [cap.id for cap in program.grades[-1].capabilities],
            ['C.COUNT', 'C.NUMBER', 'C.SUCCESSOR', 'C.ADD', 'C.SUB',
             'C.MUL', 'C.DIV'])
        self.assertEqual(release.profile.profile_id.rsplit('-', 1)[-1], '4')
        self.assertEqual(record['model_bundle'], entry_bundle)
        self.assertEqual(self.optimizer.state['step'].item(), prior_step)

    def test_wide_old_mistakes_are_deferred_without_being_discarded(self):
        course, record = self.start()
        rows = draw(self.graph, seed=17, maximum=10, capability='C.COUNT')
        wide = next(r for r in rows if r['answer_kind']=='numeric_active' and r['gold']=='10')
        small = next(r for r in rows if r['answer_kind']=='numeric_active' and r['gold']=='2')
        self.assertFalse(numeric_row_in_scope(wide, 3))
        self.assertTrue(numeric_row_in_scope(small, 3))
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
        entry_bundle = record['model_bundle']
        while True:
            release = storage._read_executable_factory_release_artifact(
                self.root, record)
            program = schedule_program_from_executable_release(release)
            maximum = record['numeric_maximum']
            capabilities = tuple(
                cap.id for cap in program.grades[-1].capabilities)
            observed.extend((maximum, capability) for capability in capabilities)
            school = storage._state_from_json(record['school'], program)
            for epoch in (school.grade_exam_epoch, school.grade_exam_epoch + 1):
                cohort, _ = storage._routine_executable_cohort(
                    self.root, record, self.fixture.manifest, release,
                    live_source_registry(), fixtures.SOURCE, self.graph,
                    capabilities=capabilities, assessment_epoch=epoch,
                    legacy_course=course)
                self.assertNotIn(cohort.digest, cohorts)
                cohorts.append(cohort.digest)
            if maximum == record['numeric_scope_final_maximum']:
                break
            course, record, _, _ = self._advance_scope(course, record)
        self.assertEqual(len(set(cohorts)), len(cohorts))
        self.assertEqual(observed,
            [(3,c) for c in
             ('C.COUNT','C.NUMBER','C.SUCCESSOR','C.ADD','C.SUB')] +
            [(4,c) for c in
             ('C.COUNT','C.NUMBER','C.SUCCESSOR','C.ADD','C.SUB','C.MUL','C.DIV')])
        self.assertEqual(record['model_bundle'], entry_bundle)

    def test_interrupted_enrollment_recovers_without_changing_student(self):
        original = storage._durable_json
        def interrupt(path, value, **kwargs):
            if (path == self.root/'state.json' and
                    value.get('numeric_maximum') == 3 and
                    value.get('factory_admission_v2') is not None):
                raise RuntimeError('enrollment pointer interrupted')
            return original(path,value,**kwargs)
        with patch('bilqis_mlx.runtime.state._durable_json',side_effect=interrupt), redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError,'pointer interrupted'):
                self.start()
        transition = numeric_entry_transition(
            self.boolean_release, self.graph,
            full_boolean=False, maximum=3)
        course = legacy_course_for_profile(
            self.fixture.grade_a, fixtures.SOURCE, transition.profile)
        pending = json.loads((self.root/'states'/
            f"{self.before_numeric['generation'] + 1:07d}.json").read_text())
        self.assertEqual(pending['numeric_maximum'], 3)
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
