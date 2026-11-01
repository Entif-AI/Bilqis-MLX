"""Disposable curriculum changes retain the student's complete native state."""
from contextlib import redirect_stdout
from dataclasses import asdict
import io
import json

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
from bilqis_mlx.profiles.catalog import next_numeric_scope_profile
from bilqis_mlx.profiles.school import boolean_entry_profile, with_disabled_future_grades
from bilqis_mlx.source_adapters.school import live_source_registry
from tests.system import test_grade_c_trainer as fixtures


from tests.integration.numeric.fixtures import NumericStaircaseFixture

class NumericProfileFixture(NumericStaircaseFixture):
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
            assessment_epoch=school.grade_exam_epoch)
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
            graph=self.fixture.parent_graph, verification_seed=2026102102)
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
