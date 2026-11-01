"""A06 x A13 formal-source type composition across current A/B/C families."""
from __future__ import annotations

import mlx.core as mx

from bilqis_mlx.learning.frame_embeddings import motif_gate_features
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
)
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextPolicy, SourceFrontier, TaskScope,
)
from bilqis_mlx.semantics.frame_adapters import public_formal_context
from bilqis_mlx.semantics.frame_schema import FrameInstance
from bilqis_mlx.semantics.tests.frame_adapters.helpers import (
    A_ORACLE, B_ORACLE, C_ORACLE, SOURCE_ROOT, FrameAdapterTestCase,
    draw_numeric_rows,
)


class PublicFormalTypeCompositionTests(FrameAdapterTestCase):
    def _cases(self):
        a = self.registry.require(
            "bilqis_mlx.grade_a_probe.make_record", A_ORACLE)
        b = self.registry.require(
            "bilqis_mlx.live_grade_b.draw_connectives", B_ORACLE)
        c = self.registry.require(
            "bilqis_mlx.numeric_curriculum.draw_numeric", C_ORACLE)
        a_row = a.draw(
            source_root=SOURCE_ROOT, graph=self.micro_graph, course=None,
            capability="A.IDENTITY", seed=31, each=2,
        )[0]
        b_row = b.draw(
            source_root=SOURCE_ROOT, graph=self.micro_graph, course=None,
            capability="B.AND", seed=31, each=4,
        )[0]
        c_row = next(
            row for row in draw_numeric_rows(self.numeric_graph, seed=19, maximum=3)
            if row["capability"] == "C.ADD"
        )
        return (
            (a, a_row, self.micro_graph, 31, 2, None),
            (b, b_row, self.micro_graph, 31, 4, None),
            (c, c_row, self.numeric_graph, 19, 12,
             {"numbers": ("0", "1", "2", "3")}),
        )

    def test_a_b_c_public_formal_types_compose_without_retyping_a06(self):
        task = TaskScope(
            "synthetic:student", "synthetic:tenant", "TRAINING",
            self.snapshot.release_sha256, "synthetic:region", "synthetic:public",
            observed_frontier=3, effective_time=5, causal_prefix_end=30,
        )
        policy = ContextPolicy(
            "synthetic:policy", 1, 1,
            ("TRAINING",), (PUBLIC_FORMAL,), ("synthetic:region",),
            ("synthetic:public",), (PUBLIC_FORMAL,),
            ((PUBLIC_FORMAL, PUBLIC_FORMAL),),
            tuple((PUBLIC_FORMAL,) * count for count in range(3, 25)),
        )
        frontier = SourceFrontier(1, 1, ())

        for adapter, row, graph, seed, each, profile in self._cases():
            with self.subTest(adapter=adapter.descriptor.adapter_id):
                projection, _admitted = public_formal_context(
                    adapter, row, self.snapshot, source_root=SOURCE_ROOT,
                    graph=graph, task_scope=task, source_frontier=frontier,
                    policy=policy, source_seed=seed, source_each=each,
                    source_profile_parameters=profile,
                )
                framed = tuple(
                    item for item in projection.envelopes
                    if type(item.frame) is FrameInstance
                )
                self.assertTrue(framed)
                envelope = framed[0]
                schema_ids = tuple(sorted({
                    item.frame.frame_schema_id for item in framed
                }))
                roles = tuple(sorted({
                    binding.role_id for item in framed
                    for binding in item.frame.bindings
                }))
                features = build_feature_manifest(
                    self.snapshot,
                    FeatureSchema(
                        roles, schema_ids,
                        source_bindings=tuple(
                            (schema_id, adapter.descriptor.adapter_id)
                            for schema_id in schema_ids
                        ),
                    ),
                )
                extents = GenerationExtents(
                    1, 1, self.snapshot.release_sha256,
                    "b" * 64, features.digest,
                )
                parameters = {
                    item.name: mx.zeros(item.shape, dtype=mx.float32)
                    for item in expected_bamf_shapes(ModelTopologySpecV2(), extents)
                    if item.name.startswith("features.")
                }

                actual = motif_gate_features(
                    parameters, projection, envelope.frame_handle, features,
                    extents=extents,
                )

                self.assertTrue(bool(mx.all(mx.isfinite(actual.vector128))))
                self.assertTrue(actual.requests)
                self.assertTrue(all(
                    next(item for item in features.concepts
                         if item.semantic_id == request.concept.semantic_id).source_status
                    == "ADMITTED_FORMAL_ABI_UNTYPED"
                    for request in actual.requests
                    if hasattr(request, "concept")
                ))
                self.assertTrue(all(
                    request.concept.type_ids
                    for request in actual.requests
                    if hasattr(request, "concept")
                ))


if __name__ == "__main__":
    import unittest
    unittest.main()
