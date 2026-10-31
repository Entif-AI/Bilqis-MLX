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

        def test_common_tail_commits_once_and_replays_only_delivery_after_crash(self):
            import json
            from bilqis_mlx import state_dag
            original_current, original_program = self.current, self.program
            for growing in (False, True):
                for appended in (False, True):
                    for delivered in (False, True):
                        with self.subTest(growing=growing, appended=appended, delivered=delivered), \
                                tempfile.TemporaryDirectory() as temporary:
                            root = Path(temporary)
                            self.current, self.program = original_current, original_program
                            graph = ({**self.graph, "tokens": [*self.graph["tokens"], "fixture.extra"]}
                                     if growing else self.graph)
                            staged = (self.append_grade_fixture(graph) if appended
                                      else self.stage(graph=graph))
                            self.graduate_fixture()
                            self.receipt["last_exam"].update(
                                exam_rubric_sha256="c" * 64, cohort_sha256="d" * 64)
                            self.receipt.update(generation=0, run_id="prepared-disposable",
                                config={"vocab_size": len(self.graph["tokens"])},
                                parameter_shapes={"weights": [2]}, model_bundle=self.checkpoint.filename)
                            materialized_student = (replace(self.checkpoint, sha256="f" * 64,
                                filename="bundles/grown") if growing else self.checkpoint)
                            materialized = release_adoption.PreparedSuccessorMaterialization(
                                self.parameters, self.optimizer, graph, materialized_student,
                                {"train_updates": 0} if growing else None,
                                {"rebaselined": True} if growing else None)
                            checkpoint = release_adoption._runtime_checkpoints
                            reconcile = checkpoint._reconcile_delivery_outbox
                            def interrupt(run_dir, record):
                                if delivered:
                                    reconcile(run_dir, record)
                                raise _BeforeMaterialization("publication interrupted")
                            with self.admitted_boundary(), patch(
                                    "bilqis_mlx.factory.candidate_realizations.admitted_candidate_graph",
                                    return_value=graph), patch.object(release_adoption,
                                    "_materialize_prepared_successor", return_value=materialized) as materializer, \
                                    patch.object(release_adoption._compatibility_executable_projection,
                                    "legacy_course_for_profile", return_value=SimpleNamespace(version="fixture")), \
                                    patch.object(release_adoption._runtime_admission,
                                    "_executable_factory_admission",
                                    wraps=release_adoption._runtime_admission._executable_factory_admission) as admission, \
                                    patch.object(checkpoint, "_persist", wraps=checkpoint._persist) as persist, \
                                    patch.object(checkpoint, "_reconcile_delivery_outbox", side_effect=interrupt):
                                with self.assertRaises(_BeforeMaterialization):
                                    release_adoption._adopt_prepared_successor(
                                        None, root, self.receipt, None, None, self.graph,
                                        self.parameters, self.optimizer, staged, reserve_gib=100.)
                            materializer.assert_called_once()
                            admission.assert_called_once()
                            persist.assert_called_once()
                            self.assertIs(admission.call_args.args[1], staged.successor)
                            saved = state_dag.read_current(root)
                            self.assertEqual(saved["generation"], 1)
                            self.assertEqual(saved["school"]["current_student"], asdict(materialized_student))
                            self.assertEqual(saved["factory_release_sha256"], staged.successor.release_sha256)
                            self.assertEqual(saved["semantic_graph_sha256"],
                                             release_adoption._runtime_state._fingerprint(graph))
                            self.assertEqual(saved["config"]["vocab_size"], len(graph["tokens"]))
                            self.assertEqual(saved["championship_school_identity"]["semantic_graph_sha256"],
                                             saved["semantic_graph_sha256"])
                            with patch.object(release_adoption, "_materialize_prepared_successor",
                                    side_effect=AssertionError("repeated materialization")), \
                                    patch.object(release_adoption._runtime_admission, "_executable_factory_admission",
                                    side_effect=AssertionError("repeated admission")), \
                                    patch.object(checkpoint, "_persist", side_effect=AssertionError("second generation")):
                                reconcile(root, saved)
                                recovered = state_dag.read_current(root)
                                bytes_after_first_recovery = {
                                    str(path.relative_to(root)): path.read_bytes()
                                    for path in root.rglob("*") if path.is_file()}
                                self.assertEqual(recovered, saved)
                                reconcile(root, recovered)
                                self.assertEqual(state_dag.read_current(root), saved)
                                self.assertEqual(
                                    {str(path.relative_to(root)): path.read_bytes()
                                     for path in root.rglob("*") if path.is_file()},
                                    bytes_after_first_recovery)
                            self._assert_committed_transition(
                                root, saved, graph, growing, appended, staged, materialized, materialized_student)

        def test_both_geometries_use_the_common_commit_tail(self):
            for growing in (False, True):
                with self.subTest(growing=growing):
                    graph = ({**self.graph, "tokens": [*self.graph["tokens"], "fixture.extra"]}
                             if growing else self.graph)
                    staged = self.stage(graph=graph)
                    materialized = release_adoption.PreparedSuccessorMaterialization(
                        self.parameters, self.optimizer, graph, self.checkpoint,
                        {"train_updates": 0} if growing else None, None)
                    with self.admitted_boundary(), patch(
                            "bilqis_mlx.factory.candidate_realizations.admitted_candidate_graph",
                            return_value=graph), patch.object(release_adoption,
                            "_materialize_prepared_successor", return_value=materialized) as materializer, \
                            patch.object(release_adoption._compatibility_executable_projection,
                            "legacy_course_for_profile", return_value=SimpleNamespace(version="fixture")), \
                            patch.object(release_adoption, "_commit_prepared_successor",
                                         return_value={"prepared": True}) as commit, \
                            patch.object(release_adoption, "_adopt_executable_profile",
                                         side_effect=AssertionError("separate profile tail")), \
                            patch.object(release_adoption, "_adopt_catalog_profile",
                                         side_effect=AssertionError("separate catalog tail")):
                        result = self.adopt(staged)
                    materializer.assert_called_once()
                    commit.assert_called_once()
                    self.assertIs(commit.call_args.args[3], staged.successor)
                    self.assertIs(commit.call_args.args[8], materialized)
                    self.assertEqual(result, (self.parameters, self.optimizer, graph,
                                              {"prepared": True}, SimpleNamespace(version="fixture")))
                    self.optimizer.update.assert_not_called()
