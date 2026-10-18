from bilqis_mlx.stagnation_control import (
    begin_recovery_cycle, complete_recovery_cycle, end_of_run_alerts,
    quarantined_capabilities, record_visit, start_session,
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
    from bilqis_mlx import stagnation_control

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
    from bilqis_mlx import stagnation_control

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
    from bilqis_mlx import stagnation_control

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
