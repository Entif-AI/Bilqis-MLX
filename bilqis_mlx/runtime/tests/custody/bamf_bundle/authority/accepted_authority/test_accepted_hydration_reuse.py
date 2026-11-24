"""Issue #1230: one numerical hydration per unchanged accepted generation."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.runtime.bamf_bundle.accepted_runtime import (
    _reset_execution_cache_owner_for_tests,
)
from bilqis_mlx.runtime.bamf_bundle.admission import (
    bind_accepted_execution_cache, load_accepted_generation,
)
from bilqis_mlx.runtime.bamf_bundle.accepted_runtime import (
    load_accepted_generation_with_pointer_if_cached,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    candidate, next_accepted_step, parent_state, publish_candidate, shape_patch,
)


class AcceptedHydrationReuseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run = self.root / "run"
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.environment.start()

    def tearDown(self):
        _reset_execution_cache_owner_for_tests()
        self.environment.stop()
        self.temporary.cleanup()

    def publish(self, source):
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            return publish_candidate(self.run, source)

    def test_unchanged_generation_reuses_exact_student_after_one_payload_load(self):
        self.publish(candidate(parent_state()))
        _reset_execution_cache_owner_for_tests()
        original = mlx_checkpoint.load_bamf_state_payload
        with shape_patch(), patch.object(
                mlx_checkpoint, "load_bamf_state_payload", wraps=original) as payload:
            first = load_accepted_generation(self.run)
            cache = bind_accepted_execution_cache(self.run)
            second = load_accepted_generation(self.run)
            rebound = bind_accepted_execution_cache(self.run)
        self.assertIs(second, first)
        self.assertIs(rebound, cache)
        self.assertEqual(payload.call_count, 1)

    def test_unchanged_hot_hydration_does_not_reverify_initial_factory_release(self):
        self.publish(candidate(parent_state()))
        _reset_execution_cache_owner_for_tests()
        from bilqis_mlx.runtime.bamf_bundle.publication import factory_release

        original = factory_release.require_initial_factory_release
        with shape_patch(), patch.object(
                factory_release, "require_initial_factory_release",
                wraps=original) as require_release:
            first = load_accepted_generation(self.run)
            second = load_accepted_generation(self.run)

        self.assertIs(second, first)
        self.assertEqual(require_release.call_count, 1)

    def test_new_generation_hydrates_once_and_cold_reset_rechecks_lineage(self):
        first_pointer = self.publish(candidate(parent_state()))
        _reset_execution_cache_owner_for_tests()
        original = mlx_checkpoint.load_bamf_state_payload
        with shape_patch(), patch.object(
                mlx_checkpoint, "load_bamf_state_payload", wraps=original) as payload:
            first = load_accepted_generation(self.run)
            self.assertIs(load_accepted_generation(self.run), first)
        self.assertEqual(payload.call_count, 1)

        successor = candidate(
            next_accepted_step(parent_state()), generation=1,
            parent=first_pointer["manifest_sha256"])
        self.publish(successor)
        with shape_patch(), patch.object(
                mlx_checkpoint, "load_bamf_state_payload", wraps=original) as payload:
            second = load_accepted_generation(self.run)
            self.assertIs(load_accepted_generation(self.run), second)
        self.assertIsNot(second, first)
        self.assertEqual(payload.call_count, 1)

        _reset_execution_cache_owner_for_tests()
        with shape_patch(), patch.object(
                mlx_checkpoint, "load_bamf_state_payload", wraps=original) as payload:
            cold = load_accepted_generation(self.run)
            self.assertIs(load_accepted_generation(self.run), cold)
        self.assertEqual(cold.generation, 1)
        # Durable accepted authority makes cold restart current-only: the parent
        # transition was established at publication and is not replayed here.
        self.assertEqual(payload.call_count, 1)

    def test_if_cached_lookup_declines_stale_generation_after_publication(self):
        first_pointer = self.publish(candidate(parent_state()))
        _reset_execution_cache_owner_for_tests()
        with shape_patch():
            first = load_accepted_generation(self.run)
            cached = load_accepted_generation_with_pointer_if_cached(self.run)
        self.assertIsNotNone(cached)
        self.assertIs(cached[1], first)

        successor = candidate(
            next_accepted_step(parent_state()), generation=1,
            parent=first_pointer["manifest_sha256"])
        self.publish(successor)

        with shape_patch():
            self.assertIsNone(load_accepted_generation_with_pointer_if_cached(self.run))
            second = load_accepted_generation(self.run)
            self.assertEqual(second.generation, 1)
            self.assertIs(load_accepted_generation_with_pointer_if_cached(self.run)[1], second)

    def test_cold_hydration_cost_is_invariant_to_lineage_depth(self):
        pointer = self.publish(candidate(parent_state()))
        state = parent_state()
        state = next_accepted_step(state)
        pointer = self.publish(candidate(
            state, generation=1, parent=pointer["manifest_sha256"]))

        _reset_execution_cache_owner_for_tests()
        original = mlx_checkpoint.load_bamf_state_payload
        with shape_patch(), patch.object(
                mlx_checkpoint, "load_bamf_state_payload", wraps=original) as payload:
            shallow = load_accepted_generation(self.run)
        shallow_payload_loads = payload.call_count
        self.assertEqual(shallow.generation, 1)

        for generation in range(2, 6):
            state = next_accepted_step(state)
            pointer = self.publish(candidate(
                state, generation=generation,
                parent=pointer["manifest_sha256"]))

        _reset_execution_cache_owner_for_tests()
        with shape_patch(), patch.object(
                mlx_checkpoint, "load_bamf_state_payload", wraps=original) as payload:
            deep = load_accepted_generation(self.run)
        deep_payload_loads = payload.call_count
        self.assertEqual(deep.generation, 5)
        self.assertEqual(shallow_payload_loads, 1)
        self.assertEqual(deep_payload_loads, shallow_payload_loads)


if __name__ == "__main__":
    unittest.main()
