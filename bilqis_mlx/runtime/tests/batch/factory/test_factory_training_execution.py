"""Factory gradient, candidate-step, and accepted C09 custody integration."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import mlx.core as mx
from mlx.utils import tree_flatten

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.teaching import describe_delivered_teaching
from bilqis_mlx.learning.atlas_readout import DecisionOutput
from bilqis_mlx.learning.tests.test_frame_encoder import FrameEncoderTests
from bilqis_mlx.learning.student_ops import train_bamf_factory_step
from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
from bilqis_mlx.runtime.atlas_model import bamf_value_and_grad
from bilqis_mlx.runtime.atlas_resources import (
    MemoryBudget, ResourceRow, estimate_row_activation_bytes,
)
from bilqis_mlx.runtime.atlas_training_adapter import pad_microbatches
from bilqis_mlx.runtime.bamf_bundle import publish_initial_generation
from bilqis_mlx.runtime.bamf_bundle.admission import (
    load_accepted_generation,
)
from bilqis_mlx.runtime.factory_candidate_training import (
    FactoryDeliveryObservation, _frame_stats,
)
from bilqis_mlx.runtime.factory_complete_solver import factory_evaluation_instrument
from bilqis_mlx.runtime.factory_task_authority import factory_task_authority
from bilqis_mlx.runtime.model_topology_v2 import bamf_parameter_census
from bilqis_mlx.runtime.task_goal_readout import (
    task_goal_route_decisions, task_goal_route_plan,
)
from bilqis_mlx.runtime.teacher_observation_capture import (
    ObservationCapture, read_sidecar, store_sidecar,
)
from bilqis_mlx.runtime.tests.capability.factory.retention.factory_retention_live_support import HP
from bilqis_mlx.runtime.tests.test_atlas_revalidation import AUTHORITY, _event
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef

from bilqis_mlx.runtime.tests.batch.training.visit_provenance_support import (
    visit_provenance,
)

from .factory_training_bridge_support import FactoryTrainingBridgeFixture


class FactoryResourcePlanningCustodyTests(unittest.TestCase):
    def test_held_packed_frame_cannot_feed_resource_stats(self):
        fixture = FrameEncoderTests()
        fixture.setUp()
        compiled, _vectors, _ast = fixture.compiled_inputs()
        owner = compiled.packed_frame_artifact_owner
        source = next(
            ref for node in owner.index.nodes
            for ref in node.immediate_dependencies
            if ref.kind is DependencyKind.SOURCE)
        owner.apply_correction(_event(source), AUTHORITY)

        with self.assertRaises(BilqisError) as caught:
            _frame_stats(SimpleNamespace(compiled=compiled))
        self.assertEqual(caught.exception.context["reason"], "BAMF_C09_ARTIFACT_HELD")


class FactoryTrainingExecutionTests(FactoryTrainingBridgeFixture):
    def route_context(self, compiled):
        authority = factory_task_authority(self.context, compiled)
        plan = task_goal_route_plan(
            authority.goal, compiled, self.feature_context.snapshot,
            self.generation)
        return authority, plan

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
        alternatives = tuple(value for value in route[0].legal_values if value != correct)
        self.assertTrue(alternatives)
        parameters = dict(self.candidate.retained_state.optimizer.parameters)
        mask = {route[0].decision_id: True}
        first = bamf_value_and_grad(
            parameters, compiled, plan,
            (DecisionOutput(route[0].decision_id, correct),), mask, None)
        second = bamf_value_and_grad(
            parameters, compiled, plan,
            (DecisionOutput(route[0].decision_id, alternatives[0]),), mask, None)
        self.assertTrue(bool(mx.array_equal(
            first.execution.output.decisions[0].logits,
            second.execution.output.decisions[0].logits)))
        self.assertNotEqual(float(first.loss_total.item()), float(second.loss_total.item()))
        for _, gradient in tree_flatten(first.gradients):
            self.assertTrue(bool(mx.all(mx.isfinite(gradient))))
        updated = {
            name: parameters[name] - mx.array(1e-6) * first.gradients[name]
            for name in parameters
        }
        mx.eval(updated)
        self.assertTrue(all(bool(mx.all(mx.isfinite(value))) for value in updated.values()))
        self.assertTrue(any(
            not bool(mx.array_equal(updated[name], parameters[name])) for name in parameters))

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
        self.assertEqual(tuple(sum(mask) for mask in packed[0].padding_mask), lengths)

    def test_student_ops_executes_one_real_factory_candidate_step_and_records_cost(self):
        rows, delivery = self._draw("B.IDBOOLOPS", 37116, 1)
        with TemporaryDirectory() as run_dir_value:
            run_dir = Path(run_dir_value)
            self._publish(run_dir)
            source_context = self.accepted_source_context(run_dir)
            parent = load_accepted_generation(run_dir)
            capture = ObservationCapture(run_dir, {})
            capture.attempt_id = "c02-parent-step"
            capture.proposal_id = store_sidecar(
                run_dir, {"attempt_id": capture.attempt_id})["sha256"]
            capture.select_option("B.IDBOOLOPS", None)
            observation = FactoryDeliveryObservation(capture, 1, rows, 37116)
            result = train_bamf_factory_step(
                run_dir, source_context, parent, str(self.artifact),
                self.feature_receipt.path, rows,
                capability="B.IDBOOLOPS", delivery=delivery,
                requested_count=2, source_seed=37116, source_each=1,
                optimizer_step_seed=17,
                visit_provenance=visit_provenance("B.IDBOOLOPS"),
                teacher_strategy={"policy": "c02-parent-production"},
                teacher_hparams=HP, max_norm=1.0, observation=observation)
            self.assertEqual(result.transaction.update_steps, 1)
            self.assertEqual(result.resource_plan.groups, ((0,),))
            self.assertEqual(len(result.route_targets), 1)
            self.assertEqual(result.realized_cost["optimizer_steps"], 1)
            payload = read_sidecar(run_dir, capture.steps[0])
            self.assertEqual(
                payload["positions"][0]["row"]["sha256"],
                store_sidecar(run_dir, rows[0])["sha256"])
            self.assertEqual(payload["controls"]["realized_cost"]["optimizer_steps"], 1)

    def test_persisted_correction_holds_training_batch_before_gradient_read(self):
        rows, delivery = self._draw("B.IDBOOLOPS", 37118, 1)
        correction = _event(DependencyRef(
            DependencyKind.SOURCE,
            "source:" + self.feature_context.features.source_bundle_id))
        with TemporaryDirectory() as run_dir_value:
            run_dir = Path(run_dir_value)
            self._publish(run_dir)
            source_context = self.accepted_source_context(run_dir)
            AcceptedRuntimeHost(run_dir).record_correction(correction)
            parent = load_accepted_generation(run_dir)
            observation = FactoryDeliveryObservation(
                ObservationCapture(run_dir, {}), 1, rows, 37118)
            with self.assertRaises(BilqisError) as caught:
                train_bamf_factory_step(
                    run_dir, source_context, parent, str(self.artifact),
                    self.feature_receipt.path, rows,
                    capability="B.IDBOOLOPS", delivery=delivery,
                    requested_count=2, source_seed=37118, source_each=1,
                    optimizer_step_seed=19,
                    visit_provenance=visit_provenance("B.IDBOOLOPS"),
                    teacher_strategy={"policy": "c09-correction-hold"},
                    teacher_hparams=HP, max_norm=1.0, observation=observation)
            self.assertEqual(caught.exception.context["reason"], "BAMF_C09_ARTIFACT_HELD")

    def test_production_step_accumulates_split_real_rows_into_one_optimizer_step(self):
        rows, delivery = self._draw("A.IDENTITY", 37117, 2)
        with TemporaryDirectory() as run_dir_value:
            run_dir = Path(run_dir_value)
            self._publish(run_dir)
            source_context = self.accepted_source_context(run_dir)
            parent = load_accepted_generation(run_dir)
            prepared = self.prepare("A.IDENTITY", 37117, 2)[1]
            row_ids = tuple(row["id"] for row in rows)
            self.assertEqual(
                tuple(row.provenance.row_id for row in prepared.training_batch.rows),
                row_ids,
            )
            self.assertEqual(
                tuple(
                    compiled.training_authority.source_row_id
                    for compiled in prepared.compiled_rows
                ),
                row_ids,
            )
            self.assertTrue(all(
                compiled.training_authority.training_batch_sha256
                == prepared.training_batch.authority_digest
                for compiled in prepared.compiled_rows
            ))
            self.assertEqual(
                tuple(
                    compiled.training_authority.source_row_sha256
                    for compiled in prepared.compiled_rows
                ),
                tuple(
                    row.provenance.source_row_content_sha256
                    for row in prepared.training_batch.rows
                ),
            )
            default_budget = MemoryBudget(
                bamf_parameter_census(parent.topology, parent.extents))
            resource_rows = tuple(
                ResourceRow.from_training_row(
                    training_row, _frame_stats(compiled),
                    generation_binding=prepared.training_batch.generation_binding,
                    delivered_content_sha256=(
                        prepared.training_batch.delivered_content_sha256),
                )
                for training_row, compiled in zip(
                    prepared.training_batch.rows, prepared.compiled_rows))
            one_row_peak = max(
                estimate_row_activation_bytes(item, parent.topology)
                for item in resource_rows)
            split_budget = replace(
                default_budget,
                allocation_bytes=(
                    default_budget.resident_bytes
                    + default_budget.activation_safety_factor * one_row_peak),
            )
            observation = FactoryDeliveryObservation(
                ObservationCapture(run_dir, {}), 1, rows, 37117)
            result = train_bamf_factory_step(
                run_dir, source_context, parent, str(self.artifact),
                self.feature_receipt.path, rows,
                capability="A.IDENTITY", delivery=delivery,
                requested_count=2, source_seed=37117, source_each=2,
                optimizer_step_seed=18,
                visit_provenance=visit_provenance("A.IDENTITY"),
                teacher_strategy={"policy": "c02-parent-production"},
                teacher_hparams=HP, max_norm=1.0, observation=observation,
                memory_budget=split_budget)
            self.assertEqual(result.resource_plan.groups, ((0,), (1,)))
            self.assertEqual(result.resource_plan.logical_row_ids, row_ids)
            self.assertEqual(
                tuple(
                    row.provenance.row_id
                    for row in result.prepared.training_batch.rows
                ),
                row_ids,
            )
            self.assertEqual(len(result.gradient_execution.loss_executions), 2)
            self.assertEqual(
                result.gradient_execution.source_digest,
                result.resource_plan.source_digest,
            )
            row_authorities = tuple(
                execution.training_authority
                for execution in result.gradient_execution.loss_executions
            )
            self.assertEqual(
                tuple(authority.source_row_id for authority in row_authorities),
                row_ids,
            )
            self.assertEqual(
                tuple(authority.source_row_sha256 for authority in row_authorities),
                tuple(
                    row.provenance.source_row_content_sha256
                    for row in prepared.training_batch.rows
                ),
            )
            self.assertEqual(
                tuple(authority.digest for authority in row_authorities),
                tuple(
                    compiled.training_authority.digest
                    for compiled in result.prepared.compiled_rows
                ),
            )
            self.assertEqual(result.transaction.update_steps, 1)
            self.assertEqual(len(result.transaction.step_proofs), 1)
            self.assertEqual(len(result.transaction.training_authorities), 1)
            authority = result.transaction.training_authorities[0]
            self.assertEqual(
                tuple(member.source_row_id for member in authority.members), row_ids)
            proof = result.transaction.step_proofs[0]
            self.assertEqual(proof.training_authority_sha256, authority.digest)
            self.assertEqual(
                proof.training_authority_members,
                tuple(
                    (member.digest, member.source_family_id, member.episode_id)
                    for member in authority.members
                ),
            )
            self.assertIsNotNone(result.transaction.motif_transition)
            advanced = False
            for name, after in result.transaction.optimizer.update_counts.items():
                before = parent.retained_state.optimizer.update_counts[name]
                delta = after - before
                self.assertTrue(bool(mx.all((delta == 0) | (delta == 1))), name)
                advanced = advanced or bool(mx.any(delta == 1))
            self.assertTrue(advanced)
            self.assertEqual(result.realized_cost["optimizer_steps"], 1)

    def _draw(self, capability, seed, each):
        rows = tuple(self.context.draw_rows(seed=seed, capability=capability, each=each))
        execution = self.context.release.execution_plan.capability_map[capability]
        delivery = describe_delivered_teaching(
            self.context.release, capability, execution.teaching_option_ids[0], rows)
        return rows, delivery

    def _publish(self, run_dir: Path) -> None:
        with patch(
            "bilqis_mlx.runtime.bamf_bundle.codec.assert_headroom", return_value=None,
        ):
            publish_initial_generation(
                run_dir, self.production_genesis(), reserve_gib=0.)


if __name__ == "__main__":
    unittest.main()
