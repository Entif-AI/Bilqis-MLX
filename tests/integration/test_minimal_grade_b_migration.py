"""Neural-inert winnowing of an already-admitted full Grade B."""
from dataclasses import asdict, replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.boolean_composite import build_course as build_composite
from bilqis_mlx.boolean_identification import build_course as build_identification
from bilqis_mlx.curriculum.scheduler import start_new
from bilqis_mlx.factory.live_releases import (
    MINIMAL_BOOLEAN_RELEASE,
    boolean_successor,
    initial_course,
    minimal_boolean_successor,
)
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime.state import _fingerprint
from bilqis_mlx.runtime.assessment import _candidate_cohort, _introduced_cohort
from bilqis_mlx.trainer import (
    VERSION, _activate_replaced_admitted_grade, _commit_scored_student,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "vendor" / "legacy-v16"


class MinimalGradeBMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest = json.loads((
            ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
        cls.manifest = manifest
        cls.a = initial_course(accepted_grade_a(manifest))
        full = boolean_successor(cls.a, SOURCE)
        full = build_composite(full, SOURCE)
        cls.old = build_identification(full, SOURCE)
        cls.new = minimal_boolean_successor(cls.a, SOURCE)
        _, _, cls.graph, _, _ = read_sources(SOURCE)

    def test_existing_full_b_is_replaced_without_neural_mutation(self):
        student = Checkpoint("a" * 64, "bundles/unchanged", 4321, True)
        base = start_new(self.old, student)
        school = replace(
            base,
            champions={"A": student, "B": student},
            queue=tuple(cap.id for cap in self.old.grades[0].capabilities),
        )
        receipt = {
            "schema": VERSION,
            "generation": 21,
            "run_id": "minimal-b-migration-fixture",
            "school": asdict(school),
            "model_bundle": student.filename,
            "curriculum_mode": self.old.version,
            "result": "ACTIVE_GRADE_A",
            "semantic_graph_sha256": _fingerprint(self.graph),
            "parameter_shapes": {
                "embedding.weight": [len(self.graph["tokens"]), 8]},
            "source_manifest_sha256": self.manifest["manifest_sha256"],
            "teacher": {"events": 99, "strategies": {}},
            "config": {
                "precision": "fp32",
                "vocab_size": len(self.graph["tokens"]),
            },
            "last_exam": {"cohort_sha256": "b" * 64},
            "qualification_cohort": {"cohort_sha256": "c" * 64},
            "last_generalization_cohort": {"cohort_sha256": "d" * 64},
            "burned_generalization_cohorts": ["e" * 64],
            "capability_best": {"legacy": {"capability": "B.OR"}},
            "graduation_perfect": {"legacy": {"capability": "B.XOR"}},
            "whole_student_peaks": [{"legacy": True}],
            "teacher_misses": [{"id": "miss", "capability": "B.OR"}],
            "teacher_miss_exposures": {"miss": 4},
            "stagnation_session": {"required_capabilities": ["B.OR"]},
            "legacy_frontier_pending_replay": True,
            "mentor_epoch": {
                "championship_school_identity": {"old": True},
                "active_roles": {"B.OR": {"checkpoint": asdict(student)}},
                "active_grade_soups": {"B": {"grade": "B"}},
                "settled_matchups": {},
            },
        }
        with TemporaryDirectory() as temp:
            root = Path(temp)
            revised = _activate_replaced_admitted_grade(
                root, receipt, self.old, self.new, self.graph)
            self.assertEqual(json.loads((root / "state.json").read_text()), revised)
            self.assertTrue((root / "states" / "0000022.json").is_file())
            events = [json.loads(line) for line in (
                root / "events.jsonl").read_text().splitlines()]

        self.assertEqual(revised["curriculum_mode"], MINIMAL_BOOLEAN_RELEASE)
        self.assertEqual(revised["live_rubric_sha256"], self.new.grades[0].assessment_sha256)
        self.assertEqual(revised["model_bundle"], receipt["model_bundle"])
        self.assertEqual(
            revised["school"]["current_student"],
            receipt["school"]["current_student"])
        self.assertEqual(revised["teacher"], receipt["teacher"])
        self.assertEqual(set(revised["school"]["champions"]), {"A"})
        self.assertEqual(
            revised["config"]["answer_heads"]["boolean_operator"]["values"],
            ["AND", "IFF"])
        self.assertEqual(revised["capability_best"], {})
        self.assertEqual(revised["graduation_perfect"], {})
        self.assertEqual(revised["whole_student_peaks"], [])
        self.assertEqual(revised["teacher_misses"], [])
        self.assertEqual(revised["teacher_miss_exposures"], {})
        self.assertEqual(revised["burned_generalization_cohorts"], [])
        self.assertFalse(revised["legacy_frontier_pending_replay"])
        self.assertIsNone(revised["last_exam"])
        self.assertIsNone(revised["stagnation_session"])
        self.assertNotIn("qualification_cohort", revised)
        self.assertNotIn("last_generalization_cohort", revised)
        epoch = revised["mentor_epoch"]
        self.assertEqual(epoch["active_roles"], {})
        self.assertEqual(epoch["active_grade_soups"], {})
        self.assertTrue(epoch["school_identity_history"])
        self.assertEqual(events[-1]["event"], "SCHOOL_GRADE_RELEASE_REPLACED")
        self.assertEqual(events[-1]["actual_neural_updates"], 0)
        self.assertEqual(events[-1]["optimizer_step"], 4321)
        self.assertEqual(
            set(events[-1]["withheld_capabilities"]),
            {"B.NOT", "B.OR", "B.XOR", "B.IMPLIES"})


    def test_a_candidate_after_minimal_b_migration_uses_a_scope_rubric(self):
        student = Checkpoint("a" * 64, "bundles/unchanged", 4321, True)
        school = start_new(self.new, student)
        receipt = {
            "school": asdict(school),
            "generation": 1,
            "run_id": "minimal-b-a-scope",
            "source_manifest_sha256": self.manifest["manifest_sha256"],
            "live_rubric_sha256": self.new.grades[0].assessment_sha256,
            "config": {},
            "answer_ids": [],
            "capability_best": {},
            "graduation_perfect": {},
        }
        class Step:
            def item(self):
                return student.optimizer_step
        class Optimizer:
            state = {"step": Step()}
        with TemporaryDirectory() as temp:
            root = Path(temp)
            cohort = _candidate_cohort(
                root, receipt, self.manifest, self.new, SOURCE, self.graph)
            cohort, _ = _introduced_cohort(
                root, self.manifest, self.new, school, cohort)
            predictions = {row["id"]: row["gold"] for row in cohort.rows}
            with patch("bilqis_mlx.trainer._bundle_pointer", return_value=student):
                _, frontier, roles, _ = _commit_scored_student(
                    None, root, receipt, self.manifest, self.new, school,
                    cohort, predictions, {}, Optimizer(), self.graph, reserve_gib=1)
        self.assertTrue(roles)
        self.assertTrue(frontier)
        self.assertEqual(
            {item["rubric"] for item in frontier.values()},
            {self.new.grades[0].assessment_sha256})


if __name__ == "__main__":
    unittest.main()
