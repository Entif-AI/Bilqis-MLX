"""Source-owned raw atoms remain differentiable through the real B03 entrypoint."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, skipUnless
from unittest.mock import patch

import mlx.core as mx
import numpy as np
import bilqis_mlx.learning.source_atoms.embedding as source_embedding
import bilqis_mlx.learning.source_atoms.encoding as source_encoding

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
    def test_learning_first_multirow_encoding_prepares_source_parameters_once(self):
        row_count = 6
        compiled = object.__new__(CompiledEncoderInput)
        rows = tuple(
            SimpleNamespace(visible_end=1, source_instance_id=f"row-{index}")
            for index in range(row_count))
        object.__setattr__(compiled, "compiled", SimpleNamespace(rows=rows))
        object.__setattr__(
            compiled, "compiler_configs",
            tuple(SimpleNamespace(task=SimpleNamespace(scope="task:scope"))
                  for _ in rows))
        object.__setattr__(compiled, "features", object())
        object.__setattr__(compiled, "extents", object())
        object.__setattr__(compiled, "member_requests", tuple(() for _ in rows))
        object.__setattr__(compiled, "atomic_handles", tuple(() for _ in rows))
        sources = tuple(
            SourceAtomRow(
                object(), {}, {}, Path("."), index, 1,
                learning_abi_indices=(0,))
            for index in range(row_count))
        banks = (SimpleNamespace(
            bank_index=0,
            active_rows=(0,),
            weights=mx.ones((1, 2), dtype=mx.float32),
        ),)
        spec = SimpleNamespace(
            semantic_bank_rows=1,
            rms_norm_epsilon=1e-6,
        )
        owned = {
            "features.local_slot": mx.zeros((1, 2), dtype=mx.float32),
            "features.norm": mx.ones((2,), dtype=mx.float32),
        }
        snapshot = SimpleNamespace(
            abi=lambda _index: SimpleNamespace(semantic_id="urn:test"))
        feature = SimpleNamespace()
        encoded = object()

        with (
            patch.object(CompiledEncoderInput, "__post_init__", return_value=None),
            patch.object(
                source_embedding, "_source_embedding_parameters",
                return_value=(spec, owned)) as prepare,
            patch.object(
                source_embedding, "generation_feature_row",
                return_value=feature),
            patch.object(
                source_embedding, "_released_factor_terms",
                return_value=()),
            patch.object(
                source_encoding, "_atomic_source_embeddings",
                return_value=tuple(() for _ in rows)),
            patch.object(
                source_encoding, "CompiledEmbeddingVectors",
                return_value=object()),
            patch.object(source_encoding, "encode_frames", return_value=encoded),
        ):
            actual, handoffs = source_encoding.encode_source_compiled_with_handoffs(
                compiled, object(), sources, object(), banks, object(),
                snapshot=snapshot)

        self.assertIs(actual, encoded)
        self.assertEqual(len(handoffs), row_count)
        self.assertEqual(prepare.call_count, 1)

    def test_learning_first_source_row_skips_source_handoff_authority(self):
        source = SourceAtomRow(
            object(), {}, {}, Path("."), 0, 1,
            learning_abi_indices=(3, 7))
        vectors = object()
        handoff = object()
        banks = object()
        with (
            patch.object(
                source_embedding, "_learning_first_source_vectors",
                return_value=(vectors, handoff)) as learning,
            patch.object(
                source_embedding, "_resolve_source_embedding_authority",
                side_effect=AssertionError("learning-first resolved source authority")),
            patch.object(
                source_embedding, "_bind_source_embedding_handoff",
                side_effect=AssertionError("learning-first rebuilt source handoff")),
        ):
            actual = source_embedding.source_atom_vectors(
                object(), object(), object(), source, object(), object(), object(),
                banks, object(), snapshot=object())

        self.assertEqual(actual, (vectors, banks, handoff))
        learning.assert_called_once()

    def test_learning_first_prepared_source_context_is_numerically_exact(self):
        source = SourceAtomRow(
            object(), {}, {}, Path("."), 0, 1,
            learning_abi_indices=(0,))
        compiled = SimpleNamespace(visible_end=1, source_instance_id="row")
        config = SimpleNamespace(task=SimpleNamespace(scope="task:scope"))
        banks = (SimpleNamespace(
            bank_index=0,
            active_rows=(0,),
            weights=mx.array([[1.0, 2.0]], dtype=mx.float32),
        ),)
        spec = SimpleNamespace(
            semantic_bank_rows=1,
            rms_norm_epsilon=1e-6,
        )
        owned = {
            "features.local_slot": mx.array([[0.25, -0.5]], dtype=mx.float32),
            "features.norm": mx.array([1.5, 0.75], dtype=mx.float32),
        }
        snapshot = SimpleNamespace(
            abi=lambda _index: SimpleNamespace(semantic_id="urn:test"))
        feature = SimpleNamespace()

        with (
            patch.object(
                source_embedding, "_source_embedding_parameters",
                return_value=(spec, owned)),
            patch.object(
                source_embedding, "generation_feature_row",
                return_value=feature),
            patch.object(
                source_embedding, "_released_factor_terms",
                return_value=(mx.array([0.5, 0.125], dtype=mx.float32),)),
        ):
            direct, _ = source_embedding._learning_first_source_vectors(
                object(), compiled, config, source, object(), object(),
                banks, snapshot)
            prepared = source_embedding._prepare_learning_source_embedding_context(
                object(), source, object(), object(), banks, snapshot)
            reused, _ = source_embedding._learning_first_source_vectors(
                object(), compiled, config, source, object(), object(),
                banks, snapshot, prepared=prepared)
            mx.eval(direct, reused)

        np.testing.assert_array_equal(np.asarray(direct), np.asarray(reused))

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
