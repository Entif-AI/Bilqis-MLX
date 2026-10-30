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


class FrameEncoderTests3(FrameEncoderTestsFixture, unittest.TestCase):
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
