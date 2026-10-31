"""Champions rendering preserves receipt-backed operator evidence."""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from bilqis_mlx.presentation.school_telemetry import LETTER_TABLES
from bilqis_mlx.presentation.spiral_dashboard import Dashboard
from bilqis_mlx.presentation.school_telemetry import LETTER_TABLES
from bilqis_mlx.state_dag import migrate_current_head


class ChampionsTests(unittest.TestCase):
    def test_merkle_state_keeps_champion_inventory_visible(self):
        from bilqis_mlx.data_plane import close_data_planes
        from bilqis_mlx.state_dag import persist
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.dict(os.environ, BILQIS_DATA_PLANE=str(root / "plane.sqlite3")):
                try:
                    persist(root, {"generation": 1, "mentor_epoch": {"active_roles": {
                        "D.COMMENCEMENT": {"correct": 12, "total": 12, "breadth": 1,
                            "checkpoint": {"sha256": "a" * 64, "optimizer_step": 100}},
                    }}})
                    board = Dashboard(stream=io.StringIO())
                    board.attach_champion_source(root)
                    self.assertEqual([(row["capability"], row["best"])
                                      for row in board._champion_rows],
                                     [("D.COMMENCEMENT", "12/12")])
                finally:
                    close_data_planes()

    def test_mastery_panel_preserves_every_active_capability_champion(self):
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
            self.assertEqual(len(a_rows), 7)
            self.assertEqual(
                {row["capability"] for row in a_rows},
                {"A.ONE", "A.TWO", "A.THREE", "A.FOUR", "A.FIVE", "A.SIX",
                 "A.SEVEN"},
            )
            seven = next(row for row in rows if row.get("capability") == "A.SEVEN")
            self.assertEqual(seven["row_type"], "champion")
            self.assertEqual(seven["best"], "7/12")
            self.assertIn("CHAMP @106", seven["outcome"])
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

    def test_champion_source_resolves_merkle_dag_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "states").mkdir()
            receipt = {
                "generation": 7,
                "mentor_epoch": {"active_roles": {
                    "C.COUNT": {
                        "capability": "C.COUNT", "correct": 12, "total": 12,
                        "breadth": 4,
                        "checkpoint": {"sha256": "a" * 64, "optimizer_step": 123},
                    },
                }},
            }
            (root / "state.json").write_text(json.dumps(receipt))
            with patch.dict(os.environ, {"BILQIS_DATA_PLANE": str(root / "plane.sqlite3")}):
                from bilqis_mlx.data_plane import close_data_planes
                close_data_planes()
                try:
                    migrate_current_head(root, receipt)
                    board = Dashboard(stream=io.StringIO(), show_all_panels=True,
                                      tables=LETTER_TABLES)
                    with patch(
                            "bilqis_mlx.presentation.renderer.champions.read_current",
                            create=True,
                            side_effect=AssertionError("full state read")):
                        board.attach_champion_source(root)
                finally:
                    close_data_planes()

            self.assertEqual(board._champion_rows[0]["capability"], "C.COUNT")

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
