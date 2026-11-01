"""Literal source-bound type/role/schema features for the B08 gate."""
from dataclasses import replace
import hashlib

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.frame_embeddings import ChildFrameRequest, motif_gate_features
from bilqis_mlx.learning.tests.test_frame_embeddings import (
    FactorCompositionTests, _context_for,
)
from bilqis_mlx.semantics.context_eligibility import frame_evidence_digest, project_context
from bilqis_mlx.semantics.frame_schema import FrameSchema, RoleSpec, make_frame_instance
from bilqis_mlx.semantics.tests.test_atlas_features import _features, _snapshot
from bilqis_mlx.semantics.tests.test_context_eligibility import _case
from bilqis_mlx.semantics.tests.test_frame_compiler import _mixed_case


class MotifFeatureTests(FactorCompositionTests):
    def value(self, parameters=None, **changes):
        return motif_gate_features(
            parameters if parameters is not None else self.params,
            _context_for(self.ref), "frame:0", self.features,
            extents=changes.get("extents", self.extents))

    def test_literal_type_role_schema_mean_and_source_identity(self):
        actual = self.value()
        np.testing.assert_allclose(np.asarray(actual.vector128), np.full(128, .75))
        self.assertEqual(actual.frame_handle, "frame:0")
        self.assertEqual(actual.context_digest, _context_for(self.ref).digest)
        self.assertEqual(actual.feature_digest, self.features.digest)
        self.assertEqual(actual.semantic_release, self.features.semantic_release)
        self.assertEqual(tuple(r.role_id for r in actual.requests), ("left", "right"))

    def test_only_raw_categorical_tables_affect_gate_features(self):
        changed = {name: (value if name in (
            "features.type", "features.role", "features.schema")
            else mx.full(value.shape, 31, dtype=value.dtype))
                   for name, value in self.params.items()}
        np.testing.assert_array_equal(
            np.asarray(self.value(changed).vector128), np.asarray(self.value().vector128))

    def test_gradients_reach_source_rows_and_no_projection_or_gate(self):
        gradient = mx.grad(lambda p: mx.sum(self.value(p).vector128))(self.params)
        for name, row, expected in (("features.type", 2, 1/3),
                                     ("features.role", 2, 1/6),
                                     ("features.role", 3, 1/6),
                                     ("features.schema", 2, 1/3)):
            with self.subTest(table=name, row=row):
                np.testing.assert_allclose(np.asarray(gradient[name][row]), expected)
        self.assertEqual(float(mx.sum(mx.abs(gradient["features.type"][0]))), 0)
        self.assertEqual(float(mx.sum(mx.abs(gradient["features.schema"][0]))), 0)
        self.assertEqual(float(mx.sum(mx.abs(gradient["features.gates"]))), 0)
        self.assertEqual(float(mx.sum(mx.abs(gradient["features.project_type"]))), 0)

    def test_foreign_feature_digest_and_missing_frame_reject(self):
        with self.assertRaises(BilqisError):
            self.value(extents=replace(self.extents, factor_map_digest="f" * 64))
        with self.assertRaises(BilqisError):
            motif_gate_features(self.params, _context_for(self.ref), "missing",
                                self.features, extents=self.extents)

    def test_forged_abi_or_type_cannot_select_a_source_row(self):
        for ref in (replace(self.ref, abi_index=12),
                    replace(self.ref, type_ids=("forged",))):
            with self.subTest(ref=ref), self.assertRaises(BilqisError):
                motif_gate_features(self.params, _context_for(ref), "frame:0",
                                    self.features, extents=self.extents)

    def test_nonfinite_selected_source_factor_rejects(self):
        parameters = {**self.params, "features.type":
                      self.params["features.type"].at[2, 0].add(float("nan"))}
        with self.assertRaises(BilqisError):
            self.value(parameters)

    def test_child_uses_qualified_type_without_a_concept_or_abi_row(self):
        _, config = _mixed_case()
        features = replace(self.features,
                           type_map=(("UNKNOWN", 0), ("NONE", 1), ("Frame", 2)),
                           role_map=(*self.features.role_map, ("child", 4)),
                           schema_map=(*self.features.schema_map, ("frame:parent", 3)))
        extents = replace(self.extents, factor_map_digest=features.digest)
        parameters = {**self.params,
                      "features.role": self.params["features.role"].at[4].add(3),
                      "features.schema": self.params["features.schema"].at[3].add(.75)}
        actual = motif_gate_features(parameters, config.approved, "frame:mixed:2",
                                     features, extents=extents)
        np.testing.assert_allclose(np.asarray(actual.vector128), (.5 + 3 + .75) / 3)
        self.assertIs(type(actual.requests[0]), ChildFrameRequest)
        self.assertFalse(hasattr(actual.requests[0], "abi_index"))

    def test_empty_legal_frame_uses_explicit_none_rows(self):
        envelopes, task, frontier, policy = _case(count=1, two_roles=True)
        template = _context_for(self.ref).envelopes[0].frame
        schema = FrameSchema(template.frame_schema_id, 1, "source:fixture",
                             (RoleSpec("left", self.ref.type_ids, 0, 1),),
                             "ORDERED", "source-expression")
        frame = make_frame_instance(
            schema, source_instance_id=template.source_instance_id, structural_path=(),
            source_span=template.source_span, parent_occurrence_id=None,
            bindings=(), causal_prefix_end=8)
        envelope = replace(envelopes[0], frame=frame, members=())
        grant = replace(frontier.grants[0], source_handle=envelope.source_handle,
                        evidence_digest=frame_evidence_digest(frame))
        projection = project_context((envelope,), task,
                                     replace(frontier, grants=(grant,)), policy)
        actual = motif_gate_features(self.params, projection, "frame:0", self.features,
                                     extents=self.extents)
        np.testing.assert_allclose(np.asarray(actual.vector128), .25 / 3)
        self.assertEqual(actual.requests, ())

    def test_overflow_retains_exact_type_id_vector_before_categorical_mean(self):
        identifiers = tuple(f"urn:type:{i:04d}" for i in range(512))
        features = _features(_snapshot(definitions=(("urn:concept:A", identifiers),)))
        ref = replace(self.ref, type_ids=identifiers)
        parameters = {**self.params, "features.type":
                      self.params["features.type"].at[0].add(2)}
        actual = motif_gate_features(
            parameters, _context_for(ref), "frame:0", features,
            extents=replace(self.extents, factor_map_digest=features.digest))
        table, rows = np.asarray(parameters["features.type"]), dict(features.type_map)
        values = []
        for identifier in identifiers:
            value = table[rows[identifier]].copy()
            if rows[identifier] == 0:
                data = b"".join(hashlib.sha256(
                    f"bamf.factor.v2|type|{identifier}|{block}".encode()).digest()
                    for block in range(4))
                value += ((np.frombuffer(data, np.uint8) / 127.5 - 1)
                          / np.sqrt(128)).astype(np.float32)
            values.append(value)
        np.testing.assert_allclose(np.asarray(actual.vector128),
                                   (np.mean(values, axis=0) + 1.5 + .25) / 3,
                                   rtol=1e-6, atol=1e-7)
