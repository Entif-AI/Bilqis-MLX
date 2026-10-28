from __future__ import annotations

from dataclasses import replace
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
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.live_grade_c import draw as draw_numeric_rows, registry_graph
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


ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "vendor/legacy-v16"
REGISTRY_PATH = ROOT / "bilqis_mlx/semantics/copular_registry_v1.json"
RELEASE = "7" * 64


def _snapshot() -> FrozenAtlasSnapshot:
    rows = json.loads(REGISTRY_PATH.read_text())["rows"][1:]
    entries = tuple(AbiEntry(
        index=index,
        bank=0,
        row=index,
        semantic_id=row[2],
        symbol=row[1],
        source="PRIOR_ACCEPTED_NATIVE_REGISTRY",
        active=True,
        teaching_candidate=True,
        reason="PRIOR_ACCEPTED_ABI",
    ) for index, row in enumerate(rows))
    return FrozenAtlasSnapshot(
        schema="bilqis.semantic-atlas-snapshot/v1",
        bundle_id="a" * 64,
        release_sha256=RELEASE,
        source_bundle_id="b" * 64,
        canonical_rdf_sha256="c" * 64,
        coverage_sha256="d" * 64,
        source_rows_sha256="e" * 64,
        conformance_sha256="f" * 64,
        prior_abi_sha256="0" * 64,
        shape_policy_sha256="1" * 64,
        active_set_sha256="2" * 64,
        counts=AtlasCounts(1, 1, 1, len(entries), 1, len(entries), 0, 0, 0, 0),
        formal_domain_bindings=(),
        abi_entries=entries,
        concepts=(),
        relations=(),
        withheld_rows=(),
        semantic_lookup=tuple(sorted((entry.semantic_id, entry.index) for entry in entries)),
        concept_lookup=(),
    )


def _walk(tree: FrameTree):
    yield tree
    for child in tree.children:
        yield from _walk(child)


class ReleasedFrameAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, _, cls.micro_graph, _, _ = read_sources(SOURCE_ROOT)
        cls.numeric_graph = registry_graph()
        cls.registry = live_source_registry()
        cls.snapshot = _snapshot()

    def _bind(self, adapter, row, graph, *, start=10, end=30):
        return bind_registered_source_row(
            adapter,
            row,
            self.snapshot,
            source_root=SOURCE_ROOT,
            graph=graph,
            source_span=SourceSpan(start, end),
            causal_prefix_end=end,
        )

    def test_released_adapter_ids_are_the_actual_current_source_registry_ids(self):
        expected = {
            MICRO_PREDICATE_ADAPTER,
            BOOLEAN_CONNECTIVE_ADAPTER,
            BOOLEAN_COMPOSITE_ADAPTER,
            BOOLEAN_IDENTIFICATION_ADAPTER,
            FINITE_NUMERIC_ADAPTER,
        }
        actual = {
            adapter.descriptor.adapter_id
            for adapter in self.registry._by_generator.values()
            if adapter.descriptor.adapter_id in expected
        }
        self.assertEqual(set(released_frame_adapter_ids()), expected)
        self.assertEqual(actual, expected)

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
        self.assertGreater(len(tuple(_walk(tree))), 1)
        self.assertEqual(validate_frame_tree(tree), tree)

    def test_registered_adapter_error_carries_span_role_and_adapter_identity(self):
        adapter = self.registry.require(
            "bilqis_mlx.live_grade_b.draw_connectives", B_ORACLE)
        row = adapter.draw(
            source_root=SOURCE_ROOT,
            graph=self.micro_graph,
            course=None,
            capability="B.AND",
            seed=31,
            each=4,
        )[0]
        forged = {**row, "gold": "INVALID"}
        with self.assertRaises(BilqisError) as caught:
            self._bind(adapter, forged, self.micro_graph, start=44, end=61)
        self.assertEqual(
            caught.exception.code,
            "SEMANTIC_FRAME.ADAPTER.INVALID_SOURCE",
        )
        self.assertEqual(caught.exception.context["adapter_id"],
                         BOOLEAN_CONNECTIVE_ADAPTER)
        self.assertEqual(caught.exception.context["role_id"], "<source-row>")
        self.assertEqual(
            (caught.exception.context["span_start"], caught.exception.context["span_end"]),
            (44, 61),
        )

    def test_child_reference_must_match_actual_subtree_record(self):
        adapter = self.registry.require(
            "bilqis_mlx.live_grade_b.draw_connectives", B_ORACLE)
        row = adapter.draw(
            source_root=SOURCE_ROOT,
            graph=self.micro_graph,
            course=None,
            capability="B.AND",
            seed=31,
            each=4,
        )[0]
        tree = self._bind(adapter, row, self.micro_graph)
        self.assertTrue(tree.children)
        forged_tree = FrameTree(tree.root, tree.children[1:])
        with self.assertRaises(BilqisError) as caught:
            validate_frame_tree(forged_tree)
        self.assertEqual(caught.exception.code, "SEMANTIC_FRAME.BINDING.INVALID")
        self.assertEqual(caught.exception.context["role_id"], "<child-frame>")


if __name__ == "__main__":
    unittest.main()
