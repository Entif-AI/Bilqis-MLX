import io
import json

from bilqis_mlx.presentation.bamf_terminal.rows import mastery_rows, retention_row
from bilqis_mlx.presentation.bamf_terminal.source import read_bamf_terminal_observation
from bilqis_mlx.presentation.school_telemetry import LETTER_TABLES, SchoolTelemetry
from bilqis_mlx.presentation.spiral_dashboard import Dashboard


def test_terminal_uses_paired_protection_and_retained_curriculum(tmp_path):
    (tmp_path / "bamf-state.json").write_text(json.dumps({"run_id": "fixture"}))
    accepted = {
        "event": "BAMF_C16_3_ACCEPTED", "event_id": "one",
        "visit_id": "one", "capability": "A.LINK", "optimizer_step": 12,
        "candidate_attempt_ordinal": 1,
        "how_outcome": {
            "scores": [["A.LINK", 1, 5, 6], ["A.EDGE", 4, 2, 6],
                       ["A.PARENT", 3, 4, 6]],
            "protected_capabilities": ["A.EDGE", "A.PARENT"],
            "context": {"grade": "A"},
            "decision": {
                "decision": "ELIGIBLE", "reason": "PAIRED_SCREEN_WITHIN_BUDGET",
                "baseline_coverage": {
                    "group_denominators": [{"group": "A", "measured": 3, "total": 3}],
                },
            },
        },
    }
    rejected = {
        "event": "BAMF_CANDIDATE_REJECTED", "event_id": "two",
        "evidence": {
            "visit_id": "two", "capability": "A.LINK",
            "candidate_optimizer_step": 24, "rejection_attempt_ordinal": 2,
            "how_outcome": {
                "scores": [["A.LINK", 5, 1, 6]],
                "protected_capabilities": ["A.EDGE", "A.PARENT"],
                "context": {"grade": "A"},
                "decision": {"decision": "REJECT", "reason": "TARGET_BASELINE_REGRESSION"},
            },
        },
    }
    (tmp_path / "events.jsonl").write_text(
        "\n".join(map(json.dumps, (accepted, rejected))) + "\n")
    _, visits = read_bamf_terminal_observation(tmp_path)
    assert retention_row(visits[0])["protected"] == "-1"
    assert retention_row(visits[0])["worst"] == "-2"
    assert retention_row(visits[1])["protected"] == "N/M"
    summaries, families = mastery_rows(visits)
    assert {row["family"]: row["after"] for row in families} == {
        "A.LINK": "5/6", "A.EDGE": "2/6", "A.PARENT": "4/6",
    }
    assert summaries[0]["latest"] == "11/18"
    assert summaries[0]["outcome"] == "RETAINED PAIR"
    board = Dashboard(stream=io.StringIO(), tables=LETTER_TABLES,
                      compact_header=True, show_all_panels=True)
    board.school_telemetry = SchoolTelemetry(board, active_grades=("A",))
    board.log_hint = str(tmp_path / "events.jsonl")
    board.draw()
    assert board._latest_all_grade_score() == (0, 0)
    rows = board._section_rows("GRADES & MASTERY")
    assert "RETAINED PAIR" in {row["outcome"] for row in rows}
    assert "TRAINED" not in board._section_label("GRADES & MASTERY", len(rows), rows, rows)
