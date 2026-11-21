"""Issue #1526: protected accepted tip makes pointer recovery bounded and rollback-safe."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.runtime.bamf_bundle.accepted_runtime import (
    _reset_execution_cache_owner_for_tests, bind_accepted_execution_cache,
)
from bilqis_mlx.runtime.bamf_bundle.publication import (
    _atomic_pointer,
)
import bilqis_mlx.runtime.bamf_bundle.publication as publication
from bilqis_mlx.runtime.bamf_bundle.publication.accepted_authority_checkpoint import (
    read_protected_accepted_authority_tip,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    candidate, next_accepted_step, parent_state, publish_candidate, shape_patch,
)


class AcceptedAuthorityRecoveryTests(unittest.TestCase):
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

    def successor(self, pointer, state):
        return candidate(
            state, generation=pointer["generation"] + 1,
            parent=pointer["manifest_sha256"])

    def test_crash_after_tip_commit_recovers_exact_child_pointer_forward(self):
        first = self.publish(candidate(parent_state()))
        child = self.successor(first, next_accepted_step(parent_state()))
        original_atomic = publication._atomic_pointer
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"), patch.object(
                publication, "_atomic_pointer",
                side_effect=RuntimeError("crash after protected tip")):
            with self.assertRaisesRegex(RuntimeError, "protected tip"):
                publish_candidate(self.run, child)

        # Filesystem pointer is still the parent, but protected B13 authority has
        # committed exactly one child. Ordinary load may only reconcile forward.
        _reset_execution_cache_owner_for_tests()
        with shape_patch():
            accepted = load_accepted_generation(self.run)
        self.assertEqual(accepted.generation, 1)
        import json
        pointer = json.loads((self.run / "bamf-state.json").read_text())
        self.assertEqual(pointer["generation"], 1)
        self.assertNotEqual(pointer["manifest_sha256"], first["manifest_sha256"])

    def test_cache_bind_recovers_tip_ahead_before_operator_host_use(self):
        first = self.publish(candidate(parent_state()))
        child = self.successor(first, next_accepted_step(parent_state()))
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"), patch.object(
                publication, "_atomic_pointer",
                side_effect=RuntimeError("crash after protected tip")):
            with self.assertRaisesRegex(RuntimeError, "protected tip"):
                publish_candidate(self.run, child)

        _reset_execution_cache_owner_for_tests()
        with shape_patch():
            cache = bind_accepted_execution_cache(self.run)
        self.assertEqual(cache.generation, 1)
        self.assertEqual(
            cache.accepted_manifest_sha256,
            read_protected_accepted_authority_tip("fixture-run").manifest_sha256,
        )
        import json
        pointer = json.loads((self.run / "bamf-state.json").read_text())
        self.assertEqual(pointer["generation"], 1)
        self.assertEqual(pointer["manifest_sha256"], cache.accepted_manifest_sha256)

    def test_checkpoint_commit_failure_retry_cannot_publish_uncheckpointed_genesis(self):
        source = candidate(parent_state())
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"), patch(
                "bilqis_mlx.runtime.bamf_bundle.publication.accepted_authority_commit."
                "commit_accepted_authority",
                side_effect=RuntimeError("checkpoint commit failed")):
            with self.assertRaisesRegex(RuntimeError, "checkpoint commit failed"):
                publish_candidate(self.run, source)

        self.assertFalse((self.run / "bamf-state.json").exists())
        self.assertIsNone(read_protected_accepted_authority_tip("fixture-run"))

        published = self.publish(source)
        tip = read_protected_accepted_authority_tip("fixture-run")
        self.assertIsNotNone(tip)
        self.assertEqual(tip.manifest_sha256, published["manifest_sha256"])
        _reset_execution_cache_owner_for_tests()
        with shape_patch():
            accepted = load_accepted_generation(self.run)
        self.assertEqual(accepted.generation, 0)

    def test_pointer_rollback_more_than_one_generation_never_becomes_current(self):
        first = self.publish(candidate(parent_state()))
        second_state = next_accepted_step(parent_state())
        second = self.publish(self.successor(first, second_state))
        third = self.publish(self.successor(second, next_accepted_step(second_state)))
        self.assertEqual(third["generation"], 2)

        _atomic_pointer(self.run / "bamf-state.json", first)
        _reset_execution_cache_owner_for_tests()
        with shape_patch(), self.assertRaises(BilqisError) as failure:
            load_accepted_generation(self.run)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_ACCEPTED_AUTHORITY_TIP_DRIFT",
        )


if __name__ == "__main__":
    unittest.main()
