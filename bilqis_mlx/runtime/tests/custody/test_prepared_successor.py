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

        def test_append_only_materialization_preserves_native_rows_moments_and_frontier(self):
            import numpy as np
            native = self.prepare_native_same_grade_growth()
            mx, optim, graph, staged, old_count, cohort = (
                native.mx, native.optim, native.graph, native.staged,
                native.old_count, native.cohort)
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

        def test_same_grade_native_growth_adopts_exact_staged_release_without_append_grade(self):
            import numpy as np
            from bilqis_mlx import state_dag

            native = self.prepare_native_same_grade_growth()
            mx, optim, graph, staged, old_count = (
                native.mx, native.optim, native.graph, native.staged, native.old_count)
            _, release_file, admission = (
                release_adoption._runtime_admission._executable_factory_admission(
                    self.root, self.current, self.checkpoint,
                    release_adoption._runtime_state._fingerprint(self.graph), self.graph))
            self.receipt.update(
                generation=0,
                factory_release_sha256=self.current.release_sha256,
                factory_release_file=release_file,
                factory_release_schema=self.current.schema,
                factory_admission_v2=asdict(admission),
            )
            prepared_sha = staged.successor.release_sha256
            old_weights = {name: np.array(value) for name, value in self.parameters.items()}
            old_moments = {name: {slot: np.array(self.optimizer.state[name][slot])
                                  for slot in ("m", "v")}
                           for name in self.parameters}
            with patch.object(release_adoption._compatibility_executable_projection,
                              "legacy_course_for_profile",
                              return_value=SimpleNamespace(version="fixture")), \
                    patch("bilqis_mlx.factory.candidate_realizations.admitted_candidate_graph",
                          return_value=graph), \
                    patch("bilqis_mlx.learning.student_ops._predictions",
                          side_effect=lambda _mx, _parameters, rows, *_:
                          {row["id"]: row["gold"] for row in rows}), \
                    patch.object(optim.AdamW, "update",
                                 side_effect=AssertionError("neural optimizer update")), \
                    patch.object(release_adoption._curriculum_scheduler,
                                 "adopt_appended_program",
                                 side_effect=AssertionError("same grade became append grade")):
                parameters, optimizer, next_graph, record, _ = (
                    release_adoption._adopt_prepared_successor(
                        mx, self.root, self.receipt, None, None, self.graph,
                        self.parameters, self.optimizer, staged, reserve_gib=0.))
            self.assertEqual(record["factory_release_sha256"], prepared_sha)
            self.assertEqual(next_graph, graph)
            self.assertEqual(record["school"]["grade_index"], 0)
            self.assertEqual(record["school"]["active_grades"], ["Z"])
            self.assertEqual(parameters["embedding.weight"].shape[0], old_count + 1)
            for name, old in old_weights.items():
                active = parameters[name][:old_count] if name == "embedding.weight" else parameters[name]
                np.testing.assert_array_equal(np.asarray(active), old)
                np.testing.assert_array_equal(np.asarray(self.parameters[name]), old)
                for slot in ("m", "v"):
                    active = optimizer.state[name][slot]
                    if name == "embedding.weight":
                        self.assertFalse(np.count_nonzero(np.asarray(active[old_count:])))
                        active = active[:old_count]
                    np.testing.assert_array_equal(np.asarray(active), old_moments[name][slot])
            self.assertEqual(int(optimizer.state["step"].item()), 7)
            self.assertEqual(int(self.optimizer.state["step"].item()), 7)
            self.assertEqual(state_dag.read_current(self.root), record)
            reread = release_adoption._runtime_admission._require_executable_factory_admission(
                self.root, record, graph)
            self.assertEqual(reread.release_sha256, prepared_sha)
