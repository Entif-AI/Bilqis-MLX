from bilqis_mlx.learning.stagnation_control import (
    begin_recovery_cycle, complete_recovery_cycle, end_of_run_alerts,
    quarantined_capabilities, record_visit, start_session,
    create_optimizer_step_grace, grace_suppressed_capabilities,
    observe_paired_progress, reconcile_optimizer_step_grace,
    reconcile_required_scope,
)
import unittest
from bilqis_mlx.learning.tests.stagnation_control.fixtures import session


def test_grace_suppresses_quarantine_but_keeps_diagnostic_evidence():
    state = begin_recovery_cycle(session(), first_recovery=("C.SUB",))
    for phase, generation in (("RECOVERY_1", 11), ("RECOVERY_2", 12)):
        state = record_visit(
            state, capability="C.SUB", phase=phase, decision="REJECT",
            retained_optimizer_updates=0, generation=generation)
    state, events = complete_recovery_cycle(
        state, weakest_tail=("C.SUB",),
        scores={"C.SUB": {"correct": 5, "total": 12}}, generation=13,
        quarantine_suppressed=("C.SUB",))
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


def test_promotion_sweep_visit_is_recorded_without_recovery_evidence():
    state = start_session(
        session_id="grade-c-promotion-visit", generation=18863,
        required_capabilities=("C.COUNT", "C.NUMBER"))
    state = record_visit(
        state, capability="C.NUMBER", phase="PROMOTION_SWEEP",
        decision="REJECT", retained_optimizer_updates=0, generation=18864)
    assert state["cycle_visits"]["C.NUMBER"]["PROMOTION_SWEEP"] == {
        "attempts": 1, "rejected": 1, "retained_updates": 0,
        "last_generation": 18864,
    }

    # A promotion-phase rejection cannot count as either recovery round.
    state = begin_recovery_cycle(
        state, first_recovery=("C.NUMBER",))
    state, events = complete_recovery_cycle(
        state, weakest_tail=("C.NUMBER",),
        scores={"C.NUMBER": {"correct": 31, "total": 33}},
        generation=18865)
    assert events == ()
    assert quarantined_capabilities(state) == ()


def test_b_is_never_withheld_even_after_full_stagnation_evidence():
    state = start_session(
        session_id="B-developmental-run", generation=60,
        required_capabilities=("B.AND", "B.IFF", "C.SUB"))
    state = begin_recovery_cycle(
        state, first_recovery=("B.AND", "B.IFF", "C.SUB"))
    for capability in ("B.AND", "B.IFF", "C.SUB"):
        for phase, generation in (("RECOVERY_1", 61),
                                  ("RECOVERY_2", 62)):
            state = record_visit(
                state, capability=capability, phase=phase,
                decision="REJECT", retained_optimizer_updates=0,
                generation=generation)
    state, events = complete_recovery_cycle(
        state,
        weakest_tail=("B.AND", "B.IFF", "C.SUB"),
        scores={
            "B.AND": {"correct": 4, "total": 12},
            "B.IFF": {"correct": 7, "total": 12},
            "C.SUB": {"correct": 11, "total": 33},
        },
        generation=63, elapsed_seconds=1500.0)

    # B gets ongoing instruction and remains debt, never a stop actuator.
    assert quarantined_capabilities(state) == ("C.SUB",)
    assert all(not capability.startswith("B.")
               for capability in quarantined_capabilities(state))
    assert ("B.AND", "B.IFF") == tuple(
        capability for capability in state["required_capabilities"]
        if capability.startswith("B."))
    assert {alert["capability"] for alert in end_of_run_alerts(state)} == {
        "C.SUB"}
    events_by_cap = {event["capability"]: event for event in events}
    for capability in ("B.AND", "B.IFF"):
        assert events_by_cap[capability]["event"] == (
            "SCHOOL_CAPABILITY_STAGNATION_QUARANTINE_SUPPRESSED")
        assert events_by_cap[capability]["diagnostic_only"] is True
        assert events_by_cap[capability]["suppression_reason"] == (
            "GRADE_B_DEVELOPMENTAL_LEARNING")
    assert events_by_cap["C.SUB"]["event"] == (
        "SCHOOL_CAPABILITY_STAGNATION_QUARANTINED")


def test_b_alone_cannot_quarantine_or_end_stagnation_run():
    state = start_session(
        session_id="B-only-developmental-run", generation=70,
        required_capabilities=("B.AND", "B.IFF"))
    state = begin_recovery_cycle(
        state, first_recovery=("B.AND", "B.IFF"))
    for capability in ("B.AND", "B.IFF"):
        for phase, generation in (("RECOVERY_1", 71),
                                  ("RECOVERY_2", 72)):
            state = record_visit(
                state, capability=capability, phase=phase,
                decision="REJECT", retained_optimizer_updates=0,
                generation=generation)
    state, events = complete_recovery_cycle(
        state, weakest_tail=("B.AND", "B.IFF"),
        scores={"B.AND": {"correct": 0, "total": 12},
                "B.IFF": {"correct": 0, "total": 12}},
        generation=73, elapsed_seconds=100_000.0)
    assert quarantined_capabilities(state) == ()
    assert end_of_run_alerts(state) == ()
    assert len(events) == 2
    assert set(state["required_capabilities"]) == {"B.AND", "B.IFF"}


class StagnationTests3(unittest.TestCase):
    def test_grace_suppresses_quarantine_but_keeps_diagnostic_evidence(self):
        test_grace_suppresses_quarantine_but_keeps_diagnostic_evidence()

    def test_b_grace_does_not_disable_other_grade_containment(self):
        test_b_grace_does_not_disable_other_grade_containment()

    def test_promotion_sweep_visit_is_recorded_without_recovery_evidence(self):
        test_promotion_sweep_visit_is_recorded_without_recovery_evidence()

    def test_b_is_never_withheld_even_after_full_stagnation_evidence(self):
        test_b_is_never_withheld_even_after_full_stagnation_evidence()

    def test_b_alone_cannot_quarantine_or_end_stagnation_run(self):
        test_b_alone_cannot_quarantine_or_end_stagnation_run()
