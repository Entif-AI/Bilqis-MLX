"""Factory compilation and live B11 routing over current A/B/C sources."""
from __future__ import annotations

import unittest
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_readout import DecisionKind, ExecutionMode
from bilqis_mlx.runtime.atlas_model import bind_compiled_training_batch, forward_bamf
from bilqis_mlx.runtime.cognitive_solver import (
    GenerationBinding, RouteKind, SolveBudget, SolveContext, solve_task,
)
from bilqis_mlx.runtime.factory_complete_solver import factory_evaluation_instrument
from bilqis_mlx.runtime.factory_task_authority import (
    factory_task_authority, factory_task_training_goal,
)
from bilqis_mlx.runtime.task_goal_readout import (
    b11_task_goal_proposer, task_goal_route_decisions, task_goal_route_plan,
    task_goal_training_targets,
)

from .factory_training_bridge_support import FactoryTrainingBridgeFixture


class FactoryTrainingBridgeTests(FactoryTrainingBridgeFixture):
    def route_context(self, compiled):
        authority = factory_task_authority(self.context, compiled)
        plan = task_goal_route_plan(
            authority.goal, compiled, self.feature_context.snapshot,
            self.generation)
        return authority, plan

    def test_current_a_b_c_draws_bind_exact_c02_rows_into_b11(self):
        cases = (
            ("A.IDENTITY", 37101, 2),
            ("B.IDBOOLOPS", 37102, 1),
            ("C.NUMBER", 37103, 3),
        )
        for capability, seed, each in cases:
            with self.subTest(capability=capability):
                rows, prepared = self.prepare(capability, seed, each)
                self.assertEqual(len(prepared.training_batch.rows), each)
                self.assertEqual(len(prepared.compiled_rows), each)
                self.assertTrue(all(
                    batch.compiled.compiled.rows[0].positions
                    for batch in prepared.compiled_rows))
                for index, (source_row, training_row, compiled) in enumerate(zip(
                        rows, prepared.training_batch.rows,
                        prepared.compiled_rows)):
                    self.assertEqual(
                        compiled.compiled.compiled.rows[0],
                        training_row.model_input.prefix)
                    self.assertEqual(
                        compiled.training_authority.training_batch_sha256,
                        prepared.training_batch.authority_digest)
                    self.assertEqual(
                        compiled.training_authority.source_row_id, source_row["id"])
                    self.assertEqual(
                        compiled.training_authority.episode_id,
                        training_row.provenance.episode_id)
                    self.assertEqual(
                        compiled.training_authority.source_row_sha256,
                        training_row.provenance.source_row_content_sha256)
                    self.assertEqual(training_row.provenance.requested_count, each + 2)
                    self.assertEqual(training_row.provenance.delivered_count, each)
                    self.assertEqual(
                        training_row.provenance.teacher_strategy,
                        (("policy", "c02-parent-integration"),))
                    self.assertFalse(hasattr(compiled, "target"))
                    self.assertFalse(hasattr(compiled.compiled, "target"))
                    self.assertEqual(index, rows.index(source_row))

    def test_training_bridge_registers_every_compiled_row_with_source_custody(self):
        with patch.object(
                type(self.context), "register_compiled_batch",
                autospec=True) as register:
            _rows, prepared = self.prepare("A.IDENTITY", 37116, 2)
        self.assertEqual(register.call_count, len(prepared.compiled_rows))
        self.assertEqual(
            tuple(call.args[1] for call in register.call_args_list),
            prepared.compiled_rows)

    def test_b11_row_binding_rejects_sibling_row_substitution(self):
        rows, prepared = self.prepare("A.IDENTITY", 37104, 2)
        first = prepared.compiled_rows[0]
        with self.assertRaises(BilqisError):
            bind_compiled_training_batch(
                prepared.training_batch, first.compiled,
                first.sources, first.feature_schema, row_index=1)
        self.assertNotEqual(rows[0]["id"], rows[1]["id"])

    def test_current_a_b_c_score_through_one_b11_backend(self):
        parameters = self.candidate.retained_state.optimizer.parameters
        for capability, seed, each in (
                ("A.IDENTITY", 37101, 2),
                ("B.IDBOOLOPS", 37112, 1),
                ("C.NUMBER", 37103, 3)):
            with self.subTest(capability=capability):
                _, prepared = self.prepare(capability, seed, each)
                compiled = prepared.compiled_rows[0]
                _, plan = self.route_context(compiled)
                output = forward_bamf(
                    parameters, compiled, plan, ExecutionMode.INFERENCE, None)
                self.assertTrue(output.decisions)
                for decision in output.decisions:
                    self.assertTrue(bool(mx.all(mx.isfinite(decision.logits))))

    def test_live_b11_proposer_routes_source_binding_into_pure_operator(self):
        rows, prepared = self.prepare("A.IDENTITY", 37118, 1)
        compiled = prepared.compiled_rows[0]
        authority, plan = self.route_context(compiled)
        proposer = b11_task_goal_proposer(
            self.candidate.retained_state.optimizer.parameters,
            compiled, plan, authority)
        result = solve_task(
            authority.goal,
            SolveContext(authority.binding, neural_proposer=proposer),
            GenerationBinding(
                self.generation, authority.goal.semantic_release,
                authority.source_binding_sha256),
            SolveBudget(authority.goal.budget))
        receipt = result.dag_receipts[-1]
        node = authority.goal.expression_or_holes.nodes[0]
        legal = {ref.identity for ref in node.candidate_operand_refs[0]}
        self.assertIs(result.route, RouteKind.NEURAL_COMPOSITION)
        self.assertEqual(result.neural_calls, 1)
        self.assertEqual(result.local_refinement_calls, 0)
        self.assertEqual(sum(item.operation_count for item in result.dag_receipts), 1)
        self.assertEqual(receipt.executed_nodes, ("choice:root",))
        self.assertEqual(receipt.selected_bindings[0][1], "SELECT_BOOLEAN")
        self.assertIn(receipt.selected_bindings[0][2][0], legal)
        self.assertIn(result.answer.value, (False, True))
        self.assertEqual(rows[0]["capability"], "A.IDENTITY")

    def test_source_owner_mints_b10_operator_training_target(self):
        rows, prepared = self.prepare("C.ADD", 37115, 3)
        compiled = prepared.compiled_rows[0]
        authority = factory_task_authority(self.context, compiled)
        resolved = factory_task_training_goal(self.context, compiled, authority)
        targets, mask = task_goal_training_targets(authority.goal, resolved)
        route = task_goal_route_decisions(authority.goal)
        self.assertEqual(len(route), 1)
        self.assertIs(route[0].kind, DecisionKind.OPERATOR)
        self.assertEqual(targets[0].decision_id, route[0].decision_id)
        self.assertEqual(targets[0].value, "ADD")
        self.assertEqual(mask, {route[0].decision_id: True})
        self.assertEqual(rows[0]["capability"], "C.ADD")


if __name__ == "__main__":
    unittest.main()
