"""Source-owned candidate execution mechanics for disposable C05 witnesses."""
from __future__ import annotations

import json
import random
from dataclasses import replace
from types import SimpleNamespace

import mlx.core as mx

from bilqis_mlx.compatibility import historical_teacher_policy
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.atlas_readout import DecisionOutput
from bilqis_mlx.learning.learning_experiment import Settings
from bilqis_mlx.runtime.accepted_teacher_custody import select_accepted_teacher_visit
from bilqis_mlx.runtime.atlas_model import (
    bamf_value_and_grad, bind_compiled_training_batch, model_backend,
)
from bilqis_mlx.runtime.atlas_visit_provenance import BamfVisitProvenance
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.bamf_bundle.admission import admit_uninterrupted_candidate_step
from bilqis_mlx.runtime.factory_complete_solver import factory_evaluation_instrument
from bilqis_mlx.runtime.factory_evaluation_compiler import compile_factory_evaluation_batch
from bilqis_mlx.runtime.factory_task_authority import factory_task_authority
from bilqis_mlx.runtime.task_goal_readout import task_goal_route_decisions, task_goal_route_plan
from bilqis_mlx.runtime.tests.capability.factory.retention.factory_retention_live_support import (
    C05_TRAINING_LEARNING_RATE, HP,
)
from bilqis_mlx.runtime.tests.capability.factory.retention.source_training_support import (
    source_training_batch,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.teacher_custody_fixtures import (
    adaptation, selection_teacher,
)


TARGET = "B.IDBOOLOPS"
TRAIN_SEED = 46117


def _execute_source_owned_candidate_step_evidence(
        run_dir, source_context, parent, cache, artifact, *,
        teacher_policy=None, teacher_visit_provenance=None,
        learning_rate=C05_TRAINING_LEARNING_RATE):
    backend = model_backend(parent.topology)
    if "gpu" not in backend.device.lower():
        raise AssertionError(f"C05 source-owned MLX backend is not GPU: {backend.device}")
    print("FACTORY_C05_DEVICE " + json.dumps({
        "default_device": str(mx.default_device()),
        "model_backend": backend.device,
        "metal_available": mx.metal.is_available(),
    }, sort_keys=True), flush=True)
    row = source_context.draw_rows(
        seed=TRAIN_SEED, capability=TARGET, each=1)[0]
    generation = execution_generation_digest(
        parent.retained_state.optimizer.parameters,
        spec=parent.topology, extents=parent.extents)
    training = source_training_batch(
        source_context, parent, artifact, row, generation,
        capability=TARGET, source_seed=TRAIN_SEED,
        optimizer_step_seed=parent.retained_state.optimizer_step,
        teacher_strategy=teacher_policy,
        teacher_visit_provenance=teacher_visit_provenance)
    compiled = compile_factory_evaluation_batch(
        source_context, parent, str(artifact), row,
        source_seed=TRAIN_SEED, source_each=1)
    live_batch = bind_compiled_training_batch(
        training, compiled.compiled, compiled.sources, compiled.feature_schema,
        active_semantic_rows=compiled.active_semantic_rows)
    authority = factory_task_authority(source_context, live_batch)
    from bilqis_mlx.runtime.bamf_bundle import authenticate_bamf_execution_feature_context
    feature_context = authenticate_bamf_execution_feature_context(
        parent, str(artifact), source_context.run_dir)
    plan = task_goal_route_plan(
        authority.goal, live_batch, feature_context.snapshot, generation)
    targets, mask = _source_targets(
        source_context, parent, artifact, row, authority)
    gradient = bamf_value_and_grad(
        dict(parent.retained_state.optimizer.parameters),
        live_batch, plan, targets, mask, cache)
    transaction = admit_uninterrupted_candidate_step(
        run_dir, parent, loss_bearing_target=True, gradient_execution=gradient,
        teacher_hparams=replace(HP, learning_rate=float(learning_rate)),
        max_norm=1.0)
    if transaction.update_steps != 1 or len(transaction.training_authorities) != 1:
        raise AssertionError("C05 source-owned step did not execute exactly once")
    return transaction, gradient, row, targets


def _teacher_selected_source_owned_candidate_step_evidence(
        run_dir, source_context, parent, cache, artifact):
    school = SimpleNamespace(
        stage="RECOVERY_1",
        current_student=SimpleNamespace(
            sha256=candidate_identity_digest(parent.retained_state)),
    )
    bootstrap = {}
    if "c03_lineage" not in parent.teacher_state:
        bootstrap = {
            "legacy_receipt": {"teacher": selection_teacher()},
            "adaptation": adaptation(),
            "prior_region": "legacy-region",
        }
    bound, teacher_policy, teacher_metadata = select_accepted_teacher_visit(
        run_dir, historical_teacher_policy, school, random.Random(17), Settings(),
        "factory/7", {}, "B", capability_id=TARGET, total_capabilities=20,
        **bootstrap)
    visit = BamfVisitProvenance.from_c03_record(bound.identity.to_record())
    transaction, gradient, row, targets = _execute_source_owned_candidate_step_evidence(
        run_dir, source_context, parent, cache, artifact,
        teacher_policy=teacher_policy, teacher_visit_provenance=visit,
        learning_rate=teacher_policy["lr"])
    return transaction, gradient, row, targets, {
        "policy_key": bound.identity.policy_key,
        "policy": teacher_policy,
        "selection_reason": teacher_metadata["selection_reason"],
        "visit": bound.identity.to_record(),
    }


def _source_owned_candidate_step_evidence(run_dir, source_context, parent, cache, artifact):
    return _execute_source_owned_candidate_step_evidence(
        run_dir, source_context, parent, cache, artifact)


def _source_owned_candidate_step(run_dir, source_context, parent, cache, artifact):
    return _source_owned_candidate_step_evidence(
        run_dir, source_context, parent, cache, artifact)[0]


def _source_targets(source_context, parent, artifact, row, authority):
    expected = factory_evaluation_instrument(
        source_context, parent, str(artifact), row,
        source_seed=TRAIN_SEED, source_each=1).case.gold
    route = task_goal_route_decisions(authority.goal)
    if len(route) != 1:
        raise AssertionError("C05 source-owned route decision drift")
    node = authority.goal.expression_or_holes.nodes[0]
    handle = next(
        item.typed.source_handle for item in authority.binding.operands
        if item.typed.type_name == expected.type_name
        and item.typed.value == expected.value)
    selected = next(
        item for item in node.candidate_operand_refs[0]
        if item.source_handle == handle)
    return (DecisionOutput(route[0].decision_id, selected.identity),), {
        route[0].decision_id: True}


__all__ = (
    "TARGET", "TRAIN_SEED", "_execute_source_owned_candidate_step_evidence",
    "_source_owned_candidate_step", "_source_owned_candidate_step_evidence",
    "_teacher_selected_source_owned_candidate_step_evidence",
)
