"""B02.4/B03.3: child-frame constituents have no invented semantic identity."""
from dataclasses import replace
import unittest
import mlx.core as mx
import numpy as np
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.frame_embeddings import (
    ChildFrameRequest, FeatureRequest, child_frame_source_context,
)
from bilqis_mlx.learning.frame_encoder import (
    AtomicFrameEmbedding, AtomicSourceHandle, CompiledEmbeddingVectors,
    CompiledEncoderInput, FrameEncoderInput, MemberEmbedding, encode_frames,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
)
from bilqis_mlx.semantics.atlas_features import ConceptFeature
from bilqis_mlx.semantics.context_eligibility import (
    ApprovedContextProjection, ContextMember, SourceFrontier,
    frame_evidence_digest, member_evidence_digest, project_context,
)
from bilqis_mlx.semantics.frame_compiler import (
    PositionKind, compile_prefix_rows, validate_partial_visible_forest,
)
from bilqis_mlx.semantics.frame_schema import (
    ChildFrameRef, FrameSchema, FrameTree, RoleOccurrence, RoleSpec,
    SourceSpan, make_frame_instance,
)
from bilqis_mlx.semantics.tests.test_atlas_features import _features
from bilqis_mlx.semantics.tests.test_frame_compiler import _mixed_case, RELEASE

from bilqis_mlx.learning.tests.frames.nested_fixtures import _source_features, _case, _source_valid_child_slot_variants


class NestedFrameConstituentTests2(unittest.TestCase):
    def test_future_parent_member_change_does_not_change_child_prefix_embedding(self):
        ast, config, compiled, vectors, params = _case()
        parent_tree, atomic_tree = ast.frames
        parent = parent_tree.root
        child = parent_tree.children[0].root
        schema = next(item for item in config.schemas
                      if item.schema_id == parent.frame_schema_id)
        changed_parent = make_frame_instance(
            schema, source_instance_id=parent.source_instance_id,
            structural_path=parent.structural_path,
            source_span=parent.source_span,
            parent_occurrence_id=parent.parent_occurrence_id,
            bindings=(RoleOccurrence(
                "child", 0, child_frame=ChildFrameRef(
                    child.occurrence_id, child.content_digest,
                    ("Frame", "SyntheticFutureVariant"))),),
            causal_prefix_end=parent.causal_prefix_end)
        changed_ast = replace(ast, frames=(
            FrameTree(changed_parent, parent_tree.children), atomic_tree))
        parent_envelope = next(
            envelope for envelope in config.approved.envelopes
            if envelope.frame.occurrence_id == parent.occurrence_id)
        changed_envelope = replace(parent_envelope, frame=changed_parent)
        evidence = {
            changed_envelope.source_handle:
                frame_evidence_digest(changed_parent)}
        evidence.update({
            member.source_handle: member_evidence_digest(
                changed_parent, member)
            for member in changed_envelope.members})
        frontier = replace(
            config.frontier,
            grants=tuple(
                replace(grant, evidence_digest=evidence[grant.source_handle])
                if grant.source_handle in evidence else grant
                for grant in config.frontier.grants))
        envelopes = tuple(
            changed_envelope if envelope.frame.occurrence_id
            == parent.occurrence_id else envelope
            for envelope in config.approved.envelopes)
        approved = project_context(
            envelopes, config.task, frontier, config.policy)
        self.assertIsInstance(approved, ApprovedContextProjection)
        changed_config = replace(
            config, approved=approved, frontier=frontier)
        changed_rows = compile_prefix_rows(
            ((changed_ast, 4, changed_config),), RELEASE)
        changed_receipt = validate_partial_visible_forest(
            changed_rows.rows[0], changed_ast, changed_config)
        original = CompiledEncoderInput(
            compile_prefix_rows(((ast, 4, config),), RELEASE),
            (config,), compiled.features, compiled.extents,
            source_asts=(ast,),
            partial_forest_receipts=(
                compiled.partial_forest_receipts[0],))
        altered = CompiledEncoderInput(
            changed_rows, (changed_config,),
            compiled.features, compiled.extents,
            source_asts=(changed_ast,),
            partial_forest_receipts=(changed_receipt,))
        prefix_vectors = CompiledEmbeddingVectors(
            (vectors.atoms[0],), (vectors.members[0],), ((),))
        self.assertEqual(original.compiled.rows, altered.compiled.rows)
        original_seed = encode_frames(
            original, prefix_vectors, params).global_seeds
        altered_seed = encode_frames(
            altered, prefix_vectors, params).global_seeds
        self.assertTrue(bool(mx.all(original_seed == altered_seed)))
