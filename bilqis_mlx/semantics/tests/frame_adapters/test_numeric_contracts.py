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


class NumericContractsTests(FrameAdapterTestCase):
    def test_numeric_source_contract_drift_rejects_actual_c_add_row(self):
        adapter = self.registry.require(
            "bilqis_mlx.numeric_curriculum.draw_numeric", C_ORACLE)
        row = next(
            item for item in draw_numeric_rows(
                self.numeric_graph, seed=19, maximum=3)
            if item["capability"] == "C.ADD")
        tampered_graph = deepcopy(self.numeric_graph)
        original = tampered_graph["row_contract_sha256"]["school.op.ADD"]
        replacement = "9" * 64 if original != "9" * 64 else "8" * 64
        tampered_graph["row_contract_sha256"]["school.op.ADD"] = replacement
        with self.assertRaises(BilqisError) as caught:
            self._bind(adapter, row, tampered_graph)
        self.assertEqual(
            caught.exception.code,
            "SEMANTIC_FRAME.ADAPTER.INVALID_SOURCE",
        )
        self.assertEqual(
            caught.exception.context["reason"],
            "FRAME_NUMERIC_CONTRACT_DRIFT",
        )
        self.assertEqual(caught.exception.context["role_id"], "<operator>")


    def test_nested_graph_governed_add_contract_drift_rejects_actual_contrast(self):
        adapter = self.registry.require(
            "bilqis_mlx.numeric_curriculum.draw_numeric", C_ORACLE)
        rows = draw_numeric_constructions(
            PLANS,
            self.numeric_graph,
            seed=23,
            maximum=3,
            each=3,
            capability="C.ADD",
        )
        row = next(
            item for item in rows
            if item["answer_kind"] == "binary"
            and "school.op.ADD" in item["record"]["symbols"])
        self.assertIn("school.op.EQ", row["record"]["symbols"])
        tampered_graph = deepcopy(self.numeric_graph)
        original = tampered_graph["row_contract_sha256"]["school.op.ADD"]
        replacement = "0" * 64 if original != "0" * 64 else "8" * 64
        tampered_graph["row_contract_sha256"]["school.op.ADD"] = replacement
        with self.assertRaises(BilqisError) as caught:
            self._bind(adapter, row, tampered_graph)
        self.assertEqual(
            caught.exception.code,
            "SEMANTIC_FRAME.ADAPTER.INVALID_SOURCE",
        )
        self.assertEqual(
            caught.exception.context["reason"],
            "FRAME_NUMERIC_CONTRACT_DRIFT",
        )
        self.assertEqual(caught.exception.context["role_id"], "<operator>")


    def test_append_only_numeric_graph_cannot_rewrite_source_meaning_or_digest(self):
        adapter = self.registry.require(
            "bilqis_mlx.numeric_curriculum.draw_numeric", C_ORACLE)
        row = draw_numeric_constructions(
            PLANS, self.numeric_graph, seed=29, maximum=3,
            each=3, capability="C.COUNT",
        )[0]
        symbol = "school.op.COUNT"
        for tamper in ("wrong_digest", "replaced_meaning"):
            with self.subTest(tamper=tamper):
                graph = deepcopy(self.numeric_graph)
                if tamper == "wrong_digest":
                    graph["row_contract_sha256"][symbol] = "0" * 64
                    expected = "FRAME_NUMERIC_CONTRACT_DRIFT"
                else:
                    node = graph["nodes"][graph["tokens"].index(symbol)]
                    node["meaning"] = node["meaning"] + " changed"
                    graph["row_contract_sha256"][symbol] = digest(node)
                    expected = "FRAME_NUMERIC_APPEND_ONLY_NODE_DRIFT"
                with self.assertRaises(BilqisError) as caught:
                    self._bind(adapter, row, graph)
                self.assertEqual(
                    caught.exception.code, "SEMANTIC_FRAME.ADAPTER.INVALID_SOURCE")
                self.assertEqual(caught.exception.context["reason"], expected)
                self.assertEqual(caught.exception.context["role_id"], "<operator>")
