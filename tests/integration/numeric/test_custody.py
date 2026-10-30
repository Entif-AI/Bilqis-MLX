"""Disposable curriculum changes retain the student's complete native state."""
from contextlib import redirect_stdout
import io
from copy import deepcopy
from pathlib import Path
import tempfile
from unittest.mock import patch

from bilqis_mlx import trainer as storage
from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
from bilqis_mlx.profiles.catalog import numeric_entry_transition
from tests.system import test_grade_c_trainer as fixtures


from tests.integration.numeric.profiles import NumericProfileFixture

class NumericStaircaseTests(NumericProfileFixture):
    def test_frontier_lineage_is_verified_before_catalog_growth_or_prediction(self):
        transition = numeric_entry_transition(
            self.boolean_release, self.graph, full_boolean=False)
        before_paths = tuple(sorted(str(path.relative_to(self.root))
                                    for path in self.root.rglob("*")))
        for field, value, expected in (
                ("factory_release_sha256", "a" * 64, "FACTORY_EXECUTABLE_COHORT_RELEASE_DRIFT"),
                ("source_sha256", "b" * 64, "FACTORY_EXECUTABLE_COHORT_SCOPE_DRIFT"),
                ("student_sha256", "c" * 64, "FACTORY_PROFILE_EXPANSION_REQUIRES_COMPLETE_PERFECT_PREFIX"),
                ("optimizer_step", -1, "FACTORY_PROFILE_EXPANSION_REQUIRES_COMPLETE_PERFECT_PREFIX")):
            changed = deepcopy(self.before_numeric)
            changed["last_exam"][field] = value
            with self.subTest(field=field), \
                    patch("bilqis_mlx.vocabulary_growth.extend_mlx_student",
                          side_effect=AssertionError("growth before frontier verification")) as growth, \
                    patch("bilqis_mlx.learning.student_ops._predictions",
                          side_effect=AssertionError("prediction before frontier verification")) as inference:
                with self.assertRaisesRegex(ValueError, "^" + expected + "$"):
                    storage._adopt_catalog_profile(
                        self.mx, self.root, changed, self.fixture.grade_a,
                        fixtures.SOURCE, self.graph, self.params, self.optimizer,
                        transition, reserve_gib=0.)
                growth.assert_not_called()
                inference.assert_not_called()
            self.assertEqual(tuple(sorted(str(path.relative_to(self.root))
                                          for path in self.root.rglob("*"))), before_paths)

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

    def test_id_parent_preview_and_answer_head_custody_survive_c_and_staircase(self):
        with tempfile.TemporaryDirectory() as temp, redirect_stdout(io.StringIO()):
            root = Path(temp)
            (identified, compatibility, release, id_answer_heads,
             mx, params, opt, receipt) = (
                self._id_parent_fixture(root))
            preview = self._numeric_staircase_preview(root)
            self.assertEqual(preview['resume_maximum'], 4)
            self.assertEqual(preview['profile_id'], release.profile.profile_id)
            transition = numeric_entry_transition(
                release, self.fixture.parent_graph,
                full_boolean=True)
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
            self.assertIsNone(c_record['school']['debt_cadence_policy'])
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
            self.assertEqual(c_record['numeric_maximum'], 4)
            self.assertEqual(staircase.grades[1], identified.grades[1])
            self.assertEqual(
                [cap.id for cap in program.grades[-1].capabilities],
                ['C.COUNT', 'C.NUMBER', 'C.SUCCESSOR', 'C.ADD', 'C.SUB',
                 'C.MUL', 'C.DIV'])
