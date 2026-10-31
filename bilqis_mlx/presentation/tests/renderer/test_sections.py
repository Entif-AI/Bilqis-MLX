"""Sections rendering preserves receipt-backed operator evidence."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from bilqis_mlx.presentation.dashboard import ingest
from bilqis_mlx.presentation.school_telemetry import LETTER_TABLES, SchoolTelemetry
from bilqis_mlx.presentation.spiral_dashboard import Dashboard
from bilqis_mlx.presentation.tests.school50.fixtures import exam
from bilqis_mlx.presentation.dashboard import build
from bilqis_mlx.presentation.school_telemetry import LETTER_TABLES
from bilqis_mlx.presentation.dashboard import build, ingest


class SectionsTests(unittest.TestCase):
    def test_grew_averages_active_capabilities_including_stagnation_withheld(self):
        board = Dashboard(
            stream=io.StringIO(), clock=lambda: 3600.0,
            show_all_panels=True, tables=LETTER_TABLES,
            compact_header=True)
        board.started = 0.0
        board.school_telemetry = SchoolTelemetry(
            board, active_grades=("A", "B"), champions={})
        for grade, scores in (
                ("A", {"A.IDENTITY": (5, 10), "A.LINK": (5, 10)}),
                ("B", {"B.AND": (5, 10), "B.OR": (5, 10)})):
            ingest(board, exam(grade, 1, f"rubric-{grade}", scores, step=100))
        board.school_telemetry.begin_execution(grade="B", step=100)
        ingest(board, exam("A", 2, "rubric-A", {
            "A.IDENTITY": (7, 10), "A.LINK": (6, 10)}, step=120))
        ingest(board, exam("B", 2, "rubric-B", {
            "B.AND": (4, 10), "B.OR": (7, 10)}, step=120))
        ingest(board, {
            "event": "SCHOOL_GRADE_RELEASE_REPLACED", "grade": "B",
            "generation": 3, "optimizer_step": 120,
            "old_capabilities": ["B.AND", "B.OR"],
            "new_capabilities": ["B.AND"],
            "withheld_capabilities": ["B.OR"],
        })

        self.assertEqual(board.state["grew"], 10)
        headings, values = board.render(width=260, height=20).splitlines()[:2]
        start = headings.index("GREW")
        self.assertEqual(values[start:start + 5].strip(), "+10")

    def test_compact_visit_panels_share_capability_and_numeric_width_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            capability = "B.VERYLONGCAPABILITY"
            (root / "state.json").write_text(json.dumps({
                "mentor_epoch": {"active_roles": {
                    capability: {
                        "capability": capability,
                        "correct": 9,
                        "total": 12,
                        "breadth": 4,
                        "checkpoint": {
                            "sha256": "a" * 64,
                            "optimizer_step": 125000,
                        },
                    },
                }},
            }))
            board = Dashboard(stream=io.StringIO(), show_all_panels=True,
                              tables=LETTER_TABLES)
            board.school_telemetry = SchoolTelemetry(board, active_grades=("B",))
            board.attach_champion_source(root)
            ingest(board, {
                "event": "SCHOOL_TEACHER_VISIT_COMMITTED",
                "grade": "B", "capability": capability,
                "optimizer_step": 125016,
                "attempted_optimizer_updates": 16,
                "retained_optimizer_updates": 0,
                "strategy": {
                    "lr": 0.00013, "depth": 2, "contrast": 1.4,
                    "old": 16.2, "preview": 2, "distill": 0.35,
                },
                "loss": 0.5583400726,
                "gradient_norm": 14.004,
                "teacher_decision": {
                    "warning_signals": [
                        "CHANCE_LEVEL_OR_LAGGING",
                        "LACK_OF_DURABLE_GAIN",
                    ],
                    "selected": {"exam_mistake_replay": 3},
                },
                "candidate_retention": {
                    "active_capability": capability,
                    "active_probe_before": 10,
                    "active_probe_after": 8,
                    "active_probe_total": 12,
                    "local_correct_delta": -2,
                    "protected_net_correct_delta": 0,
                    "worst_protected_loss": 0,
                    "decision": "REJECT",
                    "reason": "NO_MEASURABLE_TARGET_GAIN",
                },
            })

            tables = dict(LETTER_TABLES)
            self.assertEqual(
                [(c.name, c.width) for c in tables["CANDIDATES"]],
                [
                    ("CAPABILITY", 10), ("VISIT", 5), ("POLICY", 10),
                    ("LR", 2), ("WAS/CHP/NOW/ALL", 15), ("REWARD", 6),
                    ("LOSS", 5), ("GRAD", 5), ("METHOD", 6),
                    ("OLD pp", 6), ("RESULT", 6), ("REASON", 27),
                    ("WARNINGS", 12),
                ],
            )
            self.assertEqual(
                [(c.name, c.width) for c in tables["SENTINEL & RETENTION"]],
                [
                    ("CAPABILITY", 10), ("VISIT", 5), ("TARGET", 8),
                    ("DTG", 3), ("PRT", 3), ("WRS", 3),
                    ("RSULT", 5), ("EVIDENCE", 20),
                ],
            )
            self.assertEqual(
                [(c.name, c.width) for c in tables["SOUP & TEACHER"][:7]],
                [
                    ("CAPABILITY", 10), ("VISIT", 5), ("POLICY", 10),
                    ("LR", 2), ("D", 1), ("C", 1), ("OLD", 3),
                ],
            )
            self.assertEqual(tables["GRADES & MASTERY"][0].name, "CAPABILITY")
            self.assertEqual(tables["GRADES & MASTERY"][0].width, 10)
            self.assertEqual(
                (tables["GRADES & MASTERY"][1].name,
                 tables["GRADES & MASTERY"][1].width),
                ("WAS/TOP/NOW/ALL", 15),
            )
            growth = next(
                column for column in tables["GRADES & MASTERY"]
                if column.key == "right_grew"
            )
            self.assertLessEqual(growth.width, 12)

            candidate = board.rows["CANDIDATES"][-1]
            self.assertEqual(candidate["lr"], "13")
            self.assertEqual(candidate["score_line"], " 10/  9/  8/ 12")
            self.assertEqual(candidate["gradient"], "14.00")
            self.assertEqual(candidate["result"], "REJECT")
            self.assertEqual(candidate["reason"], "NO TARGET GAIN")
            self.assertEqual(candidate["warnings"], "S2,S3")

            retention = board.rows["SENTINEL & RETENTION"][-1]
            self.assertEqual(retention["capability"], capability)
            self.assertEqual(retention["decision"], "REJECT")

            soup = board.rows["SOUP & TEACHER"][-1]
            self.assertEqual(soup["capability"], capability)
            self.assertEqual(soup["lr"], "13")
            self.assertEqual(soup["depth"], "2")
            self.assertEqual(soup["contrast"], "1")
            self.assertEqual(soup["old"], "16")

            rendered = board.render(width=180, height=44)
            self.assertNotIn(capability, rendered)
            self.assertIn("B.VERYLON~", rendered)

    def test_mastery_growth_keeps_right_and_grew_subcolumns_aligned(self):
        board = Dashboard(stream=io.StringIO(), show_all_panels=True,
                          tables=LETTER_TABLES)
        board.rows["GRADES & MASTERY"].extend([
            {"grade": "A", "step": 1, "attempt": 1, "start": "12/12",
             "latest": "12/12", "best": "12/12", "outcome": "PASS"},
            {"grade": "B", "step": 1, "attempt": 1, "start": "12/12",
             "latest": "9/12", "best": "12/12", "outcome": "REGRESSED"},
        ])
        rows = [row for row in board._section_rows("GRADES & MASTERY")
                if row.get("row_type") == "summary"]
        self.assertEqual(rows[0]["right_grew"], "100% [  0%]")
        self.assertEqual(rows[1]["right_grew"], " 75% [-25%]")
        self.assertEqual(
            rows[0]["right_grew"].index("["),
            rows[1]["right_grew"].index("["),
        )

    def test_historical_generalization_does_not_replace_active_mastery(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            common = {
                "event": "SCHOOL_LIVE_EXAM_COMMITTED", "grade": "B",
                "rubric": "b" * 64, "assessment_scope_sha256": "1" * 64,
                "generator_version": "factory-live/v1", "optimizer_step": 127096,
                "student_sha256": "d" * 64,
            }
            ingest(board, {**common, "generation": 1, "exam_plane": "ROUTINE",
                "cohort_sha256": "2" * 64, "cohort_file": f"cohorts/{'2' * 64}.json",
                "scores": {"B.AND": {"correct": 12, "total": 12}}})
            ingest(board, {**common, "generation": 2, "exam_plane": "GENERALIZATION",
                "cohort_sha256": "3" * 64, "cohort_file": f"cohorts/{'3' * 64}.json",
                "scores": {"B.AND": {"correct": 5, "total": 12}}})

            report = next(iter(board.school_telemetry.latest.values()))
            self.assertEqual((report.correct, report.total), (12, 12))
            self.assertIn("LATEST B 12/12", " ".join(board.operator_lines))
            self.assertTrue(any(row.get("kind") == "HISTORICAL GENERALIZATION"
                                for row in board.rows["SYSTEM & QUALIFICATION"]))
