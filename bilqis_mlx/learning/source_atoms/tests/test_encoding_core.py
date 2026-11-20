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



from .encoding_test_support import SourceEncodingFixture

@skipUnless(REAL_BUNDLE, "real pinned A01 artifact not mounted")
class SourceEncodingCoreTests(SourceEncodingFixture):
    def test_real_b03_result_matches_literal_source_owned_identity_and_factor_equation(self):
        before = {key: id(value) for key, value in self.parameters.items()}
        result = self.encode()
        vector = np.zeros(768, dtype=np.float32)
        vector[:3] = [.2, .6, .05]
        expected = vector / np.sqrt(np.mean(vector * vector) + 1e-5)
        np.testing.assert_allclose(np.asarray(result.global_seeds),
                                   np.broadcast_to(expected, (1, 2, 768)),
                                   rtol=1e-6, atol=1e-6)
        self.assertIs(result.compiled, self.compiled.compiled)
        self.assertEqual({key: id(value) for key, value in self.parameters.items()}, before)

    def test_gradients_reach_actual_b01_identity_and_factor_coordinates(self):
        def loss(parameters):
            return self.encode(parameters).global_seeds[..., 2].sum()

        gradients = mx.grad(loss)(self.parameters)
        actual_indices = self.source.source_row["tokens"][:2]
        selected = gradients["identity.bank.0"][mx.array(actual_indices), 2]
        self.assertTrue(bool(mx.all(mx.isfinite(selected))))
        self.assertTrue(bool(mx.all(mx.abs(selected) > 0)))
        self.assertGreater(float(mx.abs(gradients["features.project_type"][2, 0])), 0)
        self.assertGreater(float(mx.abs(gradients["features.type"][1, 0])), 0)
        self.assertEqual(float(mx.abs(gradients["identity.bank.1"]).sum()), 0)

    def test_atomic_fallback_reuses_exact_source_atom_embedding_and_gradient(self):
        compiled, source = self.atomic_case()
        encoded = self.encode(compiled=compiled, source=source)
        np.testing.assert_array_equal(
            np.asarray(encoded.global_seeds[0, -1]),
            np.asarray(encoded.global_seeds[0, 0]))

        def loss(identity):
            parameters = {**self.parameters, "identity.bank.0": identity}
            return self.encode(
                parameters, compiled=compiled, source=source).global_seeds[0, -1, 2]

        gradient = mx.grad(loss)(self.parameters["identity.bank.0"])
        row = source.source_row["tokens"][0]
        self.assertGreater(float(mx.abs(gradient[row, 2])), 0)

    def test_multi_atom_atomic_fallback_remains_held_without_composition_law(self):
        compiled, source = self.atomic_case(span_end=2)
        with self.assertRaises(BilqisError) as caught:
            self.encode(compiled=compiled, source=source)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_SOURCE_ATOM_ATOMIC_FRAME_SPAN_UNAVAILABLE")

    def test_source_known_inactive_rows_do_not_force_unadmitted_bank_expansion(self):
        compiled = replace(self.compiled, extents=replace(
            self.compiled.extents, semantic_bank_count=1))
        parameters = {key: value for key, value in self.parameters.items()
                      if key != "identity.bank.1"}
        result = self.encode(parameters=parameters, compiled=compiled)
        np.testing.assert_array_equal(np.asarray(result.global_seeds),
                                      np.asarray(self.encode().global_seeds))

    def test_current_revocation_and_generation_drift_precede_vector_return(self):
        revoked = replace(self.config.frontier.grants[0], revoked=True)
        config = replace(self.config, frontier=replace(
            self.config.frontier, grants=(revoked, *self.config.frontier.grants[1:])))
        with self.assertRaises(BilqisError):
            changed = replace(self.compiled, compiler_configs=(config,))
            self.encode(compiled=changed)
        changed = replace(self.compiled, extents=replace(
            self.compiled.extents, active_semantic_digest="9" * 64))
        with self.assertRaises(BilqisError):
            self.encode(compiled=changed)
