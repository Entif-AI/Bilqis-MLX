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


ROOT = Path(__file__).resolve().parents[4]
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


class FrameAdapterTestCase(unittest.TestCase):
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
