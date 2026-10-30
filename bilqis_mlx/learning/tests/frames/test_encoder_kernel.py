"""Disposable B03.1 equations over complete concept-valued source groups."""
from dataclasses import replace
import hashlib
import unittest
import mlx.core as mx
import numpy as np
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.frame_embeddings import (
    ConceptBatch, FeatureRequest, SemanticBankView, embed_atoms,
)
from bilqis_mlx.learning.frame_encoder import (
    AtomicEncoderInput, AtomicSourceHandle, FrameEncoderInput, encode_frames, frame_encoder_parameter_view,
    CompiledEncoderInput, CompiledEmbeddingVectors, MemberEmbedding, AtomicFrameEmbedding,
)
from bilqis_mlx.learning.tests.test_frame_embeddings import _context_for
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
)
from bilqis_mlx.semantics.context_eligibility import (
    frame_evidence_digest, member_evidence_digest, project_context,
)
from bilqis_mlx.semantics.frame_schema import (
    ConceptRef, RoleOccurrence, make_frame_instance, FrameSchema, RoleSpec, atomic_fallback,
)
from bilqis_mlx.semantics.core import Literal
from bilqis_mlx.semantics.context_eligibility import ContextMember
from bilqis_mlx.semantics.frame_compiler import (
    FrameCompilerConfig, SourceAtom, StreamingAST, compile_prefix_rows,
)
from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.frame_schema import FrameTree
from bilqis_mlx.semantics.tests.test_frame_compiler import _with_atom_grants
from bilqis_mlx.semantics.tests.test_atlas_features import _features, _snapshot
from bilqis_mlx.semantics.tests.test_context_eligibility import _case

from bilqis_mlx.learning.tests.frames.encoder_fixtures import _projection, _oracle, _atomic_projection, FrameEncoderTestsFixture


class FrameEncoderTests1(FrameEncoderTestsFixture, unittest.TestCase):
    def test_exact_equations_original_members_and_source_handles(self):
        compiled, atoms = self.inputs()
        result = encode_frames(compiled, atoms, self.params)
        factors = result.features[0][0]
        expected = _oracle(np.asarray(atoms[0][0]), np.asarray(factors.schema128),
                           np.asarray(factors.mean_role128), self.params)
        np.testing.assert_allclose(np.asarray(result.global_seeds[0, 0]), expected, atol=2e-6, rtol=2e-5)
        self.assertIs(result.members, atoms)
        self.assertIs(result.handles, compiled.requests)
        self.assertEqual(tuple(r.local_slot for r in result.handles[0][0]), (0, 1))
        np.testing.assert_array_equal(np.asarray(factors.schema128), np.asarray(self.params["features.schema"][2]))
        np.testing.assert_allclose(np.asarray(factors.mean_role128),
                                   np.asarray((self.params["features.role"][2]+self.params["features.role"][3])/2))

    def test_role_swap_changes_seed_and_repeated_identity_retains_occurrences(self):
        first, atoms = self.inputs()
        swapped, other = self.inputs(refs=self.refs[::-1])
        a = encode_frames(first, atoms, self.params)
        b = encode_frames(swapped, other, self.params)
        self.assertGreater(float(mx.max(mx.abs(a.global_seeds-b.global_seeds))), 1e-4)
        repeated, values = self.inputs(refs=(self.refs[0], self.refs[0]))
        result = encode_frames(repeated, values, self.params)
        self.assertEqual(tuple(r.concept.abi_index for r in result.handles[0][0]), (11, 11))
        self.assertEqual(tuple(r.member_handle for r in result.handles[0][0]),
                         ("source:member:left", "source:member:right"))
        self.assertGreater(float(mx.max(mx.abs(values[0][0][0]-values[0][0][1]))), 0)

    def test_gradients_reach_identity_roles_schema_and_every_active_frame_tensor(self):
        def loss(params):
            compiled, atoms = self.inputs(params)
            seed = encode_frames(compiled, atoms, params).global_seeds
            return mx.sum(seed * mx.arange(768, dtype=mx.float32))
        gradients = mx.grad(loss)(self.params)
        for name in ("identity.bank.0", "features.role", "features.schema",
                     *(key for key in self.params if key.startswith("frame.") and key != "frame.empty_seed")):
            with self.subTest(name=name):
                self.assertTrue(bool(mx.all(mx.isfinite(gradients[name]))))
                self.assertGreater(float(mx.sum(mx.abs(gradients[name]))), 0)
        compiled, atoms = self.inputs()
        gradient = mx.grad(lambda x: mx.sum(encode_frames(compiled, ((x,),), self.params).global_seeds *
                                            mx.arange(768, dtype=mx.float32)))(atoms[0][0])
        self.assertTrue(bool(mx.all(mx.sum(mx.abs(gradient), axis=-1) > 0)))

    def test_reordered_incomplete_mixed_source_and_unknown_compiler_inputs_reject(self):
        compiled, atoms = self.inputs()
        group = compiled.requests[0][0]
        for members in (group[::-1], group[:1], (group[0], group[0]),
                        (group[0], self.inputs(refs=self.refs[::-1])[0].requests[0][0][1])):
            with self.subTest(members=members), self.assertRaises(BilqisError):
                candidate = replace(compiled, requests=((members,),))
                encode_frames(candidate, atoms, self.params)
        with self.assertRaises(BilqisError):
            encode_frames(object(), atoms, self.params)

    def test_bad_tensor_shapes_dtypes_and_nonfinite_values_reject(self):
        compiled, atoms = self.inputs()
        for value in (mx.zeros((1, 768)), mx.zeros((2, 768), dtype=mx.float16),
                      mx.full((2, 768), float("nan"))):
            with self.assertRaises(BilqisError):
                encode_frames(compiled, ((value,),), self.params)
        for name, value in (("frame.member_key", mx.zeros((768, 192))),
                            ("frame.pool_gate", mx.array([float("inf")]))):
            with self.assertRaises(BilqisError):
                encode_frames(compiled, atoms, {**self.params, name: value})

    def test_batch_rows_are_independent_and_member_gradient_is_not_detached(self):
        compiled, atoms = self.inputs()
        other, other_atoms = self.inputs(refs=self.refs[::-1])
        batch = replace(compiled, requests=(compiled.requests[0], other.requests[0]))
        values = (atoms[0], other_atoms[0])
        result = encode_frames(batch, values, self.params)
        np.testing.assert_array_equal(np.asarray(result.global_seeds[0]),
                                      np.asarray(encode_frames(compiled, atoms, self.params).global_seeds[0]))
        gradient = mx.grad(lambda second: mx.sum(encode_frames(
            batch, (atoms[0], (second,)), self.params).global_seeds[0]))(other_atoms[0][0])
        np.testing.assert_array_equal(np.asarray(gradient), np.zeros((2, 768), dtype=np.float32))
        with self.assertRaises(BilqisError):
            replace(compiled, requests=(compiled.requests[0]+other.requests[0],))

    def test_raw_factor_overflow_matches_independent_exact_id_expansion(self):
        compiled, atoms = self.inputs()
        features = replace(self.features, role_map=tuple((name, 0 if name == "right" else row)
                                                       for name, row in self.features.role_map),
                           schema_map=tuple((name, 0 if name == "frame:urn:concept:A" else row)
                                            for name, row in self.features.schema_map))
        compiled = replace(compiled, features=features,
                           extents=replace(self.extents, factor_map_digest=features.digest))
        def expansion(kind, identifier):
            raw = b"".join(hashlib.sha256(f"bamf.factor.v2|{kind}|{identifier}|{block}".encode()).digest()
                           for block in range(4))
            return ((np.frombuffer(raw, dtype=np.uint8)/127.5-1)/np.sqrt(128)).astype(np.float32)
        result = encode_frames(compiled, atoms, self.params).features[0][0]
        np.testing.assert_allclose(np.asarray(result.schema128),
                                   np.asarray(self.params["features.schema"][0]) +
                                   expansion("schema", "frame:urn:concept:A"), atol=1e-7)
        np.testing.assert_allclose(np.asarray(result.mean_role128),
                                   (np.asarray(self.params["features.role"][2]) +
                                    np.asarray(self.params["features.role"][0]) +
                                    expansion("role", "right"))/2, atol=1e-7)

    def test_full_b01_parameter_view_borrows_exact_canonical_tensors(self):
        spec = ModelTopologySpecV2()
        full = {item.name: mx.zeros(item.shape, dtype=mx.float32)
                for item in expected_bamf_shapes(spec, self.extents)}
        view = frame_encoder_parameter_view(full, spec=spec, extents=self.extents)
        self.assertEqual(set(view), {name for name in self.params if name != "identity.bank.0"})
        for name in view:
            self.assertIs(view[name], full[name])
        for bad in ({key: value for key, value in full.items() if key != "blocks.11.ffn_in"},
                    {**full, "secret.frame_head": mx.zeros((1,))}):
            with self.assertRaises(BilqisError):
                frame_encoder_parameter_view(bad, spec=spec, extents=self.extents)

    def test_atomic_fallback_preserves_literal_vector_handles_and_identity_gradient(self):
        projection = _atomic_projection()
        handle = AtomicSourceHandle(projection, "frame:0", "source:atomic:member")
        compiled = AtomicEncoderInput(((handle,),))
        vector = mx.arange(768, dtype=mx.float32)[None, :]
        members = ((vector,),)
        result = encode_frames(compiled, members, self.params)
        np.testing.assert_array_equal(np.asarray(result.global_seeds), np.arange(768)[None, None, :])
        self.assertIs(result.members, members)
        self.assertIs(result.handles, compiled.handles)
        self.assertEqual(result.features, ((None,),))
        gradient = mx.grad(lambda x: mx.sum(encode_frames(compiled, ((x,),), {}).global_seeds))(vector)
        np.testing.assert_array_equal(np.asarray(gradient), np.ones((1, 768)))
        gradients = mx.grad(lambda p: mx.sum(encode_frames(compiled, members, p).global_seeds))(self.params)
        self.assertTrue(all(bool(mx.all(value == 0)) for value in gradients.values()))
