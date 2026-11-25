"""Executed exact correction changes realized action, not acceptance authority."""
from types import SimpleNamespace as N

import pytest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_candidate import resolve_candidate
from bilqis_mlx.learning.teacher_realized_action import describe
from bilqis_mlx.runtime.bamf_operator.session_parts.learning_trace import CandidateLearningTrace
from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation, record_bamf_rejection
from bilqis_mlx.runtime.outcomes.observations import apply_outcome
from bilqis_mlx.runtime.outcomes.replay import replay_rejected_outcomes
from bilqis_mlx.runtime.tests.correction.capability_support_owner_support import source_qualified_state
from bilqis_mlx.runtime.tests.custody.bamf_bundle.cold_resume_probe import retained_digest
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import shape_patch
from bilqis_mlx.runtime.tests.teacher.outcomes import test_rejection_custody as custody

def _policy():
    return {'lr': .001, 'depth': 1, 'distill': 0}
ROWS = ({'id': 'primary'}, {'id': 'class'}, {'id': 'miss'})
def _controls():
    return {'fragile_preservation_delivered': 1,
            'exact_miss_delivery_ids': ('miss',), 'exact_miss_replay_delivered': 1,
            'weakness_class_matches': {'debt': ['class']}}


def _trace(selection=None, parent_step=4):
    if selection is None:
        selection = N(visit=N(identity=N(visit_id='1'*64)), option_id='A.IDENTITY')
    identity = selection.visit.identity
    return CandidateLearningTrace(
        selection, generation=getattr(identity, 'generation', 1),
        accepted_manifest_sha256=getattr(identity, 'accepted_manifest_sha256', '2'*64),
        candidate_attempt_ordinal=1, parent_optimizer_step=parent_step)


def _record(trace, step, controls=None):
    trace.delivery(None, 'A.IDENTITY', step, ROWS, controls=_controls() if controls is None else controls,
                   preservation=ROWS[1:])


def _describe(trace, policy=None):
    return describe(_policy() if policy is None else policy, **{key: value for key, value in trace.summary().items()
                              if key != 'attempt_id'})


def test_exact_credit_requires_executed_preservation_and_preserves_legacy_identity():
    trace = _trace()
    # Preparing a packet alone cannot become a realized optimizer step.
    with pytest.raises(BilqisError):
        trace.summary()
    legacy = {'fragile_preservation_delivered': 1,
              'weakness_class_matches': {'debt': ['class']}}
    _record(trace, 5, legacy)
    old = _describe(trace)
    # Fingerprint reproduced from the pinned pre-repair implementation.
    assert old['key'] == '7e99f46231b42ab6'
    assert 'exact_miss_replay_delivered' not in old['features']
    assert old == describe(_policy(), candidate_steps=1, batch_size=3,
                           policy_controls=(legacy,), guidance_applied_steps=0,
                           enrichment_examples=0)
    exact = _trace()
    _record(exact, 5)
    # Another prepared but never executed lesson does not change these facts.
    action = _describe(exact)
    assert action['key'] != old['key']
    assert action['features']['exact_miss_replay_delivered'] == 1
    assert action['features']['fragile_preservation_delivered'] == 1
    assert action['features']['weakness_class_exposures'] == {'debt': 1}
    assert action['features']['optimizer_batches_observed'] == 1
    assert exact.summary()['candidate_steps'] == 1


@pytest.mark.parametrize('bad', [
    {'exact_miss_delivery_ids': ('miss', 'miss'), 'exact_miss_replay_delivered': 2},
    {'exact_miss_delivery_ids': ('not-delivered',)},
    {'exact_miss_delivery_ids': ('primary',)},
    {'exact_miss_delivery_ids': ('class',)},
    {'exact_miss_replay_delivered': 0},
    {'exact_miss_replay_delivered': True},
    {'fragile_preservation_delivered': 2},
])
def test_trace_rejects_forged_or_misattributed_actual_credit(bad):
    trace = _trace()
    with pytest.raises(BilqisError) as error:
        _record(trace, 5, {**_controls(), **bad})
    assert error.value.context['reason'] == 'BAMF_LEARNING_TRACE_EXACT_MISS_DELIVERY_DRIFT'
    with pytest.raises(BilqisError):
        trace.summary()


@pytest.fixture
def native_custody():
    fixture = custody.NativeRejectionOutcomeTests()
    fixture.setUp()
    try:
        yield fixture
    finally:
        fixture.tearDown()


@pytest.mark.parametrize('accepted', (True, False))
def test_actual_owner_outcome_and_transaction_resolution(native_custody, monkeypatch, accepted):
    fixture = native_custody
    parent = fixture.parent()
    before = retained_digest(parent.retained_state)
    pointer = (fixture.run / 'bamf-state.json').read_bytes()
    original = custody.build_outcome
    captured = []

    def build(run, selection, evaluation, decision, evidence, **kwargs):
        # Existing issued C03/C05 fixture; replace its fabricated summary with
        # the actual ordinary delivery trace from one executed fixture step.
        trace = _trace(selection, parent.retained_state.optimizer_step)
        _record(trace, parent.retained_state.optimizer_step + 1, {
            'fragile_preservation_delivered': 1,
            'exact_miss_delivery_ids': ('miss',), 'exact_miss_replay_delivered': 1})
        captured.append(decision)
        return original(run, selection, evaluation, decision, evidence,
                        learning_summary=trace.summary())

    monkeypatch.setattr(custody, 'build_outcome', build)
    parent, teacher, cache, evidence = fixture.fixture(
        accepted=accepted, learning_first=True)
    outcome = evidence['how_outcome']
    decision, = captured
    assert decision.accepted is accepted
    assert outcome['retained_steps'] == int(accepted)
    assert outcome['attempted_steps'] == 1
    assert outcome['realized_action']['features']['exact_miss_replay_delivered'] == 1
    # Real candidate transaction, disposable tiny fixture, not a model run.
    source, transaction, candidate, _ = source_qualified_state(
        parent.retained_state, extents=parent.extents, spec=parent.topology)
    resolved = resolve_candidate(transaction, accepted=decision.accepted)
    assert resolved.optimizer_step == source.optimizer_step + int(accepted)
    if accepted:
        assert retained_digest(resolved) == retained_digest(candidate)
        credited = apply_outcome(teacher, outcome)
        assert apply_outcome(credited, outcome) == credited
    else:
        assert resolved is source
        assert retained_digest(resolved) == before
        record_bamf_rejection(fixture.run, parent, evidence)
        credited = replay_rejected_outcomes(fixture.run, parent, cache, teacher)
        assert replay_rejected_outcomes(fixture.run, parent, cache, credited) == credited
        assert (fixture.run / 'bamf-state.json').read_bytes() == pointer
        with shape_patch():
            restored = load_bamf_generation(fixture.run / 'bamf-state.json')
        assert retained_digest(restored.retained_state) == before
    assert credited['causal_experiment']['events'] == 1
    context = next(iter(credited['causal_experiment']['contexts'].values()))
    credit = next(iter(context.values()))
    record = credit['realized_actions'][outcome['realized_action']['key']]
    assert record['trials'] == 1
    assert record['retained'] == int(accepted)
    assert record['unsafe'] == int(not accepted)
