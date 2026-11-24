from bilqis_mlx.presentation.bamf_terminal_rows import (
    candidate_row,
    retention_row,
    teacher_row,
)


def test_learning_first_visit_uses_compact_retention_semantics():
    visit = {
        "capability_id": "A.LINK",
        "visit_index": 7,
        "outcome": "RUNNING",
        "selected_policy_key": "policy:ordinary",
        "selected_policy": {
            "lr": 0.0003,
            "depth": 2,
            "contrast": 0.0,
            "old": 0,
            "preview": 4,
            "distill": 0.0,
        },
        "retention_target": {
            "state": "MEASURED",
            "before": 4,
            "after": 5,
            "total": 6,
        },
        "retention_protected_count": 3,
        "retention_phase": "RECOVERY_1",
        "retention_decision": "REJECT",
        "retention_reason": "PROTECTED_CAPABILITY_REGRESSION",
    }

    candidate = candidate_row(visit)
    retention = retention_row(visit)
    teacher = teacher_row(visit)

    assert candidate["strategy"] == "policy:ord"
    assert candidate["score_line"] == "4/-/5/6"
    assert candidate["reason"] == "PROTECTED_CAPABILITY_REGRESSION"
    assert candidate["reward"] == "N/M"
    assert candidate["loss"] == "N/M"
    assert candidate["gradient"] == "N/M"
    assert retention["target"] == "4>5/6"
    assert retention["target_delta"] == "+1"
    assert retention["protected"] == "3"
    assert retention["worst"] == "N/M"
    assert retention["decision"] == "REJECT"
    assert retention["evidence"].endswith("PROTECTED_CAPABILITY_REGRESSION")
    assert teacher["policy"] == "policy:ord"
    assert teacher["credit"] == "N/M"


def test_running_visit_marks_unmeasured_and_pending_fields_explicitly():
    visit = {
        "capability_id": "A.IDENTITY",
        "visit_index": 8,
        "outcome": "RUNNING",
        "selected_policy_key": "policy:pending",
        "selected_policy": {},
    }

    candidate = candidate_row(visit)
    retention = retention_row(visit)
    teacher = teacher_row(visit)

    assert candidate["score_line"] == "PEND"
    assert candidate["warnings"] == "N/M"
    assert retention["target"] == "PEND"
    assert retention["target_delta"] == "PEND"
    assert retention["worst"] == "N/M"
    assert teacher["p_ret"] == "PEND"
    assert teacher["health"] == "PEND"
