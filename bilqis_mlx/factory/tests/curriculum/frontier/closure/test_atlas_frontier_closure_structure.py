"""A09.2 closure denominator, topology, and grade-neutral behavior."""
from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.atlas_frontier_closure import ClosureStatus
from bilqis_mlx.factory.atlas_frontier_contracts import PrerequisiteEdge
from bilqis_mlx.factory.tests.curriculum.frontier.atlas_frontier_closure_fixtures import (
    census_for,
    rehash,
    resolve,
    row,
    three_node_snapshot,
)
from bilqis_mlx.factory.tests.curriculum.frontier.test_atlas_frontier_events import (
    _snapshot,
)


class AtlasFrontierClosureStructureTests(unittest.TestCase):
    def test_source_hold_and_implementation_debt_remain_distinct(self):
        closure = resolve(_snapshot())
        self.assertEqual(closure.source_holds[0].reason_code, "RIGHTS_MISSING")
        self.assertEqual(closure.source_holds[0].owner, "source:owner")
        self.assertEqual(closure.source_holds[0].status, ClosureStatus.SOURCE_HELD)
        self.assertTrue(all(
            item.status is ClosureStatus.IMPLEMENTATION_UNCOVERED
            for item in closure.candidates))

    def test_grade_labels_do_not_change_semantic_closure(self):
        base = three_node_snapshot()
        first = resolve(rehash(base, grade_labels=("A",)))
        second = resolve(rehash(base, grade_labels=("Z",)))
        self.assertEqual(first.rule_families, second.rule_families)
        self.assertEqual(first.constituent_order, second.constituent_order)
        self.assertEqual(first.candidates, second.candidates)
        self.assertEqual(first.source_holds, second.source_holds)

    def test_family_rules_dispatch_by_family_not_grade(self):
        base = _snapshot()
        rows = (
            row("urn:one", "positive_identity"),
            row("urn:one", "numeric_composition"),
            row("urn:two", "positive_identity"),
        )
        snapshot = rehash(
            base,
            required_source_family_ids=("numeric_composition", "positive_identity"),
            coverage_rows=tuple(sorted(
                rows, key=lambda item: (item.semantic_id, item.family_id))),
        )
        closure = resolve(snapshot)
        one = tuple(item for item in closure.candidates if item.semantic_id == "urn:one")
        self.assertEqual(
            tuple(item.family_id for item in one),
            ("numeric_composition", "positive_identity"),
        )
        self.assertTrue(all(item.status is ClosureStatus.READY for item in one))

    def test_unknown_or_cyclic_prerequisite_fails_closed(self):
        base = three_node_snapshot()
        unknown = rehash(
            base,
            prerequisite_edges=(
                PrerequisiteEdge("urn:two", "urn:missing", "b" * 64),),
        )
        with self.assertRaises(BilqisError):
            resolve(unknown)
        cycle = rehash(
            base,
            prerequisite_edges=tuple(sorted((
                PrerequisiteEdge("urn:two", "urn:one", "a" * 64),
                PrerequisiteEdge("urn:one", "urn:two", "b" * 64),
            ))),
        )
        with self.assertRaises(BilqisError):
            resolve(cycle)

    def test_no_edge_means_no_dependency_is_invented(self):
        snapshot = rehash(three_node_snapshot(), prerequisite_edges=())
        by_id = {item.semantic_id: item for item in resolve(snapshot).candidates}
        self.assertEqual(by_id["urn:two"].status, ClosureStatus.READY)
        self.assertEqual(by_id["urn:two"].prerequisites, ())

    def test_exact_semantic_family_denominator_cannot_drop_one_pair(self):
        base = three_node_snapshot()
        rows = tuple(sorted((
            row("urn:one", "positive_identity"),
            row("urn:one", "numeric_composition"),
            row("urn:two", "positive_identity"),
            row("urn:two", "numeric_composition"),
            row("urn:three", "positive_identity"),
        ), key=lambda item: (item.semantic_id, item.family_id)))
        complete = rehash(
            base,
            required_source_family_ids=("numeric_composition", "positive_identity"),
            coverage_rows=rows,
        )
        census = census_for(complete)
        incomplete = rehash(
            complete,
            coverage_rows=tuple(
                item for item in complete.coverage_rows
                if (item.semantic_id, item.family_id)
                != ("urn:one", "numeric_composition")),
        )
        with self.assertRaises(BilqisError):
            resolve(incomplete, census=census)

    def test_unknown_implementation_status_fails_closed(self):
        base = three_node_snapshot()
        rows = tuple(
            replace(item, implementation_status="NOT_A_REAL_STATE")
            if item.semantic_id == "urn:one" else item
            for item in base.coverage_rows
        )
        with self.assertRaises(BilqisError):
            resolve(rehash(base, coverage_rows=rows))
