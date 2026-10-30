"""Behavior tests split from their shared fixture owner."""
from dataclasses import replace
import hashlib
from lib.ithkuil.src.skos.publication import json_bytes
import unittest
import mlx.core as mx
import numpy as np
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.frame_embeddings import ConceptBatch, FeatureRequest, SemanticBankView, embed_atoms
from bilqis_mlx.learning.frame_encoder import AtomicEncoderInput, AtomicSourceHandle, FrameEncoderInput, encode_frames, frame_encoder_parameter_view, CompiledEncoderInput, CompiledEmbeddingVectors, MemberEmbedding, AtomicFrameEmbedding
from bilqis_mlx.learning.tests.test_frame_embeddings import _context_for
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes
from bilqis_mlx.semantics.context_eligibility import frame_evidence_digest, member_evidence_digest, project_context
from bilqis_mlx.semantics.frame_schema import ConceptRef, RoleOccurrence, make_frame_instance, FrameSchema, RoleSpec, atomic_fallback
from bilqis_mlx.semantics.core import Literal
from bilqis_mlx.semantics.context_eligibility import ContextMember
from bilqis_mlx.semantics.frame_compiler import FrameCompilerConfig, SourceAtom, StreamingAST, compile_prefix_rows
from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.frame_schema import FrameTree
from bilqis_mlx.semantics.tests.test_frame_compiler import _with_atom_grants
from bilqis_mlx.semantics.tests.test_atlas_features import _features, _snapshot
from bilqis_mlx.semantics.tests.test_context_eligibility import _case
from bilqis_mlx.learning.tests.test_frame_encoder import _projection, _oracle, _atomic_projection, FrameEncoderTests

class FrameEncoderTests2(FrameEncoderTests):
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

    def test_actual_legal_empty_frame_uses_none_summary_and_empty_seed(self):
        compiled,vectors,_=self.empty_inputs()
        result=encode_frames(compiled,vectors,self.params)
        summary=(self.params["features.schema"][2]+self.params["features.role"][1])/2
        expected=self.params["frame.empty_seed"]+summary @ self.params["frame.project_summary"].T
        expected=expected*mx.rsqrt(mx.mean(expected*expected)+1e-5)*self.params["frame.norm"]
        np.testing.assert_allclose(np.asarray(result.global_seeds[0,-1]),np.asarray(expected),atol=1e-7)
        self.assertTrue(bool(mx.all(mx.isfinite(result.global_seeds))))
        self.assertEqual(result.features[0][-1].requests,())
        self.assertEqual(result.features[0][-1].frame_handle,"frame:0")
        self.assertEqual(compiled.member_requests,((),))
        gradients=mx.grad(lambda p: mx.sum(encode_frames(compiled,vectors,p).global_seeds[0,-1]*
                                          mx.arange(768,dtype=mx.float32)))(self.params)
        for name in ("frame.empty_seed","frame.project_summary","frame.norm","features.schema","features.role"):
            self.assertGreater(float(mx.sum(mx.abs(gradients[name]))),0,name)
        for name in ("frame.query_schema","frame.member_key","frame.member_value","frame.pool_gate"):
            self.assertEqual(float(mx.sum(mx.abs(gradients[name]))),0,name)

    def test_empty_frame_with_required_roles_is_rejected_by_actual_schema_contract(self):
        compiled,_,ast=self.empty_inputs()
        config=compiled.compiler_configs[0]
        required=replace(config.schemas[0],roles=tuple(replace(role,min_cardinality=1) for role in config.schemas[0].roles))
        config=replace(config,schemas=(required,),schema_map=SchemaTagMap.from_schemas(self.features.semantic_release,(required,)))
        with self.assertRaises(BilqisError):
            compile_prefix_rows(((ast,8,config),),self.features.semantic_release)

    def test_actual_a05_atomic_closure_preserves_its_supplied_embedding(self):
        full,vectors,ast=self.compiled_inputs()
        config=full.compiler_configs[0]
        projection=_atomic_projection()
        envelope=projection.envelopes[0]
        evidence={envelope.source_handle:frame_evidence_digest(envelope.frame),
                  **{member.source_handle:member_evidence_digest(envelope.frame,member) for member in envelope.members}}
        grants=tuple(replace(config.frontier.grants[0],source_handle=handle,evidence_digest=digest)
                     for handle,digest in sorted(evidence.items()))
        config=replace(config,schemas=(),schema_map=SchemaTagMap.from_schemas(self.features.semantic_release,()),
                       approved=projection,frontier=replace(config.frontier,grants=grants))
        ast=replace(ast,source_instance_id=envelope.frame.source_instance_id,frames=(FrameTree(envelope.frame),))
        config=_with_atom_grants(ast,config)
        rows=compile_prefix_rows(((ast,8,config),),self.features.semantic_release)
        compiled=CompiledEncoderInput(rows,(config,),self.features,self.extents)
        atom=AtomicFrameEmbedding(compiled.atomic_handles[0][0],mx.arange(768,dtype=mx.float32))
        vectors=replace(vectors,members=((),),atomic_frames=((atom,),))
        result=encode_frames(compiled,vectors,self.params)
        np.testing.assert_array_equal(np.asarray(result.global_seeds[0,-1]),np.asarray(atom.vector))
        self.assertIsNone(result.features[0][-1])
        gradient=mx.grad(lambda p:mx.sum(encode_frames(compiled,vectors,p).global_seeds))(self.params)
        self.assertTrue(all(bool(mx.all(value==0)) for value in gradient.values()))
        for atoms in ((),((atom,atom),)):
            with self.assertRaises(BilqisError):
                encode_frames(compiled,replace(vectors,atomic_frames=atoms),self.params)
