"""B13.6 live generation-zero preparation and issuer authority witnesses."""
from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters
from bilqis_mlx.runtime.bamf_bundle.genesis import (
    _issue_binding, validate_initial_generation_binding,
)
from bilqis_mlx.runtime.bamf_bundle.genesis_records import (
    mint_initial_generation_binding,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    genesis_preparation, shape_patch,
)


class GenerationZeroPreparationAuthorityTests(unittest.TestCase):
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

    def test_shared_publication_sink_rejects_arbitrary_genesis_authority(self):
        from bilqis_mlx.runtime.bamf_bundle import publication

        with shape_patch():
            prepared = genesis_preparation(run_seed=229)
        with patch.object(mlx_checkpoint, "assert_headroom"), self.assertRaises(BilqisError) as failure:
            publication._publish_authorized_generation(
                self.run, prepared.candidate, object(), reserve_gib=0.)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_INITIAL_GENERATION_PREPARATION_REQUIRED")
        self.assertFalse(self.run.exists())

    def test_direct_mint_cannot_authorize_shared_publication_sink(self):
        from bilqis_mlx.runtime.bamf_bundle import publication

        with shape_patch():
            prepared = genesis_preparation(run_seed=233)
        minted = mint_initial_generation_binding(prepared.candidate)
        with patch.object(mlx_checkpoint, "assert_headroom"), self.assertRaises(BilqisError) as failure:
            publication._publish_authorized_generation(
                self.run, prepared.candidate, minted, reserve_gib=0.)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_INITIAL_GENERATION_PREPARATION_REQUIRED")
        self.assertFalse(self.run.exists())

    def test_valid_factory_cannot_issue_caller_authored_b01_candidate(self):
        with shape_patch():
            prepared = genesis_preparation(run_seed=239)
        foreign_identity = replace(
            prepared.candidate.run_identity,
            initial_implementation_sha256="1" * 64)
        foreign = replace(
            prepared.candidate,
            implementation_sha256="1" * 64,
            run_identity=foreign_identity)
        with shape_patch(), self.assertRaises(BilqisError) as failure:
            _issue_binding(
                foreign, release=prepared.release, admission=prepared.admission,
                graph=prepared.graph, origin_checkpoint=prepared.origin_checkpoint,
                factory_authority=prepared.factory_authority,
                foundation_features=prepared.foundation_features)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_INITIAL_GENERATION_MODEL_AUTHORITY_DRIFT")

    def test_valid_factory_cannot_relabel_seeded_genesis_state(self):
        with shape_patch():
            prepared = genesis_preparation(run_seed=241)
        relabeled = replace(
            prepared.candidate,
            run_identity=replace(prepared.candidate.run_identity, run_seed=242))
        with shape_patch(), self.assertRaises(BilqisError) as failure:
            _issue_binding(
                relabeled, release=prepared.release, admission=prepared.admission,
                graph=prepared.graph, origin_checkpoint=prepared.origin_checkpoint,
                factory_authority=prepared.factory_authority,
                foundation_features=prepared.foundation_features)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_DRIFT")

    def test_bootstrap_rejects_post_issuance_optimizer_hyperparameter_substitution(self):
        with shape_patch():
            prepared = genesis_preparation(run_seed=243)
        altered = replace(
            prepared.candidate,
            optimizer_hyperparameters=AdamWHyperparameters(
                .002, (.9, .95), 1e-8, .01))
        with self.assertRaises(BilqisError) as binding_failure:
            validate_initial_generation_binding(altered, prepared.binding)
        self.assertEqual(
            binding_failure.exception.context["reason"],
            "BAMF_INITIAL_GENERATION_BINDING_DRIFT")
        with self.assertRaises(BilqisError) as preparation_failure:
            replace(prepared, candidate=altered)
        self.assertEqual(
            preparation_failure.exception.context["reason"],
            "BAMF_INITIAL_GENERATION_PREPARATION_REQUIRED")
        self.assertFalse((self.run / "bamf-state.json").exists())


if __name__ == "__main__":
    unittest.main()
