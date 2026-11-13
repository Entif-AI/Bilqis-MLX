"""Unchanged-geometry materialization and JIT entry guards."""
from copy import deepcopy
from dataclasses import fields
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from bilqis_mlx.factory.autonomy import compile_autonomy_plan, initial_evidence_ledger
from bilqis_mlx.factory.jit_curriculum import propose_curriculum_delta
from bilqis_mlx.runtime import release_adoption
from bilqis_mlx.runtime.jit_adoption import resolve_ready_candidate
from bilqis_mlx.runtime.tests.admission.prepared_successor_fixtures import (
    PreparedSuccessorFixture,
)


class PreparedSuccessorTests(PreparedSuccessorFixture, unittest.TestCase):
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
