"""A09.2 typed prerequisite closure and legal disposition tests."""
from dataclasses import replace
import hashlib
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.atlas_frontier_closure import (
    ClosureStatus, resolve_frontier_closure,
)
from bilqis_mlx.factory.atlas_frontier_contracts import PrerequisiteEdge
from bilqis_mlx.factory.skos_curriculum import FamilyObligation
from bilqis_mlx.factory.tests.curriculum.frontier.test_atlas_frontier_events import (
    _snapshot,
)


def _rehash(snapshot, **changes):
    draft = replace(snapshot, snapshot_sha256="0" * 64, **changes)
    return replace(draft, snapshot_sha256=draft.expected_digest())


def _row(semantic_id, family="positive_identity", *, implemented=True):
    return FamilyObligation(
        semantic_id, family, hashlib.sha256(f"{semantic_id}:{family}".encode()).hexdigest(),
        "ADMITTED" if implemented else "IMPLEMENTATION_UNCOVERED",
        "SOURCE_ADMITTED" if implemented else "FAMILY_CONSTRUCTOR_CHECKER_NOT_BOUND")


def _three_node_snapshot():
    base = _snapshot()
    rows = (_row("urn:one", implemented=False), _row("urn:two"), _row("urn:three"))
    return _rehash(
        base,
        source_eligible_concept_ids=("urn:one", "urn:three", "urn:two"),
        coverage_rows=tuple(sorted(rows, key=lambda item: (item.semantic_id, item.family_id))),
        prerequisite_edges=(PrerequisiteEdge("urn:two", "urn:one", "a" * 64),))


class AtlasFrontierClosureTests(unittest.TestCase):
    def test_true_dependency_blocks_but_unrelated_ready_work_survives(self):
        closure = resolve_frontier_closure(_three_node_snapshot())
        by_id = {(item.semantic_id, item.family_id): item for item in closure.candidates}
        self.assertEqual(
            by_id[("urn:one", "positive_identity")].status,
            ClosureStatus.IMPLEMENTATION_UNCOVERED)
        blocked = by_id[("urn:two", "positive_identity")]
        self.assertEqual(blocked.status, ClosureStatus.IMPLEMENTATION_UNCOVERED)
        self.assertEqual(blocked.reasons[-1].dependency_id, "urn:one")
        self.assertEqual(
            by_id[("urn:three", "positive_identity")].status, ClosureStatus.READY)
        self.assertLess(
            closure.constituent_order.index("urn:one"),
            closure.constituent_order.index("urn:two"))

    def test_learning_debt_blocks_only_its_dependent_branch(self):
        base = _three_node_snapshot()
        rows = tuple(replace(row, implementation_status="ADMITTED")
                     for row in base.coverage_rows)
        snapshot = _rehash(
            base, coverage_rows=rows, retained_mastery_debt=("urn:one",),
            retained_debt_source_sha256="d" * 64)
        closure = resolve_frontier_closure(snapshot)
        by_id = {item.semantic_id: item for item in closure.candidates}
        self.assertEqual(by_id["urn:one"].status, ClosureStatus.WAITING_FOR_EVIDENCE)
        self.assertEqual(by_id["urn:two"].status, ClosureStatus.WAITING_FOR_EVIDENCE)
        self.assertEqual(by_id["urn:three"].status, ClosureStatus.READY)

    def test_source_hold_and_implementation_debt_remain_distinct(self):
        closure = resolve_frontier_closure(_snapshot())
        self.assertEqual(closure.source_holds[0].reason_code, "RIGHTS_MISSING")
        self.assertEqual(closure.source_holds[0].owner, "source:owner")
        self.assertEqual(closure.source_holds[0].status, ClosureStatus.SOURCE_HELD)
        self.assertTrue(all(
            item.status is ClosureStatus.IMPLEMENTATION_UNCOVERED
            for item in closure.candidates))

    def test_direct_implementation_debt_is_not_downgraded_by_evidence_wait(self):
        base = _three_node_snapshot()
        rows = tuple(
            replace(row, implementation_status="ADMITTED")
            if row.semantic_id == "urn:one" else
            replace(row, implementation_status="IMPLEMENTATION_UNCOVERED")
            if row.semantic_id == "urn:two" else row
            for row in base.coverage_rows)
        snapshot = _rehash(
            base, coverage_rows=rows, retained_mastery_debt=("urn:one",),
            retained_debt_source_sha256="d" * 64)
        closure = resolve_frontier_closure(snapshot)
        by_id = {item.semantic_id: item for item in closure.candidates}
        self.assertEqual(by_id["urn:one"].status, ClosureStatus.WAITING_FOR_EVIDENCE)
        self.assertEqual(by_id["urn:two"].status, ClosureStatus.IMPLEMENTATION_UNCOVERED)

    def test_grade_labels_do_not_change_rules_or_closure_outcomes(self):
        base = _three_node_snapshot()
        first = resolve_frontier_closure(_rehash(base, grade_labels=("A",)))
        second = resolve_frontier_closure(_rehash(base, grade_labels=("Z",)))
        self.assertEqual(first.rule_families, second.rule_families)
        self.assertEqual(first.constituent_order, second.constituent_order)
        self.assertEqual(first.candidates, second.candidates)
        self.assertEqual(first.source_holds, second.source_holds)

    def test_distinct_family_rules_are_selected_by_family_not_grade(self):
        base = _snapshot()
        rows = (
            _row("urn:one", "positive_identity"),
            _row("urn:one", "numeric_composition"),
            _row("urn:two", "positive_identity"),
        )
        snapshot = _rehash(
            base, required_source_family_ids=("numeric_composition", "positive_identity"),
            coverage_rows=tuple(sorted(
                rows, key=lambda item: (item.semantic_id, item.family_id))))
        closure = resolve_frontier_closure(snapshot)
        one = tuple(item for item in closure.candidates if item.semantic_id == "urn:one")
        self.assertEqual(tuple(item.family_id for item in one),
                         ("numeric_composition", "positive_identity"))
        self.assertTrue(all(item.status is ClosureStatus.READY for item in one))

    def test_unknown_or_cyclic_prerequisite_fails_closed(self):
        base = _three_node_snapshot()
        unknown = _rehash(
            base, prerequisite_edges=(
                PrerequisiteEdge("urn:two", "urn:missing", "b" * 64),))
        with self.assertRaises(BilqisError):
            resolve_frontier_closure(unknown)
        cycle = _rehash(
            base, prerequisite_edges=tuple(sorted((
                PrerequisiteEdge("urn:two", "urn:one", "a" * 64),
                PrerequisiteEdge("urn:one", "urn:two", "b" * 64)))))
        with self.assertRaises(BilqisError):
            resolve_frontier_closure(cycle)

    def test_no_edge_means_no_dependency_is_invented(self):
        base = _three_node_snapshot()
        snapshot = _rehash(base, prerequisite_edges=())
        closure = resolve_frontier_closure(snapshot)
        by_id = {item.semantic_id: item for item in closure.candidates}
        self.assertEqual(by_id["urn:two"].status, ClosureStatus.READY)
        self.assertEqual(by_id["urn:two"].prerequisites, ())


if __name__ == "__main__":
    unittest.main()
