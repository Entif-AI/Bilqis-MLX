"""BAMF terminal visit identity remains one logical visit across representations."""
import io
import json

from bilqis_mlx.presentation.bamf_terminal.accounting import begin_bamf_command_accounting
from bilqis_mlx.presentation.dashboard import ingest
from bilqis_mlx.presentation.school_telemetry import LETTER_TABLES, SchoolTelemetry
from bilqis_mlx.presentation.spiral_dashboard import Dashboard


def _live_visit(capability: str, visit: int, step: int):
    return {
        "observation_id": f"observed-{visit}",
        "revision": 7,
        "run_id": "aspirant",
        "visit_index": visit,
        "capability_id": capability,
        "phase": "COMPLETED",
        "outcome": "ACCEPTED",
        "candidate_optimizer_step": step,
        "candidate_step": 12,
        "candidate_horizon": 12,
        "retention_completed": 1,
        "retention_total": 1,
        "candidate_steps": [],
        "visit_evidence": {
            "state": "COMPLETE",
            "grade_id": "A",
            "capability_id": capability,
            "teacher_policy_key": "8694ee76cff6",
            "selected_option_id": capability,
            "decision": "PROVISIONAL",
            "reason": "WITHIN_BUDGET",
            "learning_target": {
                "state": "MEASURED", "before": 3, "after": 4, "total": 6,
            },
        },
    }


def test_live_and_durable_forms_of_one_terminal_visit_count_once(tmp_path):
    run = tmp_path
    (run / "bamf-state.json").write_text(json.dumps({
        "run_id": "aspirant", "generation": 20,
    }))
    historical = {
        "event": "BAMF_CANDIDATE_REJECTED",
        "event_id": "historical",
        "evidence": {
            "capability": "A.EDGE",
            "candidate_optimizer_step": 126,
            "rejection_attempt_ordinal": 1,
            "visit_id": "historical-visit",
            "retention_reason": "NO_GAIN",
            "how_outcome": {
                "attempted_steps": 12,
                "retained_steps": 0,
                "decision": {"decision": "REJECT", "reason": "NO_GAIN"},
                "context": {"grade": "A"},
            },
        },
    }
    events = run / "events.jsonl"
    events.write_text(json.dumps(historical) + "\n")
    (run / "trainer-observed.json").write_text(json.dumps({
        "schema": "bilqis.bamf.trainer-observed/v7",
        "visits": [],
    }))
    board = Dashboard(
        stream=io.StringIO(),
        clock=lambda: 1000.0,
        tables=LETTER_TABLES,
        compact_header=True,
        show_all_panels=True,
    )
    board.school_telemetry = SchoolTelemetry(board, active_grades=("A",))
    board.log_hint = str(events)

    board.draw()
    assert board.state["visits"] == 0

    accepted = {
        "event": "BAMF_C16_3_ACCEPTED",
        "event_id": "accepted-current",
        "capability": "A.MAPS",
        "candidate_attempt_ordinal": 1,
        "optimizer_step": 138,
        "selected_policy_key": "8694ee76cff6",
        "visit_id": "authoritative-visit-id",
        "how_outcome": {
            "attempted_steps": 12,
            "retained_steps": 12,
            "scores": [["A.MAPS", 3, 4, 6]],
            "decision": {
                "decision": "PROVISIONAL",
                "reason": "WITHIN_BUDGET",
                "evaluated_capability_ids": ["A.MAPS"],
            },
            "context": {"grade": "A", "phase": "RECOVERY_1"},
        },
    }
    events.write_text(json.dumps(historical) + "\n" + json.dumps(accepted) + "\n")
    (run / "trainer-observed.json").write_text(json.dumps({
        "schema": "bilqis.bamf.trainer-observed/v7",
        "visits": [_live_visit("A.MAPS", 13, 138)],
    }))

    board.draw()

    assert board.state["visits"] == 1
    assert board.state["retained_visits"] == 1
    assert board.state["attempted_steps"] == 12
    assert [row["capability"] for row in board.rows["CANDIDATES"]].count("A.MAPS") == 1



def test_running_observation_rekeys_to_durable_terminal_identity_without_duplication(tmp_path):
    run = tmp_path
    (run / "bamf-state.json").write_text(json.dumps({
        "run_id": "aspirant", "generation": 20,
    }))
    historical = {
        "event": "BAMF_CANDIDATE_REJECTED",
        "event_id": "historical-2",
        "evidence": {
            "capability": "A.EDGE",
            "candidate_optimizer_step": 126,
            "rejection_attempt_ordinal": 1,
            "visit_id": "historical-visit-2",
            "retention_reason": "NO_GAIN",
            "how_outcome": {
                "attempted_steps": 12,
                "retained_steps": 0,
                "decision": {"decision": "REJECT", "reason": "NO_GAIN"},
                "context": {"grade": "A"},
            },
        },
    }
    events = run / "events.jsonl"
    events.write_text(json.dumps(historical) + "\n")
    (run / "trainer-observed.json").write_text(json.dumps({
        "schema": "bilqis.bamf.trainer-observed/v7",
        "visits": [],
    }))
    board = Dashboard(
        stream=io.StringIO(),
        clock=lambda: 1000.0,
        tables=LETTER_TABLES,
        compact_header=True,
        show_all_panels=True,
    )
    board.school_telemetry = SchoolTelemetry(board, active_grades=("A",))
    board.log_hint = str(events)
    board.draw()
    live = _live_visit("A.MAPS", 13, 138)
    live["phase"] = "TRAINING"
    live["outcome"] = "RUNNING"
    live["candidate_step"] = 6
    (run / "trainer-observed.json").write_text(json.dumps({
        "schema": "bilqis.bamf.trainer-observed/v7",
        "visits": [live],
    }))
    board.draw()
    assert board.state["visits"] == 0
    assert board.state["attempted_steps"] == 6
    accepted = {
        "event": "BAMF_C16_3_ACCEPTED",
        "event_id": "accepted-transition",
        "capability": "A.MAPS",
        "candidate_attempt_ordinal": 1,
        "optimizer_step": 138,
        "selected_policy_key": "8694ee76cff6",
        "visit_id": "authoritative-transition-id",
        "how_outcome": {
            "attempted_steps": 12,
            "retained_steps": 12,
            "scores": [["A.MAPS", 3, 4, 6]],
            "decision": {
                "decision": "PROVISIONAL",
                "reason": "WITHIN_BUDGET",
                "evaluated_capability_ids": ["A.MAPS"],
            },
            "context": {"grade": "A", "phase": "RECOVERY_1"},
        },
    }
    events.write_text(json.dumps(historical) + "\n" + json.dumps(accepted) + "\n")
    live["phase"] = "COMPLETED"
    live["outcome"] = "ACCEPTED"
    live["candidate_step"] = 12
    (run / "trainer-observed.json").write_text(json.dumps({
        "schema": "bilqis.bamf.trainer-observed/v7",
        "visits": [live],
    }))
    board.draw()
    assert board.state["visits"] == 1
    assert board.state["retained_visits"] == 1
    assert board.state["attempted_steps"] == 12
    assert [row["capability"] for row in board.rows["CANDIDATES"]].count("A.MAPS") == 1



def _terminal_event(index: int):
    accepted = index % 10 == 0
    how = {
        "attempted_steps": 12,
        "retained_steps": 12 if accepted else 0,
        "context": {"grade": "A"},
    }
    if accepted:
        return {
            "event": "BAMF_C16_3_ACCEPTED",
            "event_id": f"accepted-{index}",
            "visit_id": f"visit-{index}",
            "capability": "A.MAPS",
            "optimizer_step": index * 12,
            "how_outcome": how,
        }
    return {
        "event": "BAMF_CANDIDATE_REJECTED",
        "event_id": f"rejected-{index}",
        "evidence": {
            "visit_id": f"visit-{index}",
            "capability": "A.MAPS",
            "candidate_optimizer_step": index * 12,
            "rejection_attempt_ordinal": index,
            "how_outcome": how,
        },
    }


def test_command_accounting_survives_bounded_display_history(tmp_path):
    run = tmp_path
    (run / "bamf-state.json").write_text(json.dumps({
        "run_id": "aspirant", "generation": 20,
    }))
    (run / "trainer-observed.json").write_text(json.dumps({
        "schema": "bilqis.bamf.trainer-observed/v7", "visits": [],
    }))
    board = Dashboard(
        stream=io.StringIO(), clock=lambda: 1000.0,
        tables=LETTER_TABLES, compact_header=True, show_all_panels=True)
    board.school_telemetry = SchoolTelemetry(board, active_grades=("A",))
    board.log_hint = str(run / "events.jsonl")
    begin_bamf_command_accounting(board)
    ingest(board, {
        "event": "BAMF_CANDIDATE_REJECTED",
        "event_id": "resource-rejected",
        "evidence": {"visit_id": "resource-only", "capability": "A.EDGE"},
    })
    assert board.state["visits"] == 0

    events = [_terminal_event(index) for index in range(70)]
    for event in events:
        ingest(board, event)
        ingest(board, event)
    (run / "events.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in events))

    ingest(board, {
        "event": "BAMF_RUN_STOPPED",
        "run_stop_receipt": {"visits": 71, "accepted_visits": 8},
    })
    board.draw()

    assert board.state["visits"] == 71
    assert board.state["retained_visits"] == 8
    assert board.state["attempted_steps"] == 840
