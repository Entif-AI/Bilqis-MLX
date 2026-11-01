"""Render rendering preserves receipt-backed operator evidence."""
import io
from pathlib import Path
import tempfile
import unittest
from bilqis_mlx.presentation.dashboard import ingest
from bilqis_mlx.presentation.school_telemetry import LETTER_TABLES
from bilqis_mlx.presentation.spiral_dashboard import Dashboard
from bilqis_mlx.presentation.tests.school50.fixtures import exam
from types import SimpleNamespace
from bilqis_mlx.presentation.dashboard import build
from bilqis_mlx.presentation.school_telemetry import LETTER_TABLES
from bilqis_mlx.presentation.dashboard import build, ingest


class RenderTests(unittest.TestCase):
    def test_compact_header_reports_stable_run_metrics(self):
        board = Dashboard(
            stream=io.StringIO(), clock=lambda: 1800.0,
            show_all_panels=True, tables=LETTER_TABLES,
            compact_header=True)
        board.started = 0.0
        board.state.update(retained_visits=5, visits=20, attempted_steps=5400)
        board._rate_step = 5383
        board._rate_time = 1740.0

        board._sample_step_rate()
        headings, values = board.render(width=260, height=20).splitlines()[:2]

        start = headings.index("R/H")
        self.assertEqual(values[start:start + 5].strip(), "10")
        start = headings.index("RTN%")
        self.assertEqual(values[start:start + 5].strip(), "25")
        start = headings.index("ST/M")
        self.assertEqual(values[start:start + 5].strip(), "180")

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
            self.assertIn("WAS/CHP/NOW/ALL", display)
            self.assertIn("GOOD [GREW]", display)
            self.assertIn("67% [+17%]", display)
            self.assertNotIn("BRIDGE FAMILIES", display)
            self.assertIn("0.00", display)
