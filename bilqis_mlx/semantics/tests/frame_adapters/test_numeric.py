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


class NumericTests(FrameAdapterTestCase):
    def test_actual_numeric_row_uses_native_numeric_ast_and_recursive_child_frames(self):
        adapter = self.registry.require(
            "bilqis_mlx.numeric_curriculum.draw_numeric", C_ORACLE)
        row = next(
            item for item in draw_numeric_rows(
                self.numeric_graph, seed=19, maximum=3)
            if item["capability"] == "C.ADD")
        tree = self._bind(adapter, row, self.numeric_graph)
        self.assertIsInstance(tree.root, FrameInstance)
        self.assertEqual(
            tree.root.frame_schema_id,
            "frame:legacy:school.op.ADD",
        )
        self.assertIn("school.op.COUNT", row["record"]["symbols"])
        self.assertGreater(len(tuple(_walk(tree))), 1)
        self.assertEqual(validate_frame_tree(tree), tree)


    def test_all_actual_finite_numeric_families_bind_under_owner_contract_rules(self):
        adapter = self.registry.require(
            "bilqis_mlx.numeric_curriculum.draw_numeric", C_ORACLE)
        for capability in (
                "C.COUNT", "C.NUMBER", "C.SUCCESSOR", "C.ADD",
                "C.SUB", "C.MUL", "C.DIV"):
            with self.subTest(capability=capability):
                row = draw_numeric_constructions(
                    PLANS,
                    self.numeric_graph,
                    seed=29,
                    maximum=3,
                    each=3,
                    capability=capability,
                )[0]
                tree = self._bind(adapter, row, self.numeric_graph)
                self.assertEqual(validate_frame_tree(tree), tree)
                self.assertEqual(
                    tree.root.source_instance_id,
                    row.get("source_id") or row["id"],
                )
