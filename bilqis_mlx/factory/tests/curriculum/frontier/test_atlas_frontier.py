"""A09.1a immutable source/coverage planning snapshot contracts."""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.candidate_frontier import (
    Candidate, CandidateFrontierRelease, CandidateSense, load_candidate_frontier,
)
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
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
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
        root = Path(__file__).resolve().parents[5]
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
            # Generate A08 from the pinned source rows and verify its builder and
            # CSV provenance before binding real A01 data to the A09 snapshot.
            builder = root / "lib/ithkuil/src/build_curriculum_frontier.py"
            source = root / "lib/ithkuil/_data/csv"
            output = Path(directory) / "candidate-frontier"
            subprocess.run(
                [sys.executable, str(builder)], check=True, capture_output=True,
                text=True, env={**os.environ, "BILQIS_CURRICULUM_FRONTIER_OUT": str(output)},
            )
            candidate_frontier = load_candidate_frontier(
                output, source,
                expected_builder_sha256=hashlib.sha256(builder.read_bytes()).hexdigest(),
            )
            self.assertEqual(len(candidate_frontier.candidates), 240)
            self.assertGreater(len(candidate_frontier.senses), 0)
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
            self.assertEqual(
                snapshot.candidate_frontier_sha256, candidate_frontier.release_sha256)
            self.assertEqual(snapshot.ready_candidate_ids, ())
            self.assertTrue(all(item.disposition != "ADMITTED"
                                for item in candidate_frontier.candidates))
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

if __name__ == "__main__":
    unittest.main()
