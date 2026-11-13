"""Exams projection behavior from the original School50 suite."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from bilqis_mlx.presentation.dashboard import build, ingest
from bilqis_mlx.presentation.school_telemetry import LETTER_TABLES
from bilqis_mlx.presentation.spiral_dashboard import Dashboard
from bilqis_mlx.presentation.tests.school50.fixtures import exam


class ExamsTests(unittest.TestCase):
    def test_champion_child_latest_scores_match_latest_family_cohort(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            roles = {}
            current = {
                "A.ONE": (10, 12),
                "A.TWO": (11, 12),
                "A.THREE": (8, 12),
                "A.FOUR": (9, 12),
                "A.FIVE": (7, 12),
                "A.SIX": (10, 12),
            }
            for index, capability in enumerate(current):
                roles[capability] = {
                    "capability": capability,
                    "correct": 12,
                    "total": 12,
                    "breadth": 6 - index,
                    "checkpoint": {
                        "sha256": f"{index + 1:064x}",
                        "optimizer_step": 100 + index,
                    },
                }
            (root / "state.json").write_text(json.dumps({
                "mentor_epoch": {"active_roles": roles},
            }))

            board = Dashboard(stream=io.StringIO(), show_all_panels=True,
                              tables=LETTER_TABLES)
            board.rows["GRADES & MASTERY"].append({
                "grade": "A", "step": 300, "start": "60/72", "latest": "55/72",
                "best": "72/72", "to100": "17", "right_pct": "76.4%",
                "outcome": "SUMMARY",
            })
            for capability, (correct, total) in current.items():
                board.rows["BRIDGE FAMILIES"].append({
                    "grade": "A", "family": capability,
                    "start": "12/12", "before": "-", "after": f"{correct}/{total}",
                    "gain": "-", "attempt": 300, "step": 300,
                })
            board.attach_champion_source(root)

            rows = board._section_rows("GRADES & MASTERY")
            champions = [row for row in rows if row.get("row_type") == "champion"]
            bridge = {row["family"]: row["after"]
                      for row in board._section_rows("BRIDGE FAMILIES")}
            self.assertEqual(
                {row["capability"]: row["latest"] for row in champions},
                bridge,
            )
            self.assertEqual(
                sum(int(row["latest"].split("/", 1)[0]) for row in champions),
                55,
            )
            self.assertTrue(all(row["best"] == "12/12" for row in champions))

    def test_header_latest_uses_newest_generation_across_assessment_scopes(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            for generation, scope, correct, step in (
                (1, "1" * 64, 4, 100),
                (2, "2" * 64, 5, 110),
                (3, "1" * 64, 9, 120),
            ):
                event = exam(
                    "B", generation, "rubric-b",
                    {"B.FOCUS": (correct, 12)}, step=step)
                event["assessment_scope_sha256"] = scope
                ingest(board, event)

            self.assertIn("LATEST B 9/12 @step 120", board.operator_lines[0])
            mastery = next(
                row for row in board._section_rows("GRADES & MASTERY")
                if row["grade"] == "B" and row.get("row_type") == "summary")
            family = next(
                row for row in board._section_rows("BRIDGE FAMILIES")
                if row["family"] == "B.FOCUS")
            self.assertEqual(mastery["latest"], "9/12")
            self.assertEqual(family["after"], "9/12")

    def test_rotating_live_cohort_exams_never_report_cross_sample_gain(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            for number, total in ((1, 5), (2, 9)):
                ingest(board, {
                    "event": "GRADE_A_LIVE_EXAM_COMMITTED",
                    "generation": number, "rubric": "a"*64,
                    "cohort_sha256": str(number)*64,
                    "generator_version": "grade-a-live/v1",
                    "cohort_file": f"cohorts/{str(number)*64}.json",
                    "optimizer_step": 100 + number,
                    "student_sha256": str(number)*64,
                    "scores": {"A.IDENTITY": {"correct": total, "total": 12}},
                })
            latest = board._section_rows("BRIDGE FAMILIES")[-1]
            self.assertEqual(latest["before"], "-")
            self.assertEqual(latest["gain"], "-")
            self.assertFalse(board._section_rows("SENTINEL & RETENTION"))
            self.assertIn(
                "BEST OBSERVED SAMPLE (not paired)",
                " ".join(board.operator_lines),
            )
            self.assertIn("fresh sampled cohort", " ".join(board.operator_lines))
            rendered = board.render(width=180, height=42)
            self.assertNotIn("BEST OBSERVED SAMPLE (not paired)", rendered)
            self.assertNotIn("fresh sampled cohort", rendered)

    def test_current_score_grade_precedes_historical_capability_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {
                "event": "SCHOOL_LIVE_EXAM_COMMITTED", "grade": "Z",
                "generation": 1, "rubric": "z" * 64,
                "cohort_sha256": "c" * 64,
                "cohort_file": f"cohorts/{'c' * 64}.json",
                "generator_version": "current-generic/v1",
                "optimizer_step": 101, "student_sha256": "s" * 64,
                "scores": {"A.HISTORICAL": {
                    "grade": "Y", "correct": 9, "total": 12}},
            })
            family = board.rows["BRIDGE FAMILIES"][-1]
            self.assertEqual(family["grade"], "Y")
            self.assertIn("Z NOT EVALUATED IN THIS SAMPLE", " ".join(
                row["detail"] for row in board.rows["SYSTEM & QUALIFICATION"]
                if row["kind"] == "EXAM SCOPE"))

    def test_historical_live_exam_keeps_grade_and_rendered_live_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {
                "event": "GRADE_A_LIVE_EXAM_COMMITTED", "generation": 1,
                "rubric": "a" * 64, "cohort_sha256": "d" * 64,
                "cohort_file": f"cohorts/{'d' * 64}.json",
                "generator_version": "grade-a-live/v1", "optimizer_step": 100,
                "student_sha256": "e" * 64,
                "scores": {"A.IDENTITY": {"correct": 10, "total": 12}},
            })
            self.assertEqual(board.rows["BRIDGE FAMILIES"][-1]["grade"], "A")
            self.assertIn("BEST OBSERVED SAMPLE (not paired)", " ".join(
                board.operator_lines))

    def test_both_grades_use_live_144_item_cohorts_without_unpaired_gains(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp),stream=io.StringIO())
            for index, a_score, b_score in ((1,65,41),(2,70,49)):
                ingest(board,{"event":"SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED",
                    "grade":"B", "generation":index,
                    "rubric":"b"*64, "cohort_sha256":str(index)*64,
                    "generator_version":"bilqis.mlx.grade-b-connectives-constructor/v1",
                    "cohort_file":f"cohorts/{str(index)*64}.json",
                    "optimizer_step":153144+index,
                    "student_sha256":str(index)*64,
                    "scores":{
                        "A.IDENTITY":{"correct":a_score%12,"total":12},
                        "A.PARENT":{"correct":a_score//12,"total":12},
                        "B.NOT":{"correct":b_score%12,"total":12},
                        "B.AND":{"correct":b_score//12,"total":12}},
                })
            mastery = {row["grade"]:row for row in
                       board._section_rows("GRADES & MASTERY")
                       if row.get("row_type") == "summary"}
            self.assertEqual(set(mastery),{"A","B"})
            self.assertEqual(mastery["B"]["latest"],"5/24")
            self.assertEqual(board._section_rows("BRIDGE FAMILIES")[-1]["gain"],"-")
            self.assertFalse(board._section_rows("SENTINEL & RETENTION"))
