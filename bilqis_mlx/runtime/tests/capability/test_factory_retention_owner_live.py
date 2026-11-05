"""Positive #708 witness: Factory-owned C05 reaches live B13 publication."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.factory import assessment_scope_contract
from bilqis_mlx.factory.teaching import describe_delivered_teaching
from bilqis_mlx.generated_assessment import make_cohort
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.atlas_candidate import begin_candidate, resolve_candidate
from bilqis_mlx.learning.atlas_readout import DecisionOutput
from bilqis_mlx.learning.atlas_retention_decision import issue_factory_retention_decision
from bilqis_mlx.learning.source_atoms.tests.backbone_test_support import SourceBackboneTestBase
from bilqis_mlx import state_dag
from bilqis_mlx.runtime.atlas_model import bamf_value_and_grad, bind_compiled_training_batch
from bilqis_mlx.runtime.atlas_training_adapter import compile_training_batch
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
from bilqis_mlx.runtime.factory_retention_owner import evaluate_factory_retention_candidate
from bilqis_mlx.runtime.factory_task_authority import factory_task_authority
from bilqis_mlx.runtime.model_topology_v2 import expected_bamf_shapes
from bilqis_mlx.runtime.task_goal_readout import task_goal_route_decisions, task_goal_route_plan
from bilqis_mlx.runtime._assessment.executable_custody import _persist_executable_cohort
from bilqis_mlx.runtime.tests.batch.test_atlas_training_adapter import (
    _source_context, answer_plan_for, compile_prefix, feature_requests_for,
    features_for, source_ast_for,
)
from bilqis_mlx.runtime.tests.capability.factory_retention_live_support import (
    HP, genesis_bundle, live_factory_context,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import acceptance


TARGET = "B.IDBOOLOPS"
TRAIN_SEED = 46117
FIXED_SEED = 7331
FIXED_EACH = {
    "A.IDENTITY": 2, "A.PARENT": 2, "A.LINK": 2, "A.MEMBER": 2,
    "A.EDGE": 2, "A.MAPS": 2,
    "B.AND": 4, "B.IFF": 4, "B.COMPOSITE": 1, "B.IDBOOLOPS": 1,
    "C.COUNT": 3, "C.NUMBER": 3, "C.SUCCESSOR": 3, "C.ADD": 3,
    "C.SUB": 3, "C.MUL": 3, "C.DIV": 3,
}


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


def _training_batch(source_context, row, generation):
    visible = {row["id"]: len(row["tokens"])}
    frames_for_ast, task, frontier, policy = _source_context(
        (row,), source_context.release.release_sha256, visible, "allow")
    execution = source_context.release.execution_plan.capability_map[TARGET]
    delivery = describe_delivered_teaching(
        source_context.release, TARGET, execution.teaching_option_ids[0], (row,))
    source_authority = source_context.bind_rows(
        (row,), seed=TRAIN_SEED, capability=TARGET, each=1)
    return compile_training_batch(
        (row,), source_context, {"context": 1024},
        delivery=delivery, delivery_capability=TARGET,
        delivery_release_sha256=source_context.release.release_sha256,
        teacher_strategy={"policy": "factory-c05-live"}, requested_count=1,
        optimizer_step_seed=0, source_authority=source_authority,
        rehearsal_by_id={}, visible_ends=visible, source_ast_for=source_ast_for,
        compile_prefix=compile_prefix, feature_requests_for=feature_requests_for,
        features_for=features_for,
        answer_plan_for=lambda prefix, release, capability, kind: {
            **answer_plan_for(prefix, release, capability, kind),
            "generation_binding": generation,
        },
        frames_for_ast=frames_for_ast, task_scope=task,
        source_frontier=frontier, eligibility_policy=policy,
        generation_binding=generation,
    )


class FactoryRetentionOwnerLiveTests(SourceBackboneTestBase):
    def setUp(self):
        artifact = os.environ.get("BILQIS_A01_ATLAS_BUNDLE")
        if not artifact:
            self.skipTest("BILQIS_A01_ATLAS_BUNDLE fixture is not mounted")
        self.artifact = Path(artifact)
        if not self.artifact.is_dir():
            self.skipTest("BILQIS_A01_ATLAS_BUNDLE fixture is not mounted")
        super().setUp()
        self.root = Path.cwd()
        self.source = (self.root / "vendor/legacy-v16").resolve()
        if not self.source.is_dir():
            self.skipTest("pinned legacy source fixture is not mounted")

    def test_source_owned_c05_acceptance_publishes_exact_successor(self):
        source_context, _ = live_factory_context(self.root, self.source)
        genesis, _ = genesis_bundle(self, self.snapshot, self.schema)
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
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

            row = source_context.draw_rows(
                seed=TRAIN_SEED, capability=TARGET, each=1)[0]
            generation = execution_generation_digest(
                parent.retained_state.optimizer.parameters,
                spec=parent.topology, extents=parent.extents)
            training = _training_batch(source_context, row, generation)
            compiled = compile_factory_evaluation_batch(
                source_context, parent, str(self.artifact), row,
                source_seed=TRAIN_SEED, source_each=1)
            live_batch = bind_compiled_training_batch(
                training, compiled.compiled, compiled.sources,
                compiled.feature_schema,
            )
            authority = factory_task_authority(source_context, live_batch)
            feature_context = authenticate_bamf_candidate_feature_context(
                parent, str(self.artifact))
            plan = task_goal_route_plan(
                authority.goal, live_batch, feature_context.snapshot, generation)
            expected = factory_evaluation_instrument(
                source_context, parent, str(self.artifact), row,
                source_seed=TRAIN_SEED, source_each=1).case.gold
            route = task_goal_route_decisions(authority.goal)
            self.assertEqual(len(route), 1)
            node = authority.goal.expression_or_holes.nodes[0]
            handle = next(
                item.typed.source_handle for item in authority.binding.operands
                if item.typed.type_name == expected.type_name
                and item.typed.value == expected.value)
            selected = next(
                item for item in node.candidate_operand_refs[0]
                if item.source_handle == handle)
            targets = (DecisionOutput(route[0].decision_id, selected.identity),)
            mask = {route[0].decision_id: True}
            gradient = bamf_value_and_grad(
                dict(parent.retained_state.optimizer.parameters),
                live_batch, plan, targets, mask, cache)
            declared = expected_bamf_shapes(parent.topology, parent.extents)
            transaction = admit_uninterrupted_candidate_step(
                run_dir, parent,
                loss_bearing_target=True, gradient_execution=gradient,
                teacher_hparams=HP,
                decay={item.name: item.decay for item in declared},
                max_norm=1.0,
            )
            self.assertEqual(transaction.update_steps, 1)
            self.assertEqual(len(transaction.training_authorities), 1)

            evaluation = evaluate_factory_retention_candidate(
                source_context, transaction, str(self.artifact), TARGET,
                run_dir=run_dir)
            decision = issue_factory_retention_decision(evaluation)
            self.assertTrue(decision.accepted)
            retained = resolve_candidate(transaction, accepted=True)
            successor = derive_successor_bundle(
                parent, retained,
                parent_manifest_sha256=cache.accepted_manifest_sha256,
                delivery_events=())
            with patch(
                "bilqis_mlx.runtime.bamf_bundle.codec.assert_headroom",
                return_value=None,
            ):
                published = accept_and_publish(
                    run_dir, successor, retained, decision=decision,
                    feature_sha256=successor.extents.factor_map_digest)
            cold = load_accepted_generation(run_dir)
            self.assertEqual(cold.generation, 1)
            self.assertEqual(
                candidate_identity_digest(cold.retained_state),
                candidate_identity_digest(retained))
            self.assertEqual(published["generation"], 1)


if __name__ == "__main__":
    unittest.main()
