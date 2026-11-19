"""#1300 destructive-candidate rollback witness through the production root."""
from __future__ import annotations

import hashlib
from unittest.mock import patch

import mlx.core as mx
import numpy as np

import bilqis_mlx.runtime.bamf_operator.session_parts.native_session as native_session
import bilqis_mlx.runtime.factory_candidate_microbatch as candidate_microbatch
from bilqis_mlx.runtime.atlas_flywheel_runtime import AcceptedAtlasFlywheelSupervisor
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.runtime.bamf_operator.session import operate_bamf
from bilqis_mlx.runtime.tests.custody.bamf_bundle.cold_resume_probe import retained_digest
from bilqis_mlx.runtime.tests.custody.bamf_bundle.teacher_custody_fixtures import (
    selection_teacher,
)

from .conformance_1300_support import Conformance1300RuntimeSupport


BILQIS_LEAF_GATE_POLICY = "DETACHED_ONLY"


def _array_group_digest(values) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(values.items()):
        digest.update(name.encode("utf-8"))
        digest.update(np.asarray(value).tobytes())
    return digest.hexdigest()


def _optimizer_custody(state) -> dict[str, str]:
    optimizer = state.optimizer
    return {
        group: _array_group_digest(getattr(optimizer, group))
        for group in ("parameters", "m", "v", "update_counts")
    }


class IntegratedConformance1300RejectionTests(Conformance1300RuntimeSupport):
    def test_destructive_candidate_rejects_and_restores_complete_parent_custody(self):
        fixture = self._production_parameter_fixture()
        supervisor = AcceptedAtlasFlywheelSupervisor(
            self.run, self.parent_graph, reserve_gib=0.0
        )
        baseline_teacher = selection_teacher()
        for strategy in baseline_teacher["strategies"].values():
            strategy["lr"] = 0.5
        destructive_teacher = selection_teacher()
        for strategy in destructive_teacher["strategies"].values():
            strategy["lr"] = 5.0
        captured_steps = []
        gradient_injections = []
        original_execute = native_session.execute_accepted_priority_candidate
        original_scalar_gradient = candidate_microbatch.bamf_value_and_grad
        original_microbatch_gradient = candidate_microbatch.bamf_microbatch_value_and_grad

        def reverse_gradient(result):
            for name, gradient in tuple(result.gradients.items()):
                result.gradients[name] = gradient * -10.0
            mx.eval(result.gradients)
            gradient_injections.append(result)
            return result

        def destructive_scalar_gradient(*args, **kwargs):
            return reverse_gradient(original_scalar_gradient(*args, **kwargs))

        def destructive_microbatch_gradient(*args, **kwargs):
            return reverse_gradient(original_microbatch_gradient(*args, **kwargs))

        def capture_step(*args, **kwargs):
            step = original_execute(*args, **kwargs)
            captured_steps.append(step)
            return step

        with self._operator_context(fixture, teacher=baseline_teacher):
            self._admit_target(supervisor, fixture)
            self._activate_current_generated_grade()
            self._credit_all_predecessor_learning(supervisor)
            first = operate_bamf(
                self.run,
                minutes=1,
                max_visits=1,
                steps_per_visit=1,
                reserve_gib=0.0,
                source_prefetch_workers=0,
                parent_graph=self.parent_graph,
            )
            self._credit_all_predecessor_learning(supervisor)
        self.assertEqual((first.accepted, first.rejected), (1, 0))
        first_accepted = load_accepted_generation(self.run)
        self.assertIsNotNone(first_accepted.baseline_evidence)

        with self._operator_context(fixture, teacher=destructive_teacher), patch.object(
            native_session,
            "execute_accepted_priority_candidate",
            side_effect=capture_step,
        ), patch.object(
            candidate_microbatch,
            "bamf_value_and_grad",
            side_effect=destructive_scalar_gradient,
        ), patch.object(
            candidate_microbatch,
            "bamf_microbatch_value_and_grad",
            side_effect=destructive_microbatch_gradient,
        ):
            parent = load_accepted_generation(self.run)
            parent_digest = retained_digest(parent.retained_state)
            parent_optimizer = _optimizer_custody(parent.retained_state)
            parent_allocations = parent.retained_state.allocations
            parent_policy = parent.retained_state.policy
            parent_row_ages = parent_policy.row_ages
            parent_extents = parent.extents
            parent_semantic_abi = dict(parent.semantic_abi)
            parent_generation = parent.generation
            result = operate_bamf(
                self.run,
                minutes=1,
                max_visits=1,
                steps_per_visit=1,
                reserve_gib=0.0,
                source_prefetch_workers=0,
                parent_graph=self.parent_graph,
            )
            accepted = load_accepted_generation(self.run)

        self.assertEqual(result.accepted, 0)
        self.assertEqual(result.rejected, 1)
        self.assertTrue(gradient_injections)
        self.assertEqual(len(captured_steps), 1)
        candidate = captured_steps[0].transaction
        self.assertNotEqual(retained_digest(candidate), parent_digest)
        self.assertEqual(retained_digest(accepted.retained_state), parent_digest)
        accepted_optimizer = _optimizer_custody(accepted.retained_state)
        for group in ("parameters", "m", "v", "update_counts"):
            self.assertEqual(
                accepted_optimizer[group],
                parent_optimizer[group],
                f"rejected candidate changed retained optimizer {group}",
            )
        self.assertEqual(accepted.retained_state.allocations, parent_allocations)
        self.assertEqual(accepted.retained_state.policy.row_ages, parent_row_ages)
        self.assertEqual(accepted.retained_state.policy.mode, parent_policy.mode)
        self.assertEqual(accepted.retained_state.policy, parent_policy)
        self.assertEqual(accepted.extents, parent_extents)
        self.assertEqual(dict(accepted.semantic_abi), parent_semantic_abi)
        self.assertEqual(accepted.generation, parent_generation)
        self.assertEqual(
            accepted.retained_state.optimizer_step,
            parent.retained_state.optimizer_step,
        )
