"""Disposable full-model C05/C16 learning diagnostics and B13.2 continuation.

This module is not the #708 feature-authority acceptance surface.  It exercises
real source-backed MLX learning behavior and may be expensive; #708 provenance is
covered by the custody/feature-authority suites.
"""
from __future__ import annotations

# This module executes real MLX/source-backed acceptance and diagnostics. Ordinary
# differential leaf verification must not schedule it on an interactive socket;
# run its witnesses explicitly through scripts/bamf/detached_long_run.py.
BILQIS_LEAF_GATE_POLICY = "DETACHED_ONLY"

import json
import os
from dataclasses import replace
from pathlib import Path
import tempfile
from types import MappingProxyType
import unittest
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.factory import assessment_scope_contract
from bilqis_mlx.generated_assessment import make_cohort
from bilqis_mlx.learning.atlas_acceptance import (
    candidate_identity_digest, mint_acceptance_binding,
)
from bilqis_mlx.learning.atlas_candidate import begin_candidate, resolve_candidate
from bilqis_mlx.learning.atlas_readout import DecisionOutput, ExecutionMode
from bilqis_mlx.learning.atlas_retention_decision import issue_factory_retention_decision
from bilqis_mlx.learning.source_atoms.tests.backbone_test_support import SourceBackboneTestBase
from bilqis_mlx import state_dag
from bilqis_mlx.runtime.atlas_model import (
    bamf_value_and_grad, bind_compiled_training_batch, forward_bamf, model_backend,
)
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.bamf_bundle.admission import (
    accept_and_publish, admit_uninterrupted_candidate_step,
    bind_accepted_execution_cache, derive_successor_bundle,
    load_accepted_generation,
)
from bilqis_mlx.runtime.bamf_bundle import (
    authenticate_bamf_candidate_feature_context, publish_bamf_generation,
)
from bilqis_mlx.runtime.factory_complete_solver import factory_evaluation_instrument
from bilqis_mlx.runtime.factory_evaluation_compiler import compile_factory_evaluation_batch
from bilqis_mlx.runtime.factory_retention_owner import (
    _candidate_from_live_parent, evaluate_factory_retention_candidate,
)
from bilqis_mlx.runtime.factory_task_authority import factory_task_authority
from bilqis_mlx.runtime.model_topology_v2 import expected_bamf_shapes
from bilqis_mlx.runtime.task_goal_readout import task_goal_route_decisions, task_goal_route_plan
from bilqis_mlx.runtime.assessment import _persist_executable_cohort
from bilqis_mlx.runtime.tests.capability.factory.factory_retention_live_support import (
    C05_TRAINING_LEARNING_RATE, HP, genesis_bundle, live_factory_context,
)
from bilqis_mlx.runtime.tests.capability.factory.factory_retention_next_step_witness import (
    prove_source_qualified_continuation,
)
from bilqis_mlx.runtime.tests.capability.factory.factory_retention_lesson_diagnostic import (
    diagnose_factory_retention_lesson,
)
from bilqis_mlx.runtime.tests.capability.factory.factory_retention_fixed_diagnostic import (
    diagnose_fixed_capability,
)
from bilqis_mlx.runtime.tests.capability.factory.factory_retention_target_diagnostic import (
    diagnose_factory_retention_target,
)
from bilqis_mlx.runtime.tests.capability.factory.source_training_support import (
    source_training_batch,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    acceptance, retention_decision,
)


TARGET = "B.IDBOOLOPS"
TRAIN_SEED = 46117
FIXED_SEED = 7331
FIXED_EACH = MappingProxyType({
    "A.IDENTITY": 2, "A.PARENT": 2, "A.LINK": 2, "A.MEMBER": 2,
    "A.EDGE": 2, "A.MAPS": 2,
    "B.AND": 4, "B.IFF": 4, "B.COMPOSITE": 1, "B.IDBOOLOPS": 1,
    "C.COUNT": 3, "C.NUMBER": 3, "C.SUCCESSOR": 3, "C.ADD": 3,
    "C.SUB": 3, "C.MUL": 3, "C.DIV": 3,
})


def _fixed_school(run_dir, source_context, manifest_sha256):
    capabilities = tuple(
        item.capability_id for item in source_context.release.execution_plan.capabilities)
    contract = assessment_scope_contract(source_context.release, capabilities)
    rows = []
    for capability in capabilities:
        rows.extend(source_context.draw_rows(
            seed=FIXED_SEED, capability=capability,
            each=FIXED_EACH[capability]))
    cohort = make_cohort(
        rows, generator_version=contract.generator_version,
        seed=FIXED_SEED, rubric_version=contract.rubric_sha256)
    return _persist_executable_cohort(
        run_dir, {"manifest_sha256": manifest_sha256}, contract, cohort)


def _initialize_generation(run_dir, source_context, genesis):
    with patch(
        "bilqis_mlx.runtime.bamf_bundle.codec.assert_headroom",
        return_value=None,
    ):
        first = publish_bamf_generation(
            run_dir, genesis, acceptance=acceptance(genesis))
    parent = load_accepted_generation(run_dir)
    cache = bind_accepted_execution_cache(run_dir)
    fixed = _fixed_school(run_dir, source_context, first["manifest_sha256"])
    state_dag.persist(run_dir, {
        "generation": 0,
        "factory_release_sha256": source_context.release.release_sha256,
        "last_exam": fixed,
    })
    return parent, cache


def _source_owned_candidate_step_evidence(run_dir, source_context, parent, cache, artifact):
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
        capability=TARGET, source_seed=TRAIN_SEED)
    compiled = compile_factory_evaluation_batch(
        source_context, parent, str(artifact), row,
        source_seed=TRAIN_SEED, source_each=1)
    live_batch = bind_compiled_training_batch(
        training, compiled.compiled, compiled.sources, compiled.feature_schema)
    authority = factory_task_authority(source_context, live_batch)
    feature_context = authenticate_bamf_candidate_feature_context(
        parent, str(artifact))
    plan = task_goal_route_plan(
        authority.goal, live_batch, feature_context.snapshot, generation)
    targets, mask = _source_targets(
        source_context, parent, artifact, row, authority)
    gradient = bamf_value_and_grad(
        dict(parent.retained_state.optimizer.parameters),
        live_batch, plan, targets, mask, cache)
    declared = expected_bamf_shapes(parent.topology, parent.extents)
    transaction = admit_uninterrupted_candidate_step(
        run_dir, parent, loss_bearing_target=True, gradient_execution=gradient,
        teacher_hparams=replace(
            HP, learning_rate=C05_TRAINING_LEARNING_RATE),
        decay={item.name: item.decay for item in declared},
        max_norm=1.0)
    if transaction.update_steps != 1 or len(transaction.training_authorities) != 1:
        raise AssertionError("C05 source-owned step did not execute exactly once")
    return transaction, gradient, row, targets


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


def _publish_c05_successor(run_dir, source_context, parent, cache, artifact, transaction):
    evaluation = evaluate_factory_retention_candidate(
        source_context, transaction, str(artifact), TARGET, run_dir=run_dir)
    decision = issue_factory_retention_decision(evaluation)
    if not decision.accepted:
        raise AssertionError(
            "C05 Factory retention did not accept source-owned candidate: "
            f"reason={decision.reason} evidence={decision.evidence_sha256} "
            f"policy={decision.policy_sha256} "
            f"blocking_capability={evaluation.decision.blocking_capability}")
    retained = resolve_candidate(transaction, accepted=True)
    successor = derive_successor_bundle(
        parent, retained, parent_manifest_sha256=cache.accepted_manifest_sha256,
        delivery_events=({
            "event": "BAMF_GENERATION_ACCEPTED",
            "optimizer_step": retained.optimizer_step,
        },))
    with patch(
        "bilqis_mlx.runtime.bamf_bundle.codec.assert_headroom",
        return_value=None,
    ):
        published = accept_and_publish(
            run_dir, successor, retained, decision=decision,
            feature_sha256=successor.extents.factor_map_digest)
    return successor, retained, published


def _publish_disposable_source_qualified_successor(
        run_dir, parent, cache, transaction):
    """Publish a real source-trained step without treating it as C05 learning proof.

    The candidate step itself is produced by the live Factory/B11/B12 path.  The
    acceptance token is deliberately the test-only C05 fixture so B13.2 can
    exercise pointer/lock/cold-resume continuation independently of the separate
    retained-learning acceptance witness.
    """
    retained = resolve_candidate(transaction, accepted=True)
    successor = derive_successor_bundle(
        parent, retained, parent_manifest_sha256=cache.accepted_manifest_sha256,
        delivery_events=({
            "event": "BAMF_GENERATION_ACCEPTED",
            "optimizer_step": retained.optimizer_step,
        },))
    decision = retention_decision(
        parent=parent.retained_state, retained=retained)
    binding = mint_acceptance_binding(
        decision, retained, run_id=successor.run_id,
        generation=successor.generation,
        feature_sha256=successor.extents.factor_map_digest)
    with patch(
        "bilqis_mlx.runtime.bamf_bundle.codec.assert_headroom",
        return_value=None,
    ):
        published = publish_bamf_generation(
            run_dir, successor, acceptance=binding)
    return successor, retained, published


def _assert_published_generation_one(run_dir, retained, published):
    cold = load_accepted_generation(run_dir)
    if (cold.generation != 1
            or candidate_identity_digest(cold.retained_state)
            != candidate_identity_digest(retained)
            or published["generation"] != 1):
        raise AssertionError("C05 source-owned generation-one publication drift")


class FactoryRetentionOwnerLiveTests(SourceBackboneTestBase):
    def setUp(self):
        if not mx.metal.is_available():
            self.skipTest("B13.2 source witness requires Apple Metal")
        previous_device = mx.default_device()
        mx.set_default_device(mx.gpu)
        self.addCleanup(mx.set_default_device, previous_device)
        super().setUp()
        artifact = os.environ.get("BILQIS_A01_ATLAS_BUNDLE")
        if not artifact:
            self.skipTest("BILQIS_A01_ATLAS_BUNDLE fixture is not mounted")
        self.artifact = Path(artifact)
        if not self.artifact.is_dir():
            self.skipTest("BILQIS_A01_ATLAS_BUNDLE fixture is not mounted")
        self.root = Path.cwd()
        self.source = (self.root / "vendor/legacy-v16").resolve()
        if not self.source.is_dir():
            self.skipTest("pinned legacy source fixture is not mounted")

    def test_source_owned_c05_target_diagnostic(self):
        source_context, _ = live_factory_context(self.root, self.source)
        genesis, _ = genesis_bundle(
            self, self.snapshot, self.schema, self.artifact)
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            parent, cache = _initialize_generation(
                run_dir, source_context, genesis)
            transaction = _source_owned_candidate_step(
                run_dir, source_context, parent, cache, self.artifact)
            receipt = diagnose_factory_retention_target(
                source_context, transaction, str(self.artifact), TARGET,
                run_dir=run_dir)
            self.assertFalse(receipt["authorizing"])
            self.assertEqual(receipt["total"], 6)
            print("C05_TARGET_DIAGNOSTIC " + json.dumps(receipt, sort_keys=True))

    def test_source_owned_c05_lesson_diagnostic(self):
        source_context, _ = live_factory_context(self.root, self.source)
        genesis, _ = genesis_bundle(
            self, self.snapshot, self.schema, self.artifact)
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            parent, cache = _initialize_generation(
                run_dir, source_context, genesis)
            transaction = _source_owned_candidate_step(
                run_dir, source_context, parent, cache, self.artifact)
            receipt = diagnose_factory_retention_lesson(
                source_context, transaction, str(self.artifact), TARGET,
                run_dir=run_dir)
            self.assertFalse(receipt["authorizing"])
            self.assertEqual(receipt["total"], 24)
            self.assertEqual(len(receipt["lesson_capabilities"]), 4)
            print("C05_LESSON_DIAGNOSTIC " + json.dumps(receipt, sort_keys=True))

    def test_source_owned_training_step_diagnostic(self):
        source_context, _ = live_factory_context(self.root, self.source)
        genesis, _ = genesis_bundle(
            self, self.snapshot, self.schema, self.artifact)
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            parent, cache = _initialize_generation(
                run_dir, source_context, genesis)
            transaction, gradient, row, targets = _source_owned_candidate_step_evidence(
                run_dir, source_context, parent, cache, self.artifact)
            _, candidate_bundle, _, _ = _candidate_from_live_parent(run_dir, transaction)
            generation = execution_generation_digest(
                candidate_bundle.retained_state.optimizer.parameters,
                spec=candidate_bundle.topology, extents=candidate_bundle.extents)
            compiled = compile_factory_evaluation_batch(
                source_context, candidate_bundle, str(self.artifact), row,
                source_seed=TRAIN_SEED, source_each=1)
            authority = factory_task_authority(
                source_context, compiled, generation_binding=generation)
            feature_context = authenticate_bamf_candidate_feature_context(
                candidate_bundle, str(self.artifact))
            plan = task_goal_route_plan(
                authority.goal, compiled, feature_context.snapshot, generation)
            after = forward_bamf(
                candidate_bundle.retained_state.optimizer.parameters,
                compiled, plan, ExecutionMode.INFERENCE, None)

            target = targets[0]
            def summary(output):
                record = next(
                    item for item in output.decisions
                    if item.decision_id == target.decision_id)
                logits = [float(value) for value in record.logits.tolist()]
                index = record.candidates.index(target.value)
                others = [value for offset, value in enumerate(logits) if offset != index]
                return {
                    "candidates": list(record.candidates),
                    "logits": logits,
                    "gold": target.value,
                    "gold_margin": logits[index] - max(others),
                    "committed": next(
                        item.value for item in output.committed
                        if item.decision_id == target.decision_id),
                }

            before = gradient.execution.output
            receipt = {
                "schema": "bilqis.mlx.c05-training-step-diagnostic/v1",
                "authorizing": False,
                "row_id": row["id"],
                "gold": row["gold"],
                "loss_total": float(gradient.loss_total.item()),
                "before": summary(before),
                "after": summary(after),
                "parent_generation": before.generation_binding,
                "candidate_generation": after.generation_binding,
            }
            print("C05_TRAINING_STEP_DIAGNOSTIC " + json.dumps(receipt, sort_keys=True))

    def test_source_owned_c05_fixed_and_diagnostic(self):
        source_context, _ = live_factory_context(self.root, self.source)
        genesis, _ = genesis_bundle(
            self, self.snapshot, self.schema, self.artifact)
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            parent, cache = _initialize_generation(
                run_dir, source_context, genesis)
            transaction, gradient, _row, _targets = _source_owned_candidate_step_evidence(
                run_dir, source_context, parent, cache, self.artifact)
            receipt = diagnose_fixed_capability(
                source_context, transaction, str(self.artifact), TARGET, "B.AND",
                run_dir=run_dir, gradient=gradient)
            self.assertFalse(receipt["authorizing"])
            self.assertEqual(receipt["protected_capability"], "B.AND")
            self.assertEqual(receipt["total"], FIXED_EACH["B.AND"])
            print("C05_FIXED_CAPABILITY_DIAGNOSTIC " + json.dumps(
                receipt, sort_keys=True), flush=True)

    def test_source_qualified_candidate_can_publish_then_continue(self):
        source_context, _ = live_factory_context(self.root, self.source)
        genesis, _ = genesis_bundle(
            self, self.snapshot, self.schema, self.artifact)
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            parent, cache = _initialize_generation(
                run_dir, source_context, genesis)
            transaction = _source_owned_candidate_step(
                run_dir, source_context, parent, cache, self.artifact)
            successor, retained, published = _publish_disposable_source_qualified_successor(
                run_dir, parent, cache, transaction)
            _assert_published_generation_one(run_dir, retained, published)
            witness = prove_source_qualified_continuation(
                run_dir, source_context, self.artifact, successor, published,
                root=self.root, source=self.source, target=TARGET)
            self.assertTrue(witness["no_generation_2"])
            print("B13_2_BACKEND_HANDOFF " + json.dumps(witness, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
