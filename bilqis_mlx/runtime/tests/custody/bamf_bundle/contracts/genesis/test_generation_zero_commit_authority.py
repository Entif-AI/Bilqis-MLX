"""Generation-zero publication revalidates source authority at commit."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.bamf_bundle.publication as publication
import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle import publish_initial_generation
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    genesis_preparation, shape_patch,
)
from bilqis_mlx.state_dag import persist, read_current


def _advance_factory_source(prepared) -> None:
    source = Path(prepared.factory_authority.source_run_dir)
    current = read_current(source)
    advanced = dict(current)
    advanced["generation"] = current["generation"] + 1
    school = dict(current["school"])
    checkpoint = dict(school["current_student"])
    checkpoint.update(
        optimizer_step=checkpoint["optimizer_step"] + 1,
        sha256="8" * 64, filename="bundles/advanced")
    school["current_student"] = checkpoint
    advanced["school"] = school
    persist(source, advanced)


class GenerationZeroCommitAuthorityTests(unittest.TestCase):
    def test_factory_advance_during_staging_rejects_before_pointer_install(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "run"
            with patch.dict(os.environ, {"BILQIS_DATA_PLANE": str(root / "plane.sqlite3")}), \
                    shape_patch():
                prepared = genesis_preparation(run_seed=127)
                save = publication._save_publication_bundle

                def stage_then_advance(*args, **kwargs):
                    manifest = save(*args, **kwargs)
                    _advance_factory_source(prepared)
                    return manifest

                with patch.object(mlx_checkpoint, "assert_headroom"), \
                        patch.object(publication, "_save_publication_bundle",
                                     side_effect=stage_then_advance), \
                        self.assertRaises(BilqisError) as failure:
                    publish_initial_generation(run, prepared, reserve_gib=0.)

            self.assertEqual(
                failure.exception.context["reason"],
                "BAMF_INITIAL_GENERATION_FACTORY_AUTHORITY_DRIFT")
            self.assertFalse((run / "bamf-state.json").exists())


if __name__ == "__main__":
    unittest.main()
