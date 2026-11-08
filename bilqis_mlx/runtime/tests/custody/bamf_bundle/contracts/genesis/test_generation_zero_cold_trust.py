"""B13.6 cold accepted custody requires an external generation-zero trust root."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.data_plane import close_data_planes
import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation_authority
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.runtime.bamf_bundle.codec import save_bamf_bundle
from bilqis_mlx.runtime.bamf_bundle.genesis.records import (
    mint_initial_generation_binding,
)
from bilqis_mlx.runtime.bamf_bundle.records import BAMF_POINTER_SCHEMA, canonical
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    genesis_preparation, publish_genesis, shape_patch,
)


class GenerationZeroColdTrustTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run = self.root / "run"
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.environment.start()

    def tearDown(self):
        close_data_planes()
        self.environment.stop()
        self.temporary.cleanup()

    def _install_package_local_genesis(self):
        with shape_patch():
            prepared = genesis_preparation(run_seed=1301)
        stage = self.run / "forged-stage"
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            manifest = save_bamf_bundle(prepared.candidate, stage, reserve_gib=0.)
        digest = manifest["manifest_sha256"]
        target = self.run / "bamf-bundles" / digest
        target.parent.mkdir(parents=True)
        stage.rename(target)

        package_local = mint_initial_generation_binding(prepared.candidate)
        acceptance_root = self.run / "bamf-acceptance"
        acceptance_root.mkdir()
        (acceptance_root / f"{digest}.json").write_bytes(
            canonical(package_local.to_record()))
        pointer = {
            "schema": BAMF_POINTER_SCHEMA,
            "run_id": prepared.candidate.run_id,
            "generation": 0,
            "parent_manifest_sha256": None,
            "bundle": f"bamf-bundles/{digest}",
            "manifest_sha256": digest,
            "acceptance_sha256": package_local.digest,
        }
        (self.run / "bamf-state.json").write_bytes(canonical(pointer))
        return pointer

    def test_package_local_genesis_cannot_become_live_accepted_custody(self):
        self._install_package_local_genesis()
        with shape_patch(), self.assertRaises(BilqisError) as accepted_failure:
            load_accepted_generation(self.run)
        self.assertEqual(
            accepted_failure.exception.context["reason"],
            "BAMF_INITIAL_GENERATION_TRUST_ROOT_REQUIRED")

        with shape_patch(), self.assertRaises(BilqisError) as authority_failure:
            load_bamf_generation_authority(self.run / "bamf-state.json")
        self.assertEqual(
            authority_failure.exception.context["reason"],
            "BAMF_INITIAL_GENERATION_TRUST_ROOT_REQUIRED")

    def test_owner_published_trust_root_survives_data_plane_reopen(self):
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            pointer = publish_genesis(self.run, run_seed=1303)
        close_data_planes()

        with shape_patch():
            accepted = load_accepted_generation(self.run)
            authoritative, manifest = load_bamf_generation_authority(
                self.run / "bamf-state.json")

        self.assertEqual(accepted.run_identity.run_seed, 1303)
        self.assertEqual(authoritative.run_identity, accepted.run_identity)
        self.assertEqual(manifest, pointer["manifest_sha256"])


if __name__ == "__main__":
    unittest.main()
