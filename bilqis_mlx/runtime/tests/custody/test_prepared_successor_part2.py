"""Structural test shard from test_prepared_successor.py; assertions preserved."""
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
from bilqis_mlx.runtime.tests.custody.test_prepared_successor_helpers import (PreparedSuccessorFixture, _BeforeMaterialization)

class PreparedSuccessorTests(PreparedSuccessorFixture, unittest.TestCase):
        def _assert_committed_transition(self, root, saved, graph, growing, appended, staged, materialized, materialized_student):
            import json
            events = [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()]
            self.assertEqual(events, saved["delivery_outbox"])
            self.assertEqual(len(events), 1)
            event = events[0]
            self.assertEqual(event["actual_neural_updates"], 0)
            if growing:
                self.assertEqual(event["event"], "SCHOOL_SEMANTIC_CATALOG_PROFILE_ADOPTED")
                self.assertEqual(event["growth"], materialized.growth)
                self.assertEqual(event["previous_student_sha256"], self.checkpoint.sha256)
                self.assertEqual(saved["last_exam"], materialized.rebaselined_exam)
            else:
                self.assertEqual(event["event"], "SCHOOL_EXECUTION_PROFILE_ADOPTED")
                self.assertEqual(event["transition_kind"],
                                 "APPEND_GRADE" if appended else "REVISE_PROFILE")
            self.assertEqual(event["generation"], 1)
            self.assertEqual(event["grade"], "Y" if appended else "Z")
            self.assertEqual(event["factory_release_sha256"], staged.successor.release_sha256)
            self.assertEqual(event["optimizer_step"], materialized_student.optimizer_step)
            if growing:
                self.assertEqual(event["semantic_geometry"], "APPEND_ONLY_EXPANSION")
            else:
                self.assertEqual(event["previous_factory_release_sha256"], self.current.release_sha256)
                self.assertEqual(event["revised_grade"], None if appended else "Z")
                self.assertFalse(event["debt_admission"])
                self.assertEqual(event["carried_mastery_debt"], [])
            self.assertEqual(event["student_sha256"], materialized_student.sha256)
            self.optimizer.update.assert_not_called()

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
