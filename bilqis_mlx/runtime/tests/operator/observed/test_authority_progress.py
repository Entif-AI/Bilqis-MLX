"""Real operator seams retain exact hold and C05 blocker diagnostics."""
from contextlib import nullcontext
import json
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import patch

import pytest

from bilqis_mlx.runtime.bamf_operator.session import prepare_bamf_visit
from bilqis_mlx.runtime.bamf_operator.session_parts.session_execution import retention_result


@pytest.mark.parametrize('selection_status', ['HELD', 'ACTION_REQUIRED'])
def test_held_priority_reports_full_frontier_exclusions_without_execution(
        selection_status):
    messages = []
    exclusion = N(to_record=lambda: {
        'capability_id': 'cap\"one',
        'semantic_ids': ['sem.future'],
        'code': 'PREREQUISITE_HELD',
        'holds': [{
            'code': 'PREREQUISITE_EVIDENCE_REQUIRED',
            'owner': 'learner:evidence',
            'dependency_id': 'cap.parent',
        }],
    })
    selection = N(
        status=selection_status,
        holds=(('cap\"one', 'PREREQUISITE_HELD'),),
        exclusions=(exclusion,),
    )
    owner = 'bilqis_mlx.runtime.bamf_operator.session.'
    with patch(owner + '_execution_context', return_value=(object(), N(release=object()), None, None)), \
         patch(owner + 'schedule_program_from_executable_release', return_value=object()), \
         patch(owner + 'accepted_priority_school', return_value=object()), \
         patch(owner + 'select_foundation_priority_visit', return_value=selection), \
         patch(owner + '_execute_selected_visit') as execute:
        result = prepare_bamf_visit(Path('/unused'), progress=messages.append)
    assert result.status == selection_status
    payload = {
        'holds': selection.holds,
        'exclusions': [exclusion.to_record()],
    }
    assert 'priority holds: ' + json.dumps(
        payload, sort_keys=True, ensure_ascii=True) in messages
    execute.assert_not_called()


def test_c05_progress_uses_actual_owner_blocker_before_issued_token_loses_it():
    messages = []
    decision = N(accepted=False, reason='PROTECTED_CAPABILITY_REGRESSION',
                 to_record=lambda: {'reason': 'PROTECTED_CAPABILITY_REGRESSION'})
    evaluation = N(parent_state=object(), candidate_state=object(),
                   decision=N(blocking_capability='Z.established'))
    persisted = {'bytes_written': 0, 'file_fsyncs': 0, 'directory_fsyncs': 0,
                 'evidence_objects': 0, 'persistence_seconds': 0}
    with patch('bilqis_mlx.runtime.outcomes.issuance.build_outcome', return_value={}):
        result = retention_result(
            Path('/unused'), object(), N(), None, object(), 'new.target', object(),
            (N(transaction=object()),), N(finalize=lambda **kw: {'persistence': persisted}),
            1, 1, None, messages.append, None,
            evaluate_candidate=lambda *a, **kw: evaluation,
            issue_decision=lambda e: decision, identity_delta=lambda old: {},
            resource_observation=lambda *a, **kw: {}, derive_successor=lambda *a, **kw: None,
            bind_baseline_successor=lambda evaluation, successor: successor,
            finalize_generation_authority=lambda *a, **kw: None,
            prepared_visit_type=lambda *args, **kw: N(status=args[0], **kw),
            emit_progress=lambda callback, message: callback(message),
            measure_observed_phase_fn=lambda *a: nullcontext())
    assert result.status == 'REJECTED'
    assert any('blocking capability Z.established' in message for message in messages)
    assert any('PROTECTED_CAPABILITY_REGRESSION' in message for message in messages)


def test_learning_first_retention_skips_candidate_evidence_finalization():
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode

    decision = N(
        accepted=False, reason='NO_MEASURABLE_TARGET_GAIN',
        to_record=lambda: {
            'decision': 'REJECT', 'reason': 'NO_MEASURABLE_TARGET_GAIN',
        })
    evaluation = N(
        parent_state=object(), candidate_state=object(),
        decision=N(blocking_capability=None))
    capture = N(
        finalize=lambda **_kw: (_ for _ in ()).throw(
            AssertionError('ordinary mode finalized candidate evidence')),
        summary=lambda: {
            'attempt_id': 'attempt:learning-first',
            'candidate_steps': 1,
            'batch_size': 1,
            'policy_controls': ({},),
            'guidance_applied_steps': 0,
            'enrichment_examples': 0,
        })
    step = N(
        transaction=object(),
        realized_cost={
            'wall_seconds': 1.0, 'optimizer_steps': 1,
            'candidate_optimizer_steps': 1, 'c08_memory_budget_bytes': 1,
        })
    outcome = {'outcome_sha256': 'f' * 64}
    with evidence_mode(strict=False), patch(
            'bilqis_mlx.runtime.outcomes.issuance.build_outcome',
            return_value=outcome) as build:
        result = retention_result(
            Path('/unused'), object(), N(), None, object(), 'new.target', object(),
            (step,), capture, 1, 1, None, None, None,
            evaluate_candidate=lambda *a, **kw: evaluation,
            issue_decision=lambda e: decision, identity_delta=lambda old: {},
            resource_observation=lambda *a, **kw: {}, derive_successor=lambda *a, **kw: None,
            bind_baseline_successor=lambda evaluation, successor: successor,
            finalize_generation_authority=lambda *a, **kw: None,
            prepared_visit_type=lambda *args, **kw: N(status=args[0], **kw),
            emit_progress=lambda *_args: None,
            measure_observed_phase_fn=lambda *a: nullcontext())
    assert result.status == 'REJECTED'
    assert result.candidate_evidence is None
    assert result.how_outcome is outcome
    assert build.call_args.kwargs['learning_summary']['candidate_steps'] == 1


def test_learning_first_retention_does_not_enable_diagnostic_observer():
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode

    staged = []
    observer = N(stage=lambda **fields: staged.append(fields))
    owner_decision = N(
        blocking_capability=None,
        outcome_scores=(('new.target', 2, 3, 6), ('A.EDGE', 5, 5, 6)),
    )
    evaluation = N(
        parent_state=object(),
        candidate_state=object(),
        decision=owner_decision,
    )
    decision = N(
        accepted=False,
        decision='REJECT',
        reason='NO_MEASURABLE_TARGET_GAIN',
        evaluated_capability_ids=('new.target', 'A.EDGE'),
        to_record=lambda: {
            'decision': 'REJECT',
            'reason': 'NO_MEASURABLE_TARGET_GAIN',
        },
    )
    capture = N(summary=lambda: {
        'attempt_id': 'attempt:learning-first',
        'candidate_steps': 1,
        'batch_size': 1,
        'policy_controls': ({},),
        'guidance_applied_steps': 0,
        'enrichment_examples': 0,
    })
    step = N(transaction=object(), realized_cost={})
    selection = N()
    seen_kwargs = {}

    def evaluate(*_args, **kwargs):
        seen_kwargs.update(kwargs)
        return evaluation

    with evidence_mode(strict=False), patch(
            'bilqis_mlx.runtime.outcomes.issuance.build_outcome',
            return_value={
                'outcome_sha256': 'f' * 64,
                'context': {'phase': 'RECOVERY_1'},
            }):
        retention_result(
            Path('/unused'), object(), N(), None, selection, 'new.target', object(),
            (step,), capture, 1, 1, None, None, observer,
            evaluate_candidate=evaluate,
            issue_decision=lambda _evaluation: decision,
            identity_delta=lambda _old: {},
            resource_observation=lambda *_a, **_kw: {},
            derive_successor=lambda *_a, **_kw: None,
            bind_baseline_successor=lambda _evaluation, successor: successor,
            finalize_generation_authority=lambda *_a, **_kw: None,
            prepared_visit_type=lambda *args, **kw: N(status=args[0], **kw),
            emit_progress=lambda *_args: None,
            measure_observed_phase_fn=lambda *_a: nullcontext(),
        )

    assert 'observer' not in seen_kwargs
    merged = {key: value for item in staged for key, value in item.items()}
    assert merged['retention_target'] == {
        'state': 'MEASURED', 'before': 2, 'after': 3, 'total': 6}
    assert merged['retention_protected_count'] == 1
    assert merged['retention_phase'] == 'RECOVERY_1'
    assert merged['retention_decision'] == 'REJECT'
    assert merged['retention_reason'] == 'NO_MEASURABLE_TARGET_GAIN'
