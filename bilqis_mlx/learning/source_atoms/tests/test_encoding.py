"""Source-owned raw atoms remain differentiable through the real B03 entrypoint."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, skipUnless
from unittest.mock import patch

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.frame_encoder import CompiledEncoderInput
from bilqis_mlx.learning.frame_embeddings import semantic_bank_views
from bilqis_mlx.learning.source_atoms import SourceAtomRow, encode_source_compiled
from bilqis_mlx.learning.source_atoms.embedding import (
    _source_binding_vectors,
    source_atom_vectors,
)
from bilqis_mlx.runtime.atlas_artifact_owner import AtlasFeatureArtifactOwner
from bilqis_mlx.runtime.tests.test_atlas_revalidation import (
    AUTHORITY, _event, _result,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
)
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.atlas.snapshot import load_pinned_atlas_snapshot
from bilqis_mlx.semantics.tests.test_atlas_features import (
    _features as fixture_features,
    _snapshot as fixture_snapshot,
)
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextEligibility, ContextMember, SourceFrontier, SourceGrant,
    frame_evidence_digest, member_evidence_digest, project_context,
)
from bilqis_mlx.semantics.frame_compiler import (
    StreamingAST, compile_prefix_rows, validate_partial_visible_forest,
)
from bilqis_mlx.semantics.frame_schema import FrameTree, SourceSpan, atomic_fallback
from bilqis_mlx.source_adapters.tests.atoms.helpers import REAL_BUNDLE, source_case


class SourceEmbeddingBoundaryTests(TestCase):
    def test_generation_drift_precedes_owner_and_source_handoff_work(self):
        release = "a" * 64
        selection = SimpleNamespace(
            release_sha256=release,
            bundle_id="bundle",
            source_bundle_id="source-bundle")
        source = SourceAtomRow(
            selection, {}, {}, Path("."), 0, 1)
        snapshot = SimpleNamespace(
            release_sha256=release,
            bundle_id="bundle",
            source_bundle_id="source-bundle")
        features = SimpleNamespace(
            semantic_release=release,
            atlas_bundle_id="bundle",
            source_bundle_id="source-bundle",
            digest="d" * 64)
        extents = SimpleNamespace(factor_map_digest=features.digest)
        owner = object.__new__(AtlasFeatureArtifactOwner)
        with patch.object(
                AtlasFeatureArtifactOwner, "require",
                side_effect=AssertionError("artifact owner reached")), \
                patch(
                    "bilqis_mlx.learning.source_atoms.embedding."
                    "_build_source_atom_handoff_from_snapshot",
                    side_effect=AssertionError("source handoff reached")):
            with self.assertRaises(BilqisError) as caught:
                source_atom_vectors(
                    None, None, None, source, features, None, extents, (),
                    owner, snapshot=snapshot)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_SOURCE_ATOM_GENERATION_DRIFT")

    def test_generation_active_identity_absent_from_feature_manifest_uses_source_factors(self):
        snapshot = fixture_snapshot((
            ("urn:concept:A", ("urn:type:Entity",)),
            ("urn:concept:B", ("urn:type:Entity",)),
        ))
        snapshot = replace(
            snapshot,
            abi_entries=tuple(
                replace(
                    entry,
                    source="CANONICAL_SKOS",
                    active=False,
                    teaching_candidate=False,
                    reason="IMPLEMENTATION_UNCOVERED",
                ) if entry.semantic_id == "urn:concept:B" else entry
                for entry in snapshot.abi_entries
            ),
            concepts=tuple(
                replace(
                    item,
                    active=False,
                    implementation_status="IMPLEMENTATION_UNCOVERED",
                    teaching_candidate=False,
                    teaching_reason="IMPLEMENTATION_UNCOVERED",
                ) if item.concept.semantic_id == "urn:concept:B" else item
                for item in snapshot.concepts
            ),
        )
        features = fixture_features(snapshot, roles=(), schemas=())
        self.assertNotIn(
            "urn:concept:B", {item.semantic_id for item in features.concepts})

        spec = ModelTopologySpecV2()
        extents = GenerationExtents(
            1, 1, "a" * 64, "b" * 64, features.digest)
        parameters = {
            item.name: mx.zeros(item.shape, dtype=mx.float32)
            for item in expected_bamf_shapes(spec, extents)
        }
        parameters["features.norm"] = mx.ones((spec.width,), dtype=mx.float32)
        parameters["identity.bank.0"] = (
            parameters["identity.bank.0"]
            .at[12, 0].add(.2)
            .at[12, 1].add(.6)
        )
        binding = SimpleNamespace(
            candidate_semantic_id="urn:concept:B",
            candidate_abi_index=12,
            # B11's binding type is the source adapter's formal signature,
            # not the Atlas concept-type factor row.
            candidate_type_ids=("source:formal-signature",),
        )
        handoff = SimpleNamespace(bindings=(binding,))
        config = SimpleNamespace(task=SimpleNamespace(scope="task:scope"))
        bank = SimpleNamespace(
            bank_index=0,
            weights=parameters["identity.bank.0"], active_rows=(11, 12))

        result = _source_binding_vectors(
            handoff, config, features, (bank,), spec, parameters, snapshot)
        vector = np.zeros(spec.width, dtype=np.float32)
        vector[:2] = (.2, .6)
        expected = vector / np.sqrt(np.mean(vector * vector) + 1e-5)
        np.testing.assert_allclose(
            np.asarray(result[0]), expected, rtol=1e-6, atol=1e-6)

        inactive = SimpleNamespace(
            bank_index=0,
            weights=parameters["identity.bank.0"], active_rows=(11,))
        with self.assertRaises(BilqisError) as caught:
            _source_binding_vectors(
                handoff, config, features, (inactive,), spec, parameters, snapshot)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_SOURCE_ATOM_INACTIVE_IDENTITY")
