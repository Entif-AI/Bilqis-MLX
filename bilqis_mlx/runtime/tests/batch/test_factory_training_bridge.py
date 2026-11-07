"""Parent C02 Factory-to-B11 integration over current A/B/C sources."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import mlx.core as mx
from mlx.utils import tree_flatten

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.teaching import describe_delivered_teaching
from bilqis_mlx.learning.atlas_readout import DecisionOutput, ExecutionMode
from bilqis_mlx.learning.source_atoms.tests.backbone_test_support import (
    SourceBackboneTestBase,
)
from bilqis_mlx.runtime.atlas_model import (
    bamf_value_and_grad, bind_compiled_training_batch, forward_bamf,
)
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.bamf_bundle import (
    authenticate_bamf_candidate_feature_context,
)
from bilqis_mlx.runtime.factory_complete_solver import factory_evaluation_instrument
from bilqis_mlx.runtime.factory_task_authority import factory_task_authority
from bilqis_mlx.runtime.factory_training_bridge import (
    prepare_factory_training_batch,
)
from bilqis_mlx.runtime.atlas_training_adapter import pad_microbatches
from bilqis_mlx.runtime.task_goal_readout import (
    task_goal_route_decisions, task_goal_route_plan,
)
from bilqis_mlx.runtime.tests.capability.factory.retention.factory_retention_live_support import (
    genesis_bundle, live_factory_context,
)
from bilqis_mlx.semantics.atlas.feature_io import persist_feature_manifest


class FactoryTrainingBridgeTests(SourceBackboneTestBase):
    def setUp(self):
        artifact = os.environ.get("BILQIS_A01_ATLAS_BUNDLE")
        if not artifact:
            self.skipTest("BILQIS_A01_ATLAS_BUNDLE fixture is not mounted")
        self.artifact = Path(artifact)
        if not self.artifact.is_dir():
            self.skipTest("BILQIS_A01_ATLAS_BUNDLE fixture is not mounted")
        super().setUp()
        self.root = Path.cwd()
        self.context, _ = live_factory_context(
            self.root, (self.root / "vendor/legacy-v16").resolve())
        self.candidate, _ = genesis_bundle(
            self, self.snapshot, self.schema, self.artifact)
        authenticated = authenticate_bamf_candidate_feature_context(
            self.candidate, str(self.artifact))
        self.feature_root = TemporaryDirectory()
        self.addCleanup(self.feature_root.cleanup)
        self.feature_receipt = persist_feature_manifest(
            authenticated.features, self.feature_root.name)
        self.generation = execution_generation_digest(
            self.candidate.retained_state.optimizer.parameters,
            spec=self.candidate.topology, extents=self.candidate.extents)
        self.feature_context = authenticate_bamf_candidate_feature_context(
            self.candidate, str(self.artifact))

    def prepare(self, capability, seed, each):
        rows = tuple(self.context.draw_rows(
            seed=seed, capability=capability, each=each))
        execution = self.context.release.execution_plan.capability_map[capability]
        delivery = describe_delivered_teaching(
            self.context.release, capability,
            execution.teaching_option_ids[0], rows)
        return rows, prepare_factory_training_batch(
            self.context, self.candidate, str(self.artifact),
            self.feature_receipt.path, rows, self.generation,
            capability=capability, delivery=delivery, requested_count=each + 2,
            source_seed=seed, source_each=each,
            optimizer_step_seed=7,
            teacher_strategy={"policy": "c02-parent-integration"})

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
                        compiled.training_authority.source_row_id,
                        source_row["id"])
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

    def test_b11_row_binding_rejects_sibling_row_substitution(self):
        rows, prepared = self.prepare("A.IDENTITY", 37104, 2)
        first = prepared.compiled_rows[0]
        with self.assertRaises(BilqisError):
            bind_compiled_training_batch(
                prepared.training_batch, first.compiled,
                first.sources, first.feature_schema, row_index=1)
        self.assertNotEqual(rows[0]["id"], rows[1]["id"])

    def route_context(self, compiled):
        authority = factory_task_authority(self.context, compiled)
        plan = task_goal_route_plan(
            authority.goal, compiled, self.feature_context.snapshot,
            self.generation)
        return authority, plan

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

    def test_disposable_gradient_is_finite_and_target_cannot_change_logits(self):
        seed = 37114
        rows, prepared = self.prepare("B.IDBOOLOPS", seed, 1)
        compiled = prepared.compiled_rows[0]
        authority, plan = self.route_context(compiled)
        route = task_goal_route_decisions(authority.goal)
        self.assertEqual(len(route), 1)
        case = factory_evaluation_instrument(
            self.context, self.candidate, str(self.artifact), rows[0],
            source_seed=seed, source_each=1).case
        node = authority.goal.expression_or_holes.nodes[0]
        handle = next(
            item.typed.source_handle for item in authority.binding.operands
            if item.typed.type_name == case.gold.type_name
            and item.typed.value == case.gold.value)
        correct = next(
            item.identity for item in node.candidate_operand_refs[0]
            if item.source_handle == handle)
        alternatives = tuple(value for value in route[0].legal_values
                             if value != correct)
        self.assertTrue(alternatives)
        parameters = dict(self.candidate.retained_state.optimizer.parameters)
        mask = {route[0].decision_id: True}
        first = bamf_value_and_grad(
            parameters, compiled, plan,
            (DecisionOutput(route[0].decision_id, correct),), mask, None)
        second = bamf_value_and_grad(
            parameters, compiled, plan,
            (DecisionOutput(route[0].decision_id, alternatives[0]),), mask, None)
        first_logits = first.execution.output.decisions[0].logits
        second_logits = second.execution.output.decisions[0].logits
        self.assertTrue(bool(mx.array_equal(first_logits, second_logits)))
        self.assertNotEqual(float(first.loss_total.item()), float(second.loss_total.item()))
        for _, gradient in tree_flatten(first.gradients):
            self.assertTrue(bool(mx.all(mx.isfinite(gradient))))
        updated = {
            name: parameters[name] - mx.array(1e-6) * first.gradients[name]
            for name in parameters
        }
        mx.eval(updated)
        self.assertTrue(all(
            bool(mx.all(mx.isfinite(value))) for value in updated.values()))
        self.assertTrue(any(
            not bool(mx.array_equal(updated[name], parameters[name]))
            for name in parameters))

    def test_real_rows_pack_to_actual_maximum_without_identity_loss(self):
        rows, prepared = self.prepare("A.IDENTITY", 37101, 2)
        lengths = tuple(len(row.model_input.prefix.positions)
                        for row in prepared.training_batch.rows)
        packed = pad_microbatches(
            prepared.training_batch, {}, None,
            plan_microbatches=lambda batch_rows, topology, budget: ((0, 1),),
            indices_for_plan=lambda plan: plan,
            positions_for=lambda prefix: prefix.positions)
        self.assertEqual(len(packed), 1)
        self.assertEqual(len(packed[0].positions[0]), max(lengths))
        self.assertEqual(
            tuple(row.provenance.row_id for row in prepared.training_batch.rows),
            tuple(row["id"] for row in rows))
        self.assertEqual(
            tuple(sum(mask) for mask in packed[0].padding_mask), lengths)


if __name__ == "__main__":
    unittest.main()
