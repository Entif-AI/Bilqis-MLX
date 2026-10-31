"""A09.1a immutable source/coverage planning snapshot contracts."""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.candidate_frontier import (
    Candidate, CandidateFrontierRelease, CandidateSense,
)
from bilqis_mlx.factory.model import AssessmentClass, LearningEvidence
from bilqis_mlx.factory.atlas_frontier import (
    PlannerBudget, _build_snapshot, _source_edges,
    assert_initial_snapshot_current, build_curriculum_snapshot,
)
from bilqis_mlx.factory.skos_curriculum import (
    ConceptFamilyCoverage, CurriculumCandidateSet, FamilyInventoryCounts,
    FamilyObligation, LearnedFrontier, SOURCE_FAMILY_ADAPTERS,
    SemanticFamilyInventory, SourceConstructiveLesson,
    compile_semantic_curriculum,
)
from bilqis_mlx.semantics.atlas_projection import (
    CorpusCoverageRow, FormalDomainBinding, compile_atlas_release,
    persist_atlas_release,
)
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.context_eligibility import (
    ContextPolicy, SourceFrontier,
)


RELEASE = "a" * 64


def _candidate_frontier():
    sense = CandidateSense(
        "sense.one", "root.one", "ONE", "stem", "spec", "source wording",
        "1" * 64, "SELECTED", "cap.one")
    selected = Candidate(
        "candidate.ready", "CORE_D_O", "cap.one", "D", "ONE", "root.one",
        sense.sense_id, (), (), "why", "unlock", "answer", "world", "",
        ("FACTORY_ADMISSION_REQUIRED",), (), "PROPOSED_NOT_ADMITTED")
    reserve = Candidate(
        "candidate.reserve", "NEXT_96", "", "", "TWO", "root.two", "",
        (), (), "later", "later", "answer", "world", "",
        ("FACTORY_ADMISSION_REQUIRED",), (), "CANDIDATE_RESERVE")
    manifest = {
        "schema": "bilqis.mlx.candidate-frontier-release/v1",
        "builder_sha256": "2" * 64,
        "input_digest": "3" * 64,
        "output_digest": "4" * 64,
        "candidates": [asdict(selected), asdict(reserve)],
        "senses": [asdict(sense)],
    }
    digest = hashlib.sha256(json.dumps(
        manifest, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode()).hexdigest()
    release = CandidateFrontierRelease(
        manifest["builder_sha256"], manifest["input_digest"],
        manifest["output_digest"], (selected, reserve), (sense,), digest)
    release.verify()
    return release


def _candidate():
    eligible = (
        ConceptFamilyCoverage(
            "urn:one", 0, True, "SOURCE_ELIGIBLE",
            "IMPLEMENTATION_UNCOVERED", ("positive_identity",),
            ("source:one",)),
        ConceptFamilyCoverage(
            "urn:two", 1, True, "SOURCE_ELIGIBLE",
            "IMPLEMENTATION_UNCOVERED", ("positive_identity",),
            ("source:two",)),
    )
    obligations = tuple(
        FamilyObligation(
            item.semantic_id, "positive_identity", "f" * 64,
            "IMPLEMENTATION_UNCOVERED",
            "FAMILY_CONSTRUCTOR_CHECKER_NOT_BOUND")
        for item in eligible)
    held = (CorpusCoverageRow(
        "synthetic", "held", "row1", None, "SOURCE_HELD",
        "SOURCE_HELD", False, "RIGHTS_MISSING", "rights pending",
        "source:owner"),)
    ir_only = (CorpusCoverageRow(
        "synthetic", "ir", "row2", None, "SOURCE_IR_ONLY",
        "SOURCE_IR_ONLY", False, "NOT_SEMANTIC", "structural",
        "source:owner"),)
    census = SemanticFamilyInventory(
        RELEASE, "b" * 64, "c" * 64, "d" * 64,
        ("urn:one", "urn:two"), ("positive_identity",), (),
        eligible, obligations, held, ir_only, (),
        FamilyInventoryCounts(2, 0, 2, 1, 1, 0, 1, 0, 2, 2))
    return CurriculumCandidateSet(
        census, ("positive_identity",), (), ())


def _rights():
    frontier = SourceFrontier(1, 1, ())
    policy = ContextPolicy(
        "synthetic:policy", 2, 1,
        ("TRAINING",), ("PUBLIC_FORMAL",),
        ("synthetic:region",), ("synthetic:task",),
        ("PUBLIC_FORMAL",), (("PUBLIC_FORMAL", "PUBLIC_FORMAL"),),
        (("PUBLIC_FORMAL", "PUBLIC_FORMAL", "PUBLIC_FORMAL"),))
    return frontier, policy


class AtlasFrontierTests(unittest.TestCase):
    def test_real_pinned_a01_a08_snapshot_if_supplied(self):
        corpus = os.environ.get("BILQIS_ATLAS_REAL_CORPUS")
        if not corpus:
            self.skipTest("real pinned A01 corpus not supplied")
        root = Path(__file__).resolve().parents[4]
        prior = root / "bilqis_mlx/semantics/copular_registry_v1.json"
        boolean = root / "bilqis_mlx/semantics/legacy_abi_v1.json"
        numeric = root / "bilqis_mlx/semantics/numeric_v1.json"
        bindings = (
            FormalDomainBinding(
                "boolean", "bilqis_mlx/semantics/legacy_abi_v1.json",
                hashlib.sha256(boolean.read_bytes()).hexdigest(),
                ("legacy:cogal.operator.NOT", "legacy:cogal.operator.AND"),
                ("B.NOT", "B.AND")),
            FormalDomainBinding(
                "numeric", "bilqis_mlx/semantics/numeric_v1.json",
                hashlib.sha256(numeric.read_bytes()).hexdigest(),
                ("bilqis.numeric/v1:school.op.COUNT",
                 "bilqis.numeric/v1:school.op.SUCC"),
                ("C.COUNT", "C.SUCCESSOR")))
        release = compile_atlas_release(
            corpus, Path(corpus) / "coverage.json", prior, bindings)
        with tempfile.TemporaryDirectory() as directory:
            artifact = persist_atlas_release(release, directory)
            selection = AtlasArtifactSelection(
                artifact.path, artifact.bundle_id, release.digest,
                release.source_bundle_id)
            learned = LearnedFrontier(release.digest)
            candidate = compile_semantic_curriculum(
                selection, SOURCE_FAMILY_ADAPTERS, learned)
            candidate_frontier = _candidate_frontier()
            frontier, policy = _rights()
            snapshot = build_curriculum_snapshot(
                candidate, selection, learned, frontier, policy, candidate_frontier,
                budget=PlannerBudget(32, 10000, 100000),
                grade_labels=("B", "A"))
            self.assertEqual(len(snapshot.source_eligible_concept_ids), 9307)
            self.assertEqual(len(snapshot.coverage_rows), 12351)
            self.assertEqual(len(snapshot.source_held_rows), 1052)
            self.assertEqual(snapshot.grade_labels, ("A", "B"))
            self.assertEqual(snapshot.frozen_census_sha256, candidate.census.digest)
            self.assertEqual(snapshot.qualification_epoch, 0)
            snapshot.verify()
            assert_initial_snapshot_current(
                snapshot, candidate, selection, learned,
                frontier, policy, candidate_frontier,
                budget=PlannerBudget(32, 10000, 100000),
                grade_labels=("A", "B"))
            with self.assertRaises(BilqisError):
                assert_initial_snapshot_current(
                    snapshot, candidate, selection, learned,
                    frontier, policy, candidate_frontier,
                    budget=PlannerBudget(33, 10000, 100000),
                    grade_labels=("A", "B"))

    def test_unqualified_or_cyclic_prerequisites_fail_closed(self):
        candidate = _candidate()
        def lesson(source, prerequisite):
            return SourceConstructiveLesson(
                RELEASE, source, "positive_identity", "f" * 64,
                ("identity", source, "source:one"),
                ("identity", "urn:other", "source:two"),
                "SEMANTIC_ID", "bilqis.source-checker.identity/v1",
                (source,), (prerequisite,),
                ("source-identity",))
        missing = replace(
            candidate, source_lessons=(lesson("urn:one", "urn:missing"),))
        with self.assertRaises(BilqisError) as held:
            _source_edges(missing)
        self.assertEqual(
            held.exception.context["reason"],
            "BAMF_PLANNER_PREREQUISITE_NOT_SOURCE_ELIGIBLE")
        cycle = replace(
            candidate, source_lessons=(
                lesson("urn:one", "urn:two"),
                lesson("urn:two", "urn:one")))
        with self.assertRaises(BilqisError) as caught:
            _source_edges(cycle)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PLANNER_PREREQUISITE_CYCLE")

    def test_held_and_unimplemented_are_distinct_and_grade_neutral(self):
        candidate = _candidate()
        frontier, policy = _rights()
        budget = PlannerBudget(10, 100, 1000)
        first = _build_snapshot(
            candidate, frontier, policy, budget=budget,
            grade_labels=("B", "A"))
        second = _build_snapshot(
            candidate, frontier, policy, budget=budget,
            grade_labels=("A", "B"))
        self.assertEqual(first.canonical_bytes(), second.canonical_bytes())
        self.assertEqual(first.snapshot_sha256, second.snapshot_sha256)
        self.assertEqual(first.grade_labels, ("A", "B"))
        self.assertEqual(len(first.coverage_rows), 2)
        self.assertTrue(all(
            row.source_disposition == "SOURCE_ELIGIBLE"
            and row.implementation_status == "IMPLEMENTATION_UNCOVERED"
            for row in first.coverage_rows))
        self.assertEqual(first.source_held_rows[0].owner, "source:owner")
        self.assertEqual(
            first.source_held_rows[0].reason_code, "RIGHTS_MISSING")
        self.assertEqual(first.admitted_factory_release_sha256, None)
        self.assertEqual(first.qualification_epoch, 0)
        first.verify()
        with self.assertRaises(BilqisError):
            replace(
                first, source_held_rows=(
                    replace(
                        first.source_held_rows[0],
                        source_disposition="SOURCE_ELIGIBLE"),))
        with self.assertRaises(BilqisError):
            replace(first, snapshot_sha256="0" * 64).verify()
        with self.assertRaises(BilqisError):
            replace(first, schema="bilqis.factory-curriculum-snapshot/v999")

    def test_staged_admitted_and_learning_claims_remain_independent(self):
        candidate = replace(
            _candidate(), unverified_exposure_claims=("urn:one",),
            unverified_qualification_claims=("urn:two",))
        frontier, policy = _rights()
        snapshot = _build_snapshot(
            candidate, frontier, policy, budget=PlannerBudget(10, 100, 1000),
            staged_release_sha256s=("a" * 64,),
            admitted_release_sha256="b" * 64,
            admission_receipt_sha256="c" * 64)
        self.assertEqual(snapshot.staged_factory_release_sha256s, ("a" * 64,))
        self.assertEqual(snapshot.admitted_factory_release_sha256, "b" * 64)
        self.assertEqual(snapshot.unverified_exposed_capability_ids, ("urn:one",))
        self.assertEqual(snapshot.unverified_qualified_capability_ids, ("urn:two",))
        self.assertEqual(snapshot.qualification_epoch, 0)

    def test_retained_evidence_order_is_fully_canonical(self):
        candidate = _candidate()
        frontier, policy = _rights()
        common = dict(
            assessment_class=AssessmentClass.PROMOTION,
            cohort_sha256="1" * 64,
            checkpoint_sha256="2" * 64,
            optimizer_step=3,
        )
        passing = LearningEvidence(**common, passed=True)
        failing = LearningEvidence(**common, passed=False)
        first = _build_snapshot(
            candidate, frontier, policy, budget=PlannerBudget(10, 100, 1000),
            retained_evidence=(passing, failing))
        second = _build_snapshot(
            candidate, frontier, policy, budget=PlannerBudget(10, 100, 1000),
            retained_evidence=(failing, passing))
        self.assertEqual(first.canonical_bytes(), second.canonical_bytes())
        self.assertEqual(first.snapshot_sha256, second.snapshot_sha256)

    def test_frontier_and_named_learning_states_are_snapshot_identity(self):
        candidate = replace(
            _candidate(), unverified_exposure_claims=("urn:one",),
            unverified_qualification_claims=("urn:two",))
        frontier, policy = _rights()
        base = _build_snapshot(
            candidate, frontier, policy, budget=PlannerBudget(10, 100, 1000),
            candidate_frontier_sha256="3" * 64,
            ready_candidate_ids=("candidate.ready",), qualification_epoch=7)
        changed = _build_snapshot(
            candidate, frontier, policy, budget=PlannerBudget(10, 100, 1000),
            candidate_frontier_sha256="4" * 64,
            ready_candidate_ids=("candidate.ready",), qualification_epoch=7)
        self.assertEqual(base.candidate_frontier_sha256, "3" * 64)
        self.assertEqual(base.ready_candidate_ids, ("candidate.ready",))
        self.assertEqual(base.unverified_exposed_capability_ids, ("urn:one",))
        self.assertEqual(base.unverified_qualified_capability_ids, ("urn:two",))
        self.assertEqual(base.qualification_epoch, 7)
        self.assertNotEqual(base.snapshot_sha256, changed.snapshot_sha256)

    def test_rights_epoch_and_budget_changes_are_visible(self):
        candidate = _candidate()
        frontier, policy = _rights()
        base = _build_snapshot(
            candidate, frontier, policy, budget=PlannerBudget(10, 100, 1000))
        changed = _build_snapshot(
            candidate, frontier, policy, budget=PlannerBudget(11, 100, 1000))
        self.assertNotEqual(base.snapshot_sha256, changed.snapshot_sha256)
        debt = _build_snapshot(
            candidate, frontier, policy, budget=PlannerBudget(10, 100, 1000),
            retained_mastery_debt=("cap.z", "cap.a"),
            retained_debt_source_sha256="e" * 64)
        self.assertEqual(
            debt.retained_mastery_debt, ("cap.a", "cap.z"))
        self.assertNotEqual(base.snapshot_sha256, debt.snapshot_sha256)
        with self.assertRaises(BilqisError):
            _build_snapshot(
                candidate, frontier, policy,
                budget=PlannerBudget(10, 100, 1000),
                retained_mastery_debt=("cap.a",))
        with self.assertRaises(BilqisError):
            _build_snapshot(
                candidate, replace(frontier, rights_epoch=2),
                policy, budget=PlannerBudget(10, 100, 1000))


if __name__ == "__main__":
    unittest.main()
