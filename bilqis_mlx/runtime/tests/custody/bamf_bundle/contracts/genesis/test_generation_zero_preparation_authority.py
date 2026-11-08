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
from bilqis_mlx.runtime.bamf_bundle.genesis.records import (
    _mint_initial_generation_binding,
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
        minted = _mint_initial_generation_binding(prepared.candidate)
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

    def test_bootstrap_binding_rejects_non_optimizer_genesis_substitution(self):
        from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2

        with shape_patch():
            prepared = genesis_preparation(run_seed=247)
        candidate = prepared.candidate
        state = candidate.retained_state
        policy = state.policy
        with patch.object(ModelTopologySpecV2, "__post_init__", return_value=None):
            changed_topology = replace(candidate.topology, default_run_seed=1)
        changed_policy = replace(
            policy,
            row_ages=(replace(policy.row_ages[0], accepted_age=1),),
        )
        variants = {
            "teacher_state": replace(
                candidate,
                teacher_state={**candidate.teacher_state, "next_seed": 248},
            ),
            "provenance": replace(
                candidate,
                provenance=replace(candidate.provenance, source_identity="c" * 64),
            ),
            "topology": replace(candidate, topology=changed_topology),
            "extents": replace(
                candidate,
                extents=replace(candidate.extents, active_semantic_digest="9" * 64),
            ),
            "implementation": replace(candidate, implementation_sha256="1" * 64),
            "semantic_abi": replace(
                candidate,
                semantic_abi={**candidate.semantic_abi, "active_set_sha256": "9" * 64},
            ),
            "compiler_features": replace(
                candidate,
                compiler_features={**candidate.compiler_features, "compiler_sha256": "9" * 64},
            ),
            "correction_frontier": replace(
                candidate,
                correction_frontier={**candidate.correction_frontier,
                                     "correction_generation": 1},
            ),
            "evaluation_contract": replace(
                candidate,
                evaluation_contract={**candidate.evaluation_contract,
                                     "contract_sha256": "9" * 64},
            ),
            "plasticity_policy": replace(
                candidate,
                retained_state=replace(state, policy=changed_policy),
            ),
        }
        for label, altered in variants.items():
            with self.subTest(label=label):
                with self.assertRaises(BilqisError) as failure:
                    validate_initial_generation_binding(altered, prepared.binding)
                self.assertEqual(
                    failure.exception.context["reason"],
                    "BAMF_INITIAL_GENERATION_BINDING_DRIFT")


if __name__ == "__main__":
    unittest.main()
