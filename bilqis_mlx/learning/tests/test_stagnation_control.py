from bilqis_mlx.learning.stagnation_control import (
    begin_recovery_cycle, complete_recovery_cycle, end_of_run_alerts,
    quarantined_capabilities, record_visit, start_session,
    create_optimizer_step_grace, grace_suppressed_capabilities,
    observe_paired_progress, reconcile_optimizer_step_grace,
    reconcile_required_scope,
)
import unittest


def session():
    return start_session(session_id="human-command-1", generation=10,
                         required_capabilities=("B.AND", "B.NOT", "B.XOR", "B.OR", "C.SUB"))


def test_two_rejected_recovery_rounds_and_repeated_tail_quarantine_without_new_threshold():
    state = begin_recovery_cycle(session(), first_recovery=("C.SUB", "B.XOR", "B.AND"))
    for phase, generation in (("RECOVERY_1", 11), ("RECOVERY_2", 12)):
        state = record_visit(state, capability="C.SUB", phase=phase,
                             decision="REJECT", retained_optimizer_updates=0,
                             generation=generation)
    state, events = complete_recovery_cycle(
        state, weakest_tail=("C.SUB", "B.OR", "B.XOR"),
        scores={"C.SUB": {"correct": 5, "total": 12},
                "B.OR": {"correct": 8, "total": 12},
                "B.XOR": {"correct": 7, "total": 12}},
        generation=13,
        active_warnings=({"capability": "C.SUB",
                          "signal": "CHANCE_LEVEL_OR_LAGGING"},))
    assert quarantined_capabilities(state) == ("C.SUB",)
    assert events[0]["required_mastery_debt"] is True
    assert end_of_run_alerts(state)[0]["delivery"] == "END_OF_RUN_REVIEW"


def test_a_retained_recovery_update_prevents_quarantine():
    state = begin_recovery_cycle(session(), first_recovery=("C.SUB",))
    state = record_visit(state, capability="C.SUB", phase="RECOVERY_1",
                         decision="PROVISIONAL", retained_optimizer_updates=16,
                         generation=11)
    state = record_visit(state, capability="C.SUB", phase="RECOVERY_2",
                         decision="REJECT", retained_optimizer_updates=0,
                         generation=12)
    state, events = complete_recovery_cycle(
        state, weakest_tail=("C.SUB",),
        scores={"C.SUB": {"correct": 5, "total": 12}}, generation=13)
    assert not quarantined_capabilities(state)
    assert events == ()


def test_stagnation_requires_twenty_minutes_without_measured_progress():
    state = session()
    state = begin_recovery_cycle(state, first_recovery=("C.SUB",))
    for phase, generation in (("RECOVERY_1", 11), ("RECOVERY_2", 12)):
        state = record_visit(
            state, capability="C.SUB", phase=phase, decision="REJECT",
            retained_optimizer_updates=0, generation=generation)
    state, events = complete_recovery_cycle(
        state, weakest_tail=("C.SUB",),
        scores={"C.SUB": {"correct": 4, "total": 12}}, generation=13,
        elapsed_seconds=1199.0)
    assert quarantined_capabilities(state) == ()
    assert events == ()

    state = begin_recovery_cycle(state, first_recovery=("C.SUB",))
    for phase, generation in (("RECOVERY_1", 14), ("RECOVERY_2", 15)):
        state = record_visit(
            state, capability="C.SUB", phase=phase, decision="REJECT",
            retained_optimizer_updates=0, generation=generation)
    state, events = complete_recovery_cycle(
        state, weakest_tail=("C.SUB",),
        scores={"C.SUB": {"correct": 4, "total": 12}}, generation=16,
        elapsed_seconds=1200.0)
    assert quarantined_capabilities(state) == ("C.SUB",)
    assert events[0]["stagnant_seconds"] == 1200.0


def test_recent_held_out_gain_resets_stagnation_clock():
    state = session()
    state = observe_paired_progress(
        state, measured_capabilities=("C.SUB",),
        improved_capabilities=("C.SUB",), measurement_usable=True,
        elapsed_seconds=1100.0,
        progress_checkpoint={"filename": "bundles/current", "sha256": "a" * 64,
                             "optimizer_step": 100,
                             "model_and_native_adamw": True})
    state = begin_recovery_cycle(state, first_recovery=("C.SUB",))
    for phase, generation in (("RECOVERY_1", 21), ("RECOVERY_2", 22)):
        state = record_visit(
            state, capability="C.SUB", phase=phase, decision="REJECT",
            retained_optimizer_updates=0, generation=generation)
    state, events = complete_recovery_cycle(
        state, weakest_tail=("C.SUB",),
        scores={"C.SUB": {"correct": 7, "total": 12}}, generation=23,
        elapsed_seconds=1210.0)
    assert quarantined_capabilities(state) == ()
    assert events == ()


def test_unavailable_paired_measurement_cannot_prove_stagnation():
    state = session()
    state = observe_paired_progress(
        state, measured_capabilities=("C.SUB",),
        improved_capabilities=(), measurement_usable=False,
        elapsed_seconds=1190.0,
        progress_checkpoint={"filename": "bundles/current", "sha256": "b" * 64,
                             "optimizer_step": 101,
                             "model_and_native_adamw": True})
    state = begin_recovery_cycle(state, first_recovery=("C.SUB",))
    for phase, generation in (("RECOVERY_1", 21), ("RECOVERY_2", 22)):
        state = record_visit(
            state, capability="C.SUB", phase=phase, decision="REJECT",
            retained_optimizer_updates=0, generation=generation)
    state, events = complete_recovery_cycle(
        state, weakest_tail=("C.SUB",),
        scores={"C.SUB": {"correct": 7, "total": 12}}, generation=23,
        elapsed_seconds=1210.0)
    assert quarantined_capabilities(state) == ()
    assert events == ()


def test_capability_that_breaks_out_of_tail_is_not_quarantined():
    state = begin_recovery_cycle(session(), first_recovery=("C.SUB",))
    for phase, generation in (("RECOVERY_1", 11), ("RECOVERY_2", 12)):
        state = record_visit(state, capability="C.SUB", phase=phase,
                             decision="REJECT", retained_optimizer_updates=0,
                             generation=generation)
    state, events = complete_recovery_cycle(
        state, weakest_tail=("B.AND", "B.OR", "B.XOR"),
        scores={"C.SUB": {"correct": 7, "total": 12},
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
        session(), first_recovery=("C.SUB",))
    for phase, generation in (("RECOVERY_1", 11), ("RECOVERY_2", 12)):
        state = record_visit(
            state, capability="C.SUB", phase=phase, decision="REJECT",
            retained_optimizer_updates=0, generation=generation)
    state, _ = complete_recovery_cycle(
        state, weakest_tail=("C.SUB",),
        scores={"C.SUB": {"correct": 5, "total": 12}}, generation=13)
    assert end_of_run_alerts(state)[0]["action"] == "WITHHELD_UNTIL_BOUNDED_REPROBE"

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


def test_quarantine_gets_one_full_recovery_cycle_cooldown_then_bounded_reprobe():
    from bilqis_mlx.learning import stagnation_control

    state = session()
    state["cycle_index"] = 20
    state["quarantined"] = {
        "C.SUB": {
            "capability": "C.SUB",
            "cycle_index": 20,
            "reason": "fixture",
        },
    }
    state["alerts"] = [{
        "capability": "C.SUB",
        "delivery": "END_OF_RUN_REVIEW",
        "action": "WITHHELD_UNTIL_BOUNDED_REPROBE",
        "reason": "fixture",
        "trigger_generation": 100,
        "required_mastery_debt": True,
    }]

    state = begin_recovery_cycle(state, first_recovery=("B.AND",))
    assert state["cycle_index"] == 21
    assert stagnation_control.bounded_reprobe_due(state, grade="C") == ()

    state = begin_recovery_cycle(state, first_recovery=("B.AND",))
    assert state["cycle_index"] == 22
    assert stagnation_control.bounded_reprobe_due(state, grade="C") == ("C.SUB",)

    state, event = stagnation_control.activate_bounded_reprobe(
        state, capabilities=("C.SUB",), generation=110)
    assert quarantined_capabilities(state) == ()
    assert state["rehabilitation"]["mode"] == "BOUNDED_REPROBE"
    assert event["event"] == "SCHOOL_STAGNATION_BOUNDED_REPROBE_STARTED"
    assert end_of_run_alerts(state)[0]["action"] == "RELEASED_FOR_BOUNDED_REPROBE"


def test_bounded_reprobe_can_requarantine_after_fresh_two_round_failure():
    from bilqis_mlx.learning import stagnation_control

    state = session()
    state["cycle_index"] = 22
    state["quarantined"] = {
        "C.SUB": {
            "capability": "C.SUB", "cycle_index": 20,
            "reason": "fixture",
        },
    }
    state, _ = stagnation_control.activate_bounded_reprobe(
        state, capabilities=("C.SUB",), generation=110)
    state["cycle_first_recovery"] = ["C.SUB"]
    state["last_progress_elapsed_seconds"]["C.SUB"] = 0.0
    for phase, generation in (("RECOVERY_1", 111), ("RECOVERY_2", 112)):
        state = record_visit(
            state, capability="C.SUB", phase=phase, decision="REJECT",
            retained_optimizer_updates=0, generation=generation)

    state, events = complete_recovery_cycle(
        state, weakest_tail=("C.SUB",),
        scores={"C.SUB": {"correct": 5, "total": 12}}, generation=113,
        elapsed_seconds=2400.0)

    assert quarantined_capabilities(state) == ("C.SUB",)
    assert state.get("rehabilitation") is None
    assert any(event["event"] == "SCHOOL_CAPABILITY_STAGNATION_QUARANTINED"
               for event in events)
    assert any(event["event"] == "SCHOOL_STAGNATION_BOUNDED_REPROBE_COMPLETED"
               for event in events)


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


class StagnationControlUnittestCoverage(unittest.TestCase):
    """Keep the repository's unittest-based npm test command authoritative."""

    def test_promotion_sweep_visit_does_not_trigger_quarantine(self):
        test_promotion_sweep_visit_is_recorded_without_recovery_evidence()

    def test_b_stagnation_policy_never_withholds_b(self):
        test_b_is_never_withheld_even_after_full_stagnation_evidence()

    def test_b_only_cannot_stop_stagnation_run(self):
        test_b_alone_cannot_quarantine_or_end_stagnation_run()

    def test_two_rejected_recovery_rounds(self):
        test_two_rejected_recovery_rounds_and_repeated_tail_quarantine_without_new_threshold()

    def test_retained_update_prevents_quarantine(self):
        test_a_retained_recovery_update_prevents_quarantine()

    def test_twenty_minute_no_progress_window(self):
        test_stagnation_requires_twenty_minutes_without_measured_progress()

    def test_recent_gain_resets_stagnation_clock(self):
        test_recent_held_out_gain_resets_stagnation_clock()

    def test_unavailable_paired_measurement_delays_quarantine(self):
        test_unavailable_paired_measurement_cannot_prove_stagnation()

    def test_breakout_from_tail_prevents_quarantine(self):
        test_capability_that_breaks_out_of_tail_is_not_quarantined()

    def test_sole_grade_rehabilitation_prevents_requarantine(self):
        test_sole_grade_rehabilitation_releases_debt_and_prevents_requarantine()

    def test_rehabilitation_supersedes_stale_alert(self):
        test_rehabilitation_supersedes_stale_withheld_alert()

    def test_rehabilitation_exemption_is_capability_scoped(self):
        test_rehabilitation_exemption_is_limited_to_recorded_debt_capabilities()

    def test_scope_reconciliation_resets_cycle_evidence(self):
        test_scope_reconciliation_expands_required_contract_and_resets_cycle_evidence()

    def test_outside_scope_operations_fail_closed(self):
        test_stagnation_operations_reject_capabilities_outside_current_required_scope()

    def test_optimizer_step_grace_expires(self):
        test_optimizer_step_grace_is_b_scoped_and_expires_at_absolute_deadline()

    def test_repeated_grace_request_does_not_reset_deadline(self):
        test_repeated_grace_request_does_not_reset_deadline()

    def test_grace_suppresses_quarantine_but_keeps_evidence(self):
        test_grace_suppresses_quarantine_but_keeps_diagnostic_evidence()

    def test_b_grace_preserves_other_grade_containment(self):
        test_b_grace_does_not_disable_other_grade_containment()
