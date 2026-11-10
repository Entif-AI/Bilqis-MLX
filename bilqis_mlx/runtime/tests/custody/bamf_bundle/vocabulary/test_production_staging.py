"""Full-topology A02 staging through accepted B13 custody."""
from contextlib import ExitStack
from dataclasses import replace
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.learning.atlas_plasticity import IdentityRowAge
from bilqis_mlx.runtime.bamf_bundle import (
    issue_initial_foundation_feature_authority, load_bamf_generation,
    publish_bamf_generation, publish_initial_generation, stage_vocabulary_extension,
    stage_vocabulary_extension_from_source_id,
)
from bilqis_mlx.runtime.bamf_bundle.genesis import foundation as genesis_foundation
from bilqis_mlx.runtime.model_topology_v2 import (
    expected_bamf_shapes, initialize_bamf_row,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    acceptance, genesis_preparation,
)
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.atlas.vocabulary_factors import prepare_identity_factors
from bilqis_mlx.semantics.tests.atlas.vocabulary_fixtures import _allocation_fixture
from bilqis_mlx.semantics.tests.atlas.projection.helpers import (
    _fixture_bundle, _rewrite_bundle,
)


@unittest.skipUnless(os.environ.get("BILQIS_BAMF_FULL_WITNESS"),
                     "full v2 production-staging witness is explicitly gated")
class A02ProductionStagingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run = self.root / "run"
        self.pointer = self.run / "bamf-state.json"
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def _accept(self, bundle, *, parent_state=None):
        return publish_bamf_generation(
            self.run, bundle,
            acceptance=acceptance(bundle, parent=parent_state), reserve_gib=0.)

    def _publish_source_parent(self, *, source_bundle_id=None):
        current_base, _ = _allocation_fixture(highest=8192)
        current_snapshot = replace(
            current_base, bundle_id="4" * 64, release_sha256="5" * 64,
            source_bundle_id=source_bundle_id or "6" * 64, prior_abi_sha256=None)
        current_features = build_feature_manifest(current_snapshot, FeatureSchema((), ()))
        selection = AtlasArtifactSelection(
            "/artifact", current_snapshot.bundle_id, current_snapshot.release_sha256,
            current_snapshot.source_bundle_id)
        current_schema = FeatureSchema((), ())
        foundation_replay = patch.multiple(
            genesis_foundation,
            _source_owned_feature_schema=lambda _selection: (current_snapshot, current_schema),
            build_feature_manifest=lambda _snapshot, _schema: current_features,
        )
        with foundation_replay:
            authority = issue_initial_foundation_feature_authority(selection)
            prepared = genesis_preparation(
                run_id="a02-production-fixture", foundation_features=authority)
            with patch.object(mlx_checkpoint, "assert_headroom"):
                publish_initial_generation(self.run, prepared, reserve_gib=0.)
        parent = load_bamf_generation(self.pointer, publish_missing_outbox=False)
        self.assertEqual(parent.generation, 0)
        return current_snapshot, current_features, parent.retained_state.optimizer

    def _source_patches(self, current_snapshot, *, patch_bundle=True):
        source_nt = (
            '<urn:concept:8192> <http://www.w3.org/2004/02/skos/core#definition> '
            '"semantic role 8192"@en .\n').encode("utf-8")
        stack = ExitStack()
        stack.enter_context(patch(
            "bilqis_mlx.runtime.bamf_bundle.feature_authority."
            "resolve_atlas_artifact_selection",
            side_effect=lambda identity: AtlasArtifactSelection(
                "/artifact", identity.bundle_id, identity.release_sha256,
                identity.source_bundle_id)))
        for target in (
                "bilqis_mlx.runtime.bamf_bundle.feature_authority.load_pinned_atlas_snapshot",
                "bilqis_mlx.runtime.bamf_bundle.vocabulary_admission.load_pinned_atlas_snapshot",
                "bilqis_mlx.semantics.atlas.vocabulary_planning.load_pinned_atlas_snapshot",
                "bilqis_mlx.semantics.atlas.vocabulary_resources.load_pinned_atlas_snapshot"):
            stack.enter_context(patch(target, return_value=current_snapshot))
        if patch_bundle:
            stack.enter_context(patch(
                "bilqis_mlx.semantics.atlas.vocabulary_resources._verify_bundle",
                return_value=(current_snapshot.source_bundle_id, {"canonical.nt": source_nt})))
        return stack

    def _real_source_bundle(self):
        source_root = self.root / "source-bundles"
        source_root.mkdir()
        bundle, *_ = _fixture_bundle(source_root)
        canonical = (bundle / "canonical.nt").read_bytes() + (
            b'<urn:concept:8192> <http://www.w3.org/2004/02/skos/core#definition> '
            b'"semantic role 8192"@en .\n')
        return _rewrite_bundle(bundle, "canonical.nt", canonical)

    def test_stages_bank_extension_without_granting_admission(self):
        current_snapshot, current_features, optimizer = self._publish_source_parent()
        parent = load_bamf_generation(self.pointer, publish_missing_outbox=False)
        with self._source_patches(current_snapshot):
            with self.assertRaises(BilqisError):
                stage_vocabulary_extension(
                    self.run, "/artifact", Path("/source"),
                    ("urn:concept:not-present",))
            staged = stage_vocabulary_extension(
                self.run, "/artifact", Path("/source"), ("urn:concept:8192",))
        self.assertEqual(
            load_bamf_generation(self.pointer, publish_missing_outbox=False).generation, 0)
        self.assertEqual(staged.receipt.generation, 1)
        self.assertEqual(staged.receipt.semantic_bank_count, 2)
        self.assertEqual(staged.receipt.status, "STAGED_NOT_ADMITTED")
        self.assertNotEqual(
            parent.run_identity.run_seed, parent.topology.default_run_seed)
        feature_names = (
            "features.type", "features.project_type",
            "features.project_graph", "features.gates",
        )
        _, factors = prepare_identity_factors(
            current_snapshot, current_features, ("urn:concept:8192",),
            {name: parent.retained_state.optimizer.parameters[name]
             for name in feature_names},
            extents=parent.extents,
        )
        specs = {
            item.name: item for item in expected_bamf_shapes(
                parent.topology, staged.candidate.extents)
        }
        expected_row = initialize_bamf_row(
            specs["identity.bank.1"], run_seed=parent.run_identity.run_seed,
            row_id="urn:concept:8192", factor=factors[0][1],
        )
        np.testing.assert_array_equal(
            np.asarray(staged.candidate.retained_state.optimizer.parameters[
                "identity.bank.1"][0]),
            expected_row,
        )
        np.testing.assert_array_equal(
            np.asarray(staged.candidate.retained_state.optimizer.parameters["identity.bank.0"]),
            np.asarray(optimizer.parameters["identity.bank.0"]))
        self.assertTrue(bool(mx.all(
            staged.candidate.retained_state.optimizer.update_counts["identity.bank.1"] == 0)))
        self.assertIn(IdentityRowAge(1, 0, 0), staged.candidate.retained_state.policy.row_ages)
        with self.assertRaises(BilqisError) as failure:
            publish_bamf_generation(
                self.run, staged.candidate,
                acceptance=acceptance(
                    staged.candidate, parent=parent.retained_state),
                reserve_gib=0.)
        self.assertEqual(
            failure.exception.context["reason"], "BAMF_ATLAS_ADMISSION_EXECUTOR_REQUIRED")

    def test_stages_from_content_id_through_real_source_bundle_verifier(self):
        bundle = self._real_source_bundle()
        current_snapshot, _current_features, _optimizer = self._publish_source_parent(
            source_bundle_id=bundle.name)
        attacker_root = self.root / "attacker-source"
        attacker_root.mkdir()
        attacker, *_ = _fixture_bundle(attacker_root)
        attacker = _rewrite_bundle(
            attacker,
            "canonical.nt",
            (attacker / "canonical.nt").read_bytes()
            + b'<urn:attacker> <http://www.w3.org/2004/02/skos/core#definition> "other"@en .\n',
        )
        shutil.copytree(attacker, bundle.parent / attacker.name)
        with patch.dict(
                os.environ,
                {"BILQIS_A01_SOURCE_BUNDLE_ROOT": str(bundle.parent)},
                clear=False), self._source_patches(
                    current_snapshot, patch_bundle=False):
            with patch(
                    "bilqis_mlx.runtime.bamf_bundle.vocabulary_admission."
                    "shutil.disk_usage",
                    return_value=SimpleNamespace(free=0)):
                with self.assertRaises(BilqisError) as failure:
                    stage_vocabulary_extension_from_source_id(
                        self.run, "/artifact", attacker.name,
                        ("urn:concept:8192",))
            self.assertEqual(
                failure.exception.context["reason"],
                "BAMF_A02_SOURCE_BUNDLE_ID_MISMATCH",
            )
            with patch(
                    "bilqis_mlx.runtime.bamf_bundle.vocabulary_admission."
                    "shutil.disk_usage",
                    return_value=SimpleNamespace(free=1 << 50)):
                staged = stage_vocabulary_extension_from_source_id(
                    self.run, "/artifact", current_snapshot.source_bundle_id,
                    ("urn:concept:8192",))
        self.assertEqual(staged.receipt.generation, 1)
        self.assertEqual(staged.receipt.semantic_bank_count, 2)
        self.assertEqual(staged.receipt.status, "STAGED_NOT_ADMITTED")
        self.assertNotIn(
            str(bundle.parent),
            repr((staged.receipt.to_record(), staged.candidate.outbox)),
        )
        self.assertEqual(
            load_bamf_generation(
                self.pointer, publish_missing_outbox=False).generation,
            0)


class A02ContentIdentityBoundaryTests(unittest.TestCase):
    def test_wrong_content_id_is_rejected_before_staging_entry(self):
        requested = "7" * 64
        accepted = "8" * 64
        prior = SimpleNamespace(
            source_selection=SimpleNamespace(source_bundle_id=accepted))
        accepted_parent = (
            object(), "1" * 64, object(), object(), None, prior)
        with (
            patch(
                "bilqis_mlx.runtime.bamf_bundle.vocabulary_admission."
                "resolve_atlas_source_bundle",
                return_value=Path("/host") / requested,
            ),
            patch(
                "bilqis_mlx.runtime.bamf_bundle.vocabulary_admission."
                "_accepted_vocabulary_parent",
                return_value=accepted_parent,
            ),
            patch(
                "bilqis_mlx.runtime.bamf_bundle.vocabulary_admission."
                "stage_vocabulary_extension",
                side_effect=AssertionError("wrong source ID reached staging"),
            ),
        ):
            with self.assertRaises(BilqisError) as failure:
                stage_vocabulary_extension_from_source_id(
                    Path("/run"), "/artifact", requested,
                    ("urn:concept:8192",))
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_A02_SOURCE_BUNDLE_ID_MISMATCH",
        )


if __name__ == "__main__":
    unittest.main()
