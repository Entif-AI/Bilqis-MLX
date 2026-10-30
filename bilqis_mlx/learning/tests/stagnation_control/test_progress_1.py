from bilqis_mlx.learning.stagnation_control import (
    begin_recovery_cycle, complete_recovery_cycle, end_of_run_alerts,
    quarantined_capabilities, record_visit, start_session,
    create_optimizer_step_grace, grace_suppressed_capabilities,
    observe_paired_progress, reconcile_optimizer_step_grace,
    reconcile_required_scope,
)
import unittest
from bilqis_mlx.learning.tests.stagnation_control.fixtures import session


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


class StagnationTests1(unittest.TestCase):
    def test_two_rejected_recovery_rounds_and_repeated_tail_quarantine_without_new_threshold(self):
        test_two_rejected_recovery_rounds_and_repeated_tail_quarantine_without_new_threshold()

    def test_a_retained_recovery_update_prevents_quarantine(self):
        test_a_retained_recovery_update_prevents_quarantine()

    def test_stagnation_requires_twenty_minutes_without_measured_progress(self):
        test_stagnation_requires_twenty_minutes_without_measured_progress()

    def test_recent_held_out_gain_resets_stagnation_clock(self):
        test_recent_held_out_gain_resets_stagnation_clock()

    def test_unavailable_paired_measurement_cannot_prove_stagnation(self):
        test_unavailable_paired_measurement_cannot_prove_stagnation()

    def test_capability_that_breaks_out_of_tail_is_not_quarantined(self):
        test_capability_that_breaks_out_of_tail_is_not_quarantined()
