"""Deterministic prepared-cutover contract; transaction owners are isolated seams."""
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
        self.parameters = {"weights": [1., 2.]}
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

    def append_grade_fixture(self):
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
        self.graduate_fixture()
        return compile_candidate_successor(frontier, self.current, self.candidate_id,
            curriculum=curriculum, source_bindings=bindings, profile=CurriculumProfile.full(),
            source_registry=fixture.registry, answer_registry=fixture.answers,
            source_root=None, graph=self.graph, verification_seed=44)


class _BeforeMaterialization(Exception):
    pass


class PreparedSuccessorTests(PreparedSuccessorFixture, unittest.TestCase):
    def test_append_only_materialization_preserves_native_rows_moments_and_frontier(self):
        import mlx.core as mx
        import mlx.optimizers as optim
        import numpy as np
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
        before_weights = {name: np.array(value) for name, value in self.parameters.items()}
        before_moments = {name: {slot: np.array(self.optimizer.state[name][slot])
                                 for slot in ("m", "v")} for name in self.parameters}
        original_files = {str(path.relative_to(self.root)): path.read_bytes()
                          for path in self.root.rglob("*") if path.is_file()}
        release_sha = staged.successor.release_sha256
        with self.admitted_boundary(), \
                patch.object(optim.AdamW, "update", side_effect=AssertionError("neural optimizer update")), \
                patch.object(release_adoption._bilqis_mlx_vocabulary_growth, "extend_mlx_student",
                    wraps=release_adoption._bilqis_mlx_vocabulary_growth.extend_mlx_student) as growth, \
                patch.object(release_adoption._runtime_checkpoints, "_bundle_pointer",
                    wraps=release_adoption._runtime_checkpoints._bundle_pointer) as bundle, \
                patch.object(release_adoption._curriculum_scheduler, "adopt_appended_program",
                             side_effect=AssertionError("materializer changed topology")), \
                patch.object(release_adoption._runtime_admission, "_executable_factory_admission",
                             side_effect=AssertionError("materializer admitted a release")), \
                patch.object(release_adoption._runtime_checkpoints, "_persist",
                             side_effect=AssertionError("materializer published school state")), \
                patch("bilqis_mlx.learning.student_ops._predictions", side_effect=lambda _mx, _p, rows, *_:
                      {row["id"]: row["gold"] for row in rows}):
            result = release_adoption._materialize_prepared_successor(
                mx, self.root, self.receipt, self.checkpoint, staged.successor,
                self.graph, self.parameters, self.optimizer, graph, reserve_gib=0.)
        growth.assert_called_once_with(self.parameters, self.optimizer, self.graph, graph)
        bundle.assert_called_once()
        self.assertEqual(result.student.optimizer_step, 7)
        self.assertEqual(int(result.optimizer.state["step"].item()), 7)
        self.assertEqual(int(self.optimizer.state["step"].item()), 7)
        for name, old in before_weights.items():
            active = result.parameters[name][:old_count] if name == "embedding.weight" else result.parameters[name]
            np.testing.assert_array_equal(np.asarray(active), old)
            np.testing.assert_array_equal(np.asarray(self.parameters[name]), old)
            for slot in ("m", "v"):
                active = result.optimizer.state[name][slot]
                if name == "embedding.weight":
                    self.assertFalse(np.count_nonzero(np.asarray(active[old_count:])))
                    active = active[:old_count]
                np.testing.assert_array_equal(np.asarray(active), before_moments[name][slot])
                np.testing.assert_array_equal(np.asarray(self.optimizer.state[name][slot]), before_moments[name][slot])
        self.assertIs(result.graph, graph)
        self.assertEqual(result.rebaselined_exam["student_sha256"], result.student.sha256)
        self.assertEqual(result.rebaselined_exam["optimizer_step"], 7)
        self.assertEqual(result.rebaselined_exam["cohort_sha256"], cohort.digest)
        self.assertEqual(staged.successor.release_sha256, release_sha)
        self.assertEqual(result.growth["train_updates"], 0)
        for relative, content in original_files.items():
            self.assertEqual((self.root / relative).read_bytes(), content)
        self.assertFalse((self.root / "state.json").exists())
        self.assertFalse((self.root / "events.jsonl").exists())
        self.assertFalse((self.root / "factory-releases").exists())

    def test_unchanged_materialization_preserves_all_learner_identities_and_bytes(self):
        self.optimizer.state["moments"] = {"weights": [0.2, 0.3]}
        bundle = self.root / self.checkpoint.filename
        bundle.mkdir(parents=True)
        payload = bundle / "model-and-own-adamw.safetensors"
        payload.write_bytes(b"disposable-complete-student-and-own-adamw")
        before = deepcopy((self.parameters, self.optimizer.state))
        saved = payload.read_bytes()
        with patch.object(release_adoption._bilqis_mlx_vocabulary_growth,
                "extend_mlx_student", side_effect=AssertionError("unchanged geometry grew")), \
                patch.object(release_adoption._runtime_checkpoints, "_bundle_pointer",
                             side_effect=AssertionError("unchanged geometry wrote a bundle")):
            result = release_adoption._materialize_prepared_successor(
                None, self.root, self.receipt, self.checkpoint, self.staged.successor,
                self.graph, self.parameters, self.optimizer, deepcopy(self.graph), reserve_gib=100.)
        self.assertEqual(tuple(field.name for field in fields(result)), (
            "parameters", "optimizer", "graph", "student", "growth", "rebaselined_exam"))
        self.assertIs(result.parameters, self.parameters)
        self.assertIs(result.optimizer, self.optimizer)
        self.assertIs(result.graph, self.graph)
        self.assertIs(result.student, self.checkpoint)
        self.assertIsNone(result.growth)
        self.assertIsNone(result.rebaselined_exam)
        self.assertEqual((self.parameters, self.optimizer.state), before)
        self.assertEqual(payload.read_bytes(), saved)
        self.optimizer.update.assert_not_called()

    def test_unchanged_materialization_rejects_graph_substitution_before_writes(self):
        with patch.object(release_adoption._bilqis_mlx_vocabulary_growth,
                "extend_mlx_student", side_effect=AssertionError("growth before verification")), \
                patch.object(release_adoption._runtime_checkpoints, "_bundle_pointer",
                             side_effect=AssertionError("bundle before verification")):
            for changed in ({"tokens": list(reversed(self.graph["tokens"]))},
                            {**self.graph, "nodes": [{"meaning": "substituted"}]}):
                with self.subTest(graph=changed), self.assertRaisesRegex(ValueError, "SEMANTIC_GRAPH_DRIFT"):
                    release_adoption._materialize_prepared_successor(
                        None, self.root, self.receipt, self.checkpoint, self.staged.successor,
                        self.graph, self.parameters, self.optimizer, changed, reserve_gib=100.)
        self.assertEqual(tuple(self.root.iterdir()), ())
        self.optimizer.update.assert_not_called()

    def test_same_graph_routes_the_exact_sealed_successor_without_compiling(self):
        result_receipt = {"prepared": True}
        before = deepcopy((self.parameters, self.optimizer.state, self.receipt))
        materializations = []
        original = release_adoption._materialize_prepared_successor
        def materialize(*args, **kwargs):
            result = original(*args, **kwargs)
            materializations.append(result)
            return result
        with self.admitted_boundary(), patch.object(release_adoption,
                "_adopt_executable_profile", return_value=(
                    result_receipt, self.program, self.staged.successor, self.program)) as owner, \
                patch.object(release_adoption, "_materialize_prepared_successor",
                             side_effect=materialize) as materializer, \
                patch.object(release_adoption._runtime_checkpoints, "_bundle_pointer",
                             side_effect=AssertionError("unchanged geometry wrote bundle")), \
                patch.object(release_adoption._bilqis_mlx_vocabulary_growth, "extend_mlx_student",
                             side_effect=AssertionError("unchanged geometry grew")):
            result = self.adopt()
        materializer.assert_called_once()
        self.assertIs(materializations[0].student, materializer.call_args.args[3])
        self.assertEqual(materializations[0].student, self.checkpoint)
        self.assertEqual(result, (self.parameters, self.optimizer, self.graph,
                                  result_receipt, self.program))
        self.assertIs(owner.call_args.kwargs["compiled_successor"], self.staged.successor)
        self.assertEqual((self.parameters, self.optimizer.state, self.receipt), before)
        self.optimizer.update.assert_not_called()
        self.assertEqual(tuple(self.root.iterdir()), ())

    def test_graph_growth_routes_the_exact_sealed_successor_without_compiling(self):
        graph = {**self.graph, "tokens": [*self.graph["tokens"], "fixture.extra"]}
        staged = self.stage(graph=graph)
        expected = (self.parameters, self.optimizer, graph, {"prepared": True}, self.program)
        with self.admitted_boundary(), patch(
                "bilqis_mlx.factory.candidate_realizations.admitted_candidate_graph",
                return_value=graph), patch.object(release_adoption,
                "_adopt_catalog_profile", return_value=expected) as owner:
            self.assertEqual(self.adopt(staged), expected)
        self.assertIs(owner.call_args.kwargs["compiled_successor"], staged.successor)
        self.assertIs(owner.call_args.args[7], self.optimizer)
        self.optimizer.update.assert_not_called()

    def test_append_only_geometry_preserves_same_grade_topology(self):
        graph = {**self.graph, "tokens": [*self.graph["tokens"], "fixture.extra"]}
        staged = self.stage(graph=graph)
        sha = staged.successor.release_sha256
        self.graduate_fixture()
        observed = []
        original = release_adoption._profile_transition
        def transition(*args, **kwargs):
            result = original(*args, **kwargs)
            observed.append(result)
            return result
        with self.admitted_boundary(), patch(
                "bilqis_mlx.factory.candidate_realizations.admitted_candidate_graph",
                return_value=graph), patch.object(release_adoption._compatibility_executable_projection,
                    "legacy_course_for_profile", return_value=SimpleNamespace(version="fixture")), \
                patch("bilqis_mlx.runtime.assessment._load_executable_cohort"), \
                patch.object(release_adoption, "_profile_transition", side_effect=transition), \
                patch.object(release_adoption._curriculum_scheduler, "adopt_appended_program",
                             side_effect=AssertionError("geometry selected append-grade")), \
                patch.object(release_adoption, "_materialize_prepared_successor",
                             side_effect=_BeforeMaterialization):
            with self.assertRaises(_BeforeMaterialization):
                self.adopt(staged)
        self.assertEqual(len(observed), 1)
        state, revised, appended = observed[0]
        self.assertEqual(state.grade_index, 0)
        self.assertEqual(state.active_grades, ("Z",))
        self.assertEqual(revised, "Z")
        self.assertFalse(appended)
        epoch, history, identity = release_adoption._catalog_epoch_state(
            self.receipt, self.current, staged.successor,
            release_adoption._runtime_state._state_from_json(self.receipt["school"], self.program),
            state, SimpleNamespace(graph=graph),
            {"weights": SimpleNamespace(shape=(2,))}, (),
            allow_mastery_debt=False, appended=appended)
        self.assertIsNone(epoch)
        self.assertEqual(history, [])
        self.assertTrue(identity)
        self.assertEqual(staged.successor.release_sha256, sha)
        self.optimizer.update.assert_not_called()

    def test_unchanged_geometry_appends_grade_without_vocabulary_growth(self):
        staged = self.append_grade_fixture()
        sha = staged.successor.release_sha256
        self.assertEqual(staged.successor.transition.semantic_geometry, "UNCHANGED")
        observed = []
        original = release_adoption._profile_transition
        def transition(*args, **kwargs):
            result = original(*args, **kwargs)
            observed.append(result)
            return result
        with self.admitted_boundary(), patch.object(release_adoption._compatibility_executable_projection,
                "legacy_course_for_profile", return_value=SimpleNamespace(version="fixture")), \
                patch.object(release_adoption, "_profile_transition", side_effect=transition), \
                patch.object(release_adoption._runtime_admission, "_executable_factory_admission",
                             side_effect=_BeforeMaterialization), \
                patch.object(release_adoption._bilqis_mlx_vocabulary_growth, "extend_mlx_student",
                             side_effect=AssertionError("unchanged geometry grew vocabulary")):
            with self.assertRaises(_BeforeMaterialization):
                self.adopt(staged)
        state, revised, appended = observed[0]
        self.assertEqual(state.grade_index, 1)
        self.assertEqual(state.active_grades, ("Z", "Y"))
        self.assertIsNone(revised)
        self.assertTrue(appended)
        self.assertEqual(staged.successor.release_sha256, sha)
        self.optimizer.update.assert_not_called()

    def test_incompatible_geometry_refuses_before_any_transaction(self):
        staged = deepcopy(self.staged)
        object.__setattr__(staged.successor.transition, "semantic_geometry", "INCOMPATIBLE")
        object.__setattr__(staged.successor, "release_sha256", staged.successor.expected_digest())
        with self.admitted_boundary(), \
                patch.object(release_adoption, "_adopt_catalog_profile") as catalog, \
                patch.object(release_adoption, "_adopt_executable_profile") as profile:
            with self.assertRaises(ValueError):
                self.adopt(staged)
            catalog.assert_not_called()
            profile.assert_not_called()
        self.optimizer.update.assert_not_called()
        self.assertEqual(tuple(self.root.iterdir()), ())

    def test_changed_admitted_predecessor_cannot_substitute_a_new_successor(self):
        from bilqis_mlx.factory.executable_release import compile_executable_factory_release
        fixture = self.fixture.fixture
        changed = compile_executable_factory_release(
            self.current.curriculum, self.current.source_bindings, self.current.profile,
            fixture.registry, fixture.answers, source_root=None, graph=self.graph,
            verification_seed=97)
        with self.admitted_boundary(), patch.object(release_adoption._runtime_admission,
                "_require_executable_factory_admission", return_value=changed), \
                patch.object(release_adoption, "_adopt_executable_profile") as owner:
            with self.assertRaisesRegex(ValueError, "PREDECESSOR_DRIFT"):
                self.adopt()
            owner.assert_not_called()
        self.optimizer.update.assert_not_called()

    def test_jit_revalidates_before_entering_the_prepared_transaction(self):
        plan = compile_autonomy_plan(self.current)
        ledger = initial_evidence_ledger(self.current, plan=plan)
        proposal = propose_curriculum_delta(
            self.frontier, self.current, ledger, plan,
            self.checkpoint.sha256, self.checkpoint.optimizer_step,
            candidate_bindings=(self.staged.binding,))
        session = SimpleNamespace(resolve_ready_proposal=Mock(side_effect=lambda cp, prop:
            resolve_ready_candidate(self.frontier, self.current, ledger, plan,
                                    cp, prop, (self.staged,))))
        expected = (self.parameters, self.optimizer, self.graph, self.receipt, self.program)
        before = deepcopy((self.parameters, self.optimizer.state, self.receipt))
        with self.admitted_boundary(), patch.object(release_adoption._source_adapters_school,
                "live_source_registry", return_value=self.fixture.fixture.registry), \
                patch.object(release_adoption._factory_live_answers, "live_answer_registry",
                             return_value=self.fixture.fixture.answers), \
                patch.object(release_adoption, "_adopt_prepared_successor",
                             return_value=expected) as entry:
            result = release_adoption._adopt_jit_proposal(
                None, self.root, self.receipt, None, None, self.graph,
                self.parameters, self.optimizer, session, proposal, reserve_gib=100.)
        self.assertEqual(result, expected)
        session.resolve_ready_proposal.assert_called_once_with(self.checkpoint, proposal)
        self.assertIs(entry.call_args.args[8], self.staged)
        self.assertEqual((self.parameters, self.optimizer.state, self.receipt), before)
        self.optimizer.update.assert_not_called()
        self.assertEqual(ledger.receipts, ())
