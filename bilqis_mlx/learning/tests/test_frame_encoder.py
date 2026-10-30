"""Disposable B03.1 equations over complete concept-valued source groups."""
from dataclasses import replace
import hashlib
from lib.ithkuil.src.skos.publication import json_bytes
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
        self.active_digest = hashlib.sha256(json_bytes([11,12])).hexdigest()
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


    def empty_inputs(self):
        full,vectors,ast=self.compiled_inputs()
        config=full.compiler_configs[0]
        old=config.approved.envelopes[0]
        schema=replace(config.schemas[0],roles=tuple(replace(role,min_cardinality=0) for role in config.schemas[0].roles))
        frame=make_frame_instance(schema,source_instance_id=old.frame.source_instance_id,structural_path=(),
                                  source_span=old.frame.source_span,parent_occurrence_id=None,
                                  bindings=(),causal_prefix_end=8)
        envelope=replace(old,frame=frame,members=())
        frontier=replace(config.frontier,grants=tuple(replace(grant,evidence_digest=frame_evidence_digest(frame))
                         if grant.source_handle==envelope.source_handle else grant for grant in config.frontier.grants))
        projection=project_context((envelope,),config.task,frontier,config.policy)
        config=replace(config,schemas=(schema,),schema_map=SchemaTagMap.from_schemas(self.features.semantic_release,(schema,)),
                       approved=projection,frontier=frontier)
        ast=replace(ast,frames=(FrameTree(frame),))
        rows=compile_prefix_rows(((ast,8,config),),self.features.semantic_release)
        return CompiledEncoderInput(rows,(config,),self.features,self.extents),replace(vectors,members=((),)),ast


if __name__ == "__main__":
    unittest.main()
