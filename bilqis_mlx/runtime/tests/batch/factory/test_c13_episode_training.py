"""Pinned-A01 C02/B11 admission proof for the live C13 episode source."""
from __future__ import annotations

from pathlib import Path
from dataclasses import replace

import mlx.core as mx

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.live_answers import live_answer_registry
from bilqis_mlx.factory.teaching import describe_delivered_teaching
from bilqis_mlx.live_grade_c import registry_graph
from bilqis_mlx.runtime.atlas_model import bamf_value_and_grad
from bilqis_mlx.runtime.factory_task_authority import (
    bind_factory_task_compiled_batch, factory_task_authority,
    factory_task_training_goal,
)
from bilqis_mlx.runtime.factory_training_bridge import prepare_factory_training_batch
from bilqis_mlx.runtime.source_execution import SourceExecutionContext
from bilqis_mlx.runtime.task_goal_readout import (
    task_goal_route_plan, task_goal_training_targets,
)
from bilqis_mlx.runtime.tests.batch.training.visit_provenance_support import (
    visit_provenance,
)
from bilqis_mlx.semantics.frame_compiler import PositionKind
from bilqis_mlx.source_adapters.c13_episode import CAPABILITY
from bilqis_mlx.source_adapters.c13_episode_release import compile_episode_release
from bilqis_mlx.source_adapters.school import live_source_registry

from .factory_training_bridge_support import FactoryTrainingBridgeFixture


class C13EpisodeTrainingTests(FactoryTrainingBridgeFixture):
    def setUp(self):
        super().setUp()
        graph = registry_graph()
        registry = live_source_registry()
        answers = live_answer_registry()
        source_root = (Path.cwd() / "vendor/legacy-v16").resolve()
        release = compile_episode_release(
            source_root, graph, registry, answers)
        self.c13_context = SourceExecutionContext(
            release, graph, source_root, registry, answers)

    def prepare_c13(self, *, seed=31):
        rows = tuple(self.c13_context.draw_rows(
            seed=seed, capability=CAPABILITY, each=1))
        execution = self.c13_context.release.execution_plan.capability_map[CAPABILITY]
        delivery = describe_delivered_teaching(
            self.c13_context.release,
            CAPABILITY,
            execution.teaching_option_ids[0],
            rows,
        )
        prepared = prepare_factory_training_batch(
            self.c13_context,
            self.candidate,
            str(self.artifact),
            self.feature_receipt.path,
            rows,
            self.generation,
            capability=CAPABILITY,
            delivery=delivery,
            requested_count=1,
            source_seed=seed,
            source_each=1,
            optimizer_step_seed=7,
            visit_provenance=visit_provenance(CAPABILITY),
            teacher_strategy={"policy": "c13-source-admission"},
        )
        return rows, prepared

    def test_live_c13_row_reaches_signed_c02_and_b11_authority(self):
        rows, prepared = self.prepare_c13()
        self.assertEqual(len(prepared.training_batch.rows), 1)
        self.assertEqual(len(prepared.compiled_rows), 1)
        compiled = prepared.compiled_rows[0]
        training = prepared.training_batch.rows[0]
        self.assertEqual(compiled.training_authority.source_row_id, rows[0]["id"])
        self.assertEqual(
            compiled.training_authority.training_batch_sha256,
            prepared.training_batch.authority_digest,
        )
        self.assertEqual(training.provenance.source_family_id,
                         "bamf.c13.episode-binding/v1")
        self.assertTrue(all(
            position.kind is PositionKind.ATOM
            for position in compiled.compiled.compiled.rows[0].positions
        ))

    def test_wrong_source_root_rejects_before_b11_binding(self):
        rows, _prepared = self.prepare_c13(seed=33)
        context = replace(
            self.c13_context,
            source_root=(Path.cwd() / "tests").resolve(),
        )
        execution = context.release.execution_plan.capability_map[CAPABILITY]
        delivery = describe_delivered_teaching(
            context.release,
            CAPABILITY,
            execution.teaching_option_ids[0],
            rows,
        )
        with self.assertRaises(BilqisError) as caught:
            prepare_factory_training_batch(
                context,
                self.candidate,
                str(self.artifact),
                self.feature_receipt.path,
                rows,
                self.generation,
                capability=CAPABILITY,
                delivery=delivery,
                requested_count=1,
                source_seed=33,
                source_each=1,
                optimizer_step_seed=7,
                visit_provenance=visit_provenance(CAPABILITY),
                teacher_strategy={"policy": "c13-wrong-source-root"},
            )
        self.assertEqual(
            caught.exception.context["reason"],
            "SOURCE_ATOM_SOURCE_ROOT_DRIFT",
        )

    def test_live_c13_task_goal_issues_finite_loss_bearing_gradient(self):
        _rows, prepared = self.prepare_c13(seed=32)
        compiled = prepared.compiled_rows[0]
        authority = factory_task_authority(self.c13_context, compiled)
        bound = bind_factory_task_compiled_batch(compiled, authority)
        resolved = factory_task_training_goal(
            self.c13_context, bound, authority)
        targets, mask = task_goal_training_targets(authority.goal, resolved)
        plan = task_goal_route_plan(
            authority.goal,
            bound,
            self.feature_context.snapshot,
            self.generation,
        )
        self.assertTrue(targets)
        self.assertTrue(mask)
        gradient = bamf_value_and_grad(
            dict(self.candidate.retained_state.optimizer.parameters),
            bound,
            plan,
            targets,
            mask,
            None,
        )
        self.assertTrue(bool(mx.isfinite(gradient.loss_total)))
        self.assertTrue(gradient.gradients)
        self.assertTrue(all(
            bool(mx.all(mx.isfinite(value)))
            for value in gradient.gradients.values()
        ))
