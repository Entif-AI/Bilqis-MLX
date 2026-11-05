"""B09/B11/B12 production admission through current B13 authority."""
from __future__ import annotations

import inspect
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from bilqis_mlx.runtime.atlas_candidate_step import admit_current_candidate_step
from bilqis_mlx.runtime.bamf_bundle import publish_bamf_generation
from bilqis_mlx.runtime.bamf_bundle.execution_cache import (
    bind_accepted_execution_cache,
)
import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.runtime.model_topology_v2 import ParameterCensus
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    DECLARED, HP, candidate, parent_state, shape_patch,
)


class CurrentAuthorityAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run = self.root / "run"
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")}
        )
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def publish_parent(self):
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            return publish_bamf_generation(self.run, candidate(parent_state()))

    def test_execution_cache_is_minted_from_current_b13_authority(self):
        published = self.publish_parent()
        pointer = self.run / "bamf-state.json"
        with shape_patch(), patch(
            "bilqis_mlx.runtime.backbone_identity.expected_bamf_shapes",
            return_value=DECLARED,
        ), patch(
            "bilqis_mlx.runtime.topology_v2.validation.expected_bamf_shapes",
            return_value=DECLARED,
        ):
            cache = bind_accepted_execution_cache(pointer)
        self.assertEqual(cache.run_id, "fixture-run")
        self.assertEqual(cache.generation, 0)
        self.assertEqual(
            cache.accepted_manifest_sha256, published["manifest_sha256"]
        )
        self.assertEqual(
            cache.motif_manifest.digest, parent_state().allocations.manifest.digest
        )

    def test_public_candidate_admission_derives_all_authority_from_b13(self):
        published = self.publish_parent()
        pointer = self.run / "bamf-state.json"
        parameters = set(inspect.signature(admit_current_candidate_step).parameters)
        for forbidden in (
            "group_eligible",
            "active_admitted",
            "spec",
            "extents",
            "run_id",
            "generation",
            "parent_manifest_sha256",
            "parent_candidate_identity_sha256",
            "parent_optimizer_step",
            "topology_digest",
            "candidate_step_ordinal",
        ):
            self.assertNotIn(forbidden, parameters)

        parent = candidate(parent_state())
        with shape_patch(), patch(
            "bilqis_mlx.runtime.atlas_candidate_step.bamf_parameter_census",
            return_value=ParameterCensus(
                parent.topology.digest, parent.extents.digest, DECLARED
            ),
        ), patch(
            "bilqis_mlx.learning.atlas_participation_census.expected_bamf_shapes",
            return_value=DECLARED,
        ), patch(
            "bilqis_mlx.learning._retention.atlas_participation_census.expected_bamf_shapes",
            return_value=DECLARED,
        ):
            transaction = admit_current_candidate_step(
                pointer,
                loss_bearing_target=False,
                teacher_hparams=HP,
                decay={"identity.bank.0": True},
                max_norm=1.0,
            )
        self.assertEqual(
            transaction.parent.custody.manifest_sha256,
            published["manifest_sha256"],
        )
        self.assertEqual(transaction.update_steps, 0)


if __name__ == "__main__":
    unittest.main()
