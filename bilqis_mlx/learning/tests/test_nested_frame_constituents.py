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


def _source_features():
    # Synthetic A06 factor rows for the source-owned nested A05 test fixture.
    base = _features()
    return replace(
        base,
        concepts=(ConceptFeature(
            "formal:entity.1", 1, ("Entity",), (0.0,) * 64,
            "ADMITTED_SOURCE"),),
        type_map=(("Entity", 2), ("Frame", 3), ("NONE", 1), ("UNKNOWN", 0)),
        role_map=(("NONE", 1), ("UNKNOWN", 0), ("child", 3), ("subject", 2)),
        schema_map=(("NONE", 1), ("UNKNOWN", 0),
                    ("frame:child", 2), ("frame:parent", 3)),
    )


def _case():
    ast, config = _mixed_case()
    features = _source_features()
    extents = GenerationExtents(
        1, 1, "a" * 64, "b" * 64, features.digest)
    rng = np.random.default_rng(577)
    params = {
        item.name: mx.array(rng.normal(0, 0.02, item.shape).astype(np.float32))
        for item in expected_bamf_shapes(ModelTopologySpecV2(), extents)
        if item.name.startswith(("frame.", "features."))
    }
    for name in ("frame.norm", "frame.interact_norm", "features.norm"):
        params[name] = mx.ones_like(params[name])
    rows = compile_prefix_rows(
        ((ast, 4, config), (ast, 8, config)), RELEASE)
    receipts = tuple(validate_partial_visible_forest(
        row, ast, config) for row in rows.rows)
    compiled = CompiledEncoderInput(
        rows, (config, config), features, extents,
        source_asts=(ast, ast), partial_forest_receipts=receipts)
    members = tuple(
        (MemberEmbedding(
            compiled.member_requests[index][0],
            mx.arange(768, dtype=mx.float32) / 1000),)
        for index in range(2))
    atomic = AtomicFrameEmbedding(
        AtomicSourceHandle(
            config.approved, "frame:mixed:1",
            "source:member:mixed:1:0"),
        mx.ones((768,), dtype=mx.float32))
    vectors = CompiledEmbeddingVectors(
        (mx.arange(4 * 768, dtype=mx.float32).reshape(4, 768) / 2000,
         mx.arange(8 * 768, dtype=mx.float32).reshape(8, 768) / 2000),
        members, ((), (atomic,)))
    return ast, config, compiled, vectors, params


def _source_valid_child_slot_variants():
    ast, config = _mixed_case()
    child = ast.frames[0].children[0].root
    original_parent = ast.frames[0].root
    schema = FrameSchema(
        "frame:parent-slot", 1, "source:parent",
        (RoleSpec("prefix", ("Entity",), 0, 1),
         RoleSpec("child", ("Frame",), 1, 1)),
        "ORDERED", "synthetic", ast_contract_sha256="b" * 64)
    child_ref = ChildFrameRef(
        child.occurrence_id, child.content_digest, ("Frame",))
    parent_variants = (
        (RoleOccurrence("child", 0, child_frame=child_ref),),
        (RoleOccurrence(
            "prefix", 0, concept=child.bindings[0].concept),
         RoleOccurrence("child", 0, child_frame=child_ref)),
    )
    child_envelope = next(
        item for item in config.approved.envelopes
        if item.frame.occurrence_id == child.occurrence_id)
    parent_template = next(
        item for item in config.approved.envelopes
        if item.frame.occurrence_id == original_parent.occurrence_id)
    grant_template = config.frontier.grants[0]
    requests = []
    for bindings in parent_variants:
        parent = make_frame_instance(
            schema, source_instance_id=original_parent.source_instance_id,
            structural_path=original_parent.structural_path,
            source_span=original_parent.source_span,
            parent_occurrence_id=None, bindings=bindings,
            causal_prefix_end=original_parent.causal_prefix_end)
        members = tuple(
            ContextMember(
                binding.role_id, binding.occurrence_index,
                "source:member:slot:" + binding.role_id,
                visible_at_prefix=8)
            for binding in parent.bindings)
        parent_envelope = replace(
            parent_template, frame_handle="frame:slot:parent",
            source_handle="source:frame:slot:parent",
            frame=parent, members=members)
        envelopes = (child_envelope, parent_envelope)
        grants = []
        for envelope in envelopes:
            grants.append(replace(
                grant_template, source_handle=envelope.source_handle,
                evidence_digest=frame_evidence_digest(envelope.frame)))
            for member in envelope.members:
                grants.append(replace(
                    grant_template, source_handle=member.source_handle,
                    evidence_digest=member_evidence_digest(
                        envelope.frame, member)))
        frontier = SourceFrontier(
            config.frontier.rights_epoch,
            config.frontier.correction_generation,
            tuple(sorted(grants, key=lambda grant: grant.source_handle)))
        projection = project_context(
            envelopes, config.task, frontier, config.policy)
        requests.append(ChildFrameRequest.from_context(
            projection, parent_envelope.frame_handle,
            "source:member:slot:child"))
    features = replace(
        _source_features(),
        schema_map=(("NONE", 1), ("UNKNOWN", 0),
                    ("frame:child", 2), ("frame:parent", 3),
                    ("frame:parent-slot", 4)))
    extents = GenerationExtents(
        1, 1, "a" * 64, "b" * 64, features.digest)
    rng = np.random.default_rng(578)
    params = {
        item.name: mx.array(
            rng.normal(0, 0.02, item.shape).astype(np.float32))
        for item in expected_bamf_shapes(ModelTopologySpecV2(), extents)
        if item.name.startswith(("frame.", "features."))
    }
    return requests, features, extents, params


class NestedFrameConstituentTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
