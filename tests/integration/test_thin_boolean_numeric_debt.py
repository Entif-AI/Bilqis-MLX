"""Real-provider A→thin B→C admission preserves unfinished Boolean learning."""
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx import trainer
from bilqis_mlx.runtime import release_adoption
from bilqis_mlx.curriculum.scheduler import start_new
from bilqis_mlx.factory.execution import CurriculumProfile, GradeProfile
from bilqis_mlx.profiles.catalog import numeric_entry_transition
from bilqis_mlx.runtime.exam_execution import _measure_debt_admission_boundary
from bilqis_mlx.runtime.release_adoption import _adopt_executable_profile, _adopt_catalog_profile
from tests.system import test_grade_c_trainer as fixtures

SOURCE = fixtures.SOURCE


class ThinBooleanNumericDebtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from bilqis_mlx.compatibility import historical_teacher_policy as policy
        from bilqis_mlx.grade_a_release import accepted_grade_a
        from bilqis_mlx.live_grade_a import live_course as live_a
        from bilqis_mlx.live_grade_b import live_course as live_b
        from bilqis_mlx.live_grade_c import registry_graph
        from bilqis_mlx.semantics.foundation.abi import HISTORICAL_PREFIX_SIZE

        cls.manifest = json.loads((Path(__file__).resolve().parents[2] /
            "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
        cls.grade_a = live_a(accepted_grade_a(cls.manifest))
        cls.previous = live_b(cls.grade_a, SOURCE)
        registered = registry_graph()
        tokens = registered["tokens"][:HISTORICAL_PREFIX_SIZE]
        cls.parent_graph = {**registered, "tokens": tokens,
            "nodes": registered["nodes"][:HISTORICAL_PREFIX_SIZE],
            "row_contract_sha256": {name: registered["row_contract_sha256"][name]
                                    for name in tokens}}
        strategy = dict(old=4, preview=0, depth=1, contrast=0.0,
                        lr=0.00013, distill=0.0)
        key = policy._policy_key(strategy)
        cls.teacher = dict(strategies={key: strategy}, global_stats={key: policy._stats()},
                           grade_stats={}, events=0, mutations=0)
        cls.policy_sha = trainer._fingerprint({
            "fixture_only": "thin-boolean-numeric-debt-disposable-policy/v1",
            "teacher": cls.teacher})
        cls.engine = policy

    def setUp(self):
        self.fixture = fixtures.GradeCTrainerTests()
        for name in ("manifest", "grade_a", "previous", "parent_graph", "teacher", "policy_sha"):
            setattr(self.fixture, name, deepcopy(getattr(self, name)))
        self.fixture.engine = self.engine

    def test_unmastered_not_and_do_not_block_designed_counting_entry(self):
        self._progress(automatic=False)

    def test_automatic_debt_boundaries_preserve_thin_b_and_numeric_ceiling(self):
        self._progress(automatic=True)

    def _progress(self, *, automatic):
        fixture = self.fixture
        mx, params, own = fixture.toy()
        graph = fixture.parent_graph
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            run = Path(directory)
            pointer = trainer._bundle_pointer(run, 'initial', params, own, graph, reserve_gib=0.)
            base = fixture.receipt(start_new(fixture.grade_a, pointer), pointer, params)
            base.update(curriculum_mode=fixture.grade_a.version, last_exam=None)
            base = trainer._persist(run, base)
            base, release, _ = trainer._ensure_executable_release(
                run, base, fixture.grade_a, fixture.grade_a, SOURCE, graph)
            profile = CurriculumProfile('test/not-and', (
                GradeProfile('B', enabled_capabilities=('B.NOT', 'B.AND')),
                GradeProfile('C', enabled_capabilities=()),))

            def imperfect(_mx, _params, rows, *_args):
                first = {}
                for row in rows:
                    first.setdefault(row['capability'], row['id'])
                return {row['id']: ('FALSE' if row['gold'] == 'TRUE' else 'TRUE')
                        if row['id'] == first[row['capability']] else row['gold'] for row in rows}

            with patch('bilqis_mlx.learning.student_ops._predictions', side_effect=imperfect):
                measured = _measure_debt_admission_boundary(
                    mx, run, base, fixture.manifest, fixture.grade_a, SOURCE, params, graph)
                stale = {**measured, 'debt_admission_boundary_exam': {
                    **measured['debt_admission_boundary_exam'], 'optimizer_step': -1}}
                with self.assertRaisesRegex(ValueError, 'DEBT_ADMISSION_REQUIRES_EXACT_COMPLETE_BOUNDARY'):
                    _adopt_executable_profile(run, stale, fixture.grade_a, SOURCE, graph,
                                              profile, allow_mastery_debt=True)
                if automatic:
                    admitted, course, release = self._auto_boolean_entry(
                        mx, run, measured, fixture, params, own, graph, profile)
                else:
                    admitted, course, release, _ = _adopt_executable_profile(
                        run, measured, fixture.grade_a, SOURCE, graph, profile, allow_mastery_debt=True)
                self.assertEqual(admitted['school']['current_student'], base['school']['current_student'])
                self.assertIsNone(admitted['mentor_epoch']['previous_graduate'])
                self.assertFalse(admitted['school']['champions'])
                self.assertIsNotNone(trainer._verify_saved_cohort(run, admitted, course))
                # Take the complete current exam even though B has not graduated.
                measured = _measure_debt_admission_boundary(
                    mx, run, admitted, fixture.manifest, course, SOURCE, params, graph)
                transition = replace(numeric_entry_transition(
                    release, graph, full_boolean=False, maximum=3), numeric_scope_final_maximum=4)
                if automatic:
                    measured = {**measured, 'school': {**measured['school'],
                        'stage': 'AWAITING_NEXT_GRADE_WITH_DEBT', 'queue': [],
                        'carried_mastery_debt': list(measured['debt_admission_boundary_exam']['scores'])}}
                    runtime_dispatch = release_adoption._auto_adopt_known_grade_boundary
                    with patch.object(release_adoption,
                            '_auto_adopt_known_grade_boundary',
                            wraps=runtime_dispatch) as dispatch_spy:
                        _, grown_own, _, numeric, numeric_course, changed = (
                            release_adoption._auto_adopt_known_grade_boundary(
                                mx, run, measured, course, fixture.grade_a, SOURCE,
                                fixture.manifest, params, own, graph, reserve_gib=0.,
                                full_grade_b=False, numeric_staircase=False))
                    dispatch_spy.assert_called_once_with(
                        mx, run, measured, course, fixture.grade_a, SOURCE,
                        fixture.manifest, params, own, graph, reserve_gib=0.,
                        full_grade_b=False, numeric_staircase=False)
                    self.assertTrue(changed)
                else:
                    _, grown_own, _, numeric, numeric_course = _adopt_catalog_profile(
                        mx, run, measured, fixture.grade_a, SOURCE, graph, params, own,
                        transition, reserve_gib=0., allow_mastery_debt=True)
                self.assertIsNotNone(trainer._verify_saved_cohort(run, numeric, numeric_course))

        self.assertEqual(numeric['school']['active_grades'], ['A', 'B', 'C'])
        self.assertEqual(numeric['school']['queue'], ['C.COUNT'])
        self.assertTrue({'B.NOT', 'B.AND'} <= set(numeric['school']['carried_mastery_debt']))
        self.assertFalse(numeric['school']['champions'])
        self.assertEqual(numeric['numeric_maximum'], 3)
        self.assertEqual(numeric['numeric_scope_final_maximum'], 4)
        self.assertEqual(int(grown_own.state['step'].item()), int(own.state['step'].item()))
        self.assertEqual(numeric['mentor_epoch']['previous_boundary_checkpoint'],
                         admitted['school']['current_student'])

    def _auto_boolean_entry(self, mx, run, measured, fixture, params, own, graph, profile):
        measured = {**measured, 'school': {**measured['school'],
            'stage': 'AWAITING_NEXT_GRADE_WITH_DEBT', 'queue': [],
            'carried_mastery_debt': list(measured['debt_admission_boundary_exam']['scores'])},
            'numeric_scope_final_maximum': 4}
        from bilqis_mlx.runtime import release_adoption
        runtime_dispatch = release_adoption._auto_adopt_known_grade_boundary
        with patch('bilqis_mlx.profiles.catalog.boolean_entry_profile', return_value=profile):
            with patch.object(release_adoption,
                    '_auto_adopt_known_grade_boundary',
                    wraps=runtime_dispatch) as dispatch_spy:
                _, _, _, admitted, course, changed = (
                    release_adoption._auto_adopt_known_grade_boundary(
                        mx, run, measured, fixture.grade_a, fixture.grade_a,
                        SOURCE, fixture.manifest, params, own, graph,
                        reserve_gib=0., full_grade_b=False,
                        numeric_staircase=False))
        dispatch_spy.assert_called_once_with(
            mx, run, measured, fixture.grade_a, fixture.grade_a,
            SOURCE, fixture.manifest, params, own, graph,
            reserve_gib=0., full_grade_b=False,
            numeric_staircase=False)
        self.assertTrue(changed)
        release = trainer._read_executable_factory_release_artifact(run, admitted)
        return admitted, course, release
