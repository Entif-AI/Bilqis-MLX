from bilqis_mlx.learning.stagnation_control import (
    begin_recovery_cycle, complete_recovery_cycle, end_of_run_alerts,
    quarantined_capabilities, record_visit, start_session,
    create_optimizer_step_grace, grace_suppressed_capabilities,
    observe_paired_progress, reconcile_optimizer_step_grace,
    reconcile_required_scope,
)
import unittest
from bilqis_mlx.learning.tests.stagnation_control.fixtures import session


def test_sole_grade_rehabilitation_releases_debt_and_prevents_requarantine():
    from bilqis_mlx.learning import stagnation_control

    state = session()
    debt = ("B.AND", "B.NOT", "B.XOR", "B.OR")
    state["quarantined"] = {
        capability: {"capability": capability, "reason": "fixture"}
        for capability in debt
    }
    state, event = stagnation_control.activate_sole_grade_rehabilitation(
        state, capabilities=debt, generation=20)
    assert quarantined_capabilities(state) == ()
    assert state["rehabilitation"]["grade"] == "B"
    assert tuple(state["rehabilitation"]["capabilities"]) == debt
    assert event["event"] == "SCHOOL_STAGNATION_REHABILITATION_STARTED"

    state = begin_recovery_cycle(state, first_recovery=("B.NOT",))
    for phase, generation in (("RECOVERY_1", 21), ("RECOVERY_2", 22)):
        state = record_visit(
            state, capability="B.NOT", phase=phase, decision="REJECT",
            retained_optimizer_updates=0, generation=generation)
    state, events = complete_recovery_cycle(
        state, weakest_tail=("B.NOT",),
        scores={"B.NOT": {"correct": 5, "total": 12}}, generation=23)
    assert quarantined_capabilities(state) == ()
    assert events == ()


def test_rehabilitation_supersedes_stale_withheld_alert():
    from bilqis_mlx.learning import stagnation_control

    state = begin_recovery_cycle(
        session(), first_recovery=("C.SUB",))
    for phase, generation in (("RECOVERY_1", 11), ("RECOVERY_2", 12)):
        state = record_visit(
            state, capability="C.SUB", phase=phase, decision="REJECT",
            retained_optimizer_updates=0, generation=generation)
    state, _ = complete_recovery_cycle(
        state, weakest_tail=("C.SUB",),
        scores={"C.SUB": {"correct": 5, "total": 12}}, generation=13)
    assert end_of_run_alerts(state)[0]["action"] == "WITHHELD_FOR_REMAINDER_OF_SESSION"

    state, _ = stagnation_control.activate_sole_grade_rehabilitation(
        state, capabilities=("C.SUB",), generation=14)
    alert = end_of_run_alerts(state)[0]
    assert alert["action"] == "RELEASED_FOR_SOLE_GRADE_REHABILITATION"
    assert alert["resolution_generation"] == 14


def test_rehabilitation_exemption_is_limited_to_recorded_debt_capabilities():
    from bilqis_mlx.learning import stagnation_control

    state = start_session(
        session_id="human-command-2", generation=20,
        required_capabilities=("B.AND", "B.NOT", "C.SUB"))
    state["quarantined"] = {
        "B.NOT": {"capability": "B.NOT", "reason": "fixture"},
    }
    state, _ = stagnation_control.activate_sole_grade_rehabilitation(
        state, capabilities=("B.NOT",), generation=21)

    state = begin_recovery_cycle(state, first_recovery=("C.SUB",))
    for phase, generation in (("RECOVERY_1", 22), ("RECOVERY_2", 23)):
        state = record_visit(
            state, capability="C.SUB", phase=phase, decision="REJECT",
            retained_optimizer_updates=0, generation=generation)
    state, events = complete_recovery_cycle(
        state, weakest_tail=("C.SUB",),
        scores={"C.SUB": {"correct": 5, "total": 12}}, generation=24)
    assert quarantined_capabilities(state) == ("C.SUB",)
    assert events[0]["capability"] == "C.SUB"


def test_scope_reconciliation_expands_required_contract_and_resets_cycle_evidence():
    state = start_session(
        session_id="human-command-scope", generation=40,
        required_capabilities=("A.IDENTITY", "A.LINK"))
    state = begin_recovery_cycle(
        state, first_recovery=("A.LINK",))
    state = record_visit(
        state, capability="A.LINK", phase="RECOVERY_1",
        decision="REJECT", retained_optimizer_updates=0, generation=41)
    state["quarantined"]["A.IDENTITY"] = {
        "capability": "A.IDENTITY", "reason": "fixture"}

    updated, event = reconcile_required_scope(
        state,
        required_capabilities=(
            "A.IDENTITY", "A.LINK", "B.AND", "B.IFF"),
        generation=42)

    assert updated["required_capabilities"] == [
        "A.IDENTITY", "A.LINK", "B.AND", "B.IFF"]
    assert updated["cycle_first_recovery"] == []
    assert updated["cycle_visits"] == {}
    assert set(updated["quarantined"]) == {"A.IDENTITY"}
    assert event["event"] == "SCHOOL_STAGNATION_SCOPE_RECONCILED"
    assert event["added_capabilities"] == ["B.AND", "B.IFF"]
    assert event["removed_capabilities"] == []


def test_stagnation_operations_reject_capabilities_outside_current_required_scope():
    state = start_session(
        session_id="human-command-scope-guard", generation=50,
        required_capabilities=("A.IDENTITY", "A.LINK"))
    with unittest.TestCase().assertRaisesRegex(
            ValueError, "STAGNATION_VISIT_OUTSIDE_REQUIRED_SCOPE"):
        record_visit(
            state, capability="B.AND", phase="RECOVERY_1",
            decision="REJECT", retained_optimizer_updates=0, generation=51)
    with unittest.TestCase().assertRaisesRegex(
            ValueError, "STAGNATION_RECOVERY_OUTSIDE_REQUIRED_SCOPE"):
        begin_recovery_cycle(state, first_recovery=("B.AND",))


def test_optimizer_step_grace_is_b_scoped_and_expires_at_absolute_deadline():
    grace = create_optimizer_step_grace(
        grade="B", optimizer_step=231_912, optimizer_steps=100_000)
    required = ("A.IDENTITY", "B.AND", "B.NOT", "C.SUB")
    assert grace["until_optimizer_step"] == 331_912
    assert grace_suppressed_capabilities(
        grace, required_capabilities=required,
        optimizer_step=331_911) == ("B.AND", "B.NOT")
    assert grace_suppressed_capabilities(
        grace, required_capabilities=required,
        optimizer_step=331_912) == ()


def test_repeated_grace_request_does_not_reset_deadline():
    first, created = reconcile_optimizer_step_grace(
        None, requested_grade="B", requested_steps=100_000,
        optimizer_step=231_912)
    assert created is True
    again, created = reconcile_optimizer_step_grace(
        first, requested_grade="B", requested_steps=100_000,
        optimizer_step=250_000)
    assert created is False
    assert again == first
    assert again["until_optimizer_step"] == 331_912


class StagnationTests2(unittest.TestCase):
    def test_sole_grade_rehabilitation_releases_debt_and_prevents_requarantine(self):
        test_sole_grade_rehabilitation_releases_debt_and_prevents_requarantine()

    def test_rehabilitation_supersedes_stale_withheld_alert(self):
        test_rehabilitation_supersedes_stale_withheld_alert()

    def test_rehabilitation_exemption_is_limited_to_recorded_debt_capabilities(self):
        test_rehabilitation_exemption_is_limited_to_recorded_debt_capabilities()

    def test_scope_reconciliation_expands_required_contract_and_resets_cycle_evidence(self):
        test_scope_reconciliation_expands_required_contract_and_resets_cycle_evidence()

    def test_stagnation_operations_reject_capabilities_outside_current_required_scope(self):
        test_stagnation_operations_reject_capabilities_outside_current_required_scope()

    def test_optimizer_step_grace_is_b_scoped_and_expires_at_absolute_deadline(self):
        test_optimizer_step_grace_is_b_scoped_and_expires_at_absolute_deadline()

    def test_repeated_grace_request_does_not_reset_deadline(self):
        test_repeated_grace_request_does_not_reset_deadline()
