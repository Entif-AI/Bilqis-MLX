"""Rendering projection behavior from the original School50 suite."""
import io
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from bilqis_mlx.presentation.dashboard import build
from bilqis_mlx.presentation.school_telemetry import LETTER_TABLES
from bilqis_mlx.presentation.spiral_dashboard import Dashboard


class RenderingTests(unittest.TestCase):
    def test_middle_pane_keeps_only_live_teacher_controls_and_compact_system_feed(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            tables = dict(board.tables)
            self.assertEqual(
                [(column.name, column.width) for column in tables["SOUP & TEACHER"]],
                [
                    ("CAPABILITY", 10), ("VISIT", 5), ("POLICY", 10),
                    ("LR", 2), ("D", 1), ("C", 1), ("OLD", 3),
                    ("DSTIL", 5), ("CREDIT", 7), ("P(RET)", 6), ("HEALTH", 9),
                ],
            )
            self.assertEqual(
                [(column.name, column.width)
                 for column in tables["SYSTEM & QUALIFICATION"]],
                [("TYPE", 7), ("DETAILS", 32)],
            )
            board.rows["SYSTEM & QUALIFICATION"].append({
                "kind": "DIAGNOSTIC", "grade": "B",
                "detail": "active S2:B.OR | 14 NOT MEASURED",
            })
            system = board._section_rows("SYSTEM & QUALIFICATION")[-1]
            self.assertEqual(system["detail"], "S2[OR] 14 NM")

            rendered = board.render(width=210, height=40)
            self.assertIn(" | ", rendered.splitlines()[5])
            self.assertIn("SOUP & TEACHER", rendered)
            self.assertIn("SYSTEM & QUALIFICATION", rendered)
            self.assertNotIn("SOUP_KL", rendered)
            self.assertNotIn("COVER", rendered)
            self.assertNotIn("PREVIEW", rendered)
            self.assertNotIn("PAR_KL", rendered)
            self.assertNotIn("BRG_CE", rendered)

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

    def test_letter_school_uses_single_cockpit_header_and_blank_spacer(self):
        board = Dashboard(
            stream=io.StringIO(),
            clock=lambda: 136045.0,
            show_all_panels=True,
            tables=LETTER_TABLES,
            title="BILQIS",
            compact_header=True,
        )
        board.started = 0.0
        board.time_budget_seconds = 288000
        board.run_name = "codex-0001-prometheus"
        board.mode = "LIVE"
        board.state.update(
            phase="MAIN",
            prefix="A",
            next="-",
            failures="?",
            max_failures="?",
            step=126136,
            visits=3221,
            teacher=7480,
            retained_visits=5,
            stop="RUNNING",
        )
        board._steps_per_min = 186
        board.rows["GRADES & MASTERY"].extend([
            {"grade": "A", "step": 126120, "attempt": 5833,
             "start": "71/72", "latest": "71/72", "best": "71/72",
             "outcome": "NO TITLE CHANGE"},
            {"grade": "B", "step": 126120, "attempt": 5833,
             "start": "38/72", "latest": "38/72", "best": "38/72",
             "outcome": "NO TITLE CHANGE"},
        ])
        for grade in ("A", "B"):
            for index in range(6):
                board.rows["BRIDGE FAMILIES"].append({
                    "grade": grade,
                    "family": f"{grade}.C{index}",
                    "step": 126120,
                    "attempt": 5833,
                    "start": "6/12",
                    "before": "-",
                    "after": "6/12",
                    "gain": "-",
                })
        cumulative_key = (("A", "B"), "rubric", "scope")
        board.school_telemetry = SimpleNamespace(
            cumulative_latest=(
                cumulative_key, 109, 144, 126120, "144/144 REQUIRED"),
            cumulative_best={cumulative_key: (109, 144, 126120)},
        )
        board.operator_lines = [
            "START GENERATED SAMPLE B 38/72 @step 126120 | LATEST B 38/72",
            "TO100 34/72 wrong (fresh sampled cohort)",
            "CUMULATIVE A+B: latest 109/144 @step 126120",
        ]

        rendered = board.render(width=210, height=40)
        lines = rendered.splitlines()
        headings, values = lines[:2]
        for heading in (
                "BILQIS", "RUNTIME", "MAX TIME", "STEPS", "EXAM", "VISITS",
                "TEACHER", "GRADES", "CAPS", "STUDENT LATEST", "STUDENT BEST",
                "ST/M", "RTN", "RTN%", "GREW", "R/H", "RUN"):
            self.assertIn(heading, headings)
        self.assertIn("A:MAIN", values)
        self.assertIn("1d 13h 47m 25s", values)
        self.assertIn("47% / 3d 8h max", values)
        self.assertIn("126136", values)
        self.assertIn("5833", values)
        self.assertIn("3221", values)
        self.assertIn("7480", values)
        self.assertIn("109/144 @126120", values)
        self.assertIn("codex-0001-prometheus", values)
        self.assertEqual(lines[2], "")
        self.assertNotIn("RUNNING", rendered)
        self.assertNotIn("raw log:", rendered)
        self.assertNotIn("SCHOOL50", rendered)
        self.assertNotIn("START GENERATED SAMPLE", rendered)
        self.assertNotIn("TO100 34/72", rendered)
        self.assertNotIn("CUMULATIVE A+B:", rendered)

    def test_system_feed_compacts_known_rows_and_keeps_latest_state_per_kind_and_grade(self):
        board = Dashboard(stream=io.StringIO(), show_all_panels=True,
                          tables=LETTER_TABLES)
        system = board.rows["SYSTEM & QUALIFICATION"]
        system.extend([
            {"kind": "DIAGNOSTIC", "grade": "B",
             "detail": "active S1:B.AND, S2:B.IFF | S3 unavailable | 14 NOT MEASURED"},
            {"kind": "TEACH OUTCOME", "grade": "B",
             "detail": "NOT_MEASURED_CHANGED_EXAM x3"},
            {"kind": "CAP BEST", "grade": "B",
             "detail": ("Best slots: A.LINK 12/12, A.PARENT 12/12, "
                        "B.IFF 8/12, B.OR 7/12 at step 125944 | NOT grade mastery")},
            {"kind": "CHAMPION", "grade": "B",
             "detail": "No title change: DENY_EARNING_QUESTION_REGRESSION | step 125944"},
            {"kind": "DIAGNOSTIC", "grade": "B",
             "detail": ("active S2:B.IFF, S2:B.NOT, S2:B.OR | "
                        "S3 unavailable | 14 NOT MEASURED")},
        ])

        rows = board._section_rows("SYSTEM & QUALIFICATION")
        self.assertEqual(
            [row["kind"] for row in rows],
            ["B:TEACH", "B:CHAMP", "B:DIAG"],
        )
        self.assertEqual(rows[0]["detail"], "NM CHANGED EXAM x3")
        self.assertEqual(rows[1]["detail"], "NO TITLE: DENY QUESTION REG @125944")
        self.assertEqual(rows[2]["detail"], "S2[IFF,NOT,OR] S3 OFF 14 NM")
