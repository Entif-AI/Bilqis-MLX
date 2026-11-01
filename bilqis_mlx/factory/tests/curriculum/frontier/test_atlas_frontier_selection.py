"""A09.3 pure bounded semantic selection, before JIT translation."""
from dataclasses import replace
import hashlib
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.atlas_frontier_closure import (
    CandidateClosure,
    ClosureReason,
    ClosureStatus,
    FrontierClosure,
    SourceHold,
)
from bilqis_mlx.factory.atlas_frontier_contracts import PlannerBudget, PrerequisiteEdge
from bilqis_mlx.factory.atlas_frontier_selection import (
    select_frontier_delta,
)
from bilqis_mlx.factory.atlas_frontier_selection_validation import (
    TargetDeltaProjection,
    catalog_digest,
    obligation_signature,
)
from bilqis_mlx.factory.skos_curriculum import IMPLEMENTATION_UNCOVERED, PROGRAM_BOUND
from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.factory.executable_release import compile_executable_factory_release
from bilqis_mlx.factory.execution import CurriculumProfile
from bilqis_mlx.factory.tests.curriculum.frontier.atlas_frontier_closure_fixtures import (
    rehash,
    three_node_snapshot,
)
from bilqis_mlx.factory.tests.test_executable_release import _answers
from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_course, _synthetic_registry


def _release():
    curriculum, bindings = from_legacy_course(_synthetic_course(6))
    return compile_executable_factory_release(
        curriculum, bindings, CurriculumProfile.full(), _synthetic_registry(), _answers(),
        source_root=None,
        graph={
            "tokens": ["fixture.padding", "cogal.value.false", "cogal.value.true"],
        },
        verification_seed=20261019,
    )


def _snapshot(release, *, cursor=0, budget=None, prerequisite_edges=None):
    base = three_node_snapshot()
    semantic_ids = ("z.op.0", "z.op.1", "z.op.2")
    rows = tuple(sorted((
        replace(base.coverage_rows[0], semantic_id=semantic_ids[0],
                implementation_status=PROGRAM_BOUND),
        replace(base.coverage_rows[1], semantic_id=semantic_ids[1],
                implementation_status=PROGRAM_BOUND),
        replace(base.coverage_rows[2], semantic_id=semantic_ids[2],
                implementation_status=PROGRAM_BOUND),
    ), key=lambda item: (item.semantic_id, item.family_id)))
    return rehash(
        base,
        source_eligible_concept_ids=semantic_ids,
        coverage_rows=rows,
        prerequisite_edges=(
            (PrerequisiteEdge("z.op.1", "z.op.0", "a" * 64),)
            if prerequisite_edges is None else prerequisite_edges),
        admitted_factory_release_sha256=release.release_sha256,
        admission_receipt_sha256="7" * 64,
        cursor=cursor,
        budget=budget or PlannerBudget(9, 16, 1000),
    )


def _candidate(snapshot, identity, *, family_id="positive_identity", prerequisites=None,
               status=ClosureStatus.READY, reasons=()):
    row = next(item for item in snapshot.coverage_rows
               if item.semantic_id == identity and item.family_id == family_id)
    if prerequisites is None:
        prerequisites = tuple(sorted(
            edge.prerequisite_semantic_id for edge in snapshot.prerequisite_edges
            if edge.semantic_id == identity))
    return CandidateClosure(
        identity,
        family_id,
        row.source_evidence_sha256,
        status,
        prerequisites,
        reasons,
    )


def _closure(snapshot, candidates, order=None):
    if order is None:
        graph = {identity: [] for identity in snapshot.source_eligible_concept_ids}
        for edge in snapshot.prerequisite_edges:
            graph[edge.semantic_id].append(edge.prerequisite_semantic_id)
        seen, active, ordered = set(), set(), []
        def visit(identity):
            if identity in seen:
                return
            if identity in active:
                self.fail("test fixture cycle")
            active.add(identity)
            for prerequisite in sorted(graph[identity]):
                visit(prerequisite)
            active.remove(identity)
            seen.add(identity)
            ordered.append(identity)
        for identity in sorted(graph):
            visit(identity)
        order = tuple(ordered)
    provisional = FrontierClosure(
        snapshot.snapshot_sha256,
        "e" * 64,
        ("positive_identity",),
        order,
        tuple(sorted(candidates)),
        tuple(sorted(SourceHold(
            f"{row.domain}/{row.table}/{row.key}", row.reason_code, row.owner)
            for row in snapshot.source_held_rows)),
        "0" * 64,
    )
    return replace(provisional, closure_sha256=provisional.expected_digest())


def _options(snapshot, release, closure, *, capabilities=None, identities=None):
    capabilities = capabilities or {
        "z.op.0": ("Z.N0",), "z.op.1": ("Z.N1",), "z.op.2": ("Z.N2",),
    }
    identities = identities or {
        "z.op.0": ("z.op.0",), "z.op.1": ("z.op.1",), "z.op.2": ("z.op.2",),
    }
    result = []
    for identity in sorted(capabilities):
        rows = tuple(sorted(
            item for item in closure.candidates
            if item.semantic_id == identity and item.status is ClosureStatus.READY))
        if not rows or len(rows) != sum(
                item.semantic_id == identity for item in closure.candidates):
            continue
        provisional = TargetDeltaProjection(
            semantic_id=identity,
            obligation_signature=obligation_signature(rows),
            current_release_sha256=release.release_sha256,
            current_semantic_catalog_sha256=release.semantic_catalog_sha256,
            added_capability_ids=capabilities[identity],
            introduced_semantic_ids=identities[identity],
            projected_semantic_catalog_sha256=catalog_digest(
                release.semantic_catalog + identities[identity]),
            projection_sha256="0" * 64,
        )
        result.append(replace(
            provisional, projection_sha256=provisional.expected_digest()))
    return tuple(result)


class AtlasFrontierSelectionTests(unittest.TestCase):
    def test_slope_then_marginal_unlocks_then_cursor_then_semantic_id(self):
        release = _release()
        snapshot = _snapshot(release, prerequisite_edges=(
            PrerequisiteEdge("z.op.1", "z.op.2", "a" * 64),))
        blocked = ClosureReason(
            "PREREQUISITE_WAITING_FOR_EVIDENCE", "factory:prerequisite", "z.op.2")
        closure = _closure(snapshot, (
            _candidate(snapshot, "z.op.0"),
            _candidate(snapshot, "z.op.1", status=ClosureStatus.WAITING_FOR_EVIDENCE,
                       prerequisites=("z.op.2",), reasons=(blocked,)),
            _candidate(snapshot, "z.op.2"),
        ))
        selection = select_frontier_delta(
            snapshot, closure, release, _options(snapshot, release, closure))
        self.assertEqual(selection.selected_semantic_id, "z.op.2")
        self.assertEqual(selection.downstream_unlocks, 1)
        self.assertEqual(selection.prerequisite_slope, 0)

    def test_cursor_is_read_only_oldest_unvisited_tie_breaker(self):
        release = _release()
        snapshot = _snapshot(release, cursor=1, prerequisite_edges=())
        closure = _closure(snapshot, tuple(
            _candidate(snapshot, identity) for identity in snapshot.source_eligible_concept_ids))
        selection = select_frontier_delta(
            snapshot, closure, release, _options(snapshot, release, closure))
        self.assertEqual(selection.selected_semantic_id, "z.op.1")
        self.assertEqual(selection.cursor, 1)
        self.assertEqual(snapshot.cursor, 1)

    def test_all_required_families_for_semantic_are_indivisible(self):
        release = _release()
        snapshot = _snapshot(release, budget=PlannerBudget(1, 16, 1000))
        snapshot = rehash(snapshot, coverage_rows=tuple(sorted(
            snapshot.coverage_rows + (replace(
                snapshot.coverage_rows[0], family_id="numeric_composition",
                source_evidence_sha256="b" * 64,
                implementation_status=IMPLEMENTATION_UNCOVERED),),
            key=lambda item: (item.semantic_id, item.family_id))),
            required_source_family_ids=("numeric_composition", "positive_identity"))
        blocked = ClosureReason(
            "FAMILY_IMPLEMENTATION_UNCOVERED", "family:numeric_composition")
        inherited = ClosureReason(
            "PREREQUISITE_IMPLEMENTATION_UNCOVERED", "factory:prerequisite", "z.op.0")
        closure = _closure(snapshot, (
            _candidate(snapshot, "z.op.0"),
            _candidate(snapshot, "z.op.0", family_id="numeric_composition",
                       status=ClosureStatus.IMPLEMENTATION_UNCOVERED, reasons=(blocked,)),
            _candidate(snapshot, "z.op.1", status=ClosureStatus.IMPLEMENTATION_UNCOVERED,
                       reasons=(inherited,)),
            _candidate(snapshot, "z.op.2"),
        ))
        selection = select_frontier_delta(
            snapshot, closure, release, _options(snapshot, release, closure))
        self.assertNotEqual(selection.selected_semantic_id, "z.op.0")
        self.assertTrue(all(
            item.semantic_id != "z.op.0" for item in selection.selected_obligations))

    def test_identity_budget_counts_only_semantics_missing_from_current_catalog(self):
        release = _release()
        snapshot = _snapshot(release, budget=PlannerBudget(9, 1, 1000))
        closure = _closure(snapshot, (
            _candidate(snapshot, "z.op.0"),
            _candidate(snapshot, "z.op.1"),
            _candidate(snapshot, "z.op.2"),
        ))
        selection = select_frontier_delta(
            snapshot, closure, release, _options(snapshot, release, closure))
        self.assertLessEqual(len(selection.introduced_semantic_ids), 1)

    def test_candidate_signature_ignores_grade_and_policy_but_full_digest_does_not(self):
        release = _release()
        base = _snapshot(release)
        closure = _closure(base, tuple(
            _candidate(base, identity) for identity in base.source_eligible_concept_ids))
        first = select_frontier_delta(
            base, closure, release, _options(base, release, closure))
        relabeled = rehash(base, grade_labels=("Z",), policy_epoch=base.policy_epoch + 1)
        relabeled_closure = _closure(relabeled, tuple(
            _candidate(relabeled, identity) for identity in relabeled.source_eligible_concept_ids))
        second = select_frontier_delta(
            relabeled, relabeled_closure, release,
            _options(relabeled, release, relabeled_closure))
        self.assertEqual(first.candidate_signature, second.candidate_signature)
        self.assertNotEqual(first.selection_sha256, second.selection_sha256)
