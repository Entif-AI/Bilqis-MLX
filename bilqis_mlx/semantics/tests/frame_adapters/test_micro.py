from __future__ import annotations

from dataclasses import replace
from copy import deepcopy
import json
from pathlib import Path
import unittest

from bilqis_mlx.boolean_composite import (
    CAPABILITY as BOOLEAN_COMPOSITE_CAPABILITY,
    GENERATOR as BOOLEAN_COMPOSITE_GENERATOR,
    ORACLE as BOOLEAN_COMPOSITE_ORACLE,
)
from bilqis_mlx.boolean_identification import (
    CAPABILITY as BOOLEAN_IDENTIFICATION_CAPABILITY,
    GENERATOR as BOOLEAN_IDENTIFICATION_GENERATOR,
    ORACLE as BOOLEAN_IDENTIFICATION_ORACLE,
)
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.generated_assessment import digest
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.live_grade_c import PLANS, draw as draw_numeric_rows, registry_graph
from bilqis_mlx.numeric_curriculum import draw_numeric as draw_numeric_constructions
from bilqis_mlx.semantics.atlas_projection import AbiEntry, AtlasCounts, FrozenAtlasSnapshot
from bilqis_mlx.semantics.frame_adapters import (
    BOOLEAN_COMPOSITE_ADAPTER,
    BOOLEAN_CONNECTIVE_ADAPTER,
    BOOLEAN_IDENTIFICATION_ADAPTER,
    FINITE_NUMERIC_ADAPTER,
    MICRO_PREDICATE_ADAPTER,
    bind_registered_source_row,
    released_frame_adapter_ids,
)
from bilqis_mlx.semantics.frame_schema import (
    AtomicFrame,
    FrameInstance,
    FrameTree,
    SourceSpan,
    validate_frame_tree,
)
from bilqis_mlx.source_adapters.school import (
    A_ORACLE,
    B_ORACLE,
    C_ORACLE,
    live_source_registry,
)


from .helpers import FrameAdapterTestCase, ROOT, SOURCE_ROOT, RELEASE, REGISTRY_PATH, _snapshot, _walk


class MicroTests(FrameAdapterTestCase):
    def test_actual_micro_predicate_rows_bind_all_six_source_families(self):
        adapter = self.registry.require(
            "bilqis_mlx.grade_a_probe.make_record", A_ORACLE)
        for capability in (
                "A.IDENTITY", "A.PARENT", "A.LINK",
                "A.MEMBER", "A.EDGE", "A.MAPS"):
            with self.subTest(capability=capability):
                row = adapter.draw(
                    source_root=SOURCE_ROOT,
                    graph=self.micro_graph,
                    course=None,
                    capability=capability,
                    seed=31,
                    each=2,
                )[0]
                tree = self._bind(adapter, row, self.micro_graph)
                self.assertIsInstance(tree.root, FrameInstance)
                self.assertEqual(tree.root.source_instance_id, row["id"])
                self.assertTrue(tree.root.frame_schema_id.startswith("frame:legacy:"))
                self.assertEqual(validate_frame_tree(tree), tree)


    def test_actual_boolean_direct_and_composite_rows_bind_nested_source_ast(self):
        direct = self.registry.require(
            "bilqis_mlx.live_grade_b.draw_connectives", B_ORACLE)
        direct_row = direct.draw(
            source_root=SOURCE_ROOT,
            graph=self.micro_graph,
            course=None,
            capability="B.AND",
            seed=31,
            each=4,
        )[0]
        direct_tree = self._bind(direct, direct_row, self.micro_graph)
        self.assertIsInstance(direct_tree.root, FrameInstance)
        self.assertGreater(len(tuple(_walk(direct_tree))), 1)
        self.assertEqual(direct_tree.root.source_instance_id, direct_row["source_id"])

        composite = self.registry.require(
            BOOLEAN_COMPOSITE_GENERATOR, BOOLEAN_COMPOSITE_ORACLE)
        composite_row = composite.draw(
            source_root=SOURCE_ROOT,
            graph=self.micro_graph,
            course=None,
            capability=BOOLEAN_COMPOSITE_CAPABILITY,
            seed=37,
            each=4,
        )[0]
        composite_tree = self._bind(composite, composite_row, self.micro_graph)
        self.assertIsInstance(composite_tree.root, FrameInstance)
        self.assertGreater(len(tuple(_walk(composite_tree))), 1)


    def test_inverse_boolean_identification_preserves_input_atomically_without_target_leak(self):
        adapter = self.registry.require(
            BOOLEAN_IDENTIFICATION_GENERATOR, BOOLEAN_IDENTIFICATION_ORACLE)
        row = adapter.draw(
            source_root=SOURCE_ROOT,
            graph=self.micro_graph,
            course=None,
            capability=BOOLEAN_IDENTIFICATION_CAPABILITY,
            seed=41,
            each=4,
        )[0]
        self.assertNotIn("root", row["record"])
        tree = self._bind(adapter, row, self.micro_graph)
        self.assertIsInstance(tree.root, AtomicFrame)
        self.assertEqual(tree.root.source_data, row["record"])
        self.assertNotIn("root", tree.root.source_data)
        self.assertNotIn("gold", tree.root.source_data)
