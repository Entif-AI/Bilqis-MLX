"""Source-owned raw atoms remain differentiable through the real B03 entrypoint."""
from dataclasses import replace
from unittest import TestCase, skipUnless

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.frame_encoder import CompiledEncoderInput
from bilqis_mlx.learning.source_atoms import SourceAtomRow, encode_source_compiled
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
)
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.atlas_snapshot import load_pinned_atlas_snapshot
from bilqis_mlx.semantics.frame_compiler import compile_prefix_rows
from bilqis_mlx.source_adapters.tests.atoms.helpers import REAL_BUNDLE, source_case


@skipUnless(REAL_BUNDLE, "real pinned A01 artifact not mounted")
class SourceEncodingTests(TestCase):
    def setUp(self):
        ast, self.config, _, _, selection, row, graph, args = source_case(visible_end=2)
        self.source = SourceAtomRow(selection, row, graph, **args)
        self.snapshot = load_pinned_atlas_snapshot(selection)
        self.schema = FeatureSchema((), ())
        features = build_feature_manifest(self.snapshot, self.schema)
        extents = GenerationExtents(
            1 + max(entry.bank for entry in self.snapshot.abi_entries), 1,
            self.snapshot.active_set_sha256, "b" * 64, features.digest)
        rows = compile_prefix_rows(((ast, 2, self.config),), self.snapshot.release_sha256)
        self.compiled = CompiledEncoderInput(rows, (self.config,), features, extents)
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
        return encode_source_compiled(
            self.compiled if compiled is None else compiled,
            self.parameters if parameters is None else parameters,
            (self.source if source is None else source,), self.schema)

    def test_real_b03_result_matches_literal_source_owned_identity_and_factor_equation(self):
        before = {key: id(value) for key, value in self.parameters.items()}
        result = self.encode()
        vector = np.zeros(768, dtype=np.float32)
        vector[:3] = [.2, .6, .05]
        expected = vector / np.sqrt(np.mean(vector * vector) + 1e-5)
        np.testing.assert_allclose(np.asarray(result.global_seeds),
                                   np.broadcast_to(expected, (1, 2, 768)),
                                   rtol=1e-6, atol=1e-6)
        self.assertIs(result.compiled, self.compiled.compiled)
        self.assertEqual({key: id(value) for key, value in self.parameters.items()}, before)

    def test_gradients_reach_actual_b01_identity_and_factor_coordinates(self):
        def loss(parameters):
            return self.encode(parameters).global_seeds[..., 2].sum()

        gradients = mx.grad(loss)(self.parameters)
        actual_indices = self.source.source_row["tokens"][:2]
        selected = gradients["identity.bank.0"][mx.array(actual_indices), 2]
        self.assertTrue(bool(mx.all(mx.isfinite(selected))))
        self.assertTrue(bool(mx.all(mx.abs(selected) > 0)))
        self.assertGreater(float(mx.abs(gradients["features.project_type"][2, 0])), 0)
        self.assertGreater(float(mx.abs(gradients["features.type"][1, 0])), 0)
        self.assertEqual(float(mx.abs(gradients["identity.bank.1"]).sum()), 0)

    def test_source_known_inactive_rows_do_not_force_unadmitted_bank_expansion(self):
        compiled = replace(self.compiled, extents=replace(
            self.compiled.extents, semantic_bank_count=1))
        parameters = {key: value for key, value in self.parameters.items()
                      if key != "identity.bank.1"}
        result = self.encode(parameters=parameters, compiled=compiled)
        np.testing.assert_array_equal(np.asarray(result.global_seeds),
                                      np.asarray(self.encode().global_seeds))

    def test_current_revocation_and_generation_drift_precede_vector_return(self):
        revoked = replace(self.config.frontier.grants[0], revoked=True)
        config = replace(self.config, frontier=replace(
            self.config.frontier, grants=(revoked, *self.config.frontier.grants[1:])))
        with self.assertRaises(BilqisError):
            changed = replace(self.compiled, compiler_configs=(config,))
            self.encode(compiled=changed)
        changed = replace(self.compiled, extents=replace(
            self.compiled.extents, active_semantic_digest="9" * 64))
        with self.assertRaises(BilqisError):
            self.encode(compiled=changed)

    def test_partial_parameter_tree_and_caller_atom_vectors_are_not_accepted(self):
        partial = {key: value for key, value in self.parameters.items()
                   if key != "blocks.11.ffn_in"}
        with self.assertRaises(BilqisError):
            self.encode(parameters=partial)
        with self.assertRaises(TypeError):
            encode_source_compiled(
                self.compiled, self.parameters, (self.source,), self.schema,
                atom_vectors=mx.zeros((1, 2, 768)))
