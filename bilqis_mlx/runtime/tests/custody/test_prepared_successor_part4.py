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
