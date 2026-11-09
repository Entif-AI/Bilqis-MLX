"""B13 package-import transitions preserve v1 training rules and require issuance."""
from dataclasses import replace
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime import mlx_checkpoint
import bilqis_mlx.runtime.bamf_bundle as bamf_bundle
from bilqis_mlx.runtime.bamf_bundle import (
    PackageImportTransition, load_bamf_generation,
)
from bilqis_mlx.runtime.bamf_bundle.package_import_transition import (
    _issue_package_import_transition,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    candidate, parent_state, publish_candidate, shape_patch,
)


def _transition():
    return _issue_package_import_transition(
        package_sha256="1" * 64, screened_candidate_sha256="2" * 64,
        reset_policy_sha256="3" * 64, c05_evidence_sha256="4" * 64,
        c05_policy_sha256="5" * 64, source_clearance_sha256="6" * 64)


class PackageImportTransitionTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root / "run"
        self.env = patch.dict(os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.env.start()
        self.addCleanup(self.env.stop)

    def publish(self, source):
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            return publish_candidate(self.run, source)

    def initial(self):
        state = parent_state()
        pointer = self.publish(candidate(state))
        with shape_patch():
            published = load_bamf_generation(self.run / "bamf-state.json")
        return published.retained_state, pointer

    def import_candidate(self, state, parent, transition=None):
        base = candidate(state, 1, parent)
        return replace(
            base, transition=_transition() if transition is None else transition,
            outbox=({"event": "BAMF_PACKAGE_IMPORT_ACCEPTED", "optimizer_step": state.optimizer_step},))

    def test_issued_equal_step_import_publishes_and_cold_reads_serialized_v2(self):
        state, first = self.initial()
        second = self.publish(self.import_candidate(state, first["manifest_sha256"]))
        with shape_patch():
            loaded = load_bamf_generation(self.run / "bamf-state.json")
        self.assertEqual(loaded.generation, 1)
        self.assertEqual(loaded.retained_state.optimizer_step, state.optimizer_step)
        self.assertEqual(loaded.transition["kind"], "PACKAGE_IMPORT")
        self.assertEqual(loaded.transition["package_sha256"], "1" * 64)
        self.assertEqual(second["parent_manifest_sha256"], first["manifest_sha256"])

    def test_caller_minted_matching_v2_cannot_publish(self):
        state, first = self.initial()
        forged = dict(_transition())
        with self.assertRaises(BilqisError):
            self.publish(self.import_candidate(state, first["manifest_sha256"], forged))
        pointer = json.loads((self.run / "bamf-state.json").read_text())
        self.assertEqual(pointer["manifest_sha256"], first["manifest_sha256"])

    def test_package_import_cannot_claim_a_native_optimizer_step(self):
        state, first = self.initial()
        advanced = replace(state, optimizer_step=state.optimizer_step + 1)
        with self.assertRaises(BilqisError):
            self.publish(self.import_candidate(advanced, first["manifest_sha256"]))

    def test_retained_candidate_equal_step_rule_is_unchanged(self):
        state, first = self.initial()
        with self.assertRaises(BilqisError):
            self.publish(candidate(state, 1, first["manifest_sha256"]))

    def test_package_transition_cannot_be_publicly_constructed(self):
        with self.assertRaises(BilqisError):
            PackageImportTransition()

    def test_package_transition_issuer_is_not_public(self):
        self.assertFalse(hasattr(bamf_bundle, "issue_package_import_transition"))


if __name__ == "__main__":
    import unittest
    unittest.main()
