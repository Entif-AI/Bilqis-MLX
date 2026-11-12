"""Shared assertions and setup for C08 real-Factory execution witnesses."""
from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.factory.teaching import describe_delivered_teaching
from bilqis_mlx.runtime.atlas_resources import (
    MemoryBudget, ResourceRow, estimate_row_activation_bytes,
)
from bilqis_mlx.runtime.bamf_bundle import publish_initial_generation
from bilqis_mlx.runtime.factory_candidate_training import (
    FactoryDeliveryObservation, _frame_stats,
)
from bilqis_mlx.runtime.model_topology_v2 import bamf_parameter_census
from bilqis_mlx.runtime.teacher_observation_capture import ObservationCapture, store_sidecar


def observation(run_dir, capability, rows, seed):
    capture = ObservationCapture(run_dir, {})
    capture.attempt_id = f"factory-step:{capability}:{seed}"
    capture.proposal_id = store_sidecar(
        run_dir, {"attempt_id": capture.attempt_id})["sha256"]
    capture.select_option(capability, None)
    return capture, FactoryDeliveryObservation(capture, 1, rows, seed)


def draw(case, capability, seed, each):
    rows = tuple(case.context.draw_rows(seed=seed, capability=capability, each=each))
    execution = case.context.release.execution_plan.capability_map[capability]
    delivery = describe_delivered_teaching(
        case.context.release, capability, execution.teaching_option_ids[0], rows)
    return rows, delivery


def publish(case, run_dir):
    with patch("bilqis_mlx.runtime.bamf_bundle.codec.assert_headroom", return_value=None):
        publish_initial_generation(run_dir, case.production_genesis(), reserve_gib=0.)


def assert_prepared_logical_rows(case, prepared, row_ids):
    case.assertEqual(
        tuple(row.provenance.row_id for row in prepared.training_batch.rows), row_ids)
    case.assertEqual(
        tuple(compiled.training_authority.source_row_id
              for compiled in prepared.compiled_rows), row_ids)
    case.assertTrue(all(
        compiled.training_authority.training_batch_sha256
        == prepared.training_batch.authority_digest
        for compiled in prepared.compiled_rows))
    case.assertEqual(
        tuple(compiled.training_authority.source_row_sha256
              for compiled in prepared.compiled_rows),
        tuple(row.provenance.source_row_content_sha256
              for row in prepared.training_batch.rows))


def split_budget(parent, prepared):
    default_budget = MemoryBudget(
        bamf_parameter_census(parent.topology, parent.extents))
    resource_rows = tuple(
        ResourceRow.from_training_row(
            training_row, _frame_stats(compiled),
            generation_binding=prepared.training_batch.generation_binding,
            delivered_content_sha256=prepared.training_batch.delivered_content_sha256,
        )
        for training_row, compiled in zip(
            prepared.training_batch.rows, prepared.compiled_rows))
    one_row_peak = max(
        estimate_row_activation_bytes(item, parent.topology)
        for item in resource_rows)
    return replace(
        default_budget,
        allocation_bytes=(default_budget.resident_bytes
                          + default_budget.activation_safety_factor * one_row_peak),
    )


def _authority_identity(authority):
    return (
        authority.release_sha256,
        authority.generation_binding,
        authority.training_batch_sha256,
        authority.delivery_capability,
        authority.source_row_id,
        authority.source_row_sha256,
        authority.source_family_id,
        authority.episode_id,
        authority.visit_id,
    )


def assert_split_step_result(case, result, prepared, row_ids, parent):
    case.assertEqual(result.resource_plan.groups, ((0,), (1,)))
    case.assertEqual(result.resource_plan.logical_row_ids, row_ids)
    case.assertEqual(
        tuple(row.provenance.row_id for row in result.prepared.training_batch.rows),
        row_ids)
    case.assertEqual(len(result.gradient_execution.loss_executions), 2)
    case.assertEqual(
        result.gradient_execution.source_digest, result.resource_plan.source_digest)
    row_authorities = tuple(
        execution.training_authority
        for execution in result.gradient_execution.loss_executions)
    case.assertEqual(
        tuple(authority.source_row_id for authority in row_authorities), row_ids)
    case.assertEqual(
        tuple(authority.source_row_sha256 for authority in row_authorities),
        tuple(row.provenance.source_row_content_sha256
              for row in prepared.training_batch.rows))
    for execution_authority, compiled in zip(
            row_authorities, result.prepared.compiled_rows):
        prepared_authority = compiled.training_authority
        case.assertEqual(
            _authority_identity(execution_authority),
            _authority_identity(prepared_authority))
        case.assertTrue(
            set(prepared_authority.immediate_dependencies)
            <= set(execution_authority.immediate_dependencies))
    case.assertEqual(result.transaction.update_steps, 1)
    case.assertEqual(len(result.transaction.step_proofs), 1)
    case.assertEqual(len(result.transaction.training_authorities), 1)
    authority = result.transaction.training_authorities[0]
    case.assertEqual(tuple(member.source_row_id for member in authority.members), row_ids)
    proof = result.transaction.step_proofs[0]
    case.assertEqual(proof.training_authority_sha256, authority.digest)
    case.assertEqual(
        proof.training_authority_members,
        tuple((member.digest, member.source_family_id, member.episode_id)
              for member in authority.members))
    case.assertIsNotNone(result.transaction.motif_transition)
    deltas = tuple(
        after - parent.retained_state.optimizer.update_counts[name]
        for name, after in result.transaction.optimizer.update_counts.items())
    case.assertTrue(all(bool(mx.all((delta == 0) | (delta == 1))) for delta in deltas))
    case.assertTrue(any(bool(mx.any(delta == 1)) for delta in deltas))
    case.assertEqual(result.realized_cost["optimizer_steps"], 1)


__all__ = (
    "assert_prepared_logical_rows", "assert_split_step_result", "draw",
    "observation", "publish", "split_budget",
)
