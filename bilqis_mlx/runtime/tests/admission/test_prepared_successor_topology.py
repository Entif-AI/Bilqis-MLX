"""Prepared release readiness and grade topology remain independent of geometry."""
from copy import deepcopy
from dataclasses import asdict
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from bilqis_mlx.runtime import release_adoption
from bilqis_mlx.runtime.tests.admission.prepared_successor_fixtures import (
    PreparedSuccessorFixture, _BeforeMaterialization,
)


class PreparedTopologyTests(PreparedSuccessorFixture, unittest.TestCase):
    def test_same_abi_prepared_release_waits_for_readiness_then_adopts_exact_sha(self):
        """A staged same-ABI release becomes active only after boundary evidence."""
        from bilqis_mlx import state_dag

        staged = self.append_grade_fixture(ready=False)
        self.assertEqual(staged.successor.transition.semantic_geometry, "UNCHANGED")
        prepared_sha = staged.successor.release_sha256
        _, release_file, admission = (
            release_adoption._runtime_admission._executable_factory_admission(
                self.root, self.current, self.checkpoint,
                release_adoption._runtime_state._fingerprint(self.graph), self.graph))
        self.receipt.update(
            generation=0,
            run_id="same-abi-prepared-fixture",
            config={"vocab_size": len(self.graph["tokens"])},
            parameter_shapes={name: list(value.shape)
                              for name, value in self.parameters.items()},
            factory_release_sha256=self.current.release_sha256,
            factory_release_file=release_file,
            factory_release_schema=self.current.schema,
            factory_admission_v2=asdict(admission),
            source_manifest_sha256="a" * 64,
            semantic_graph_sha256=release_adoption._runtime_state._fingerprint(self.graph),
        )
        before = deepcopy((self.parameters, self.optimizer.state, self.graph))
        baseline_files = {str(path.relative_to(self.root)): path.read_bytes()
                          for path in self.root.rglob("*") if path.is_file()}
        with patch.object(release_adoption._compatibility_executable_projection,
                          "legacy_course_for_profile",
                          return_value=SimpleNamespace(version="fixture")), \
                patch.object(release_adoption._factory_executable_release,
                             "compile_executable_factory_release",
                             side_effect=AssertionError("recompiled")), \
                patch.object(release_adoption._factory_executable_release,
                             "compile_successor_profile_release",
                             side_effect=AssertionError("recompiled")):
            with self.assertRaisesRegex(
                    ValueError, "FACTORY_PROFILE_EXPANSION_NOT_AT_GRADE_BOUNDARY"):
                self.adopt(staged)
            self.assertEqual(
                {str(path.relative_to(self.root)): path.read_bytes()
                 for path in self.root.rglob("*") if path.is_file()}, baseline_files)
            self.assertEqual((self.parameters, self.optimizer.state, self.graph), before)
            self.optimizer.update.assert_not_called()
            established = self.receipt
            self.graduate_fixture()
            readiness = self.receipt
            self.receipt = {**established,
                            "school": readiness["school"],
                            "last_exam": {**readiness["last_exam"],
                                          "exam_rubric_sha256": "b" * 64,
                                          "cohort_sha256": "c" * 64}}
            parameters, optimizer, graph, record, _ = self.adopt(staged)
        self.assertEqual(record["factory_release_sha256"], prepared_sha)
        self.assertIs(parameters, self.parameters)
        self.assertIs(optimizer, self.optimizer)
        self.assertEqual(graph, self.graph)
        self.assertEqual((self.parameters, self.optimizer.state, self.graph), before)
        self.optimizer.update.assert_not_called()
        self.assertEqual(state_dag.read_current(self.root), record)
        reread = release_adoption._runtime_admission._require_executable_factory_admission(
            self.root, record, self.graph)
        self.assertEqual(reread.release_sha256, prepared_sha)

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
                    return_value=release_adoption.PreparedSuccessorMaterialization(
                        self.parameters, self.optimizer, graph, self.checkpoint, {}, None)), \
                patch.object(release_adoption._runtime_admission, "_executable_factory_admission",
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
