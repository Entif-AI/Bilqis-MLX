"""Separate salience, current holds and recovery observations without authority."""
from dataclasses import replace
import random
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.diagnostics.signals import observe_salience_priority
from bilqis_mlx.learning.salience_teacher import AttentionFrontier, choose_priority_teaching
from bilqis_mlx.learning.salience_contracts import AuthoritySnapshot, ActionKind, Metric
from bilqis_mlx.learning.atlas_salience import derive_salience, verify_salience_inputs
from bilqis_mlx.learning.salience_history import SalienceHistory, EventKind, append_salience_event
from bilqis_mlx.learning.tests.test_atlas_salience import _policy, _fact, _novelty, _option, _signed
from bilqis_mlx.learning.tests.test_salience_teacher import _fixture
from bilqis_mlx.learning.tests.test_salience_history import _window_policy, _event
from bilqis_mlx.learning.tests.test_salience_patterns import _history, _aggregation_policy, _REGISTRY
from bilqis_mlx.learning.tests.test_learning_experiment import schedule_program
from bilqis_mlx.learning.learning_experiment import Settings
from bilqis_mlx.curriculum.scheduler import start_new
import bilqis_mlx.compatibility.historical_teacher_policy as engine


def _frontier(*, only_held=False):
    epoch, original, history, school, _ = _fixture()
    context = original.options[0].context
    other = replace(context, capability_id='other-capability')
    snapshot = AuthoritySnapshot((context, other), 1000, _REGISTRY)
    policy = _policy()
    def evidence(context, novel=False):
        facts = (_fact(Metric.DECLARED_IMPACT, 1, policy, context=context),
                 _fact(Metric.BLOCKED_COUNT, 0, policy, context=context),
                 _fact(Metric.DEADLINE_AT, 1001, policy, context=context))
        if novel:
            facts += (_fact(Metric.NOVELTY_COMPARISON,
                            replace(_novelty(), observed_outcome_sha256='4' * 64), policy, context=context),)
        return derive_salience(verify_salience_inputs(facts, policy, snapshot, context))
    known, novel = evidence(other), evidence(context, True)
    options = ((_option('held', novel, rights=False, relevant=True),) if only_held else (
        _option('routine', known), _option('novel', novel, action=ActionKind.EXPLORATION, exploration=True),
        _option('urgent', known, relevant=True), _option('held', novel, rights=False, relevant=True)))
    items = tuple((option.stable_id, novel if option.stable_id in ('held', 'novel') else known) for option in options)
    return epoch, AttentionFrontier(options, items, snapshot), history, school


class SalienceDiagnosticsTests(unittest.TestCase):
    def test_separate_dimensions_order_masks_and_held_evidence(self):
        _, frontier, history, _ = _frontier()
        program = schedule_program(('grade-one', ('other-capability',)),
                                   ('grade-two', (frontier.options[1].context.capability_id,)))
        report = observe_salience_priority(frontier, history, program)
        self.assertEqual(tuple(option.stable_id for option in report.ranked.ordered), ('urgent', 'novel', 'routine'))
        by_id = {item.option.stable_id: item for item in report.options}
        self.assertEqual(int(by_id['held'].evidence.novelty.ordinal), 3)
        self.assertEqual(by_id['held'].hold_reason, 'SOURCE_RIGHTS_OR_PREREQUISITE_HELD')
        self.assertEqual(by_id['routine'].supervision_mask, (True, True, False))
        self.assertEqual(by_id['held'].supervision_mask, (True, True, True))
        self.assertEqual(report.aggregation_status, 'NOT_MEASURED')
        self.assertIsNone(report.aggregation)
        self.assertFalse(report.teaching_permission)
        with self.assertRaises(BilqisError):
            observe_salience_priority(frontier, history, program, annotations=('unconsumed',))

    def test_native_grade_renaming_preserves_priority_and_actionable_holds(self):
        epoch, frontier, history, school = _frontier()
        results = []
        for names in (('A', 'B'), ('later', 'first')):
            program = schedule_program((names[0], (frontier.options[1].context.capability_id,)),
                                       (names[1], ('other-capability',)))
            state = start_new(program, school.current_student)
            report = observe_salience_priority(frontier, history, program)
            decision = choose_priority_teaching(frontier, history, epoch, engine, state,
                                                random.Random(12), Settings(), program=program)
            self.assertEqual(decision.lesson_grade, names[1])
            results.append((report.ranked, decision.selected_option_id, decision.policy_json))
            _, held_frontier, _, _ = _frontier(only_held=True)
            held = choose_priority_teaching(held_frontier, history, epoch, engine, state,
                                            random.Random(12), Settings(), program=program)
            self.assertEqual(held.status, 'NO_ADMISSIBLE_TEACHING')
            self.assertIsNone(held.policy_json)
        self.assertEqual(results[0], results[1])

    def test_missing_vs_measured_unchanged_and_explicit_later_changes(self):
        _, frontier, _, _ = _frontier()
        policy = _policy()
        history = SalienceHistory(_window_policy(policy), ())
        lesson = _event(0, policy, kind=EventKind.ACCEPTED_LESSON, defect=None)
        second_lesson = _event(1, policy, kind=EventKind.ACCEPTED_LESSON, defect=None)
        unchanged = _event(2, policy, kind=EventKind.FOLLOWUP, linked=lesson.source_receipt_sha256,
                           defect=None, before='4' * 64, after='4' * 64)
        for event in (lesson, second_lesson, unchanged,
                      *(_event(index, policy, defect=None) for index in range(3, 20))):
            history = append_salience_event(history, event, event.evidence.basis.snapshot)
        program = schedule_program(('one', ('other-capability', frontier.options[1].context.capability_id)))
        report = observe_salience_priority(frontier, history, program)
        recovery = report.recovery[0]
        effects = {item.anchor_receipt_sha256: item for item in recovery.lesson_effects}
        self.assertEqual(effects[lesson.source_receipt_sha256].action_status, 'MEASURED_UNCHANGED')
        self.assertEqual(effects[second_lesson.source_receipt_sha256].action_status, 'NOT_MEASURED')
        self.assertEqual(effects[lesson.source_receipt_sha256].route_status, 'NOT_MEASURED')
        self.assertEqual(effects[lesson.source_receipt_sha256].followup_event_digests, (unchanged.digest(),))
        self.assertEqual(recovery.count_scope, 'CURRENT_WINDOW')
        self.assertEqual(recovery.correction_scope, 'CAPABILITY_PARTITION_PREFIX')

    def test_current_rights_hold_applies_without_optional_aggregation(self):
        _, frontier, _, _ = _frontier()
        history = _history(20)
        program = schedule_program(('one', ('other-capability', frontier.options[1].context.capability_id)))
        snapshot = replace(frontier.snapshot, contexts=tuple(replace(context, rights_epoch=2)
                                                            for context in frontier.snapshot.contexts))
        # Rebuild current signed options/evidence at the new rights epoch; old history stays historical.
        evidence_by_id, options = [], []
        for option in frontier.options:
            context = replace(option.context, rights_epoch=2)
            old = dict(frontier.evidence)[option.stable_id].basis
            facts = tuple(_signed(replace(fact, context=context)) for fact in old.facts)
            evidence = derive_salience(verify_salience_inputs(facts, old.policy, snapshot, context))
            options.append(_signed(replace(option, context=context, salience_inputs_digest=evidence.basis.digest(),
                                            rights_eligible=False)))
            evidence_by_id.append((option.stable_id, evidence))
        current = AttentionFrontier(tuple(options), tuple(evidence_by_id), snapshot)
        report = observe_salience_priority(current, history, program)
        self.assertEqual(report.recovery[0].authority_status, 'HISTORICAL_CURRENTLY_HELD')
        self.assertEqual(report.ranked.ordered, ())
        self.assertEqual(report.recovery[0].window.events, history.events)
        measured = observe_salience_priority(current, history, program, aggregation_policy=_aggregation_policy(history))
        self.assertEqual(measured.aggregation_status, 'MEASURED')
        self.assertEqual(measured.aggregation.investigation_pattern_ids, ())

    def test_prior_window_anchor_changed_axis_and_cumulative_corrections(self):
        from bilqis_mlx.runtime.operator_registry import RouteKind
        _, frontier, _, _ = _frontier()
        policy = _policy()
        lesson = _event(0, policy, kind=EventKind.ACCEPTED_LESSON, defect=None)
        correction = _event(1, policy, kind=EventKind.CORRECTION_APPLIED, defect=None)
        events = [lesson, correction, _event(2, policy, kind=EventKind.FOLLOWUP,
                  linked=correction.source_receipt_sha256, defect=False)]
        events.extend(_event(index, policy, defect=None) for index in range(3, 20))
        changed = _event(20, policy, kind=EventKind.FOLLOWUP,
                         linked=lesson.source_receipt_sha256, defect=None, before='4' * 64, after='5' * 64)
        changed = _signed(replace(changed, before_route=RouteKind.EXACT, after_route=RouteKind.NEURAL_COMPOSITION))
        events.extend((changed, _event(21, policy, kind=EventKind.FOLLOWUP,
                      linked=lesson.source_receipt_sha256, defect=None, before='4' * 64, after='4' * 64),
                       _event(22, policy, kind=EventKind.FOLLOWUP,
                              linked=correction.source_receipt_sha256, defect=True)))
        events.extend(_event(index, policy, defect=None) for index in range(23, 40))
        history = SalienceHistory(_window_policy(policy), ())
        for event in events:
            history = append_salience_event(history, event, event.evidence.basis.snapshot)
        program = schedule_program(('one', ('other-capability', frontier.options[1].context.capability_id)))
        report = observe_salience_priority(frontier, history, program)
        first, second = report.recovery
        self.assertEqual(first.authority_status, 'CURRENT_SOURCE_BOUND')
        self.assertEqual(first.lesson_effects[0].action_status, 'NOT_MEASURED')
        self.assertEqual(second.lesson_effects[0].action_status, 'CHANGED')
        self.assertEqual(second.lesson_effects[0].route_status, 'CHANGED')
        self.assertEqual(second.lesson_effects[0].anchor_event_digest, lesson.digest())
        self.assertEqual(first.window.correction_followups[0].status, 'NO_RECURRENCE_IN_MEASURED_FOLLOWUP')
        self.assertEqual(second.window.correction_followups[0].status, 'RECURRENCE_OBSERVED')
        with self.assertRaises(BilqisError):
            observe_salience_priority(frontier, history, schedule_program(('missing', ('not-the-capability',))))

    def test_partial_trailing_and_future_events_remain_authority_observations(self):
        _, frontier, _, _ = _frontier()
        program = schedule_program(('one', ('other-capability', frontier.options[1].context.capability_id)))
        history = _history(21)
        partial = observe_salience_priority(frontier, replace(history, events=history.events[:1]), program)
        twenty = observe_salience_priority(frontier, replace(history, events=history.events[:20]), program)
        trailing = observe_salience_priority(frontier, history, program)
        self.assertNotEqual(twenty.history_digest, trailing.history_digest)
        self.assertEqual(partial.window_policy_digest, history.policy.digest())
        self.assertEqual(partial.history_events[0].authority_status, 'CURRENT_SOURCE_BOUND')
        self.assertIsNone(partial.history_events[0].completed_window_id)
        self.assertEqual(len(trailing.history_events), 21)
        self.assertIsNone(trailing.history_events[-1].completed_window_id)
        self.assertEqual(trailing.history_events[-1].event, history.events[-1])
        old_rights_event = _event(0, _policy(), context=replace(history.events[0].evidence.scope, rights_epoch=0))
        revoked = observe_salience_priority(frontier, replace(history, events=(old_rights_event,)), program)
        self.assertEqual(revoked.history_events[0].authority_status, 'HISTORICAL_CURRENTLY_HELD')
        future_event = _event(2000, _policy())
        future = observe_salience_priority(frontier, replace(history, events=(future_event,)), program)
        self.assertEqual(future.history_events[0].authority_status, 'FUTURE_OBSERVATION_HELD')

    def test_first_correction_anchor_is_not_reinterpreted_as_accepted_lesson(self):
        _, frontier, _, _ = _frontier()
        policy = _policy()
        correction = _event(0, policy, kind=EventKind.CORRECTION_APPLIED, defect=None)
        lesson = _event(1, policy, kind=EventKind.ACCEPTED_LESSON, defect=None,
                        receipt=correction.source_receipt_sha256)
        followup = _event(2, policy, kind=EventKind.FOLLOWUP, defect=None,
                          linked=correction.source_receipt_sha256, before='4' * 64, after='5' * 64)
        events = (correction, lesson, followup, *(_event(index, policy, defect=None) for index in range(3, 20)))
        history = SalienceHistory(_window_policy(policy), events)
        program = schedule_program(('one', ('other-capability', frontier.options[1].context.capability_id)))
        recovery = observe_salience_priority(frontier, history, program).recovery[0]
        self.assertEqual(recovery.window.changed_actions, 0)
        self.assertEqual(recovery.lesson_effects, ())
