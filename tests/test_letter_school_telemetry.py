"""Grade-neutral School50 evidence, including future grades and empty channels."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from bilqis_mlx.grade_a_dashboard import build, ingest
from bilqis_mlx.spiral_dashboard import Dashboard, TABLES


def exam(grade, generation, rubric, scores, *, step, sha="signed-model"):
    return {"event": "SCHOOL_EXAM_COMMITTED", "grade": grade,
            "generation": generation, "rubric": rubric,
            "optimizer_step": step, "student_sha256": sha, "phase": "MAIN",
            "scores": {cap: {"correct": correct, "total": total}
                       for cap, (correct, total) in scores.items()}}


class SchoolTelemetryTests(unittest.TestCase):
    def test_six_legacy_panel_names_remain_but_new_school_columns_are_useful(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            self.assertEqual(set(board.rows), {name for name, _ in TABLES})
            self.assertEqual([x.name for x in dict(board.tables)["CANDIDATES"]][:3],
                             ["CAPABILITY", "VISIT", "POLICY"])
            self.assertEqual([x.name for x in dict(TABLES)["CANDIDATES"]][:3],
                             ["GRADE", "TRY", "STRATEGY"])
            self.assertTrue(Dashboard(stream=io.StringIO()).rows)

    def test_capability_best_below_perfect_is_displayed_without_grade_mastery(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "SCHOOL_CAPABILITY_BEST_COMMITTED",
                           "grade": "A", "optimizer_step": 116776,
                           "student_sha256": "e" * 64,
                           "rubric": "a" * 64,
                           "scores": {"A.IDENTITY": {"correct": 5, "total": 12},
                                      "A.LINK": {"correct": 7, "total": 12}},
                           "capabilities": ["A.IDENTITY", "A.LINK"]})
            message = board.rows["SYSTEM & QUALIFICATION"][-1]["detail"]
            self.assertIn("A.IDENTITY", message)
            self.assertIn("A.LINK", message)
            self.assertIn("NOT grade mastery", message)
            self.assertFalse(board.rows["SENTINEL & RETENTION"])

    def test_real_source_visit_shows_strategy_loss_reward_and_no_fake_sentinel(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "GRADE_A_TEACHER_VISIT_COMMITTED",
                           "generation": 2, "capability": "A.IDENTITY",
                           "optimizer_step": 116776, "teacher_policy": "c0d92a80eada",
                           "strategy": {"lr": .00013, "depth": 1, "contrast": 1.,
                                        "old": 16, "preview": 4, "distill": .15},
                           "unavailable_teacher_dimensions": ["old", "preview", "distill"],
                           "source_training_accuracy_before": 7/12,
                           "source_training_accuracy_after": 11/12,
                           "teacher_reward": 4/12, "gradient_norm": 1.26,
                           "loss": .467, "next_phase": "MAIN"})
            candidate = board.rows["CANDIDATES"][-1]
            teacher = board.rows["SOUP & TEACHER"][-1]
            self.assertEqual(candidate["capability"], "A.IDENTITY")
            self.assertIn("58.3", candidate["train"])
            self.assertIn("91.7", candidate["train"])
            self.assertEqual(candidate["reward"], "+0.333")
            self.assertEqual(teacher["old"], "OFF")
            self.assertEqual(teacher["preview"], "OFF")
            self.assertEqual(teacher["distill"], "OFF")
            self.assertIn("0.467", candidate["loss"])
            self.assertIn("1.26", candidate["gradient"])
            self.assertFalse(board.rows["SENTINEL & RETENTION"])
            self.assertTrue(any("NOT MEASURED" in x["detail"]
                                for x in board.rows["SYSTEM & QUALIFICATION"]))

    def test_first_latest_best_and_regression_use_same_sealed_rubric(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            for index, numbers in enumerate(((7, 5), (10, 8), (6, 4)), 1):
                ingest(board, exam("A", index * 5, "rubric-a",
                    {"A.IDENTITY": (numbers[0], 12), "A.PARENT": (numbers[1], 12)},
                    step=116760 + 16 * index))
            rows = board._section_rows("BRIDGE FAMILIES")
            self.assertEqual(len(rows), 2)
            identity = next(r for r in rows if r["family"] == "A.IDENTITY")
            self.assertEqual(identity["first"], "7/12")
            self.assertEqual(identity["before"], "10/12")
            self.assertEqual(identity["after"], "6/12")
            self.assertEqual(identity["gain"], "-4")
            mastery = board._section_rows("GRADES & MASTERY")
            self.assertEqual(len(mastery), 1)
            self.assertEqual(mastery[0]["latest"], "10/24")
            self.assertEqual(mastery[0]["best"], "18/24")
            self.assertEqual(mastery[0]["to100"], "14")
            text = board.render(width=180, height=42)
            self.assertIn("FIRST SEALED A 12/24", text)
            self.assertIn("LATEST A 10/24", text)
            self.assertIn("BEST A 18/24", text)
            self.assertIn("TO100 14/24", text)

    def test_future_b_cumulative_exam_preserves_per_grade_and_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, exam("A", 8, "rubric-a", {"A.IDENTITY": (9, 12)},
                               step=117000, sha="old-a"))
            ingest(board, exam("B", 12, "rubric-a+b", {
                "A.IDENTITY": (8, 12), "B.DIRECTION": (11, 12)},
                step=117500, sha="whole-a+b"))
            mastery = {r["grade"]: r for r in board._section_rows("GRADES & MASTERY")}
            self.assertEqual(set(mastery), {"A", "B"})
            self.assertEqual(mastery["A"]["latest"], "8/12")
            self.assertEqual(mastery["B"]["latest"], "11/12")
            self.assertEqual(mastery["A"]["step"], 117500)
            identity = next(r for r in board._section_rows("BRIDGE FAMILIES")
                            if r["family"] == "A.IDENTITY")
            self.assertEqual(identity["gain"], "-")
            self.assertEqual(identity["before"], "-")
            self.assertTrue(all(not r.get("mastered", False) for r in mastery.values()))

    def test_future_sentinel_soup_and_qualification_emit_without_grade_renames(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "SCHOOL_SENTINEL_COMMITTED", "grade": "C",
                           "generation": 50, "optimizer_step": 131000,
                           "partition": "independent_validation", "probe_delta_pp": 5.,
                           "dataset_sha256": "a" * 64, "student_sha256": "b" * 64,
                           "sentinel_delta_pp": 2.5, "worst_delta_pp": -6.25,
                           "cross_entropy_delta": -.3, "correct_probability_delta": .03,
                           "margin_delta": .12, "family_count": 8})
            ingest(board, {"event": "SCHOOL_SOUP_COMMITTED", "grade": "C",
                           "generation": 51, "optimizer_step": 131000,
                           "teacher_only": True, "teacher_digest": "c" * 64,
                           "soup_kl": .04, "parent_kl": .03,
                           "coverage": .85, "supervised_loss": .7,
                           "teacher_credit": .2, "bridge_ce": .4})
            ingest(board, {"event": "SCHOOL_QUALIFICATION_COMMITTED", "grade": "C",
                           "generation": 52, "status": "SOURCE_ATTESTED",
                           "details": "NI typed morphology checked"})
            self.assertEqual(board.rows["SENTINEL & RETENTION"][-1]["grade"], "C")
            self.assertEqual(board.rows["SENTINEL & RETENTION"][-1]["sent"], "+2.5pp")
            self.assertEqual(board.rows["SOUP & TEACHER"][-1]["soup"], "0.040")
            self.assertEqual(board.rows["SOUP & TEACHER"][-1]["cover"], "85.0%")
            self.assertEqual(board.rows["SOUP & TEACHER"][-1]["sup"], "0.700")
            self.assertEqual(board.rows["SOUP & TEACHER"][-1]["bridge_ce"], "0.400")
            self.assertTrue(any("SOURCE_ATTESTED" in r["detail"]
                                for r in board.rows["SYSTEM & QUALIFICATION"]))

    def test_unverified_future_sentinel_and_student_soup_cannot_claim_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            with self.assertRaisesRegex(ValueError, "SOURCE_PROVENANCE_REQUIRED"):
                ingest(board, {"event": "SCHOOL_SENTINEL_COMMITTED", "grade": "B",
                               "partition": "independent_validation", "probe_delta_pp": 5})
            with self.assertRaisesRegex(ValueError, "TEACHER_ONLY_REQUIRED"):
                ingest(board, {"event": "SCHOOL_SOUP_COMMITTED", "grade": "B",
                               "teacher_only": False, "soup_kl": .01})
            self.assertFalse(board.rows["SENTINEL & RETENTION"])
            self.assertFalse(board.rows["SOUP & TEACHER"])

    def test_future_schema_version_must_not_silently_reinterpret_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            with self.assertRaisesRegex(ValueError, "UNSUPPORTED_SCHEMA"):
                ingest(board, {"event": "SCHOOL_VISIT_COMMITTED", "grade": "Z",
                               "telemetry_schema": "bilqis.school50.telemetry/v999",
                               "capability": "Z.UNKNOWN", "optimizer_step": 300000})
            self.assertFalse(board.rows["CANDIDATES"])

    def test_disk_headroom_is_visible_and_grade_neutral_in_system_panel(self):
        free = int(100.28 * 1024 ** 3)
        with tempfile.TemporaryDirectory() as tmp, patch(
            "bilqis_mlx.disk.shutil.disk_usage",
            return_value=SimpleNamespace(total=1000 * 1024 ** 3,
                                         used=0, free=free)):
            board = build(Path(tmp), stream=io.StringIO())
            disk = next(x for x in board.rows["SYSTEM & QUALIFICATION"]
                        if x["kind"] == "DISK")
            self.assertIn("100.28 GiB", disk["detail"])
            self.assertIn("BLOCKED", disk["detail"])
            ingest(board, {"event": "SCHOOL_RESOURCE_OBSERVED", "grade": "B",
                           "free_bytes": free + 1024 ** 3,
                           "reserve_bytes": 100 * 1024 ** 3,
                           "estimated_write_bytes": 600_000_000})
            updated = [x for x in board.rows["SYSTEM & QUALIFICATION"]
                       if x["kind"] == "DISK"]
            self.assertEqual(len(updated), 1)
            self.assertIn("READY", updated[0]["detail"])

    def test_future_constructed_family_probes_have_lineage_and_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "SCHOOL_FAMILY_PROBE_COMMITTED", "grade": "B",
                           "generation": 51, "family": "B.CASE.CONTRAST",
                           "before": {"correct": 3, "total": 10},
                           "after": {"correct": 8, "total": 10},
                           "partition": "independent_validation", "dataset_sha256": "a" * 64,
                           "student_sha256": "b" * 64, "optimizer_step": 132000})
            family = board._section_rows("BRIDGE FAMILIES")[-1]
            self.assertEqual(family["family"], "B.CASE.CONTRAST")
            self.assertEqual(family["before"], "3/10")
            self.assertEqual(family["after"], "8/10")
            self.assertEqual(family["gain"], "+5")
            self.assertFalse(board.rows["GRADES & MASTERY"][-1].get("mastered", False))
            with self.assertRaisesRegex(ValueError, "SOURCE_PROVENANCE_REQUIRED"):
                ingest(board, {"event": "SCHOOL_FAMILY_PROBE_COMMITTED", "grade": "B",
                               "family": "B.CASE.CONTRAST", "before": {"correct": 3, "total": 10},
                               "after": {"correct": 10, "total": 10}})

    def test_mismatched_checkpoint_in_one_exam_cannot_claim_mastery(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            corrupted = exam("A", 1, "rubric-a", {"A.IDENTITY": (12, 12)},
                             step=117000, sha="whole")
            corrupted["scores"]["A.IDENTITY"]["checkpoint_sha256"] = "different"
            with self.assertRaisesRegex(ValueError, "CHECKPOINT_MISMATCH"):
                ingest(board, corrupted)
            self.assertTrue(all(row.get("latest") == "-"
                                for row in board.rows["GRADES & MASTERY"]))

    def test_old_wide_three_pane_format_keeps_decisive_new_metrics_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "GRADE_A_TEACHER_VISIT_COMMITTED",
                           "generation": 2, "capability": "A.IDENTITY", "optimizer_step": 116776,
                           "teacher_policy": "policyabc0123",
                           "strategy": {"lr": .00013, "depth": 2, "contrast": 1},
                           "source_training_accuracy_before": .50,
                           "source_training_accuracy_after": 1.0,
                           "teacher_reward": .5, "loss": .123,
                           "gradient_norm": 1.2e-10, "next_phase": "MAIN"})
            for gen, score in ((3, 6), (6, 8)):
                ingest(board, exam("A", gen, "rubric-a",
                                   {"A.IDENTITY": (score, 12)}, step=116776 + gen))
            display = board.render(width=276, height=40)
            self.assertIn("LOSS", display)
            self.assertIn("GRAD", display)
            self.assertIn("FIRST", display)
            self.assertIn("LATEST", display)
            self.assertIn("BEST", display)
            self.assertIn("TO100", display)
            self.assertIn("GAIN", display)
            self.assertIn("+2", display)
            self.assertIn("1.2e-10", display)

    def test_generalization_gap_is_observational_not_an_optimizer_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "SCHOOL_VISIT_COMMITTED", "grade": "B",
                           "capability": "B.RULE", "generation": 1,
                           "optimizer_step": 150000,
                           "source_training_accuracy_before": 1.,
                           "source_training_accuracy_after": 1.,
                           "teacher_reward": 0., "teacher_policy": "existing"})
            ingest(board, exam("B", 2, "rubric-b", {"B.RULE": (6, 12)},
                               step=150000))
            self.assertTrue(any("GENERALIZATION GAP" in line
                                for line in board.operator_lines))
            self.assertTrue(any("recent source-train" in line.lower()
                                for line in board.operator_lines))
            self.assertEqual(board.rows["GRADES & MASTERY"][-1]["to100"], "6")

    def test_historical_champion_does_not_hide_latest_grade_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "state.json").write_text(json.dumps({
                "school": {"active_grades": ["A", "B"],
                           "current_student": {"optimizer_step": 123400},
                           "champions": {"A": {"optimizer_step": 123000}},
                           "stage": "MAIN", "visits": 4},
                "teacher": {"events": 10}, "result": "ACTIVE_SCHOOL"}))
            board = build(run, stream=io.StringIO())
            ingest(board, exam("B", 5, "rubric-a+b", {
                "A.IDENTITY": (7, 12), "B.FOCUS": (8, 12)},
                step=123400, sha="student-B-step"))
            latest_a = next(x for x in board._section_rows("GRADES & MASTERY")
                            if x["grade"] == "A")
            self.assertTrue(latest_a["mastered"])
            self.assertIn("CURRENT REGRESSION", latest_a["outcome"])
            self.assertEqual(latest_a["latest"], "7/12")
            self.assertEqual(board.state["prefix"], "B")
            self.assertEqual(board.grade_program, ("A", "B"))


if __name__ == "__main__":
    unittest.main()
