"""Neural-inert winnowing of an already-admitted full Grade B."""
from dataclasses import asdict, replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.boolean_composite import build_course as build_composite
from bilqis_mlx.boolean_identification import build_course as build_identification
from bilqis_mlx.curriculum.scheduler import assessment_capabilities, start_new
from bilqis_mlx.factory.live_releases import (
    MINIMAL_BOOLEAN_RELEASE,
    boolean_successor,
    initial_course,
    minimal_boolean_successor,
)
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.generated_assessment import make_cohort
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.learning.stagnation_control import start_session as start_stagnation_session
from bilqis_mlx.runtime.state import _fingerprint
from bilqis_mlx.runtime.assessment import _candidate_executable_cohort
from bilqis_mlx.runtime.admission import _executable_factory_admission
from bilqis_mlx.compatibility.executable_projection import (
    compile_projected_executable_release,
)
from bilqis_mlx.source_adapters.school import live_source_registry
from bilqis_mlx.trainer import (
    VERSION, _activate_replaced_admitted_grade, _commit_scored_student,
    _repair_scope_rubric_evidence, _repair_championship_source_context,
    _reconcile_stagnation_scope,
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
        class Step:
            def item(self):
                return student.optimizer_step
        class Optimizer:
            state = {"step": Step()}
        with TemporaryDirectory() as temp:
            root = Path(temp)
            release, program, canonical_course = (
                compile_projected_executable_release(
                    self.new, self.a, SOURCE, self.graph))
            school = start_new(program, student)
            release, release_file, admission = _executable_factory_admission(
                root, release, student, _fingerprint(self.graph), self.graph)
            receipt = {
                "school": asdict(school),
                "generation": 1,
                "run_id": "minimal-b-a-scope",
                "source_manifest_sha256": self.manifest["manifest_sha256"],
                "semantic_graph_sha256": _fingerprint(self.graph),
                "factory_release_sha256": release.release_sha256,
                "factory_release_file": release_file,
                "factory_admission_v2": asdict(admission),
                "live_rubric_sha256": program.grades[0].assessment_sha256,
                "config": {},
                "answer_ids": [],
                "capability_best": {},
                "graduation_perfect": {},
            }
            a_scope = tuple(
                capability.id for capability in program.grades[0].capabilities)
            cohort, _ = _candidate_executable_cohort(
                root, receipt, self.manifest, release,
                live_source_registry(), SOURCE, self.graph,
                capabilities=a_scope, legacy_course=canonical_course)
            predictions = {row["id"]: row["gold"] for row in cohort.rows}
            with patch("bilqis_mlx.trainer._bundle_pointer", return_value=student):
                _, frontier, roles, _ = _commit_scored_student(
                    None, root, receipt, self.manifest, canonical_course, school,
                    cohort, predictions, {}, Optimizer(), self.graph, reserve_gib=1)
        self.assertTrue(roles)
        self.assertTrue(frontier)
        self.assertEqual(
            {item["rubric"] for item in frontier.values()},
            {program.grades[0].assessment_sha256})

    def test_resume_repairs_mislabeled_scope_evidence_without_neural_update(self):
        student = Checkpoint("a" * 64, "bundles/unchanged", 4321, True)
        school = start_new(self.new, student)
        a_rubric = self.new.grades[0].assessment_sha256
        b_rubric = self.new.grades[-1].assessment_sha256
        receipt = {
            "schema": VERSION,
            "generation": 7,
            "run_id": "scope-repair-fixture",
            "school": asdict(school),
            "model_bundle": student.filename,
            "curriculum_mode": self.new.version,
            "result": "ACTIVE_GRADE_A",
            "semantic_graph_sha256": _fingerprint(self.graph),
            "championship_school_identity": {"fixture": True},
            "live_rubric_sha256": a_rubric,
            "capability_best": {
                b_rubric + ":A.IDENTITY": {
                    "capability": "A.IDENTITY",
                    "rubric": b_rubric,
                    "correct": 12,
                    "total": 12,
                    "checkpoint": asdict(student),
                    "evaluation_id": "capability-evaluation/bad",
                },
            },
            "championship_epoch_history": [],
            "mentor_epoch": {
                "schema": "fixture",
                "active_roles": {
                    "A.IDENTITY": {
                        "capability": "A.IDENTITY",
                        "rubric": b_rubric,
                        "cohort_sha256": "c" * 64,
                        "checkpoint": asdict(student),
                    },
                },
                "active_grade_soups": {"A": {"grade": "A"}},
            },
            "last_exam": {
                "student_sha256": student.sha256,
                "optimizer_step": student.optimizer_step,
                "exam_rubric_sha256": a_rubric,
                "scores": {
                    cap.id: {"correct": 12, "total": 12}
                    for cap in self.new.grades[0].capabilities
                },
            },
        }
        with TemporaryDirectory() as temp:
            root = Path(temp)
            repaired = _repair_scope_rubric_evidence(root, receipt, self.new)
            events = [
                json.loads(line)
                for line in (root / "events.jsonl").read_text().splitlines()
            ]
        self.assertEqual(repaired["generation"], 8)
        self.assertEqual(repaired["school"]["current_student"], asdict(student))
        self.assertEqual(repaired["capability_best"], {})
        self.assertEqual(repaired["mentor_epoch"]["active_roles"], {})
        self.assertEqual(repaired["mentor_epoch"]["active_grade_soups"], {})
        self.assertEqual(len(repaired["championship_epoch_history"]), 1)
        self.assertEqual(
            events[-1]["event"], "SCHOOL_SCOPE_RUBRIC_EVIDENCE_REPAIRED")
        self.assertEqual(events[-1]["actual_neural_updates"], 0)
        self.assertTrue(events[-1]["model_and_own_adamw_unchanged"])

    def test_resuming_v2_does_not_erase_valid_different_scope_evidence(self):
        """An exam's *latest* rubric never supersedes other proven strata.

        A cumulative/partial exam can score the same capability under a new
        signed v2 scope. Capability and championship records from a different
        v2 scope are separate authority, not malformed source evidence.
        """
        student = Checkpoint("a" * 64, "bundles/unchanged", 4321, True)
        school = start_new(self.new, student)
        prior_rubric = self.new.grades[-1].assessment_sha256
        latest_rubric = self.new.grades[0].assessment_sha256
        leader = {
            "capability": "A.IDENTITY", "rubric": prior_rubric,
            "correct": 12, "total": 12, "checkpoint": asdict(student),
            "evaluation_id": "capability-evaluation/original",
        }
        role = {**leader, "cohort_sha256": "c" * 64}
        receipt = {
            "generation": 10, "run_id": "valid-v2-cross-scope",
            "school": asdict(school),
            "factory_admission_v2": {"factory_release_sha256": "e" * 64},
            "factory_release_sha256": "e" * 64,
            "capability_best": {prior_rubric + ":A.IDENTITY": leader},
            "championship_epoch_history": [],
            "mentor_epoch": {
                "active_roles": {"A.IDENTITY": role},
                "active_grade_soups": {"A": {"grade": "A"}},
            },
            "last_exam": {
                "factory_release_sha256": "e" * 64,
                "exam_rubric_sha256": latest_rubric,
                "scores": {"A.IDENTITY": {"correct": 11, "total": 12}},
            },
        }
        with TemporaryDirectory() as temp:
            root = Path(temp)
            result = _repair_scope_rubric_evidence(root, receipt, self.new)
            self.assertFalse((root / "state.json").exists())
            self.assertFalse((root / "events.jsonl").exists())
        self.assertIs(result, receipt)
        self.assertEqual(result["capability_best"][prior_rubric + ":A.IDENTITY"],
                         leader)
        self.assertEqual(result["mentor_epoch"]["active_roles"]["A.IDENTITY"],
                         role)

    def test_resume_resets_titles_missing_distinct_cohort_source_rubric(self):
        student = Checkpoint("a" * 64, "bundles/unchanged", 4321, True)
        school = start_new(self.new, student)
        a_rubric = self.new.grades[0].assessment_sha256
        b_rubric = self.new.grades[-1].assessment_sha256
        rows = ({"id": "q0", "capability": "A.IDENTITY", "gold": "TRUE"},)
        cohort = make_cohort(
            rows, generator_version="minimal-b-source", seed=19,
            rubric_version=self.new.version)
        evidence = {
            "cohort_sha256": cohort.digest,
            "rubric_sha256": a_rubric,
            "source_oracle_sha256": self.manifest["manifest_sha256"],
        }
        receipt = {
            "schema": VERSION,
            "generation": 9,
            "run_id": "source-context-repair-fixture",
            "school": asdict(school),
            "model_bundle": student.filename,
            "curriculum_mode": self.new.version,
            "result": "ACTIVE_GRADE_A",
            "semantic_graph_sha256": _fingerprint(self.graph),
            "championship_school_identity": {"fixture": True},
            "capability_best": {},
            "championship_epoch_history": [],
            "mentor_epoch": {
                "schema": "fixture",
                "active_roles": {
                    "A.IDENTITY": {
                        "capability": "A.IDENTITY",
                        "rubric": a_rubric,
                        "cohort_sha256": cohort.digest,
                        "checkpoint": asdict(student),
                        "qualification_witnesses": [evidence],
                        "surviving_battery": [evidence],
                    },
                },
                "active_grade_soups": {"A": {"grade": "A"}},
            },
        }
        with TemporaryDirectory() as temp:
            root = Path(temp)
            cohorts = root / "cohorts"
            cohorts.mkdir()
            (cohorts / f"{cohort.digest}.json").write_text(json.dumps({
                "schema": self.new.version,
                "source_manifest_sha256": self.manifest["manifest_sha256"],
                "rubric_sha256": b_rubric,
                "generator_version": "minimal-b-source",
                "seed": 19,
                "cohort_sha256": cohort.digest,
                "rows": list(rows),
            }))
            repaired = _repair_championship_source_context(
                root, receipt, self.new)
            events = [
                json.loads(line)
                for line in (root / "events.jsonl").read_text().splitlines()
            ]
        self.assertEqual(repaired["generation"], 10)
        self.assertEqual(repaired["school"]["current_student"], asdict(student))
        self.assertEqual(repaired["mentor_epoch"]["active_roles"], {})
        self.assertEqual(repaired["mentor_epoch"]["active_grade_soups"], {})
        self.assertEqual(len(repaired["championship_epoch_history"]), 1)
        self.assertEqual(
            events[-1]["event"],
            "SCHOOL_CHAMPIONSHIP_SOURCE_CONTEXT_REPAIRED")
        self.assertEqual(events[-1]["actual_neural_updates"], 0)

    def test_in_command_a_to_b_transition_reconciles_stagnation_scope_before_b_work(self):
        student = Checkpoint("a" * 64, "bundles/unchanged", 4321, True)
        a_state = start_new(self.new, student)
        b_state = replace(
            a_state,
            grade_index=1,
            stage="MAIN",
            queue=("B.AND", "B.IFF"),
            champions={"A": student},
        )
        a_required = assessment_capabilities(self.new, a_state)
        b_required = assessment_capabilities(self.new, b_state)
        self.assertNotEqual(a_required, b_required)
        receipt = {
            "schema": VERSION,
            "generation": 60,
            "run_id": "in-command-a-to-b-stagnation-fixture",
            "school": asdict(b_state),
            "model_bundle": student.filename,
            "curriculum_mode": self.new.version,
            "result": "ACTIVE_GRADE_B",
            "stagnation_session": start_stagnation_session(
                session_id="same-human-command",
                generation=50,
                required_capabilities=a_required),
        }
        with TemporaryDirectory() as temp:
            root = Path(temp)
            reconciled = _reconcile_stagnation_scope(
                root, receipt, self.new, b_state)
            events = [
                json.loads(line)
                for line in (root / "events.jsonl").read_text().splitlines()
            ]
        self.assertEqual(reconciled["generation"], 61)
        self.assertEqual(
            tuple(reconciled["stagnation_session"]["required_capabilities"]),
            b_required)
        self.assertEqual(
            reconciled["stagnation_session"]["cycle_first_recovery"], [])
        self.assertEqual(
            reconciled["stagnation_session"]["cycle_visits"], {})
        self.assertEqual(
            events[-1]["event"], "SCHOOL_STAGNATION_SCOPE_RECONCILED")
        self.assertEqual(events[-1]["added_capabilities"], ["B.AND", "B.IFF"])
        self.assertEqual(events[-1]["actual_neural_updates"], 0)


if __name__ == "__main__":
    unittest.main()
