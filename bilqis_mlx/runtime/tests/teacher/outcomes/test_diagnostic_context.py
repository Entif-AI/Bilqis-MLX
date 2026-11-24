"""Verified selection salience and outcome credit share one diagnostic key."""
from copy import deepcopy
import random

import pytest

from bilqis_mlx.compatibility import historical_teacher_policy as engine
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.learning_experiment import Settings
from bilqis_mlx.learning.teacher_strategy_population import effective_policy_key
from bilqis_mlx.learning.tests.test_salience_teacher import _fixture
from bilqis_mlx.runtime.outcomes.observations import apply_outcome
from bilqis_mlx.runtime.state import _fingerprint
from bilqis_mlx.runtime.teacher_policy_selection import select_visit_policy
from bilqis_mlx.semantics.domains import contract_digest


def selected_outcome(diagnostics=None):
    epoch, _, _, school, evidence = _fixture()
    teacher = epoch.teacher()
    capability, scope = evidence.scope.capability_id, evidence.scope.scope
    if diagnostics is None:
        diagnostics = {'salience_evidence': evidence, 'teacher_epoch_digest': contract_digest(epoch)}
    key, policy, metadata = select_visit_policy(engine, teacher, capability, school,
        random.Random(12), Settings(), scope, diagnostics, 'any-grade')
    diagnostic_key = metadata['diagnostic_context_key']
    payload = teacher['causal_experiment']['diagnostic_contexts'][diagnostic_key]
    value = {
        'schema': 'bilqis.bamf.teacher-outcome/v1', 'attempt_id': 'selected:1',
        'teacher_visit': {'accepted_manifest_sha256': 'a' * 64,
            'student_sha256': epoch.student_sha256, 'policy_key': key, 'capability_id': capability},
        'context': {'grade': 'any-grade', 'phase': school.stage, 'curriculum_scope': scope,
            'rubric_sha256': 'd' * 64, 'diagnostics': payload, 'diagnostic_context_key': diagnostic_key},
        'selected_teacher': deepcopy(teacher), 'selected_policy': policy,
        'effective_policy_key': effective_policy_key(policy), 'realized_action': None,
        'attempted_steps': 1, 'retained_steps': 1,
        'decision': {'decision': 'PROVISIONAL', 'reason': 'PAIRED_SCREEN_WITHIN_BUDGET',
                     'evidence_sha256': 'e' * 64},
        'scores': [[capability, 1, 2, 4]], 'protected_capabilities': [],
    }
    value['outcome_sha256'] = _fingerprint(value)
    return teacher, value, school, diagnostics


def test_native_selection_and_feedback_preserve_verified_salience_key():
    teacher, value, school, diagnostics = selected_outcome()
    credited = apply_outcome(teacher, value)
    visit, context = value['teacher_visit'], value['context']
    scope = visit['capability_id'] + '|' + school.stage + '|' + context['curriculum_scope']
    record = credited['causal_experiment']['contexts'][scope][visit['policy_key']]
    assert record['diagnostic_stats'][context['diagnostic_context_key']]['retained'] == 1
    assert 'salience' in context['diagnostics']
    key, _, selected = select_visit_policy(engine, credited, visit['capability_id'], school,
        random.Random(12), Settings(), context['curriculum_scope'], diagnostics, 'any-grade')
    assert selected['diagnostic_context_key'] == context['diagnostic_context_key']
    assert key == visit['policy_key']


def test_compact_selection_reconstructs_diagnostic_context_before_identity_check():
    epoch, _, _, school, evidence = _fixture()
    parent = epoch.teacher()
    teacher = deepcopy(parent)
    capability, scope = evidence.scope.capability_id, evidence.scope.scope
    diagnostics = {
        'salience_evidence': evidence,
        'teacher_epoch_digest': contract_digest(epoch),
    }
    key, policy, metadata = select_visit_policy(
        engine, teacher, capability, school, random.Random(12), Settings(),
        scope, diagnostics, 'any-grade')
    diagnostic_key = metadata['diagnostic_context_key']
    payload = teacher['causal_experiment']['diagnostic_contexts'][diagnostic_key]
    value = {
        'schema': 'bilqis.bamf.teacher-outcome/v1', 'attempt_id': 'compact:1',
        'proposal_id': 'a' * 64, 'candidate_evidence': {'sha256': 'b' * 64},
        'teacher_visit': {
            'accepted_manifest_sha256': 'a' * 64,
            'student_sha256': epoch.student_sha256, 'policy_key': key,
            'capability_id': capability,
        },
        'context': {
            'grade': 'any-grade', 'phase': school.stage,
            'curriculum_scope': scope, 'rubric_sha256': 'd' * 64,
            'diagnostics': payload, 'diagnostic_context_key': diagnostic_key,
        },
        'selected_teacher_sha256': _fingerprint(teacher),
        'selected_policy': policy,
        'effective_policy_key': effective_policy_key(policy),
        'realized_action': None, 'attempted_steps': 1, 'retained_steps': 0,
        'decision': {
            'decision': 'REJECT', 'reason': 'NO_MEASURABLE_TARGET_GAIN',
            'evidence_sha256': 'e' * 64,
        },
        'scores': [[capability, 1, 1, 4]], 'protected_capabilities': [],
    }
    value['outcome_sha256'] = _fingerprint(value)

    credited = apply_outcome(parent, value)

    assert credited['causal_experiment']['diagnostic_contexts'][diagnostic_key] == payload


def test_changed_selected_diagnostic_payload_cannot_credit():
    teacher, value, _, _ = selected_outcome()
    value['context']['diagnostics'] = {'salience': 'changed'}
    value['outcome_sha256'] = _fingerprint({k:v for k,v in value.items() if k != 'outcome_sha256'})
    with pytest.raises(BilqisError):
        apply_outcome(teacher, value)


def test_ordinary_previsit_consumes_current_parent_competence():
    from types import SimpleNamespace
    from bilqis_mlx.runtime.teacher_policy_selection import ordinary_previsit_diagnostics
    from bilqis_mlx.runtime.priority_competence import CapabilityCompetence, CompetenceScore

    epoch, _, _, school, evidence = _fixture()
    capability, scope = evidence.scope.capability_id, evidence.scope.scope

    def select(competence):
        teacher = epoch.teacher()
        option = SimpleNamespace(competence=competence)
        diagnostics = ordinary_previsit_diagnostics(option, structural_debt=None)
        key, policy, metadata = select_visit_policy(
            engine, teacher, capability, school, random.Random(12), Settings(),
            scope, diagnostics, "any-grade")
        diagnostic_key = metadata["diagnostic_context_key"]
        payload = teacher["causal_experiment"]["diagnostic_contexts"][diagnostic_key]
        return key, policy, diagnostic_key, payload

    unknown = select(CapabilityCompetence())
    measured = CapabilityCompetence(reference=CompetenceScore(
        2, 6, "FIXED_REFERENCE", "a" * 64))
    deficit = select(measured)
    assert deficit == select(measured)
    assert unknown[2] != deficit[2]
    assert unknown[3]["native_previsit"]["fixed_reference_deficit"] is None
    assert deficit[3]["native_previsit"]["fixed_reference_deficit"] is True
    assert deficit[3]["native_previsit"]["structural_debt"] is None


def test_ordinary_diagnostic_credit_changes_actual_selection_rationale():
    from types import SimpleNamespace
    from bilqis_mlx.runtime.teacher_policy_selection import ordinary_previsit_diagnostics
    from bilqis_mlx.runtime.priority_competence import CapabilityCompetence, CompetenceScore

    measured = CapabilityCompetence(reference=CompetenceScore(
        2, 6, "FIXED_REFERENCE", "a" * 64))
    known = ordinary_previsit_diagnostics(
        SimpleNamespace(competence=measured), structural_debt=True)
    teacher, value, school, _ = selected_outcome(known)
    credited = apply_outcome(teacher, value)
    visit, context = value["teacher_visit"], value["context"]

    def select(diagnostics):
        return select_visit_policy(
            engine, deepcopy(credited), visit["capability_id"], school,
            random.Random(12), Settings(), context["curriculum_scope"],
            diagnostics, "any-grade")

    key, _, metadata = select(known)
    assert key == visit["policy_key"]
    assert metadata["diagnostic_context_consumed"] is True
    assert metadata["selection_reason"] == "DIAGNOSTIC_OR_PRESSURE_CONTEXT"
    unknown = ordinary_previsit_diagnostics(
        SimpleNamespace(competence=CapabilityCompetence()), structural_debt=None)
    _, _, different = select(unknown)
    assert different["diagnostic_context_consumed"] is False
    assert different["diagnostic_context_key"] != metadata["diagnostic_context_key"]
