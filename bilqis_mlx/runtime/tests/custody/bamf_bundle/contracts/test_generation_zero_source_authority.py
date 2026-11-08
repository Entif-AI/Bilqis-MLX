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
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.atlas_plasticity import IdentityRowAge, PlasticityPolicy
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters
from bilqis_mlx.runtime.bamf_bundle import publish_initial_generation
from bilqis_mlx.runtime.bamf_bundle.genesis import (
    _issue_binding, validate_initial_generation_binding,
)
from bilqis_mlx.runtime.bamf_bundle import genesis as genesis_owner
from bilqis_mlx.runtime.bamf_bundle.genesis_records import (
    mint_initial_generation_binding,
)
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

    def test_plain_factory_receipt_and_checkpoint_do_not_establish_bootstrap_authority(self):
        """Self-consistent Factory values are not the persisted runtime owner's grant."""
        with shape_patch():
            prepared = genesis_preparation(run_seed=219)
        with shape_patch(), self.assertRaises(BilqisError):
            genesis_owner.prepare_initial_generation(
                run_id=prepared.candidate.run_id,
                run_seed=prepared.candidate.run_identity.run_seed,
                origin_checkpoint=prepared.origin_checkpoint,
                release=prepared.release,
                admission=prepared.admission,
                graph=prepared.graph,
                model_authority=b01_generation_authority(prepared.candidate.extents),
                optimizer_hyperparameters=prepared.candidate.optimizer_hyperparameters,
                provenance=prepared.candidate.provenance,
                foundation_features=prepared.foundation_features,
                delivery_events=prepared.candidate.outbox)

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
        with shape_patch(), self.assertRaises(BilqisError) as failure:
            _issue_binding(
                foreign, release=prepared.release, admission=prepared.admission,
                graph=prepared.graph, origin_checkpoint=prepared.origin_checkpoint,
                factory_authority=prepared.factory_authority,
                foundation_features=prepared.foundation_features)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_DRIFT")
        with self.assertRaises(BilqisError) as preparation_failure:
            replace(prepared, candidate=foreign)
        self.assertEqual(
            preparation_failure.exception.context["reason"],
            "BAMF_INITIAL_GENERATION_PREPARATION_REQUIRED")
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
        with shape_patch(), patch.object(
                genesis_owner, "_create_unbound_bamf_optimizer",
                side_effect=AssertionError("model allocation reached")):
            for authority in wrong:
                with self.subTest(authority=authority), self.assertRaises(BilqisError) as failure:
                    genesis_owner.prepare_initial_generation(
                        run_id=prepared.candidate.run_id,
                        run_seed=prepared.candidate.run_identity.run_seed,
                        factory_authority=prepared.factory_authority,
                        origin_checkpoint=prepared.origin_checkpoint,
                        release=prepared.release, admission=prepared.admission,
                        graph=prepared.graph, model_authority=authority,
                        optimizer_hyperparameters=prepared.candidate.optimizer_hyperparameters,
                        provenance=prepared.candidate.provenance,
                        foundation_features=prepared.foundation_features,
                        delivery_events=prepared.candidate.outbox)
                self.assertEqual(
                    failure.exception.context["reason"],
                    "BAMF_INITIAL_GENERATION_MODEL_AUTHORITY_DRIFT")


    def test_caller_cannot_preage_foundation_rows_even_with_rehashed_identity(self):
        with shape_patch():
            prepared = genesis_preparation(run_seed=247)
        candidate = prepared.candidate
        forged_state = replace(
            candidate.retained_state,
            policy=PlasticityPolicy(
                "FOUNDATION", 0, (IdentityRowAge(0, 0, 8),)))
        forged = replace(
            candidate,
            retained_state=forged_state,
            run_identity=replace(
                candidate.run_identity,
                initial_candidate_identity_sha256=candidate_identity_digest(forged_state)))
        with shape_patch(), self.assertRaises(BilqisError) as failure:
            _issue_binding(
                forged, release=prepared.release, admission=prepared.admission,
                graph=prepared.graph, origin_checkpoint=prepared.origin_checkpoint,
                factory_authority=prepared.factory_authority,
                foundation_features=prepared.foundation_features)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_INITIAL_GENERATION_MODEL_AUTHORITY_DRIFT")

    def test_valid_factory_cannot_publish_caller_authored_foundation_sidecars(self):
        with shape_patch():
            prepared = genesis_preparation(run_seed=251)
        candidate = prepared.candidate
        variants = (
            replace(candidate, semantic_abi={
                **candidate.semantic_abi, "active_set_sha256": "1" * 64}),
            replace(candidate, compiler_features={
                **candidate.compiler_features, "compiler_sha256": "2" * 64}),
            replace(candidate, correction_frontier={
                **candidate.correction_frontier,
                "frontier": [{"caller_authored": True}]}),
            replace(candidate, teacher_state={
                **candidate.teacher_state,
                "next_seed": candidate.teacher_state["next_seed"] + 1}),
            replace(candidate, evaluation_contract={
                **candidate.evaluation_contract, "contract_sha256": "3" * 64}),
        )
        for altered in variants:
            with self.subTest(sidecars=altered), shape_patch(), \
                    self.assertRaises(BilqisError) as failure:
                _issue_binding(
                    altered, release=prepared.release, admission=prepared.admission,
                    graph=prepared.graph,
                    origin_checkpoint=prepared.origin_checkpoint,
                    factory_authority=prepared.factory_authority,
                    foundation_features=prepared.foundation_features)
            self.assertEqual(
                failure.exception.context["reason"],
                "BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_DRIFT")
            with self.assertRaises(BilqisError) as preparation_failure:
                replace(prepared, candidate=altered)
            self.assertEqual(
                preparation_failure.exception.context["reason"],
                "BAMF_INITIAL_GENERATION_PREPARATION_REQUIRED")
            self.assertFalse((self.run / "bamf-state.json").exists())


if __name__ == "__main__":
    unittest.main()
