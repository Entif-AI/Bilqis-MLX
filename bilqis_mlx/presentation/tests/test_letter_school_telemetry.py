"""Grade-neutral School50 evidence, including future grades and empty channels."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from bilqis_mlx.presentation.dashboard import build, ingest
from bilqis_mlx.presentation.school_telemetry import LETTER_TABLES, SchoolTelemetry
from bilqis_mlx.presentation.spiral_dashboard import Dashboard, TABLES


def exam(grade, generation, rubric, scores, *, step, sha="signed-model"):
    return {"event": "SCHOOL_EXAM_COMMITTED", "grade": grade,
            "generation": generation, "rubric": rubric,
            "optimizer_step": step, "student_sha256": sha, "phase": "MAIN",
            "scores": {cap: {"correct": correct, "total": total}
                       for cap, (correct, total) in scores.items()}}


class SchoolTelemetryTests(unittest.TestCase):
    def test_grade_release_replacement_removes_obsolete_curriculum_from_live_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {
                "event": "SCHOOL_TEACHER_VISIT_COMMITTED",
                "grade": "B",
                "generation": 10,
                "capability": "B.OR",
                "optimizer_step": 100,
                "retained_optimizer_updates": 0,
            })
            ingest(board, exam(
                "B", 11, "old-rubric",
                {cap: (6, 12) for cap in (
                    "B.NOT", "B.AND", "B.OR", "B.XOR",
                    "B.IMPLIES", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS")},
                step=100))
            ingest(board, {
                "event": "SCHOOL_GRADE_RELEASE_REPLACED",
                "grade": "B",
                "generation": 12,
                "old_capabilities": [
                    "B.NOT", "B.AND", "B.OR", "B.XOR",
                    "B.IMPLIES", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS"],
                "new_capabilities": [
                    "B.AND", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS"],
                "withheld_capabilities": [
                    "B.NOT", "B.OR", "B.XOR", "B.IMPLIES"],
            })
            self.assertNotIn(
                "B.OR",
                {row.get("capability") for row in board.rows["CANDIDATES"]})
            self.assertFalse(any(
                row.get("grade") == "B"
                for row in board._section_rows("GRADES & MASTERY")
                if row.get("row_type") == "summary"))
            self.assertTrue(any(
                row.get("kind") == "CURRICULUM" and
                "B.AND, B.IFF, B.COMPOSITE, B.IDBOOLOPS" in row.get("detail", "")
                for row in board.rows["SYSTEM & QUALIFICATION"]))

    def test_session_start_reanchors_start_score_without_erasing_historical_best(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, exam("A", 10, "rubric-a", {"A.IDENTITY": (7, 12)},
                               step=100))
            ingest(board, exam("A", 20, "rubric-a", {"A.IDENTITY": (10, 12)},
                               step=120))
            ingest(board, {"event": "SCHOOL_SESSION_STARTED", "grade": "A",
                           "generation": 20, "optimizer_step": 120,
                           "checkpoint_sha256": "a" * 64})
            ingest(board, exam("A", 30, "rubric-a", {"A.IDENTITY": (8, 12)},
                               step=136))

            mastery = next(
                row for row in board._section_rows("GRADES & MASTERY")
                if row.get("row_type") == "summary"
            )
            self.assertEqual(mastery["start"], "10/12")
            self.assertEqual(mastery["latest"], "8/12")
            self.assertEqual(mastery["best"], "10/12")
            self.assertIn("START", " ".join(board.operator_lines))
            display = board.render(width=180, height=42)
            self.assertNotIn("START", display)
            self.assertNotIn("FIRST", display)

    def test_method_column_projects_actual_instruction_mechanism(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {
                "event": "SCHOOL_TEACHER_VISIT_COMMITTED",
                "grade": "B", "active_grade": "C", "capability": "B.IFF",
                "optimizer_step": 232472, "retained_optimizer_updates": 0,
                "teacher_decision": {"selected": {
                    "exam_mistake_replay": 128,
                    "prerequisite_connections": [],
                    "champion_priority": 0,
                }},
                "boolean_association_bridge": {
                    "active_for_visit": True,
                    "borrowed_source_grades": ["A", "C"],
                    "delivered_examples": 128,
                },
            })
            self.assertEqual(board.rows["CANDIDATES"][-1]["method"], "COMPOSE+MISS")

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
                    ("LR", 2), ("WAS/TOP/NOW/ALL", 15), ("REWARD", 6),
                    ("LOSS", 5), ("GRAD", 5), ("METHOD", 6),
                    ("OLDpp", 8), ("RESULT", 6), ("REASON", 24),
                    ("WARNINGS", 10),
                ],
            )
            self.assertEqual(
                [(c.name, c.width) for c in tables["SENTINEL & RETENTION"]],
                [
                    ("CAPABILITY", 10), ("VISIT", 5), ("TARGET", 8),
                    ("DTGT", 4), ("PROT", 4), ("WRST", 4),
                    ("RESULT", 6), ("EVIDENCE", 20),
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

    def test_middle_pane_keeps_only_live_teacher_controls_and_compact_system_feed(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            tables = dict(board.tables)
            self.assertEqual(
                [(column.name, column.width) for column in tables["SOUP & TEACHER"]],
                [
                    ("CAPABILITY", 10), ("VISIT", 5), ("POLICY", 10),
                    ("LR", 2), ("D", 1), ("C", 1), ("OLD", 3),
                    ("DSTIL", 5), ("CREDIT", 7),
                ],
            )
            self.assertEqual(
                [(column.name, column.width)
                 for column in tables["SYSTEM & QUALIFICATION"]],
                [("TYPE", 7), ("DETAILS", 38)],
            )

            board.rows["SYSTEM & QUALIFICATION"].append({
                "kind": "DIAGNOSTIC", "grade": "B",
                "detail": "active S2:B.OR | 14 NOT MEASURED",
            })
            system = board._section_rows("SYSTEM & QUALIFICATION")[-1]
            self.assertEqual(
                system["detail"],
                "S2[OR] 14 NM",
            )

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

    def test_curriculum_header_reports_visibility_and_trained_score(self):
        board = Dashboard(stream=io.StringIO(), show_all_panels=True,
                          tables=LETTER_TABLES)
        board.state.update(_all_grade_correct=100, _all_grade_total=144)
        board.rows["GRADES & MASTERY"].extend([
            {"grade": "A", "step": 126056, "attempt": 5789,
             "start": "70/72", "latest": "63/72", "best": "72/72",
             "outcome": "NO TITLE CHANGE"},
            {"grade": "B", "step": 126056, "attempt": 5789,
             "start": "33/72", "latest": "37/72", "best": "47/72",
             "outcome": "NO TITLE CHANGE"},
        ])
        for grade in ("A", "B"):
            for index in range(6):
                board.rows["BRIDGE FAMILIES"].append({
                    "grade": grade,
                    "family": f"{grade}.C{index}",
                    "step": 126056,
                    "attempt": 5789,
                    "start": "6/12",
                    "before": "-",
                    "after": "6/12",
                    "gain": "-",
                })

        available = board._section_rows("GRADES & MASTERY")
        self.assertEqual(
            board._section_label(
                "GRADES & MASTERY", len(available), available, available),
            "CURRICULUM [14/14 visible]: 100/144 (69.4%) TRAINED",
        )
        rendered = board.render(width=210, height=60)
        self.assertIn(
            "CURRICULUM [14/14 visible]: 100/144 (69.4%) TRAINED",
            rendered,
        )
        self.assertNotIn("TRAIN: S 126056", rendered)

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
                "STEPS/MIN", "RETAINED", "RUN"):
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

    def test_candidate_retention_populates_retention_panel_with_real_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {
                "event": "SCHOOL_TEACHER_VISIT_COMMITTED",
                "grade": "B", "capability": "B.IFF", "optimizer_step": 232472,
                "attempted_optimizer_updates": 16, "retained_optimizer_updates": 0,
                "candidate_retention": {
                    "active_probe_before": 10, "active_probe_after": 8,
                    "active_probe_total": 12, "local_correct_delta": -2,
                    "protected_net_correct_delta": 0, "worst_protected_loss": 0,
                    "decision": "REJECT", "reason": "NO_MEASURABLE_TARGET_GAIN",
                    "unsampled_admitted_capabilities": 18,
                },
            })
            row = board.rows["SENTINEL & RETENTION"][-1]
            self.assertEqual(row["capability"], "B.IFF")
            self.assertEqual(row["target"], "10>8/12")
            self.assertEqual(row["target_delta"], "-2")
            self.assertEqual(row["protected"], "+0")
            self.assertEqual(row["worst"], "0")
            self.assertEqual(row["decision"], "REJECT")
            self.assertIn("NO_MEASURABLE_TARGET_GAIN", row["evidence"])

    def test_mastery_panel_lists_up_to_six_highest_scoring_champions_per_grade(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            roles = {}
            for index, (capability, correct, total, breadth, step) in enumerate((
                ("A.ONE", 11, 12, 1, 100),
                ("A.TWO", 12, 12, 2, 101),
                ("A.THREE", 12, 12, 5, 102),
                ("A.FOUR", 10, 12, 4, 103),
                ("A.FIVE", 9, 12, 3, 104),
                ("A.SIX", 8, 12, 2, 105),
                ("A.SEVEN", 7, 12, 1, 106),
                ("B.ONE", 9, 12, 1, 107),
            )):
                roles[capability] = {
                    "capability": capability,
                    "correct": correct,
                    "total": total,
                    "breadth": breadth,
                    "checkpoint": {
                        "sha256": f"{index + 1:064x}",
                        "optimizer_step": step,
                    },
                }
            (root / "state.json").write_text(json.dumps({
                "mentor_epoch": {"active_roles": roles},
            }))

            board = Dashboard(stream=io.StringIO(), show_all_panels=True,
                              tables=LETTER_TABLES)
            board.rows["GRADES & MASTERY"].extend([
                {"grade": "A", "step": 200, "start": "60/72", "latest": "70/72",
                 "best": "71/72", "to100": "2", "right_pct": "97.2%",
                 "outcome": "SUMMARY"},
                {"grade": "B", "step": 200, "start": "40/72", "latest": "50/72",
                 "best": "51/72", "to100": "22", "right_pct": "69.4%",
                 "outcome": "SUMMARY"},
            ])
            for capability, item in roles.items():
                board.rows["BRIDGE FAMILIES"].append({
                    "grade": capability.split(".", 1)[0],
                    "family": capability,
                    "step": 200,
                    "attempt": 9,
                    "start": f"{item['correct']}/{item['total']}",
                    "before": "-",
                    "after": f"{item['correct']}/{item['total']}",
                    "gain": "-",
                })
            board.attach_champion_source(root)

            rows = board._section_rows("GRADES & MASTERY")
            a_rows = [row for row in rows
                      if row.get("row_type") == "champion" and row["grade"] == "A"]
            self.assertEqual(len(a_rows), 6)
            self.assertEqual(
                {row["capability"] for row in a_rows},
                {"A.ONE", "A.TWO", "A.THREE", "A.FOUR", "A.FIVE", "A.SIX"},
            )
            seven = next(row for row in rows if row.get("capability") == "A.SEVEN")
            self.assertEqual(seven["row_type"], "family")
            three = next(row for row in a_rows if row["capability"] == "A.THREE")
            self.assertEqual(three["latest"], "12/12")
            self.assertEqual(three["best"], "12/12")
            self.assertIn("CHAMP @102", three["outcome"])
            self.assertEqual(rows[0]["row_type"], "summary")
            self.assertEqual(rows[8]["grade"], "B")
            self.assertEqual(rows[8]["row_type"], "summary")

            # Champion child rows must not replace grade summaries in the
            # dashboard's whole-school latest score calculation.
            self.assertEqual(board._latest_all_grade_score(), (120, 144))

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

    def test_mastery_panel_folds_family_rows_into_compact_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "state.json").write_text(json.dumps({
                "mentor_epoch": {"active_roles": {
                    "B.OR": {
                        "capability": "B.OR",
                        "correct": 7,
                        "total": 12,
                        "breadth": 5,
                        "checkpoint": {
                            "sha256": "a" * 64,
                            "optimizer_step": 125096,
                        },
                    },
                }},
            }))
            board = Dashboard(stream=io.StringIO(), show_all_panels=True,
                              tables=LETTER_TABLES)
            board.rows["GRADES & MASTERY"].append({
                "grade": "B", "step": 125656, "attempt": 5463,
                "start": "30/72", "latest": "39/72", "best": "47/72",
                "to100": "33", "right_pct": "54.2%",
                "outcome": "NO TITLE CHANGE | SAMPLE 39/72",
            })
            board.rows["BRIDGE FAMILIES"].append({
                "grade": "B", "family": "B.OR", "step": 125656,
                "attempt": 5463, "start": "5/12", "before": "6/12",
                "after": "8/12", "gain": "+2",
            })
            board.attach_champion_source(root)

            table_names = [name for name, _ in LETTER_TABLES]
            self.assertNotIn("BRIDGE FAMILIES", table_names)
            rows = board._section_rows("GRADES & MASTERY")
            summary, family = rows
            self.assertEqual(summary["subject"], "B")
            self.assertEqual(summary["score_line"], " 30/ 47/ 39/ 72")
            self.assertEqual(summary["right_grew"], " 54% [+13%]")
            self.assertEqual(summary["outcome"], "NO TITLE CHANGE")
            self.assertEqual(family["subject"], "B.OR")
            self.assertEqual(family["score_line"], "  5/  7/  8/ 12")
            self.assertEqual(family["right_grew"], " 67% [+25%]")
            self.assertEqual(family["outcome"], "CHAMP @125096 | br5")

            columns = dict(LETTER_TABLES)["GRADES & MASTERY"]
            self.assertEqual(
                [column.key for column in columns],
                ["subject", "score_line", "right_grew", "outcome"],
            )
            self.assertEqual(columns[0].name, "CAPABILITY")

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

    def test_retention_decision_not_instructional_note_controls_commit_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            for cap, decision, reason, updates in (
                ("C.NUMBER", "REJECT", "NO_MEASURABLE_TARGET_GAIN", 0),
                ("C.MUL", "REJECT", "FRAGILE_COMPOSITION_REPLAY_REGRESSION", 0),
                ("B.NOT", "PROVISIONAL", "PAIRED_SCREEN_WITHIN_BUDGET", 16),
            ):
                ingest(board, {
                    "event": "SCHOOL_TEACHER_VISIT_COMMITTED",
                    "capability": cap, "grade": cap[0],
                    "optimizer_step": 229512,
                    "retained_optimizer_updates": updates,
                    "candidate_retention": {"decision": decision, "reason": reason},
                    "teacher_decision": {"selected": {"exam_mistake_replay": 1}},
                })
            c_number, c_mul, b_not = list(board.rows["CANDIDATES"])[-3:]
            self.assertIn("REJECT", c_number["decision"])
            self.assertIn("NO TARGET GAIN", c_number["decision"])
            self.assertNotIn("LESSON COMMITTED", c_number["decision"])
            self.assertIn("REJECT", c_mul["decision"])
            self.assertIn("OR/XOR", c_mul["decision"])
            self.assertIn("RETAIN 16", b_not["decision"])
            self.assertIn("miss 1", b_not["decision"])
            self.assertNotIn("LESSON COMMITTED", b_not["decision"])

    def test_inconsistent_retention_metadata_does_not_claim_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "SCHOOL_TEACHER_VISIT_COMMITTED",
                "grade": "C", "capability": "C.NUMBER",
                "retained_optimizer_updates": 0,
                "candidate_retention": {"decision": "PROVISIONAL",
                                        "reason": "PAIRED_SCREEN_WITHIN_BUDGET"}})
            self.assertIn("ADMISSION CONFLICT",
                          board.rows["CANDIDATES"][-1]["decision"])

    def test_unavailable_longitudinal_history_names_the_actual_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "SCHOOL_LIVE_EXAM_COMMITTED", "grade": "B",
                "generation": 22, "rubric": "b" * 64,
                "cohort_sha256": "c" * 64, "optimizer_step": 123,
                "cohort_file": f"cohorts/{'c' * 64}.json",
                "generator_version": "test-fixed-b-cohort/v1",
                "student_sha256": "a" * 64,
                "scores": {"B.OR": {"correct": 11, "total": 12}},
                "learning_diagnostics": {
                    "active_warnings": [], "history_usable": False,
                    "history_issue": "DIAGNOSTIC_NON_MONOTONIC_CHECKPOINT_HISTORY",
                    "findings": [{"status": "NOT_MEASURED", "signal": "LACK_OF_DURABLE_GAIN",
                                  "capability": "B.OR"}]}})
            system = board.rows["SYSTEM & QUALIFICATION"]
            diagnostic = next(row for row in system if row["kind"] == "DIAGNOSTIC")
            self.assertIn("S3 unavailable", diagnostic["detail"])
            self.assertIn("1 NOT MEASURED", diagnostic["detail"])
            self.assertNotIn("no active warnings", diagnostic["detail"])
            history_error = next(row for row in system if row["kind"] == "HISTORY ISSUE")
            self.assertEqual(history_error["detail"],
                             "DIAGNOSTIC_NON_MONOTONIC_CHECKPOINT_HISTORY")

    def test_paired_s3_recovery_does_not_keep_unavailable_banner(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "SCHOOL_LIVE_EXAM_COMMITTED", "grade": "B",
                "generation": 23, "rubric": "b" * 64,
                "cohort_sha256": "d" * 64, "optimizer_step": 139,
                "cohort_file": f"cohorts/{'d' * 64}.json",
                "generator_version": "fresh-b-cohort/v2",
                "student_sha256": "e" * 64,
                "scores": {"B.OR": {"correct": 10, "total": 12}},
                "learning_diagnostics": {
                    "active_warnings": [{"signal": "LACK_OF_DURABLE_GAIN",
                                         "capability": "B.OR", "target": "CAPABILITY"}],
                    "history_usable": False, "s3_usable": True,
                    "history_issue": "DIAGNOSTIC_NON_MONOTONIC_CHECKPOINT_HISTORY",
                    "findings": [{"status": "OBSERVED_LONGITUDINALLY",
                                  "signal": "LACK_OF_DURABLE_GAIN",
                                  "capability": "B.OR"}]}})
            system = board.rows["SYSTEM & QUALIFICATION"]
            diagnostic = next(row for row in system if row["kind"] == "DIAGNOSTIC")
            self.assertIn("S3:B.OR", diagnostic["detail"])
            self.assertNotIn("S3 unavailable", diagnostic["detail"])
            history_error = next(row for row in system if row["kind"] == "HISTORY ISSUE")
            self.assertIn("paired S3 recovered", history_error["detail"])

    def test_candidate_probe_score_uses_same_compact_score_shape_as_mastery(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            labels = [column.name for column in dict(board.tables)["CANDIDATES"]]
            self.assertIn("WAS/TOP/NOW/ALL", labels)
            self.assertNotIn("LESSON% BFR>AFTER", labels)
            self.assertNotIn("TRAIN BEFORE>AFTER", labels)

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

    def test_independent_perfect_grade_bests_do_not_claim_cumulative_graduation(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            for generation, a, b in ((1, 12, 10), (2, 8, 12), (3, 11, 11)):
                ingest(board, {
                    "event": "SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED", "grade": "B",
                    "generation": generation, "rubric": "b" * 64,
                    "cohort_sha256": str(generation) * 64,
                    "generator_version": "grade-b-live/v1",
                    "cohort_file": f"cohorts/{str(generation)*64}.json",
                    "optimizer_step": 200 + generation,
                    "student_sha256": str(generation) * 64,
                    "phase": "RECOVERY_1",
                    "scores": {"A.IDENTITY": {"correct": a, "total": 12},
                               "B.NOT": {"correct": b, "total": 12}},
                })
            grades = {row["grade"]: row for row in
                      board._section_rows("GRADES & MASTERY")
                      if row.get("row_type") == "summary"}
            self.assertEqual(grades["A"]["best"], "12/12")
            self.assertEqual(grades["B"]["best"], "12/12")
            rows = [row for row in board.rows["SYSTEM & QUALIFICATION"]
                    if row["kind"] == "CUMULATIVE"]
            self.assertEqual(len(rows), 1)
            self.assertIn("latest 22/24", rows[0]["detail"])
            self.assertIn("best same student 22/24", rows[0]["detail"])
            self.assertIn("24/24 REQUIRED", rows[0]["detail"])
            self.assertIn("CUMULATIVE", " ".join(board.operator_lines))
            self.assertNotIn("QUALIFIED", " ".join(board.operator_lines))

            ingest(board, {"event": "SCHOOL_SESSION_STOPPED", "grade": "B",
                           "stop_reason": "TIME_LIMIT_REACHED",
                           "visits_this_command": 3, "elapsed_seconds": 5401.,
                           "optimizer_step": 203})
            self.assertIn("TIME_LIMIT_REACHED", board.mode)
            self.assertIn("24/24 REQUIRED", " ".join(board.operator_lines))

    def test_cumulative_perfect_requires_one_complete_scored_student(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED",
                "grade": "B", "generation": 1, "rubric": "b" * 64,
                "cohort_sha256": "c" * 64, "cohort_file": f"cohorts/{'c'*64}.json",
                "generator_version": "grade-b-live/v1", "optimizer_step": 300,
                "student_sha256": "d" * 64, "phase": "AWAITING_NEXT_GRADE",
                "scores": {"A.IDENTITY": {"correct": 12, "total": 12},
                           "B.NOT": {"correct": 12, "total": 12}}})
            rows = [row for row in board.rows["SYSTEM & QUALIFICATION"]
                    if row["kind"] == "CUMULATIVE"]
            self.assertEqual(len(rows), 1)
            self.assertIn("24/24", rows[0]["detail"])
            self.assertIn("GATE MET", rows[0]["detail"])

    def test_cumulative_backward_a_replay_shows_a_as_exam_target_not_b(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp),stream=io.StringIO())
            ingest(board,{"event":"SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED",
                "grade":"A","phase":"MAIN","generation":27,
                "rubric":"b"*64,"cohort_sha256":"8"*64,
                "generator_version":"bilqis.mlx.grade-b-connectives-constructor/v1",
                "cohort_file":f"cohorts/{'8'*64}.json",
                "optimizer_step":154008,"student_sha256":"8"*64,
                "scores":{"A.IDENTITY":{"correct":12,"total":12},
                           "B.NOT":{"correct":9,"total":12}}})
            self.assertEqual(board.school_telemetry.last_exam_grade,"A")
            self.assertIn("LATEST A 12/12",board.operator_lines[0])
            self.assertEqual(board.state["prefix"],"A")

    def test_saved_b_grade_dashboard_shows_current_cumulative_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            state = {"curriculum_mode":"bilqis.mlx.grade-a-b-live/20261015-v1",
                "result":"GRADE_B_REVALIDATING_A", "teacher":{"events":4000},
                "school":{"stage":"MAIN", "active_grades":["A","B"],
                    "grade_index":0,"visits":1000,
                    "current_student":{"optimizer_step":154000},
                    "champions":{}},"last_exam":None}
            (run/"state.json").write_text(json.dumps(state))
            board = build(run,stream=io.StringIO())
            source = next(row["detail"] for row in
                          board.rows["SYSTEM & QUALIFICATION"]
                          if row["kind"]=="RUBRIC")
            self.assertIn("generated 144",source)
            self.assertIn("same-checkpoint",source)

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
                           "loss": .467, "next_phase": "MAIN",
                           "teacher_decision": {
                               "warning_signals": ["DISCONNECTED_PREREQUISITES"],
                               "selected": {"exam_mistake_replay": 2,
                                            "champion_priority": 1},
                           }})
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
            self.assertIn("S4", candidate["decision"])
            self.assertIn("miss 2", candidate["decision"])
            self.assertIn("champ 1", candidate["decision"])
            self.assertFalse(board.rows["SENTINEL & RETENTION"])
            self.assertTrue(any("NOT MEASURED" in x["detail"]
                                for x in board.rows["SYSTEM & QUALIFICATION"]))

    def test_live_exam_projects_warning_and_teacher_outcome_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {
                "event": "SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED", "grade": "B",
                "generation": 8, "rubric": "b" * 64,
                "cohort_sha256": "c" * 64,
                "generator_version": "grade-b-live/v1",
                "cohort_file": f"cohorts/{'c'*64}.json",
                "optimizer_step": 200, "student_sha256": "d" * 64,
                "scores": {"B.NOT": {"correct": 6, "total": 12}},
                "learning_diagnostics": {
                    "active_warnings": [{"signal":"CHANCE_LEVEL_OR_LAGGING",
                                         "target":"CAPABILITY","capability":"B.NOT"}],
                    "findings": [{"signal":"CHANCE_LEVEL_OR_LAGGING",
                                  "status":"OBSERVED_IN_COHORT","capability":"B.NOT"},
                                 {"signal":"LACK_OF_DURABLE_GAIN",
                                  "status":"NOT_MEASURED","capability":"B.NOT"}],
                },
                "teacher_outcomes": [{
                    "capability":"B.NOT",
                    "attribution":"MEASURED_FIXED_EXAM_UNIQUE_ACTION",
                    "delta_correct": 2,
                }],
            })
            system = board.rows["SYSTEM & QUALIFICATION"]
            diagnostic = next(row for row in system if row["kind"] == "DIAGNOSTIC")
            outcome = next(row for row in system if row["kind"] == "TEACH OUTCOME")
            self.assertIn("S2:B.NOT", diagnostic["detail"])
            self.assertIn("1 NOT MEASURED", diagnostic["detail"])
            self.assertIn("B.NOT +2", outcome["detail"])

    def test_exam_without_logical_target_grade_remains_renderable(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {
                "event": "SCHOOL_LIVE_EXAM_COMMITTED", "grade": "B",
                "generation": 13008, "rubric": "b" * 64,
                "assessment_scope_sha256": "s" * 64,
                "cohort_sha256": "c" * 64,
                "generator_version": "grade-live/v2",
                "cohort_file": f"cohorts/{'c' * 64}.json",
                "optimizer_step": 230344, "student_sha256": "d" * 64,
                "phase": "RECOVERY_1",
                "scores": {
                    "A.LINK": {"correct": 11, "total": 12},
                    "C.MUL": {"correct": 19, "total": 21},
                },
            })
            scope = next(
                row for row in board.rows["SYSTEM & QUALIFICATION"]
                if row["kind"] == "EXAM SCOPE")
            self.assertEqual(scope["grade"], "B")
            self.assertIn("B NOT EVALUATED", scope["detail"])
            self.assertIn("A+C", scope["detail"])
            self.assertIn("B NOT EVALUATED", board.operator_lines[0])

    def test_grade_a_live_exam_scope_separates_different_capability_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            common = {
                "event": "GRADE_A_LIVE_EXAM_COMMITTED",
                "grade": "A",
                "rubric": "a" * 64,
                "generator_version": "grade-a-live/v1",
                "optimizer_step": 200,
                "student_sha256": "d" * 64,
            }
            ingest(board, {
                **common,
                "generation": 1,
                "assessment_scope_sha256": "1" * 64,
                "cohort_sha256": "2" * 64,
                "cohort_file": f"cohorts/{'2' * 64}.json",
                "scores": {
                    "A.IDENTITY": {"correct": 12, "total": 12},
                    "A.LINK": {"correct": 11, "total": 12},
                },
            })
            ingest(board, {
                **common,
                "generation": 2,
                "assessment_scope_sha256": "3" * 64,
                "cohort_sha256": "4" * 64,
                "cohort_file": f"cohorts/{'4' * 64}.json",
                "scores": {
                    "A.IDENTITY": {"correct": 12, "total": 12},
                },
            })

            self.assertEqual(len(board.school_telemetry.latest), 2)

    def test_grade_a_live_exam_same_scope_rejects_capability_inventory_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            common = {
                "event": "GRADE_A_LIVE_EXAM_COMMITTED",
                "grade": "A",
                "rubric": "a" * 64,
                "assessment_scope_sha256": "1" * 64,
                "generator_version": "grade-a-live/v1",
                "optimizer_step": 200,
                "student_sha256": "d" * 64,
            }
            ingest(board, {
                **common,
                "generation": 1,
                "cohort_sha256": "2" * 64,
                "cohort_file": f"cohorts/{'2' * 64}.json",
                "scores": {
                    "A.IDENTITY": {"correct": 12, "total": 12},
                    "A.LINK": {"correct": 11, "total": 12},
                },
            })
            with self.assertRaisesRegex(ValueError, "RUBRIC_ITEMS_DRIFT"):
                ingest(board, {
                    **common,
                    "generation": 2,
                    "cohort_sha256": "3" * 64,
                    "cohort_file": f"cohorts/{'3' * 64}.json",
                    "scores": {
                        "A.IDENTITY": {"correct": 12, "total": 12},
                    },
                })

    def test_withheld_scope_receipt_bug_separates_partial_and_full_exams(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            common = {
                "event": "SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED",
                "grade": "B", "rubric": "b" * 64,
                "assessment_scope_sha256": "1" * 64,
                "generator_version": "grade-b-live/v1",
                "optimizer_step": 200, "student_sha256": "d" * 64,
                "withheld_capabilities": ["B.IFF"],
            }
            ingest(board, {
                **common, "generation": 1, "exam_plane": "ROUTINE",
                "cohort_sha256": "2" * 64,
                "cohort_file": f"cohorts/{'2' * 64}.json",
                "scores": {
                    "B.AND": {"correct": 5, "total": 12},
                    "B.NOT": {"correct": 7, "total": 12},
                },
            })
            ingest(board, {
                **common, "generation": 2, "exam_plane": "GENERALIZATION",
                "cohort_sha256": "3" * 64,
                "cohort_file": f"cohorts/{'3' * 64}.json",
                "scores": {
                    "B.AND": {"correct": 6, "total": 12},
                    "B.IFF": {"correct": 8, "total": 12},
                    "B.NOT": {"correct": 8, "total": 12},
                },
            })
            reports = [report for (grade, _, _), report in
                       board.school_telemetry.latest.items() if grade == "B"]
            self.assertEqual(len(reports), 2)
            self.assertEqual({report.total for report in reports}, {24, 36})

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
            self.assertEqual(identity["start"], "7/12")
            self.assertEqual(identity["before"], "10/12")
            self.assertEqual(identity["after"], "6/12")
            self.assertEqual(identity["gain"], "-4")
            mastery = [row for row in board._section_rows("GRADES & MASTERY")
                       if row.get("row_type") == "summary"]
            self.assertEqual(len(mastery), 1)
            self.assertEqual(mastery[0]["latest"], "10/24")
            self.assertEqual(mastery[0]["best"], "18/24")
            self.assertEqual(mastery[0]["to100"], "14")
            operator = " ".join(board.operator_lines)
            self.assertIn("START SEALED A 12/24", operator)
            self.assertIn("LATEST A 10/24", operator)
            self.assertIn("BEST A 18/24", operator)
            self.assertIn("TO100 14/24", operator)
            text = board.render(width=180, height=42)
            self.assertNotIn("START SEALED A 12/24", text)
            self.assertNotIn("LATEST A 10/24", text)
            self.assertNotIn("BEST A 18/24", text)
            self.assertNotIn("TO100 14/24", text)

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

    def test_autonomy_events_are_visible_in_system_telemetry(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {
                "event": "SCHOOL_AUTONOMY_EVIDENCE_RECORDED",
                "grade": "B",
                "generation": 60,
                "capability": "B.IDBOOLOPS",
                "obligation": "B.IDBOOLOPS/prerequisite/B.XOR",
                "passed": False,
                "cohort_sha256": "a" * 64,
                "student_sha256": "b" * 64,
                "optimizer_step": 140000,
            })
            ingest(board, {
                "event": "SCHOOL_AUTONOMY_TEACHING_RECORDED",
                "grade": "B",
                "generation": 61,
                "capability": "B.IDBOOLOPS",
                "obligation": "B.IDBOOLOPS/prerequisite/B.XOR",
                "parent_student_sha256": "b" * 64,
                "student_sha256": "c" * 64,
                "optimizer_step": 140016,
            })
            ingest(board, {
                "event": "SCHOOL_AUTONOMY_SOURCE_COVERAGE_BLOCKED",
                "grade": "B",
                "generation": 62,
                "debt": ["B.IDBOOLOPS:TRANSFER:SOURCE_PROJECTION_UNSUPPORTED"],
                "model_and_optimizer_unchanged": True,
            })

            autonomy = [
                row for row in board.rows["SYSTEM & QUALIFICATION"]
                if row.get("kind") == "AUTONOMY"
            ]
            self.assertEqual(len(autonomy), 3)
            self.assertIn("FAIL B.IDBOOLOPS", autonomy[0]["detail"])
            self.assertIn("B.IDBOOLOPS/prerequisite/B.XOR", autonomy[0]["detail"])
            self.assertIn("TEACH B.IDBOOLOPS", autonomy[1]["detail"])
            self.assertIn("SOURCE COVERAGE BLOCKED", autonomy[2]["detail"])
            self.assertIn("SOURCE_PROJECTION_UNSUPPORTED", autonomy[2]["detail"])

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
            "bilqis_mlx.runtime.disk.shutil.disk_usage",
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
            self.assertFalse(any(row.get("mastered", False)
                                 for row in board.rows["GRADES & MASTERY"]))
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
            self.assertIn("WAS/TOP/NOW/ALL", display)
            self.assertIn("RIGHT[GREW]%", display)
            self.assertIn("67% [+17%]", display)
            self.assertNotIn("BRIDGE FAMILIES", display)
            self.assertIn("0.00", display)

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
