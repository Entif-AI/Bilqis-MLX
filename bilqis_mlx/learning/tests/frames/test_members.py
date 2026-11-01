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


class NestedFrameConstituentTests1(unittest.TestCase):
    def test_source_valid_parent_slot_changes_child_factor_and_gradient(self):
        requests, features, extents, params = _source_valid_child_slot_variants()
        first, second = requests
        self.assertEqual((first.local_slot, second.local_slot), (0, 1))
        self.assertEqual(first.child, second.child)
        self.assertEqual(first.role_id, second.role_id)
        self.assertEqual(first.schema_id, second.schema_id)
        first_vector = child_frame_source_context(
            params, first, features, extents=extents)
        second_vector = child_frame_source_context(
            params, second, features, extents=extents)
        self.assertGreater(
            float(mx.sum(mx.abs(first_vector - second_vector))), 0)
        def slot_objective(table):
            changed = dict(params)
            changed["features.local_slot"] = table
            return mx.sum(child_frame_source_context(
                changed, second, features, extents=extents)
                * mx.arange(768, dtype=mx.float32))
        derivative = mx.grad(slot_objective)(
            params["features.local_slot"])
        self.assertGreater(float(mx.sum(mx.abs(derivative[1]))), 0)
        self.assertEqual(float(mx.sum(mx.abs(derivative[0]))), 0)

    def test_nested_child_source_is_typed_and_parent_uses_earlier_closure(self):
        ast, config, compiled, vectors, params = _case()
        child = ChildFrameRequest.from_context(
            config.approved, "frame:mixed:2",
            "source:member:mixed:2:0")
        self.assertEqual(child.child.occurrence_id,
                         ast.frames[0].children[0].root.occurrence_id)
        self.assertEqual(child.child_frame_handle, "frame:mixed:0")
        self.assertFalse(hasattr(child, "concept"))
        self.assertFalse(hasattr(child, "abi_index"))
        with self.assertRaises(BilqisError):
            FrameEncoderInput(
                (((child,),),), compiled.features, compiled.extents)
        self.assertEqual(len(compiled.member_requests[0]), 1)
        self.assertEqual(len(compiled.member_requests[1]), 1)
        self.assertEqual(
            compiled._groups[1][-1], (child,))
        encoded = encode_frames(compiled, vectors, params)
        child_index = next(
            i for i, item in enumerate(compiled.compiled.rows[1].positions)
            if item.kind is PositionKind.CLOSURE
            and item.frame_handle == "frame:mixed:0")
        parent_index = next(
            i for i, item in enumerate(compiled.compiled.rows[1].positions)
            if item.kind is PositionKind.CLOSURE
            and item.frame_handle == "frame:mixed:2")
        self.assertLess(child_index, parent_index)
        self.assertEqual(encoded.global_seeds.shape[-1], 768)
        self.assertGreater(
            float(mx.sum(mx.abs(encoded.global_seeds[1, parent_index]))), 0)
        def parent_objective(member):
            changed = replace(
                vectors, members=(
                    vectors.members[0],
                    (replace(vectors.members[1][0], vector=member),)))
            return mx.sum(encode_frames(
                compiled, changed, params).global_seeds[1, parent_index]
                * mx.arange(768, dtype=mx.float32))
        derivative = mx.grad(parent_objective)(vectors.members[1][0].vector)
        self.assertGreater(float(mx.sum(mx.abs(derivative))), 0)
        def factor_objective(type_table):
            changed = dict(params)
            changed["features.type"] = type_table
            return mx.sum(encode_frames(
                compiled, vectors, changed).global_seeds[1, parent_index]
                * mx.arange(768, dtype=mx.float32))
        factor_grad = mx.grad(factor_objective)(params["features.type"])
        self.assertGreater(
            float(mx.sum(mx.abs(factor_grad[3]))), 0)
        def slot_objective(slot_table):
            changed = dict(params)
            changed["features.local_slot"] = slot_table
            return mx.sum(encode_frames(
                compiled, vectors, changed).global_seeds[1, parent_index]
                * mx.arange(768, dtype=mx.float32))
        slot_grad = mx.grad(slot_objective)(
            params["features.local_slot"])
        self.assertGreater(
            float(mx.sum(mx.abs(slot_grad[0]))), 0)
        self.assertEqual(
            float(mx.sum(mx.abs(slot_grad[1]))), 0)

    def test_orphan_relabel_future_and_unqualified_reconstruction_reject(self):
        ast, config, compiled, vectors, params = _case()
        child = ChildFrameRequest.from_context(
            config.approved, "frame:mixed:2",
            "source:member:mixed:2:0")
        for change in (
            {"child": replace(child.child, content_digest="0" * 64)},
            {"child_frame_handle": "frame:mixed:1"},
            {"role_id": "subject"},
            {"local_slot": 1},
        ):
            with self.subTest(change=change), self.assertRaises(BilqisError):
                replace(child, **change)
        with self.assertRaises(BilqisError):
            ChildFrameRequest.from_context(
                config.approved, "frame:mixed:0",
                "source:member:mixed:0:0")
        with self.assertRaises(BilqisError):
            replace(
                compiled,
                partial_forest_receipts=(
                    compiled.partial_forest_receipts[1],
                    compiled.partial_forest_receipts[0]))
        with self.assertRaises(BilqisError):
            replace(compiled, source_asts=(None, ast))
        revoked_frontier = replace(
            config.frontier,
            grants=tuple(
                replace(grant, revoked=True)
                if grant.source_handle in {
                    "source:frame:mixed:2",
                    "source:member:mixed:2:0"} else grant
                for grant in config.frontier.grants))
        with self.assertRaises(BilqisError):
            replace(
                compiled, compiler_configs=(
                    replace(config, frontier=revoked_frontier), config))
        with self.assertRaises(BilqisError):
            CompiledEncoderInput(
                compile_prefix_rows(((ast, 8, config),), RELEASE),
                (config,), compiled.features, compiled.extents)
        baseline = encode_frames(compiled, vectors, params)
        # A parent future member is absent from p4's closure and input vector.
        self.assertEqual(
            tuple(item.frame_handle for item in compiled.compiled.rows[0].positions
                  if item.kind is PositionKind.CLOSURE),
            ("frame:mixed:0",))
        self.assertTrue(bool(mx.all(mx.isfinite(baseline.global_seeds))))
