"""Released A06 factor composition feeding B02 and shared depth selection."""
from dataclasses import replace
import hashlib
from lib.ithkuil.src.skos.publication import json_bytes
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.frame_embeddings import (
    ConceptBatch, FeatureRequest, SemanticBankView, _local_position, compose_factor_features, embed_atoms, semantic_logits,
    IndexedLogits, gather_constituents, masked_semantic_loss, plan_identity_initialization,
    embedding_parameter_view,
)
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes
from bilqis_mlx.runtime.model_topology import DEFAULT_OPTIMIZER
from bilqis_mlx.semantics.frame_schema import (
    ConceptRef, FrameSchema, RoleOccurrence, RoleSpec, SourceSpan, make_frame_instance,
)
from bilqis_mlx.semantics.context_eligibility import (
    ContextMember, frame_evidence_digest, member_evidence_digest, project_context,
)
from bilqis_mlx.semantics.tests.test_context_eligibility import _case
from bilqis_mlx.semantics.tests.test_atlas_features import _features, _snapshot


def _context_for(concept, source_instance="fixture:released-source", schema_id="frame:urn:concept:A"):
    envelopes, task, frontier, policy = _case(count=1, two_roles=True)
    schema = FrameSchema(schema_id, 1, "source:fixture",
                         tuple(RoleSpec(role, concept.type_ids, 1, 1) for role in ("left", "right")),
                         "ORDERED", "source-expression")
    frame = make_frame_instance(schema, source_instance_id=source_instance, structural_path=(),
                                source_span=SourceSpan(0, 8), parent_occurrence_id=None,
                                bindings=tuple(RoleOccurrence(role, 0, concept=concept) for role in ("left", "right")),
                                causal_prefix_end=8)
    members = tuple(ContextMember(role, 0, "source:member:"+role, 8) for role in ("left", "right"))
    envelope = replace(envelopes[0], frame=frame, members=members)
    evidence = {envelope.source_handle: frame_evidence_digest(frame),
                **{member.source_handle: member_evidence_digest(frame, member) for member in members}}
    grants = tuple(replace(frontier.grants[0], source_handle=handle, evidence_digest=digest)
                   for handle, digest in sorted(evidence.items()))
    return project_context((envelope,), task, replace(frontier, grants=grants), policy)


class FactorCompositionTests(unittest.TestCase):
    def setUp(self):
        self.features = _features()
        self.extents = GenerationExtents(1, 1, hashlib.sha256(json_bytes([11])).hexdigest(), "b" * 64, self.features.digest)
        ledger = expected_bamf_shapes(ModelTopologySpecV2(), self.extents)
        self.params = {item.name: mx.zeros(item.shape, dtype=mx.float32)
                       for item in ledger if item.name.startswith("features.")}
        self.params["features.type"] = self.params["features.type"].at[2].add(.5)
        self.params["features.role"] = self.params["features.role"].at[2].add(1).at[3].add(2)
        self.params["features.schema"] = self.params["features.schema"].at[2].add(.25)
        self.params["features.project_type"] = self.params["features.project_type"].at[0, 0].add(2)
        self.params["features.project_role"] = self.params["features.project_role"].at[1, 0].add(3)
        self.params["features.project_schema"] = self.params["features.project_schema"].at[2, 0].add(4)
        self.params["features.project_graph"] = self.params["features.project_graph"].at[3, 4].add(5)
        self.params["features.local_slot"] = self.params["features.local_slot"].at[0, 4].add(7)
        self.params["features.gates"] = mx.full((4,), -2, dtype=mx.float32)
        self.params["features.norm"] = mx.ones((768,), dtype=mx.float32)
        self.ref = ConceptRef("urn:concept:A", self.features.semantic_release, 11,
                              ("urn:type:Entity",), "fixture:qualified-source")

    def request(self, role="left"):
        return FeatureRequest.from_context(_context_for(self.ref), "frame:0", "source:member:"+role)


if __name__ == "__main__":
    unittest.main()
