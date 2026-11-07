"""B13.6 generation-zero source authority cannot be caller-invented."""
from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle import publish_initial_generation
from bilqis_mlx.runtime.bamf_bundle.genesis import _issue_binding
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    genesis_preparation, shape_patch,
)


class GenerationZeroSourceAuthorityTests(unittest.TestCase):
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

    def test_direct_issuer_rejects_unvalidated_factory_origin(self):
        with shape_patch():
            prepared = genesis_preparation(run_seed=211)
        with self.assertRaises(BilqisError) as failure:
            _issue_binding(
                prepared.candidate, release=object(), admission=object(),
                graph={}, origin_checkpoint=object())
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_INVALID")

    def test_foreign_provenance_rejects_before_pointer_mutation(self):
        with shape_patch():
            prepared = genesis_preparation(run_seed=223)
        foreign = replace(
            prepared.candidate,
            provenance=replace(
                prepared.candidate.provenance,
                source_identity="caller-invented-source",
                release_digest="1" * 64,
                teacher_identity="caller-invented-teacher",
                teacher_epoch=999),
            teacher_state={
                **prepared.candidate.teacher_state,
                "teacher_identity": "caller-invented-teacher",
                "teacher_epoch": 999,
            },
            correction_frontier={
                **prepared.candidate.correction_frontier,
                "source_identity": "caller-invented-source",
                "release_digest": "1" * 64,
            },
        )
        forged = replace(prepared, candidate=foreign)
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            with self.assertRaises(BilqisError) as failure:
                publish_initial_generation(self.run, forged, reserve_gib=0.)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_DRIFT")
        self.assertFalse((self.run / "bamf-state.json").exists())


if __name__ == "__main__":
    unittest.main()
