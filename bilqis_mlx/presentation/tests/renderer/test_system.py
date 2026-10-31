"""System rendering preserves receipt-backed operator evidence."""
import io
from pathlib import Path
import tempfile
import unittest
from bilqis_mlx.presentation.school_telemetry import LETTER_TABLES
from bilqis_mlx.presentation.spiral_dashboard import Dashboard
from bilqis_mlx.presentation.dashboard import build
from bilqis_mlx.presentation.school_telemetry import LETTER_TABLES
from bilqis_mlx.presentation.dashboard import build


class SystemTests(unittest.TestCase):
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
