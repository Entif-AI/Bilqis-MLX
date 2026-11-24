"""BAMF GREW follows the retained reference, not a fresh target lottery."""
import io
import json

from bilqis_mlx.presentation.bamf_terminal.accounting import begin_bamf_command_accounting
from bilqis_mlx.presentation.dashboard import ingest
from bilqis_mlx.presentation.school_telemetry import LETTER_TABLES, SchoolTelemetry
from bilqis_mlx.presentation.spiral_dashboard import Dashboard


def _event(index, target, scores, *, accepted=True, fixed=None):
    how = {
        "scores": scores, "protected_capabilities": [r[0] for r in scores if r[0] != target],
        "attempted_steps": 12, "retained_steps": 12 if accepted else 0,
        "context": {"grade": "A", "factory_release_sha256": "a" * 64,
                    "rubric_sha256": "b" * 64, "total_capabilities": 3},
        "decision": {"decision": "PROVISIONAL" if accepted else "REJECT",
                     "baseline_coverage": {"group_denominators": [
                         {"group": "A", "measured": 3, "total": 3}]}},
    }
    if fixed is not None:
        how["fixed_reference_scores"] = fixed
        how["fixed_reference_cohort_sha256"] = "c" * 64
    event = {"event_id": str(index), "visit_id": str(index), "capability": target,
             "candidate_attempt_ordinal": index, "optimizer_step": index * 12,
             "how_outcome": how}
    if accepted:
        return {"event": "BAMF_C16_3_ACCEPTED", **event}
    return {"event": "BAMF_CANDIDATE_REJECTED", "event_id": str(index),
            "evidence": {**event, "candidate_optimizer_step": index * 12}}


def test_command_growth_uses_reference_baseline_and_excludes_rejected_after(tmp_path):
    (tmp_path / "bamf-state.json").write_text(json.dumps({"run_id": "fixture"}))
    log = tmp_path / "events.jsonl"
    prior = _event(1, "A.EDGE", [
        ["A.EDGE", 0, 6, 6], ["A.LINK", 2, 3, 6], ["A.PARENT", 3, 4, 6]])
    log.write_text(json.dumps(prior) + "\n")
    board = Dashboard(stream=io.StringIO(), tables=LETTER_TABLES,
                      compact_header=True, show_all_panels=True)
    board.school_telemetry = SchoolTelemetry(board, active_grades=("A",))
    board.log_hint = str(log)
    begin_bamf_command_accounting(board)
    board.draw()
    assert board.state["grew"] == 0

    first = _event(2, "A.LINK", [
        ["A.LINK", 0, 6, 6], ["A.EDGE", 3, 2, 6], ["A.PARENT", 4, 5, 6]])
    second = _event(3, "A.EDGE", [
        ["A.EDGE", 0, 6, 6], ["A.LINK", 3, 1, 6], ["A.PARENT", 5, 3, 6]])
    rejected = _event(4, "A.LINK", [
        ["A.LINK", 1, 0, 6], ["A.EDGE", 2, 0, 6], ["A.PARENT", 3, 0, 6]],
        accepted=False)
    for event in (first, second, rejected):
        with log.open("a") as stream:
            stream.write(json.dumps(event) + "\n")
        ingest(board, event)
        board.draw()
    assert board.state["grew"] == -22
    summary = next(r for r in board._section_rows("GRADES & MASTERY") if r["row_type"] == "summary")
    assert summary["start"] == "10/18"
    assert summary["latest"] == "6/18"
    assert summary["right_grew"] == " 33% [-22%]"
    assert summary["outcome"] == "REF 3/3"
    assert board._latest_all_grade_score() == (0, 0)
    assert "-22" in board._compact_headers(board.state)[0][1]

    # A new command re-anchors to current retained evidence, not the old run start.
    begin_bamf_command_accounting(board)
    board.draw()
    assert board.state["grew"] == 0


def test_fixed_reference_target_drives_growth_and_partial_is_explicit(tmp_path):
    (tmp_path / "bamf-state.json").write_text(json.dumps({"run_id": "fixture"}))
    log = tmp_path / "events.jsonl"
    initial = _event(1, "A.EDGE", [["A.EDGE", 0, 6, 6]],
                     fixed=[["A.EDGE", 3, 4, 6], ["A.LINK", 4, 4, 6],
                            ["A.PARENT", 5, 5, 6]])
    log.write_text(json.dumps(initial) + "\n")
    board = Dashboard(stream=io.StringIO(), tables=LETTER_TABLES,
                      compact_header=True, show_all_panels=True)
    board.school_telemetry = SchoolTelemetry(board, active_grades=("A",))
    board.log_hint = str(log)
    begin_bamf_command_accounting(board)
    board.draw()
    assert board.state["grew"] == 0
    assert board.state["_bamf_growth_coverage"] == (3, 3, 0)

    event = _event(2, "A.EDGE", [["A.EDGE", 0, 6, 6]],
                   fixed=[["A.EDGE", 4, 1, 6], ["A.LINK", 4, 4, 6]])
    with log.open("a") as stream:
        stream.write(json.dumps(event) + "\n")
    ingest(board, event)
    board.draw()
    assert board.state["grew"] == -17
    assert board.state["_bamf_growth_coverage"] == (3, 3, 1)
    summary = next(r for r in board._section_rows("GRADES & MASTERY") if r["row_type"] == "summary")
    assert summary["start"] == "13/18"
    assert summary["latest"] == "10/18"
    assert summary["right_grew"] == " 56% [-17%]"
    assert summary["outcome"] == "REF 3/3 S1"
    assert "-17~" in board._compact_headers(board.state)[0][1]
