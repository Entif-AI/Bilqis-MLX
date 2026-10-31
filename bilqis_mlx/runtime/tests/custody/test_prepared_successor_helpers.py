"""Shared fixtures extracted structurally from test_prepared_successor.py."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, fields, replace
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from bilqis_mlx.curriculum.scheduler import start_new
from bilqis_mlx.factory.autonomy import compile_autonomy_plan, initial_evidence_ledger
from bilqis_mlx.factory.jit_curriculum import propose_curriculum_delta
from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
from bilqis_mlx.factory.tests.test_candidate_staging import CandidateStagingFixture
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime import release_adoption
from bilqis_mlx.runtime.jit_adoption import resolve_ready_candidate

class PreparedSuccessorFixture(CandidateStagingFixture):
    def setUp(self):
        super().setUp()
        self.staged = self.stage()
        self.graph = self.fixture.fixture.graph
        self.checkpoint = Checkpoint("e" * 64, "bundles/fixture", 0, True)
        self.program = schedule_program_from_executable_release(self.current)
        self.receipt = {"school": asdict(start_new(self.program, self.checkpoint))}
        self.parameters = {"weights": SimpleNamespace(shape=(2,), values=[1., 2.])}
        self.optimizer = SimpleNamespace(
            state={"step": 0}, update=Mock(side_effect=AssertionError("neural update")))
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @contextmanager
    def admitted_boundary(self):
        with patch.object(release_adoption._runtime_admission,
                "_require_executable_factory_admission", return_value=self.current), \
                patch.object(release_adoption._factory_executable_release,
                    "compile_executable_factory_release", side_effect=AssertionError("recompiled")), \
                patch.object(release_adoption._factory_executable_release,
                    "compile_successor_profile_release", side_effect=AssertionError("recompiled")):
            yield

    def adopt(self, staged=None):
        return release_adoption._adopt_prepared_successor(
            None, self.root, self.receipt, None, None, self.graph,
            self.parameters, self.optimizer, self.staged if staged is None else staged,
            reserve_gib=100.)


    def graduate_fixture(self):
        school = replace(start_new(self.program, self.checkpoint),
                         stage="AWAITING_NEXT_GRADE", queue=(),
                         champions={self.program.grades[0].id: self.checkpoint})
        self.receipt = {"school": asdict(school), "source_manifest_sha256": "a" * 64,
            "semantic_graph_sha256": release_adoption._runtime_state._fingerprint(self.graph),
            "last_exam": {"student_sha256": self.checkpoint.sha256, "optimizer_step": 0,
                "scores": {cap.id: {"correct": cap.exam_item_count, "total": cap.exam_item_count}
                           for grade in self.program.grades for cap in grade.capabilities}}}

    def append_grade_fixture(self, graph=None, *, ready=True):
        from bilqis_mlx.factory.candidate_staging import compile_candidate_successor, candidate_source_anchor
        from bilqis_mlx.factory.executable_release import compile_executable_factory_release
        from bilqis_mlx.factory.execution import CurriculumProfile, GradeProfile
        fixture = self.fixture.fixture
        grade = self.current.curriculum.grades[0]
        cap = replace(grade.capabilities[0], capability_id="Y.C0")
        added = replace(grade, grade_id="Y", capabilities=(cap,),
                        exam_item_counts=((cap.capability_id, 4),), teaching_stages=())
        curriculum = replace(self.current.curriculum, grades=(grade, added))
        frontier = replace(self.frontier, candidates=(replace(
            self.frontier.candidates[0], proposed_capability_id=cap.capability_id),
            *self.frontier.candidates[1:]))
        frontier = replace(frontier, senses=(replace(
            frontier.senses[0], selected_target_capability=cap.capability_id),))
        frontier = replace(frontier, release_sha256=frontier.expected_digest())
        binding = replace(self.current.source_bindings.bindings[0],
            capability_id=cap.capability_id,
            source_anchor=candidate_source_anchor(frontier, self.candidate_id))
        bindings = replace(self.current.source_bindings,
            bindings=(*self.current.source_bindings.bindings, binding))
        self.current = compile_executable_factory_release(
            curriculum, bindings, CurriculumProfile("fixture/prior", (
                GradeProfile("Y", enabled_capabilities=()),)), fixture.registry,
            fixture.answers, source_root=None, graph=self.graph, verification_seed=43)
        self.program = schedule_program_from_executable_release(self.current)
        if ready:
            self.graduate_fixture()
        return compile_candidate_successor(frontier, self.current, self.candidate_id,
            curriculum=curriculum, source_bindings=bindings, profile=CurriculumProfile.full(),
            source_registry=fixture.registry, answer_registry=fixture.answers,
            source_root=None, graph=self.graph if graph is None else graph, verification_seed=44)

    def prepare_native_same_grade_growth(self):
        import mlx.core as mx
        import mlx.optimizers as optim
        from bilqis_mlx.factory.executable_release import compile_executable_factory_release
        from bilqis_mlx.generated_assessment import score
        from bilqis_mlx.runtime.assessment import _routine_executable_cohort
        from bilqis_mlx.vocabulary_growth import digest

        nodes = [{"id": token, "meaning": token, "semantic_id": "fixture:" + token,
                  "family": "logic", "subtype": "atomic", "signature": "SemanticSymbol",
                  "arity": 0, "source": "fixture:native-growth", "admission_receipt": "a" * 64}
                 for token in self.graph["tokens"]]
        self.graph = {**self.graph, "nodes": nodes,
                      "row_contract_sha256": {node["id"]: digest(node) for node in nodes}}
        fixture = self.fixture.fixture
        self.current = compile_executable_factory_release(
            self.current.curriculum, self.current.source_bindings, self.current.profile,
            fixture.registry, fixture.answers, source_root=None, graph=self.graph,
            verification_seed=71)
        self.program = schedule_program_from_executable_release(self.current)
        extra = {"id": "fixture.extra", "meaning": "new disposable identity",
                 "semantic_id": "fixture:extra", "family": "logic", "subtype": "atomic",
                 "signature": "SemanticSymbol", "arity": 0, "source": "fixture:native-growth",
                 "admission_receipt": "b" * 64}
        graph = {**self.graph, "tokens": [*self.graph["tokens"], extra["id"]],
                 "nodes": [*nodes, extra], "row_contract_sha256": {
                     **self.graph["row_contract_sha256"], extra["id"]: digest(extra)}}
        staged = self.stage(graph=graph)
        old_count = len(self.graph["tokens"])
        self.parameters = {"embedding.weight": mx.arange(old_count * 2, dtype=mx.float32).reshape(old_count, 2),
                           "linear.weight": mx.ones((2, 2), dtype=mx.float32)}
        self.optimizer = optim.AdamW(learning_rate=0.001, bias_correction=True)
        self.optimizer.init(self.parameters)
        self.optimizer.state["step"] = mx.array(7, dtype=mx.uint64)
        for name, value in self.parameters.items():
            self.optimizer.state[name]["m"] = mx.full(value.shape, 0.25, dtype=mx.float32)
            self.optimizer.state[name]["v"] = mx.full(value.shape, 0.5, dtype=mx.float32)
        mx.eval(self.parameters, self.optimizer.state)
        self.checkpoint = release_adoption._runtime_checkpoints._bundle_pointer(
            self.root, "native-parent", self.parameters, self.optimizer, self.graph, reserve_gib=0.)
        self.graduate_fixture()
        self.receipt.update(generation=1, run_id="disposable-native-growth",
                            config={"vocab_size": old_count, "precision": "fp32"},
                            answer_ids={"FALSE": 1, "TRUE": 2})
        cohort, pointer = _routine_executable_cohort(
            self.root, self.receipt, {"manifest_sha256": "a" * 64}, self.current,
            fixture.registry, None, self.graph,
            capabilities=tuple(self.current.execution_plan.capability_map), assessment_epoch=0)
        measured = score(cohort, {row["id"]: row["gold"] for row in cohort.rows}, asdict(self.checkpoint))
        self.receipt["last_exam"] = {**pointer, "student_sha256": self.checkpoint.sha256,
            "optimizer_step": 7, "exam_rubric_sha256": pointer["rubric_sha256"],
            "scores": measured["scores"], "misses_for_teacher": []}
        return SimpleNamespace(mx=mx, optim=optim, graph=graph, staged=staged,
                               old_count=old_count, cohort=cohort)

class _BeforeMaterialization(Exception):
    pass
