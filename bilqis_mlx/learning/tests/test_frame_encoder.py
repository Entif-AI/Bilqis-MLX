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
    CompiledEncoderInput, CompiledEmbeddingVectors, MemberEmbedding,
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


def _projection(concepts):
    envelopes, task, frontier, policy = _case(count=1, two_roles=True)
    old = _context_for(concepts[0]).envelopes[0]
    schema = FrameSchema(old.frame.frame_schema_id, 1, "source:fixture",
                         tuple(RoleSpec(role, concepts[0].type_ids, 1, 1) for role in ("left", "right")),
                         "ORDERED", "source-expression")
    frame = make_frame_instance(schema, source_instance_id="fixture:encoder", structural_path=(),
                                source_span=old.frame.source_span, parent_occurrence_id=None,
                                bindings=tuple(RoleOccurrence(role, 0, concept=ref)
                                               for role, ref in zip(("left", "right"), concepts)),
                                causal_prefix_end=8)
    envelope = replace(envelopes[0], frame=frame, members=old.members)
    evidence = {envelope.source_handle: frame_evidence_digest(frame),
                **{m.source_handle: member_evidence_digest(frame, m) for m in envelope.members}}
    grants = tuple(replace(frontier.grants[0], source_handle=h, evidence_digest=d)
                   for h, d in sorted(evidence.items()))
    return project_context((envelope,), task, replace(frontier, grants=grants), policy)


def _oracle(members, schema, role, parameters):
    p = {k: np.asarray(v) for k, v in parameters.items()}
    def norm(x, key):
        return x / np.sqrt(np.mean(x*x, axis=-1, keepdims=True) + 1e-5) * p[key]
    def softmax(x):
        e = np.exp(x - np.max(x, axis=-1, keepdims=True))
        return e / e.sum(axis=-1, keepdims=True)
    u = members @ p["frame.member_value"].T
    q = schema @ p["frame.query_schema"].T
    k = members @ p["frame.member_key"].T
    a = softmax(q @ k.T / np.sqrt(192))
    score = (u @ p["frame.interact_query"].T) @ (u @ p["frame.interact_key"].T).T / np.sqrt(192)
    v = norm(u + (softmax(score) @ (u @ p["frame.interact_value"].T)) @
             p["frame.interact_output"].T, "frame.interact_norm")
    pooled = a @ u + (1 / (1 + np.exp(-p["frame.pool_gate"]))) * (a @ v)
    return norm(pooled @ p["frame.project_output"].T +
                ((schema + role) / 2) @ p["frame.project_summary"].T, "frame.norm")


def _atomic_projection():
    envelopes, task, frontier, policy = _case(count=1)
    frame = atomic_fallback(Literal(True, "Bool"), source_instance_id="fixture:atomic", structural_path=(),
                            source_span=envelopes[0].frame.source_span,
                            parent_occurrence_id=None, causal_prefix_end=8)
    member = ContextMember("<atomic>", 0, "source:atomic:member", 8)
    envelope = replace(envelopes[0], frame=frame, members=(member,))
    evidence = {envelope.source_handle: frame_evidence_digest(frame),
                member.source_handle: member_evidence_digest(frame, member)}
    grants = tuple(replace(frontier.grants[0], source_handle=h, evidence_digest=d)
                   for h, d in sorted(evidence.items()))
    return project_context((envelope,), task, replace(frontier, grants=grants), policy)


class FrameEncoderTests(unittest.TestCase):
    def setUp(self):
        self.features = _features(_snapshot(definitions=(("urn:concept:A", ("urn:type:Entity",)),
                                                        ("urn:concept:B", ("urn:type:Entity",)))))
        self.active_digest = hashlib.sha256(b"[11,12]").hexdigest()
        self.extents = GenerationExtents(1, 1, self.active_digest, "b"*64, self.features.digest)
        rng = np.random.default_rng(442)
        self.params = {item.name: mx.array(rng.normal(0, .04, item.shape).astype(np.float32))
                       for item in expected_bamf_shapes(ModelTopologySpecV2(), self.extents)
                       if item.name.startswith(("features.", "frame."))}
        for name in ("features.norm", "frame.norm", "frame.interact_norm"):
            self.params[name] = mx.ones_like(self.params[name])
        self.params["frame.pool_gate"] = mx.array([-2.], dtype=mx.float32)
        self.params["identity.bank.0"] = mx.zeros((8192, 768), dtype=mx.float32).at[11:13].add(
            mx.array(rng.normal(0, .1, (2, 768)).astype(np.float32)))
        self.refs = tuple(ConceptRef("urn:concept:"+name, self.features.semantic_release, index,
                                    ("urn:type:Entity",), "fixture:encoder")
                          for name, index in (("A", 11), ("B", 12)))

    def inputs(self, params=None, refs=None):
        params = self.params if params is None else params
        projection = _projection(self.refs if refs is None else refs)
        requests = tuple(FeatureRequest.from_context(projection, "frame:0", "source:member:"+role)
                         for role in ("left", "right"))
        compiled = FrameEncoderInput(((requests,),), self.features, self.extents)
        bank = SemanticBankView(0, params["identity.bank.0"], (11, 12),
                                self.features.semantic_release, self.active_digest)
        atoms = embed_atoms(params, ConceptBatch((requests,), (bank,), self.extents), self.features)[0]
        return compiled, ((atoms,),)

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

    def test_atomic_fallback_rejects_nonatomic_or_foreign_handles_and_bad_vectors(self):
        projection = _atomic_projection()
        handle = AtomicSourceHandle(projection, "frame:0", "source:atomic:member")
        for fields in ({"frame_handle": "invented"}, {"member_handle": "invented"},
                       {"projection": self.inputs()[0].requests[0][0][0].projection}):
            with self.assertRaises(BilqisError):
                replace(handle, **fields)
        compiled = AtomicEncoderInput(((handle,),))
        for value in (mx.zeros((768,)), mx.zeros((2, 768)), mx.zeros((1, 768), dtype=mx.float16),
                      mx.full((1, 768), float("nan"))):
            with self.assertRaises(BilqisError):
                encode_frames(compiled, ((value,),), {})

    def compiled_inputs(self, prefix=8):
        provisional, members = self.inputs()
        projection = provisional.requests[0][0][0].projection
        frame = projection.frame("frame:0")
        schema = FrameSchema(frame.frame_schema_id, 1, "source:fixture",
                             tuple(RoleSpec(role, self.refs[0].type_ids, 1, 1) for role in ("left", "right")),
                             "ORDERED", "source-expression")
        _, task, frontier, policy = _case(count=1, two_roles=True)
        envelope = projection.envelopes[0]
        evidence = {envelope.source_handle: frame_evidence_digest(frame),
                    **{m.source_handle: member_evidence_digest(frame, m) for m in envelope.members}}
        grants = tuple(replace(frontier.grants[0], source_handle=h, evidence_digest=d)
                       for h,d in sorted(evidence.items()))
        config = FrameCompilerConfig((schema,), SchemaTagMap.from_schemas(self.features.semantic_release, (schema,)),
                                     projection, task, replace(frontier, grants=grants), policy)
        ast = StreamingAST(frame.source_instance_id,
                           tuple(SourceAtom(i, f"token{i}", f"source:atom:{i}") for i in range(8)),
                           (FrameTree(frame),))
        config = _with_atom_grants(ast, config)
        rows = compile_prefix_rows(((ast, prefix, config),), self.features.semantic_release)
        compiled = CompiledEncoderInput(rows, (config,), self.features, self.extents)
        vectors = CompiledEmbeddingVectors((mx.arange(prefix*768, dtype=mx.float32).reshape(prefix,768)/1000,),
                    (tuple(MemberEmbedding(request, members[0][0][index])
                           for index, request in enumerate(compiled.member_requests[0])),))
        return compiled, vectors, ast

    def test_actual_a05_atoms_and_closure_keep_source_maps_and_member_gradients(self):
        compiled, vectors, _ = self.compiled_inputs()
        result = encode_frames(compiled, vectors, self.params)
        np.testing.assert_array_equal(np.asarray(result.global_seeds[0,:8]), np.asarray(vectors.atoms[0]))
        old, members = self.inputs()
        np.testing.assert_allclose(np.asarray(result.global_seeds[0,8]),
                                   np.asarray(encode_frames(old,members,self.params).global_seeds[0,0]), atol=1e-7)
        self.assertIs(result.compiled, compiled.compiled)
        self.assertIs(result.handles, compiled.compiled.padded_positions)
        self.assertEqual(result.compiled.rows[0].maps.role_access[0].role_id, "left")
        self.assertEqual(result.features[0][8].requests, compiled.member_requests[0])
        def objective(array):
            entries = tuple(replace(item, vector=array[i]) for i,item in enumerate(vectors.members[0]))
            return mx.sum(encode_frames(compiled, replace(vectors, members=(entries,)), self.params).global_seeds *
                          mx.arange(768, dtype=mx.float32))
        derivative=mx.grad(objective)(mx.stack([item.vector for item in vectors.members[0]]))
        self.assertTrue(bool(mx.all(mx.sum(mx.abs(derivative),axis=-1)>0)))
        raw_gradient=mx.grad(lambda array: mx.sum(encode_frames(
            compiled,replace(vectors,atoms=(array,)),self.params).global_seeds[0,:8]))(vectors.atoms[0])
        np.testing.assert_array_equal(np.asarray(raw_gradient),np.ones((8,768)))

    def test_actual_partial_prefix_and_unequal_rows_have_no_future_or_padding_handles(self):
        partial, vectors, ast = self.compiled_inputs(3)
        full, full_vectors, _ = self.compiled_inputs()
        result = encode_frames(partial,vectors,self.params)
        self.assertEqual(partial.member_requests,((),))
        np.testing.assert_array_equal(np.asarray(result.global_seeds[0]), np.asarray(vectors.atoms[0]))
        changed = replace(ast, atoms=ast.atoms[:3]+tuple(replace(atom,token="changed-future") for atom in ast.atoms[3:]))
        rows = compile_prefix_rows(((changed,3,partial.compiler_configs[0]),),self.features.semantic_release)
        other=encode_frames(replace(partial,compiled=rows),vectors,self.params)
        np.testing.assert_array_equal(np.asarray(result.global_seeds),np.asarray(other.global_seeds))
        both_rows=compile_prefix_rows(((ast,3,partial.compiler_configs[0]),
                                      (ast,8,full.compiler_configs[0])),self.features.semantic_release)
        both=replace(full,compiled=both_rows,compiler_configs=(partial.compiler_configs[0],full.compiler_configs[0]))
        both_vectors=CompiledEmbeddingVectors((vectors.atoms[0],full_vectors.atoms[0]),((),full_vectors.members[0]))
        encoded=encode_frames(both,both_vectors,self.params)
        np.testing.assert_array_equal(np.asarray(encoded.global_seeds[0,:3]),np.asarray(result.global_seeds[0]))
        np.testing.assert_array_equal(np.asarray(encoded.global_seeds[0,3:]),np.zeros((6,768)))
        self.assertEqual(encoded.handles[0][3:],(None,)*6)

    def test_actual_compiler_rechecks_rights_and_exact_member_vector_bijection(self):
        compiled,vectors,_=self.compiled_inputs()
        for entries in (vectors.members[0][::-1],vectors.members[0][:1],vectors.members[0]*2):
            with self.assertRaises(BilqisError):
                encode_frames(compiled,replace(vectors,members=(entries,)),self.params)
        config=compiled.compiler_configs[0]
        revoked=replace(config,frontier=replace(config.frontier,grants=tuple(
            replace(grant,revoked=True) for grant in config.frontier.grants)))
        with self.assertRaises(BilqisError):
            replace(compiled,compiler_configs=(revoked,))
        stale_policy=replace(config,policy=replace(config.policy,policy_epoch=2))
        with self.assertRaises(BilqisError):
            replace(compiled,compiler_configs=(stale_policy,))
        schema=replace(config.schemas[0],roles=tuple(replace(role,max_cardinality=2) for role in config.schemas[0].roles))
        changed_schema=replace(config,schemas=(schema,),schema_map=SchemaTagMap.from_schemas(
            self.features.semantic_release,(schema,)))
        with self.assertRaises(BilqisError):
            replace(compiled,compiler_configs=(changed_schema,))
        with self.assertRaises(BilqisError):
            encode_frames(compiled,replace(vectors,atoms=(mx.zeros((9,768)),)),self.params)


if __name__ == "__main__":
    unittest.main()
