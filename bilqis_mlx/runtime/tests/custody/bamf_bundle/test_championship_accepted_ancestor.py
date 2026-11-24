"""Real B13 custody proof for native championship incumbent ancestry."""
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.data_plane import data_plane
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning._atlas_candidate.identity_binding import (
    candidate_identity_for_canonical_consumer,
)
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation
from bilqis_mlx.runtime.bamf_operator.championship import _accepted_ancestor
from bilqis_mlx.runtime.tests.custody.bamf_bundle.cold_resume_probe import (
    continue_generation,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    candidate, parent_state, publish_candidate, shape_patch,
)
import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint


class ChampionshipAcceptedAncestorTests(unittest.TestCase):
    def test_cold_b13_chain_reopens_exact_historical_championship_checkpoint(self):
        with TemporaryDirectory() as tmp, patch.dict(
                os.environ, {"BILQIS_DATA_PLANE": str(Path(tmp) / "plane.sqlite3")}):
            run = Path(tmp) / "run"
            with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
                publish_candidate(run, candidate(parent_state()))
            first = continue_generation(run)
            with shape_patch():
                generation_one = load_bamf_generation(run / "bamf-state.json")
            first_manifest = first["published"]["manifest_sha256"]
            second = continue_generation(run)
            second_manifest = second["published"]["manifest_sha256"]
            third = continue_generation(run)
            with shape_patch():
                generation_three = load_bamf_generation(run / "bamf-state.json")
            pointer = json.loads((run / "bamf-state.json").read_text())
            self.assertEqual(pointer["manifest_sha256"], third["published"]["manifest_sha256"])
            # Retired intermediate tensor bytes are not a prerequisite for
            # reopening the still-owned championship checkpoint.
            plane = data_plane()
            manifests = [json.loads(plane.get_node(digest)) for digest in (
                first_manifest, second_manifest, pointer["manifest_sha256"])]
            tensors = [manifest["tensors"]["object_sha256"] for manifest in manifests]
            self.assertNotIn(tensors[1], (tensors[0], tensors[2]))
            plane.require_file_object(tensors[1]).unlink()

            checkpoint = Checkpoint(
                candidate_identity_for_canonical_consumer(
                    generation_one.retained_state),
                "bamf-generations/1",
                generation_one.retained_state.optimizer_step,
                True,
            )
            cache = type("Cache", (), {
                "accepted_manifest_sha256": pointer["manifest_sha256"],
            })()
            with shape_patch():
                reopened, manifest_sha256 = _accepted_ancestor(
                    run, generation_three, cache, checkpoint)
            self.assertEqual(reopened.generation, 1)
            self.assertEqual(manifest_sha256, first_manifest)
            self.assertEqual(
                candidate_identity_for_canonical_consumer(reopened.retained_state),
                checkpoint.sha256)

            tampered = Checkpoint(
                checkpoint.sha256, "bamf-generations/99",
                checkpoint.optimizer_step, True)
            with shape_patch(), self.assertRaises(BilqisError):
                _accepted_ancestor(run, generation_three, cache, tampered)


if __name__ == "__main__":
    unittest.main()
