"""Destructive-candidate rollback witness reusable inside one #1300 run."""
from __future__ import annotations

from contextlib import ExitStack
import hashlib
from unittest.mock import patch

import mlx.core as mx
import numpy as np

import bilqis_mlx.runtime.bamf_operator.session_parts.native_session as native_session
import bilqis_mlx.runtime.factory_candidate_microbatch as candidate_microbatch
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.runtime.tests.custody.bamf_bundle.cold_resume_probe import retained_digest
from .accepted_step_assertions import assert_horizon_gradients


def _array_group_digest(values) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(values.items()):
        digest.update(name.encode("utf-8"))
        digest.update(np.asarray(value).tobytes())
    return digest.hexdigest()


def optimizer_custody(state) -> dict[str, str]:
    return {
        group: _array_group_digest(getattr(state.optimizer, group))
        for group in ("parameters", "m", "v", "update_counts")
    }


def parent_custody(parent, run_dir) -> dict:
    policy = parent.retained_state.policy
    return {
        "pointer_bytes": (run_dir / "bamf-state.json").read_bytes(),
        "retained_digest": retained_digest(parent.retained_state),
        "optimizer": optimizer_custody(parent.retained_state),
        "allocations": parent.retained_state.allocations,
        "policy": policy,
        "row_ages": policy.row_ages,
        "extents": parent.extents,
        "semantic_abi": dict(parent.semantic_abi),
        "learning_health_state": parent.learning_health_state,
        "generation": parent.generation,
        "optimizer_step": parent.retained_state.optimizer_step,
    }


class DestructiveCandidateCapture:
    def __init__(self):
        self.steps = []
        self.gradients = []
        self.step_gradients = {}

    def context(self):
        stack = ExitStack()
        original_execute = native_session.execute_accepted_priority_candidate
        scalar = candidate_microbatch.bamf_value_and_grad
        microbatch = candidate_microbatch.bamf_microbatch_value_and_grad

        def reverse(result):
            for name, gradient in tuple(result.gradients.items()):
                result.gradients[name] = gradient * -10.0
            mx.eval(result.gradients)
            self.gradients.append(result)
            return result

        def capture(*args, **kwargs):
            start = len(self.gradients)
            step = original_execute(*args, **kwargs)
            self.steps.append(step)
            self.step_gradients[id(step)] = tuple(self.gradients[start:])
            return step

        stack.enter_context(patch.object(
            native_session, "execute_accepted_priority_candidate", side_effect=capture))
        stack.enter_context(patch.object(
            candidate_microbatch, "bamf_value_and_grad",
            side_effect=lambda *a, **k: reverse(scalar(*a, **k))))
        stack.enter_context(patch.object(
            candidate_microbatch, "bamf_microbatch_value_and_grad",
            side_effect=lambda *a, **k: reverse(microbatch(*a, **k))))
        return stack


def assert_complete_rollback(test, run_dir, before: dict, capture) -> None:
    accepted = load_accepted_generation(run_dir)
    test.assertTrue(capture.gradients)
    test.assertTrue(capture.steps)
    terminal = capture.steps[-1]
    candidate = terminal.transaction
    assert_horizon_gradients(test, capture, terminal)
    start_index = len(capture.steps) - candidate.update_steps
    test.assertGreaterEqual(start_index, 0)
    attempt_steps = tuple(capture.steps[start_index:])
    test.assertEqual(
        tuple(step.transaction.update_steps for step in attempt_steps),
        tuple(range(1, candidate.update_steps + 1)),
    )
    test.assertTrue(all(
        step.transaction.parent is candidate.parent for step in attempt_steps
    ))
    test.assertTrue(all(
        step.transaction.step_proofs
        == candidate.step_proofs[:step.transaction.update_steps]
        for step in attempt_steps
    ))
    test.assertTrue(all(capture.step_gradients.get(id(step)) for step in attempt_steps))
    test.assertNotEqual(retained_digest(candidate), before["retained_digest"])
    test.assertEqual(
        (run_dir / "bamf-state.json").read_bytes(),
        before["pointer_bytes"],
    )
    test.assertEqual(retained_digest(accepted.retained_state), before["retained_digest"])
    actual_optimizer = optimizer_custody(accepted.retained_state)
    for group in ("parameters", "m", "v", "update_counts"):
        test.assertEqual(actual_optimizer[group], before["optimizer"][group])
    test.assertEqual(accepted.retained_state.allocations, before["allocations"])
    test.assertEqual(accepted.retained_state.policy.row_ages, before["row_ages"])
    test.assertEqual(accepted.retained_state.policy, before["policy"])
    test.assertEqual(accepted.extents, before["extents"])
    test.assertEqual(dict(accepted.semantic_abi), before["semantic_abi"])
    test.assertEqual(accepted.learning_health_state, before["learning_health_state"])
    test.assertEqual(accepted.generation, before["generation"])
    test.assertEqual(
        accepted.retained_state.optimizer_step,
        before["optimizer_step"],
    )
