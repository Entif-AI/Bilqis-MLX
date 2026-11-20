"""Finite-gradient and full-AdamW publication witness for one accepted #1300 visit."""
from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import patch

import bilqis_mlx.runtime.bamf_operator.session_parts.native_session as native_session
import bilqis_mlx.runtime.bamf_operator.session as operator_session
import bilqis_mlx.runtime.factory_candidate_microbatch as candidate_microbatch
from bilqis_mlx.runtime.atlas_admission import read_accepted_atlas_factory_release
from bilqis_mlx.runtime.bamf_bundle.feature.acceptance import (
    accepted_binding_for_manifest,
    accepted_generation,
)
from .accepted_step_assertions import (
    assert_first_baseline,
    assert_horizon_gradients,
    assert_publication_identity,
)


class AcceptedStepCapture:
    def __init__(self):
        self.steps = []
        self.gradient_results = []
        self.step_gradients = {}
        self.publications = []
        self.evaluations = []

    def context(self):
        stack = ExitStack()
        original_execute = native_session.execute_accepted_priority_candidate
        original_publish = operator_session.accept_and_publish
        original_evaluate = native_session.evaluate_factory_retention_candidate
        scalar = candidate_microbatch.bamf_value_and_grad
        microbatch = candidate_microbatch.bamf_microbatch_value_and_grad

        def capture_gradient(result):
            self.gradient_results.append(result)
            return result

        def capture_step(*args, **kwargs):
            start = len(self.gradient_results)
            step = original_execute(*args, **kwargs)
            self.steps.append(step)
            self.step_gradients[id(step)] = tuple(self.gradient_results[start:])
            return step

        def capture_publish(run_dir, *args, **kwargs):
            result = original_publish(run_dir, *args, **kwargs)
            pointer, student = accepted_generation(run_dir / "bamf-state.json")
            binding = accepted_binding_for_manifest(
                run_dir,
                pointer["manifest_sha256"],
                student,
                expected_acceptance_sha256=pointer["acceptance_sha256"],
            )
            release_sha256 = read_accepted_atlas_factory_release(
                run_dir).release_sha256
            self.publications.append((binding, student, release_sha256))
            return result

        def capture_evaluation(*args, **kwargs):
            evaluation = original_evaluate(*args, **kwargs)
            self.evaluations.append(evaluation)
            return evaluation

        stack.enter_context(patch.object(
            native_session, "execute_accepted_priority_candidate", side_effect=capture_step))
        stack.enter_context(patch.object(
            operator_session, "accept_and_publish", side_effect=capture_publish))
        stack.enter_context(patch.object(
            native_session,
            "evaluate_factory_retention_candidate",
            side_effect=capture_evaluation,
        ))
        stack.enter_context(patch.object(
            candidate_microbatch, "bamf_value_and_grad",
            side_effect=lambda *a, **k: capture_gradient(scalar(*a, **k))))
        stack.enter_context(patch.object(
            candidate_microbatch, "bamf_microbatch_value_and_grad",
            side_effect=lambda *a, **k: capture_gradient(microbatch(*a, **k))))
        return stack

    def assert_finite_nonzero(self, test, *, step=None) -> None:
        if step is None:
            test.assertTrue(self.gradient_results)
            return
        assert_horizon_gradients(test, self, step)

    def assert_published_identity(self, test, run_dir):
        return assert_publication_identity(test, self, run_dir)

    def assert_first_baseline_for(self, test, run_dir, capability_id: str) -> None:
        assert_first_baseline(test, self, run_dir, capability_id)
