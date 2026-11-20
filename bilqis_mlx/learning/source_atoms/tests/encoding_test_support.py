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



class SourceEncodingFixture(TestCase):
    def setUp(self):
        ast, self.config, _, _, selection, row, graph, args = source_case(visible_end=2)
        self.source = SourceAtomRow(selection, row, graph, **args)
        self.snapshot = load_pinned_atlas_snapshot(selection)
        self.active_indices = tuple(
            entry.index for entry in self.snapshot.abi_entries if entry.active)
        self.schema = FeatureSchema((), ())
        features = build_feature_manifest(self.snapshot, self.schema)
        extents = GenerationExtents(
            1 + max(entry.bank for entry in self.snapshot.abi_entries), 1,
            self.snapshot.active_set_sha256, "b" * 64, features.digest)
        rows = compile_prefix_rows(((ast, 2, self.config),), self.snapshot.release_sha256)
        self.compiled = CompiledEncoderInput(rows, (self.config,), features, extents)
        self.artifact_owner = AtlasFeatureArtifactOwner(features, self.schema)
        self.parameters = {
            item.name: mx.zeros(item.shape, dtype=mx.float32)
            for item in expected_bamf_shapes(ModelTopologySpecV2(), extents)}
        self.parameters["features.norm"] = mx.ones((768,), dtype=mx.float32)
        self.parameters["identity.bank.0"] = (
            self.parameters["identity.bank.0"].at[:228, 0].add(.2).at[:228, 1].add(.6))
        self.parameters["features.type"] = self.parameters["features.type"].at[1, 0].add(.1)
        self.parameters["features.project_type"] = (
            self.parameters["features.project_type"].at[2, 0].add(1))

    def encode(self, parameters=None, compiled=None, source=None):
        actual_parameters = self.parameters if parameters is None else parameters
        actual_compiled = self.compiled if compiled is None else compiled
        banks = semantic_bank_views(
            actual_parameters, actual_compiled.extents,
            actual_compiled.features.semantic_release, self.active_indices)
        return encode_source_compiled(
            actual_compiled,
            actual_parameters,
            (self.source if source is None else source,), self.schema,
            banks,
            self.artifact_owner)

    def atomic_case(self, span_end=1):
        ast, config, _, _, selection, row, graph, args = source_case(
            visible_end=span_end)
        atomic = atomic_fallback(
            {"kind": "source-atom", "token": ast.atoms[0].token},
            source_instance_id=ast.source_instance_id, structural_path=(0,),
            source_span=SourceSpan(0, span_end), parent_occurrence_id=None,
            causal_prefix_end=span_end)
        frame_handle = "source-atomic:test:frame"
        member = ContextMember(
            "<atomic>", 0, "source-atomic:test:member", span_end)
        envelope = ContextEligibility(
            frame_handle, atomic, "source-atomic:test:source", (member,),
            config.task.principal_id, config.task.tenant_id, config.task.purpose,
            PUBLIC_FORMAL, self.snapshot.release_sha256,
            config.task.jurisdiction, config.task.scope, PUBLIC_FORMAL,
            config.policy.policy_epoch, config.frontier.rights_epoch,
            config.frontier.correction_generation, 0, 0, None, span_end)
        grants = list(config.frontier.grants)
        for handle, digest in (
            (envelope.source_handle, frame_evidence_digest(atomic)),
            (member.source_handle, member_evidence_digest(atomic, member)),
        ):
            grants.append(SourceGrant(
                handle, config.task.principal_id, config.task.tenant_id,
                PUBLIC_FORMAL, self.snapshot.release_sha256, digest,
                (config.task.purpose,), (config.task.jurisdiction,),
                (config.task.scope,), config.frontier.rights_epoch,
                config.frontier.correction_generation, 0, 0))
        frontier = SourceFrontier(
            config.frontier.rights_epoch, config.frontier.correction_generation,
            tuple(sorted(grants, key=lambda item: item.source_handle)))
        projection = project_context(
            (envelope,), config.task, frontier, config.policy)
        config = replace(config, approved=projection, frontier=frontier)
        ast = StreamingAST(
            ast.source_instance_id, ast.atoms, (FrameTree(atomic),))
        rows = compile_prefix_rows(
            ((ast, span_end, config),), self.snapshot.release_sha256)
        receipt = validate_partial_visible_forest(rows.rows[0], ast, config)
        compiled = CompiledEncoderInput(
            rows, (config,), self.compiled.features, self.compiled.extents,
            source_asts=(ast,), partial_forest_receipts=(receipt,))
        return compiled, SourceAtomRow(selection, row, graph, **args)
