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
class SourceEncodingCorrectionTests(SourceEncodingFixture):
    def test_generation_drift_rejects_before_owner_or_source_handoff_work(self):
        banks = semantic_bank_views(
            self.parameters, self.compiled.extents,
            self.compiled.features.semantic_release, self.active_indices)
        drifted_extents = replace(
            self.compiled.extents, factor_map_digest="c" * 64)
        with patch.object(
                AtlasFeatureArtifactOwner, "require",
                side_effect=AssertionError("artifact owner reached")), \
                patch(
                    "bilqis_mlx.learning.source_atoms.embedding."
                    "_build_source_atom_handoff_from_snapshot",
                    side_effect=AssertionError("source handoff reached")):
            with self.assertRaises(BilqisError) as caught:
                source_atom_vectors(
                    self.parameters,
                    self.compiled.compiled.rows[0],
                    self.compiled.compiler_configs[0],
                    self.source,
                    self.compiled.features,
                    self.schema,
                    drifted_extents,
                    banks,
                    self.artifact_owner,
                    snapshot=self.snapshot)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_SOURCE_ATOM_GENERATION_DRIFT")

    def test_source_correction_holds_real_features_before_next_use(self):
        event = _event(self.artifact_owner.source_dependency)
        queue = self.artifact_owner.apply_correction(event, AUTHORITY)
        self.assertEqual(
            queue.held_artifact_ids,
            (self.artifact_owner.current_node.artifact_id,))
        with self.assertRaises(BilqisError) as caught:
            self.encode()
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C09_ARTIFACT_HELD")

    def test_equal_revalidation_clears_hold_but_changed_output_rejects_old_features(self):
        event = _event(self.artifact_owner.source_dependency)
        self.artifact_owner.apply_correction(event, AUTHORITY)
        progress = self.artifact_owner.advance(
            _result(
                self.artifact_owner.current_node,
                digest=self.artifact_owner.current_node.content_digest,
                correction=event),
            AUTHORITY)
        self.assertEqual(progress.queue.pending, ())
        self.assertEqual(progress.queue.held_artifact_ids, ())
        self.encode()

        changed_owner = AtlasFeatureArtifactOwner(self.compiled.features, self.schema)
        changed_event = _event(changed_owner.source_dependency)
        changed_owner.apply_correction(changed_event, AUTHORITY)
        changed_owner.advance(_result(
            changed_owner.current_node, digest="c" * 64,
            correction=changed_event), AUTHORITY)
        with self.assertRaises(BilqisError) as caught:
            encode_source_compiled(
                self.compiled, self.parameters, (self.source,), self.schema,
                semantic_bank_views(
                    self.parameters, self.compiled.extents,
                    self.compiled.features.semantic_release, self.active_indices),
                changed_owner)
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C09_ATLAS_FEATURE_CONTENT_DRIFT")

    def test_partial_parameter_tree_and_caller_atom_vectors_are_not_accepted(self):
        partial = {key: value for key, value in self.parameters.items()
                   if key != "blocks.11.ffn_in"}
        with self.assertRaises(BilqisError):
            self.encode(parameters=partial)
        with self.assertRaises(TypeError):
            encode_source_compiled(
                self.compiled, self.parameters, (self.source,), self.schema,
                semantic_bank_views(
                    self.parameters, self.compiled.extents,
                    self.compiled.features.semantic_release, self.active_indices),
                self.artifact_owner,
                atom_vectors=mx.zeros((1, 2, 768)))
