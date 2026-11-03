"""B13.5 accepted-generation acceptance-provenance witnesses.

Publication is not acceptance. A generation may only be published, and may only
mint accepted-generation authority, when the retention owner has accepted the
exact candidate state.
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import (
    AcceptedCandidateBinding, mint_acceptance_binding,
)
from bilqis_mlx.runtime.bamf_bundle import (
    publish_bamf_generation, read_accepted_generation_feature_receipt,
)

from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    acceptance, accepted_state, candidate, parent_state, shape_patch,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.test_feature_authority import (
    FEATURE_SCHEMA, RELEASE, source_features, feature_bound,
)


class GenerationAcceptanceProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run = self.root / "run"
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def publish(self, source, **kwargs):
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            return publish_bamf_generation(self.run, source, **kwargs)

    def test_publication_without_retention_acceptance_is_refused(self):
        with self.assertRaises(BilqisError) as failure:
            self.publish(candidate(parent_state()))
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_GENERATION_ACCEPTANCE_REQUIRED")
        self.assertFalse((self.run / "bamf-state.json").exists())

    def test_acceptance_for_another_candidate_state_is_refused(self):
        source = candidate(parent_state())
        other = acceptance(candidate(accepted_state(parent_state())))
        with self.assertRaises(BilqisError) as failure:
            self.publish(source, acceptance=other)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_GENERATION_ACCEPTANCE_DRIFT")

    def test_acceptance_with_another_feature_identity_is_refused(self):
        source = candidate(parent_state())
        binding = mint_acceptance_binding(
            source.retained_state, run_id=source.run_id,
            generation=source.generation, feature_sha256="a" * 64,
            retention_reason="FIXTURE_RETENTION_ACCEPTED")
        with self.assertRaises(BilqisError) as failure:
            self.publish(source, acceptance=binding)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_GENERATION_ACCEPTANCE_DRIFT")

    def test_caller_cannot_construct_an_acceptance_binding(self):
        source = candidate(parent_state())
        binding = acceptance(source)
        with self.assertRaises(BilqisError):
            AcceptedCandidateBinding(
                binding.run_id, binding.generation,
                binding.candidate_identity_sha256, binding.feature_sha256,
                binding.optimizer_step, binding.retention_reason)

    def test_receipt_refuses_a_generation_without_acceptance_custody(self):
        features = source_features()
        source = feature_bound(candidate(parent_state()), features)
        self.publish(source, acceptance=acceptance(source))
        binding_path = (self.run / "bamf-acceptance"
                        / f"{json_manifest_sha(self.run)}.json")
        binding_path.unlink()
        with shape_patch(), \
                patch("bilqis_mlx.runtime.bamf_bundle.feature_authority."
                      "build_feature_manifest", return_value=features), \
                patch("bilqis_mlx.runtime.bamf_bundle.feature_authority."
                      "load_pinned_atlas_snapshot", side_effect=lambda selection: selection):
            with self.assertRaises(BilqisError) as failure:
                read_accepted_generation_feature_receipt(
                    self.run / "bamf-state.json", "/artifact")
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_GENERATION_ACCEPTANCE_MISSING")


def json_manifest_sha(run_dir: Path) -> str:
    import json
    return json.loads((run_dir / "bamf-state.json").read_text())["manifest_sha256"]


if __name__ == "__main__":
    unittest.main()
