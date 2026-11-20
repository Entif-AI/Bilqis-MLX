"""Destructive-candidate rollback witness reusable inside one #1300 run."""
from __future__ import annotations

from contextlib import ExitStack
import hashlib
from unittest.mock import patch

import mlx.core as mx
import numpy as np

import bilqis_mlx.runtime.bamf_operator.session_parts.native_session as native_session
import bilqis_mlx.runtime.factory_candidate_microbatch as candidate_microbatch
from bilqis_mlx.learning.frame_embeddings.common import BANK_ROWS
from bilqis_mlx.runtime.atlas_optimizer import AdamWStateTree
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.semantics.abi import load_historical_graph
from bilqis_mlx.runtime.tests.custody.bamf_bundle.cold_resume_probe import retained_digest
from .accepted_step_assertions import assert_horizon_gradients
from .constants import FALSE_SYMBOL, TRUE_SYMBOL


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


def collapse_semantic_pair(parameters, keep_index: int, collapse_index: int):
    """Collapse one active semantic row onto another without changing tree shape."""
    if (type(keep_index) is not int or keep_index < 0
            or type(collapse_index) is not int or collapse_index < 0
            or keep_index == collapse_index):
        raise ValueError("CONFORMANCE_1300_COLLAPSE_INDEX_INVALID")
    keep_bank, keep_row = divmod(keep_index, BANK_ROWS)
    collapse_bank, collapse_row = divmod(collapse_index, BANK_ROWS)
    keep_name = f"identity.bank.{keep_bank}"
    collapse_name = f"identity.bank.{collapse_bank}"
    if keep_name not in parameters or collapse_name not in parameters:
        raise ValueError("CONFORMANCE_1300_COLLAPSE_BANK_MISSING")
    changed = dict(parameters)
    source = changed[keep_name][keep_row]
    target = changed[collapse_name][collapse_row]
    changed[collapse_name] = changed[collapse_name].at[collapse_row].add(
        source - target
    )
    mx.eval(changed[collapse_name])
    return changed


def boolean_literal_indices() -> tuple[int, int]:
    """Resolve tied FALSE/TRUE rows from the protected historical ABI."""
    tokens = load_historical_graph()["tokens"]
    return tokens.index(FALSE_SYMBOL), tokens.index(TRUE_SYMBOL)


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
    def __init__(self, *, collapse_semantic_indices: tuple[int, int] | None = None):
        self.steps = []
        self.gradients = []
        self.step_gradients = {}
        self.evaluations = []
        self.collapse_semantic_indices = (
            boolean_literal_indices()
            if collapse_semantic_indices is None
            else collapse_semantic_indices
        )

    def context(self):
        stack = ExitStack()
        original_execute = native_session.execute_accepted_priority_candidate
        original_evaluate = native_session.evaluate_factory_retention_candidate
        scalar = candidate_microbatch.bamf_value_and_grad
        microbatch = candidate_microbatch.bamf_microbatch_value_and_grad

        def capture_gradient(result):
            self.gradients.append(result)
            return result

        def destroy_parameter_delta(transaction):
            """Adversarially perturb one disposable candidate after real AdamW work.

            Keep the production CandidateTransaction object, its native gradient
            proofs, update counts, moments, and training authority intact.  Only
            replace its speculative numerical optimizer tree, then re-run the
            transaction's own structural validation before C05 sees it.
            """
            parameters = collapse_semantic_pair(
                transaction.optimizer.parameters,
                *self.collapse_semantic_indices,
            )
            optimizer = AdamWStateTree(
                parameters,
                transaction.optimizer.m,
                transaction.optimizer.v,
                transaction.optimizer.update_counts,
            )
            object.__setattr__(transaction, "optimizer", optimizer)
            transaction.__post_init__()
            return transaction

        def capture(*args, **kwargs):
            start = len(self.gradients)
            step = original_execute(*args, **kwargs)
            destroy_parameter_delta(step.transaction)
            self.steps.append(step)
            self.step_gradients[id(step)] = tuple(self.gradients[start:])
            return step

        def capture_evaluation(*args, **kwargs):
            evaluation = original_evaluate(*args, **kwargs)
            self.evaluations.append(evaluation)
            return evaluation

        stack.enter_context(patch.object(
            native_session, "execute_accepted_priority_candidate", side_effect=capture))
        stack.enter_context(patch.object(
            native_session, "evaluate_factory_retention_candidate",
            side_effect=capture_evaluation))
        stack.enter_context(patch.object(
            candidate_microbatch, "bamf_value_and_grad",
            side_effect=lambda *a, **k: capture_gradient(scalar(*a, **k))))
        stack.enter_context(patch.object(
            candidate_microbatch, "bamf_microbatch_value_and_grad",
            side_effect=lambda *a, **k: capture_gradient(microbatch(*a, **k))))
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
    candidate_optimizer = optimizer_custody(candidate)
    test.assertNotEqual(
        candidate_optimizer["parameters"], before["optimizer"]["parameters"])
    test.assertTrue(any(
        candidate_optimizer[group] != before["optimizer"][group]
        for group in ("m", "v", "update_counts")
    ))
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
