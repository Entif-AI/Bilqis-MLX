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
from bilqis_mlx.runtime.bamf_bundle import genesis as genesis_owner
from bilqis_mlx.runtime.model_topology_v2 import (
    B01GenerationAuthority, ParameterCensus, b01_generation_authority,
)
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

    def test_wrong_b01_model_authority_rejects_before_allocation(self):
        with shape_patch():
            prepared = genesis_preparation(run_seed=227)
        expected = b01_generation_authority(prepared.candidate.extents)
        census = expected.parameter_census
        wrong = (
            B01GenerationAuthority(
                ParameterCensus(
                    "0" * 64, census.extents_digest, census.parameters),
                expected.implementation_sha256),
            B01GenerationAuthority(
                ParameterCensus(
                    census.topology_digest, "0" * 64, census.parameters),
                expected.implementation_sha256),
            B01GenerationAuthority(
                census, "0" * 64),
        )
        with patch.object(
                genesis_owner, "_create_unbound_bamf_optimizer",
                side_effect=AssertionError("model allocation reached")):
            for authority in wrong:
                with self.subTest(authority=authority), self.assertRaises(BilqisError) as failure:
                    genesis_owner.prepare_initial_generation(
                        run_id=prepared.candidate.run_id,
                        run_seed=prepared.candidate.run_identity.run_seed,
                        origin_checkpoint=prepared.origin_checkpoint,
                        release=prepared.release, admission=prepared.admission,
                        graph=prepared.graph, model_authority=authority,
                        optimizer_hyperparameters=prepared.candidate.optimizer_hyperparameters,
                        provenance=prepared.candidate.provenance,
                        semantic_abi=prepared.candidate.semantic_abi,
                        compiler_features=prepared.candidate.compiler_features,
                        correction_frontier=prepared.candidate.correction_frontier,
                        teacher_state=prepared.candidate.teacher_state,
                        evaluation_contract=prepared.candidate.evaluation_contract,
                        delivery_events=prepared.candidate.outbox)
                self.assertEqual(
                    failure.exception.context["reason"],
                    "BAMF_INITIAL_GENERATION_MODEL_AUTHORITY_DRIFT")

    def test_shared_publication_sink_rejects_arbitrary_genesis_authority(self):
        from bilqis_mlx.runtime.bamf_bundle import publication

        with shape_patch():
            prepared = genesis_preparation(run_seed=229)
        with patch.object(mlx_checkpoint, "assert_headroom"), self.assertRaises(BilqisError) as failure:
            publication._publish_authorized_generation(
                self.run, prepared.candidate, object(), reserve_gib=0.)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_INITIAL_GENERATION_BINDING_DRIFT")
        self.assertFalse(self.run.exists())


if __name__ == "__main__":
    unittest.main()
