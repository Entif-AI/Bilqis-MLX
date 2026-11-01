"""Disposable curriculum changes retain the student's complete native state."""
from contextlib import redirect_stdout
import io
import json

from bilqis_mlx import trainer as storage
from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
from bilqis_mlx.live_grade_c import draw
from bilqis_mlx.profiles.catalog import next_numeric_scope_profile, numeric_row_in_scope
from bilqis_mlx.source_adapters.school import live_source_registry
from tests.system import test_grade_c_trainer as fixtures


from tests.integration.numeric.profiles import NumericProfileFixture

class NumericStaircaseTests(NumericProfileFixture):
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
            self.assertEqual(report['numeric_staircase']['resume_maximum'], 4)
            self.assertEqual(report['numeric_staircase']['final_maximum'], 10)
            self.assertFalse(report['neural_training_started_by_this_command'])
            self.assertEqual((self.root/'state.json').read_bytes(), original)

    def test_numeric_profile_sequence_cannot_skip_or_exceed_final_maximum(self):
        course, record = self.start()
        observed = [record['numeric_maximum']]
        release = storage._read_executable_factory_release_artifact(
            self.root, record)
        while record['numeric_maximum'] < record['numeric_scope_final_maximum']:
            course, record, release, _ = self._advance_scope(course, record)
            observed.append(record['numeric_maximum'])
        self.assertEqual(observed, [4, 5, 6, 7, 8, 9, 10])
        self.assertIsNone(next_numeric_scope_profile(
            release, final_maximum=record['numeric_scope_final_maximum']))

    def test_entry_scope_four_includes_multiply_and_divide_without_extra_revision(self):
        course, record = self.start()
        entry_bundle = record['model_bundle']
        prior_step = self.optimizer.state['step'].item()
        release = storage._read_executable_factory_release_artifact(self.root, record)
        program = schedule_program_from_executable_release(release)
        self.assertEqual(record['numeric_maximum'], 4)
        self.assertEqual(record['school']['introduction_stage'], 0)
        self.assertEqual(record['school']['queue'], ['C.COUNT'])
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
        self.assertFalse(numeric_row_in_scope(wide, 4))
        self.assertTrue(numeric_row_in_scope(small, 4))
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
                    capabilities=capabilities, assessment_epoch=epoch)
                self.assertNotIn(cohort.digest, cohorts)
                cohorts.append(cohort.digest)
            if maximum == record['numeric_scope_final_maximum']:
                break
            course, record, _, _ = self._advance_scope(course, record)
        self.assertEqual(len(set(cohorts)), len(cohorts))
        capabilities = ('C.COUNT','C.NUMBER','C.SUCCESSOR','C.ADD','C.SUB','C.MUL','C.DIV')
        self.assertEqual(observed,
            [(maximum, capability)
             for maximum in range(4, 11) for capability in capabilities])
        self.assertEqual(record['model_bundle'], entry_bundle)
