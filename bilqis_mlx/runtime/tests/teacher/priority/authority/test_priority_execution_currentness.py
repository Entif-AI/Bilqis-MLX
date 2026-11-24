"""Portable execution and currentness tests, using the shared priority harness."""
from types import SimpleNamespace
import sys
from unittest.mock import patch
import pytest

from bilqis_mlx.runtime.tests.teacher.priority.test_priority_execution import (
    pytestmark, priority, HParams, Observation, Offer, Visit, lawful,
    _candidate_owner, _contracts_owner,
)
from bilqis_mlx.errors import BilqisError

def test_execution_owns_rows_policy_and_teacher_rate(priority):
    candidate = _candidate_owner(priority)
    identity = SimpleNamespace(to_record=lambda: {'visit': 1})
    selected = priority._issue_result('TEACHER_SELECTED', 'o', Offer(), Visit(identity),
        {'lr': 0.25, 'nested': {'x': 1}}, {}, 'g', (), '/run', lawful())
    selected.policy['nested']['x'] = 99
    release = SimpleNamespace(execution_plan=SimpleNamespace(capability_map={
        'cap': SimpleNamespace(teaching_option_ids=('instruction',))}))
    with patch.object(candidate, 'AdamWHyperparameters', HParams), \
         patch.object(candidate, '_require_current_visit'), \
         patch.object(candidate.BamfVisitProvenance, 'from_c03_record', return_value='provenance'), \
         patch.object(candidate, 'describe_delivered_teaching', return_value='delivery'), \
         patch.object(candidate, 'execute_factory_candidate_step', return_value='step') as execute:
        assert priority.execute_accepted_priority_candidate(selected, SimpleNamespace(release=release), 'atlas', 'features',
            teacher_hparams=HParams(0.01, (0.8, 0.9), 1e-8, 0.2), observation=Observation(({'id': 'old'},), 0),
            optimizer_step_seed=3, max_norm=1, capture_diagnostics=True) == 'step'
    args, kw = execute.call_args
    assert args[5] == ({'id': 'one', 'capability': 'cap'},)
    assert kw['teacher_strategy'] == {'lr': 0.25, 'nested': {'x': 1}}
    assert kw['teacher_hparams'] == HParams(0.25, (0.8, 0.9), 1e-8, 0.2)
    assert kw['observation'] == Observation(
        args[5], 7, controls={
            'fragile_preservation_delivered': 0,
            'retention_support_delivered': 0,
            'fresh_support_delivered': 0,
        })
    assert kw['capture_diagnostics'] is True
    assert kw['prepared_source'] is selected.offer.materialized


def test_execution_reuses_authenticated_planning_parent(priority):
    candidate = _candidate_owner(priority)
    identity = SimpleNamespace(to_record=lambda: {'visit': 1})
    selected = priority._issue_result('TEACHER_SELECTED', 'o', Offer(), Visit(identity),
        {'lr': 0.25}, {}, 'g', (), '/run', lawful())
    release = SimpleNamespace(execution_plan=SimpleNamespace(capability_map={
        'cap': SimpleNamespace(teaching_option_ids=('instruction',))}))
    with patch.object(candidate, 'AdamWHyperparameters', HParams), \
         patch.object(candidate, '_require_current_visit') as require_visit, \
         patch.object(candidate.BamfVisitProvenance, 'from_c03_record', return_value='provenance'), \
         patch.object(candidate, 'describe_delivered_teaching', return_value='delivery'), \
         patch.object(candidate, 'execute_factory_candidate_step', return_value='step') as execute:
        assert priority.execute_accepted_priority_candidate(
            selected, SimpleNamespace(release=release), 'atlas', 'features',
            teacher_hparams=HParams(0.01, (0.8, 0.9), 1e-8, 0.2),
            observation=Observation(({'id': 'old'},), 0), optimizer_step_seed=3,
            max_norm=1, candidate_step_started_at=123.0,
            source_prepare_wall_seconds=0.75) == 'step'
    require_visit.assert_called_once_with(
        'planned-parent', 'planned-cache', selected.visit,
        candidate_identity_sha256='planned-id',
        currentness_step='currentness',
        currentness_transaction='currentness')
    assert execute.call_args.args[2] == 'planned-parent'
    assert execute.call_args.kwargs['semantic_context'] == 'semantic-context'
    assert execute.call_args.kwargs['currentness_transaction'] == 'currentness'
    assert execute.call_args.kwargs['currentness_binding_wall_seconds'] >= 0.0
    assert execute.call_args.kwargs['candidate_step_started_at'] == 123.0
    assert execute.call_args.kwargs[
        'upstream_pre_neural_source_compile_wall_seconds'] >= 0.75


def test_final_live_currentness_fence_is_immediately_before_candidate_execution(priority):
    candidate = _candidate_owner(priority)
    currentness_owner = sys.modules[
        'bilqis_mlx.runtime.bamf_bundle.currentness_transaction']
    identity = SimpleNamespace(to_record=lambda: {'visit': 1})
    selected = priority._issue_result('TEACHER_SELECTED', 'o', Offer(), Visit(identity),
        {'lr': 0.25}, {}, 'g', (), '/run', lawful())
    release = SimpleNamespace(execution_plan=SimpleNamespace(capability_map={
        'cap': SimpleNamespace(teaching_option_ids=('instruction',))}))
    events = []

    def fence(step, transaction, parent):
        events.append('fence')
        return step

    def execute(*args, **kwargs):
        events.append('execute')
        return 'step'

    def delivery(*args, **kwargs):
        events.append('delivery')
        return 'delivery'

    with patch.object(candidate, 'AdamWHyperparameters', HParams), \
         patch.object(candidate, '_require_current_visit'), \
         patch.object(candidate.BamfVisitProvenance, 'from_c03_record', return_value='provenance'), \
         patch.object(candidate, 'describe_delivered_teaching', side_effect=delivery), \
         patch.object(currentness_owner, 'require_live_accepted_currentness_step', side_effect=fence), \
         patch.object(candidate, 'execute_factory_candidate_step', side_effect=execute):
        assert priority.execute_accepted_priority_candidate(
            selected, SimpleNamespace(release=release), 'atlas', 'features',
            teacher_hparams=HParams(0.01, (0.8, 0.9), 1e-8, 0.2),
            observation=Observation(({'id': 'old'},), 0), optimizer_step_seed=3,
            max_norm=1) == 'step'

    assert events[-2:] == ['fence', 'execute']


def test_visit_binding_pays_static_priority_authority_once(priority):
    candidate = _candidate_owner(priority)
    currentness_owner = sys.modules[
        'bilqis_mlx.runtime.bamf_bundle.currentness_transaction']

    class CountingOffer(Offer):
        def __init__(self):
            self.current_calls = 0
            self.materialized = SimpleNamespace(
                offer=self,
                rows=({'id': 'one', 'capability': 'cap'},),
            )

        def require_current(self, context, parent, *, prepared_rows=None):
            self.current_calls += 1
            return self.materialized

    offer = CountingOffer()
    identity = SimpleNamespace(to_record=lambda: {'visit': 1})
    selected = priority._issue_result(
        'TEACHER_SELECTED', 'o', offer, Visit(identity), {'lr': 0.25}, {}, 'g', (),
        '/run', lawful())
    release = SimpleNamespace(
        release_sha256='b' * 64,
        execution_plan=SimpleNamespace(capability_map={
        'cap': SimpleNamespace(teaching_option_ids=('instruction',))}))
    source_context = SimpleNamespace(release=release)
    calls = []

    with patch.object(
            currentness_owner, 'refresh_accepted_currentness',
            side_effect=lambda transaction, parent:
            calls.append('refresh') or transaction), \
         patch.object(
            currentness_owner, 'require_live_accepted_currentness_step',
            side_effect=lambda step, transaction, parent:
            calls.append('live-fence') or step), \
         patch.object(candidate, 'AdamWHyperparameters', HParams), \
         patch.object(candidate, '_require_current_visit') as require_visit, \
         patch.object(
            candidate.BamfVisitProvenance, 'from_c03_record',
            return_value='provenance'), \
         patch.object(
            candidate, 'describe_delivered_teaching',
            return_value='delivery'), \
         patch.object(
            candidate, 'execute_factory_candidate_step',
            return_value='step') as execute:
        binding = priority.prepare_accepted_priority_candidate_visit(
            selected, source_context)
        for _ in range(2):
            assert priority.execute_accepted_priority_candidate(
                selected, source_context, 'atlas', 'features',
                teacher_hparams=HParams(0.01, (0.8, 0.9), 1e-8, 0.2),
                observation=Observation(({'id': 'old'},), 0),
                optimizer_step_seed=3, max_norm=1,
                candidate_visit=binding) == 'step'

    assert offer.current_calls == 1
    assert require_visit.call_count == 1
    assert calls.count('live-fence') == 1
    assert calls.count('refresh') == 3
    assert execute.call_count == 2


