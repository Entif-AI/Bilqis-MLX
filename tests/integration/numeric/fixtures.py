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
from bilqis_mlx.curriculum.scheduler import start_new
from bilqis_mlx.factory.executable_release import (
    answer_heads_from_executable_release, compile_successor_profile_release)
from bilqis_mlx.factory.live_answers import live_answer_registry
from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
from bilqis_mlx.learning.championship_identity import build_school_identity
from bilqis_mlx.profiles.catalog import numeric_entry_transition
from bilqis_mlx.profiles.school import boolean_entry_profile, with_disabled_future_grades
from bilqis_mlx.source_adapters.school import live_source_registry
from tests.system import test_grade_c_trainer as fixtures


from bilqis_mlx.paths import REPO_ROOT
class NumericStaircaseFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from bilqis_mlx.compatibility import historical_teacher_policy as policy
        from bilqis_mlx.grade_a_release import accepted_grade_a
        from bilqis_mlx.live_grade_a import live_course as live_a
        from bilqis_mlx.live_grade_b import live_course as live_b
        from bilqis_mlx.live_grade_c import registry_graph
        from bilqis_mlx.semantics.abi import HISTORICAL_PREFIX_SIZE

        cls.manifest = json.loads((REPO_ROOT /
            "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
        cls.grade_a = live_a(accepted_grade_a(cls.manifest))
        cls.previous = live_b(cls.grade_a, fixtures.SOURCE)
        registered = registry_graph()
        tokens = registered["tokens"][:HISTORICAL_PREFIX_SIZE]
        cls.parent_graph = {**registered, "tokens": tokens,
            "nodes": registered["nodes"][:HISTORICAL_PREFIX_SIZE],
            "row_contract_sha256": {name: registered["row_contract_sha256"][name]
                                    for name in tokens}}
        strategy = dict(old=4, preview=0, depth=1, contrast=0.0, lr=0.00013, distill=0.0)
        key = policy._policy_key(strategy)
        cls.teacher = dict(strategies={key: strategy}, global_stats={key: policy._stats()},
                           grade_stats={}, events=0, mutations=0)
        cls.policy_sha = storage._fingerprint({
            "fixture_only": "numeric-staircase-disposable-policy/v1", "teacher": cls.teacher})
        cls.engine = policy

    def setUp(self):
        self.fixture = fixtures.GradeCTrainerTests()
        for name in ("manifest", "grade_a", "previous", "parent_graph", "teacher", "policy_sha"):
            setattr(self.fixture, name, deepcopy(getattr(self, name)))
        self.fixture.engine = self.engine
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
                graph=self.graph, verification_seed=2026102101)
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
                full_boolean=False)
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
