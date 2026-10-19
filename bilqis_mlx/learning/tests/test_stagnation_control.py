from bilqis_mlx.learning.stagnation_control import (
    begin_recovery_cycle, complete_recovery_cycle, end_of_run_alerts,
    quarantined_capabilities, record_visit, start_session,
    create_optimizer_step_grace, grace_suppressed_capabilities,
    reconcile_optimizer_step_grace,
)
import unittest


def session():
    return start_session(session_id="human-command-1", generation=10,
                         required_capabilities=("B.AND", "B.NOT", "B.XOR", "B.OR"))


def test_two_rejected_recovery_rounds_and_repeated_tail_quarantine_without_new_threshold():
    state = begin_recovery_cycle(session(), first_recovery=("B.NOT", "B.XOR", "B.AND"))
    for phase, generation in (("RECOVERY_1", 11), ("RECOVERY_2", 12)):
        state = record_visit(state, capability="B.NOT", phase=phase,
                             decision="REJECT", retained_optimizer_updates=0,
                             generation=generation)
    state, events = complete_recovery_cycle(
        state, weakest_tail=("B.NOT", "B.OR", "B.XOR"),
        scores={"B.NOT": {"correct": 5, "total": 12},
                "B.OR": {"correct": 8, "total": 12},
                "B.XOR": {"correct": 7, "total": 12}},
        generation=13,
        active_warnings=({"capability": "B.NOT",
                          "signal": "CHANCE_LEVEL_OR_LAGGING"},))
    assert quarantined_capabilities(state) == ("B.NOT",)
    assert events[0]["required_mastery_debt"] is True
    assert end_of_run_alerts(state)[0]["delivery"] == "END_OF_RUN_REVIEW"


def test_a_retained_recovery_update_prevents_quarantine():
    state = begin_recovery_cycle(session(), first_recovery=("B.NOT",))
    state = record_visit(state, capability="B.NOT", phase="RECOVERY_1",
                         decision="PROVISIONAL", retained_optimizer_updates=16,
                         generation=11)
    state = record_visit(state, capability="B.NOT", phase="RECOVERY_2",
                         decision="REJECT", retained_optimizer_updates=0,
                         generation=12)
    state, events = complete_recovery_cycle(
        state, weakest_tail=("B.NOT",),
        scores={"B.NOT": {"correct": 5, "total": 12}}, generation=13)
    assert not quarantined_capabilities(state)
    assert events == ()


def test_capability_that_breaks_out_of_tail_is_not_quarantined():
    state = begin_recovery_cycle(session(), first_recovery=("B.NOT",))
    for phase, generation in (("RECOVERY_1", 11), ("RECOVERY_2", 12)):
        state = record_visit(state, capability="B.NOT", phase=phase,
                             decision="REJECT", retained_optimizer_updates=0,
                             generation=generation)
    state, events = complete_recovery_cycle(
        state, weakest_tail=("B.AND", "B.OR", "B.XOR"),
        scores={"B.NOT": {"correct": 7, "total": 12},
                "B.AND": {"correct": 4, "total": 12},
                "B.OR": {"correct": 5, "total": 12},
                "B.XOR": {"correct": 5, "total": 12}}, generation=13)
    assert not quarantined_capabilities(state)
    assert events == ()


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
        session(), first_recovery=("B.NOT",))
    for phase, generation in (("RECOVERY_1", 11), ("RECOVERY_2", 12)):
        state = record_visit(
            state, capability="B.NOT", phase=phase, decision="REJECT",
            retained_optimizer_updates=0, generation=generation)
    state, _ = complete_recovery_cycle(
        state, weakest_tail=("B.NOT",),
        scores={"B.NOT": {"correct": 5, "total": 12}}, generation=13)
    assert end_of_run_alerts(state)[0]["action"] == "WITHHELD_FOR_REMAINDER_OF_SESSION"

    state, _ = stagnation_control.activate_sole_grade_rehabilitation(
        state, capabilities=("B.NOT",), generation=14)
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

    state = begin_recovery_cycle(state, first_recovery=("B.AND",))
    for phase, generation in (("RECOVERY_1", 22), ("RECOVERY_2", 23)):
        state = record_visit(
            state, capability="B.AND", phase=phase, decision="REJECT",
            retained_optimizer_updates=0, generation=generation)
    state, events = complete_recovery_cycle(
        state, weakest_tail=("B.AND",),
        scores={"B.AND": {"correct": 5, "total": 12}}, generation=24)
    assert quarantined_capabilities(state) == ("B.AND",)
    assert events[0]["capability"] == "B.AND"


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


def test_grace_suppresses_quarantine_but_keeps_diagnostic_evidence():
    state = begin_recovery_cycle(session(), first_recovery=("B.NOT",))
    for phase, generation in (("RECOVERY_1", 11), ("RECOVERY_2", 12)):
        state = record_visit(
            state, capability="B.NOT", phase=phase, decision="REJECT",
            retained_optimizer_updates=0, generation=generation)
    state, events = complete_recovery_cycle(
        state, weakest_tail=("B.NOT",),
        scores={"B.NOT": {"correct": 5, "total": 12}}, generation=13,
        quarantine_suppressed=("B.NOT",))
    assert quarantined_capabilities(state) == ()
    assert events[0]["event"] == "SCHOOL_CAPABILITY_STAGNATION_QUARANTINE_SUPPRESSED"
    assert events[0]["would_quarantine"] is True
    assert events[0]["diagnostic_only"] is True


def test_b_grace_does_not_disable_other_grade_containment():
    state = start_session(
        session_id="human-command-3", generation=30,
        required_capabilities=("B.NOT", "C.SUB"))
    state = begin_recovery_cycle(state, first_recovery=("B.NOT", "C.SUB"))
    for capability in ("B.NOT", "C.SUB"):
        for phase, generation in (("RECOVERY_1", 31), ("RECOVERY_2", 32)):
            state = record_visit(
                state, capability=capability, phase=phase, decision="REJECT",
                retained_optimizer_updates=0, generation=generation)
    state, events = complete_recovery_cycle(
        state, weakest_tail=("B.NOT", "C.SUB"),
        scores={"B.NOT": {"correct": 5, "total": 12},
                "C.SUB": {"correct": 17, "total": 21}},
        generation=33, quarantine_suppressed=("B.NOT",))
    assert quarantined_capabilities(state) == ("C.SUB",)
    by_capability = {event["capability"]: event for event in events}
    assert by_capability["B.NOT"]["event"] == (
        "SCHOOL_CAPABILITY_STAGNATION_QUARANTINE_SUPPRESSED")
    assert by_capability["C.SUB"]["event"] == "SCHOOL_CAPABILITY_STAGNATION_QUARANTINED"


class StagnationControlUnittestCoverage(unittest.TestCase):
    """Keep the repository's unittest-based npm test command authoritative."""

    def test_two_rejected_recovery_rounds(self):
        test_two_rejected_recovery_rounds_and_repeated_tail_quarantine_without_new_threshold()

    def test_retained_update_prevents_quarantine(self):
        test_a_retained_recovery_update_prevents_quarantine()

    def test_breakout_from_tail_prevents_quarantine(self):
        test_capability_that_breaks_out_of_tail_is_not_quarantined()

    def test_sole_grade_rehabilitation_prevents_requarantine(self):
        test_sole_grade_rehabilitation_releases_debt_and_prevents_requarantine()

    def test_rehabilitation_supersedes_stale_alert(self):
        test_rehabilitation_supersedes_stale_withheld_alert()

    def test_rehabilitation_exemption_is_capability_scoped(self):
        test_rehabilitation_exemption_is_limited_to_recorded_debt_capabilities()

    def test_optimizer_step_grace_expires(self):
        test_optimizer_step_grace_is_b_scoped_and_expires_at_absolute_deadline()

    def test_repeated_grace_request_does_not_reset_deadline(self):
        test_repeated_grace_request_does_not_reset_deadline()

    def test_grace_suppresses_quarantine_but_keeps_evidence(self):
        test_grace_suppresses_quarantine_but_keeps_diagnostic_evidence()

    def test_b_grace_preserves_other_grade_containment(self):
        test_b_grace_does_not_disable_other_grade_containment()
