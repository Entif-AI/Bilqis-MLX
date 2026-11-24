"""Deterministic HOW credit; callers supply live-issued or committed evidence."""
from copy import deepcopy

from bilqis_mlx.compatibility import historical_teacher_policy
from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning import learning_experiment, plasticity_escape
from bilqis_mlx.learning.teacher_strategy_population import (
    LEGACY_CHECKPOINT_RETIREMENT_POLICY,
    effective_policy_key,
)
from bilqis_mlx.runtime.state import _fingerprint

LEGACY_SCHEMA = 'bilqis.bamf.teacher-outcome/v1'
SCHEMA = 'bilqis.bamf.teacher-outcome/v2'
SCORE_FIELDS = ('capability', 'before', 'after', 'total')


def invalid():
    ErrorBus.Raise(SCHOOL.TEACHER_OBSERVATION.INVALID)


def outcome_digest(observation):
    return _fingerprint({key: value for key, value in observation.items()
                         if key != 'outcome_sha256'})


def ledger(teacher, manifest):
    record = teacher.get('how_outcomes', {})
    if record.get('parent_manifest_sha256') != manifest:
        return {'parent_manifest_sha256': manifest, 'head': None, 'applied': {}}
    return deepcopy(record)


def _compact_selected_teacher(teacher, context):
    selected = deepcopy(teacher)
    key = context.get('diagnostic_context_key')
    if key is None:
        return selected
    diagnostics = context.get('diagnostics')
    if not isinstance(key, str) or not key or not isinstance(diagnostics, dict):
        invalid()
    channel = selected.get('causal_experiment')
    if not isinstance(channel, dict):
        invalid()
    contexts = channel.setdefault('diagnostic_contexts', {})
    if not isinstance(contexts, dict):
        invalid()
    existing = contexts.get(key)
    if existing is not None and existing != diagnostics:
        invalid()
    contexts[key] = deepcopy(diagnostics)
    return selected


def _deltas(observation):
    scores = observation['scores']
    deltas = {}
    for row in scores:
        if not isinstance(row, (list, tuple)) or len(row) != len(SCORE_FIELDS):
            invalid()
        cap, before, after, total = row
        if (not isinstance(cap, str) or not cap or cap in deltas
                or any(type(value) is not int for value in (before, after, total))
                or total <= 0 or not 0 <= before <= total or not 0 <= after <= total):
            invalid()
        deltas[cap] = (after - before) / total
    return deltas


def _apply_outcome(teacher, observation, *, selected_teacher_override=None):
    """Return a credited copy, or the unchanged copy for identical delivery."""
    if (not isinstance(observation, dict) or observation.get('schema') not in (LEGACY_SCHEMA, SCHEMA)
            or observation.get('outcome_sha256') != outcome_digest(observation)):
        invalid()
    visit, context = observation['teacher_visit'], observation['context']
    manifest = visit['accepted_manifest_sha256']
    prior = ledger(teacher, manifest)
    attempt, digest = observation['attempt_id'], observation['outcome_sha256']
    if attempt in prior['applied']:
        if prior['applied'][attempt] != digest:
            invalid()
        return deepcopy(teacher)
    if 'selected_teacher' in observation:
        if selected_teacher_override is not None:
            invalid()
        selected = deepcopy(observation['selected_teacher'])
    else:
        selected_sha256 = observation.get('selected_teacher_sha256')
        selected = (
            _compact_selected_teacher(teacher, context)
            if selected_teacher_override is None
            else deepcopy(selected_teacher_override)
        )
        if (not isinstance(selected_sha256, str)
                or selected_sha256 != _fingerprint(selected)):
            invalid()
    if ledger(selected, manifest) != prior:
        invalid()
    key, cap = visit['policy_key'], visit['capability_id']
    policy = selected.get('strategies', {}).get(key)
    if (policy != observation['selected_policy']
            or effective_policy_key(policy) != observation['effective_policy_key']):
        invalid()
    deltas = _deltas(observation)
    protected = observation['protected_capabilities']
    decision = observation['decision']
    retained = decision['decision'] == 'PROVISIONAL'
    if (cap not in deltas or not set(protected) <= set(deltas) - {cap}
            or decision['decision'] not in {'REJECT', 'PROVISIONAL'}
            or type(observation['attempted_steps']) is not int
            or observation['attempted_steps'] < 1
            or type(observation['retained_steps']) is not int
            or observation['retained_steps'] != (observation['attempted_steps'] if retained else 0)):
        invalid()
    causal = {
        'version': learning_experiment.VERSION, 'active_capability': cap,
        'phase': context['phase'], 'decision': decision['decision'],
        'reason': decision['reason'], 'deltas': deltas,
        'protected_capabilities': protected,
        'paired_scores_sha256': decision['evidence_sha256'],
        'source_cohort_sha256': context['rubric_sha256'],
    }
    # Preserve the replay semantics of previously signed v1 observations.
    # New observations carry the raw correct-answer loss to inherited feedback.
    if observation['schema'] == SCHEMA:
        causal['worst_protected_loss'] = max(
            (max(0, before - after) for name, before, after, _ in observation['scores']
             if name in protected), default=0)
    feedback = learning_experiment.observe_context(
        selected, capability=cap, phase=context['phase'], policy_key=key,
        decision=causal, local_gain=deltas[cap],
        curriculum_scope=context['curriculum_scope'], diagnostics=context['diagnostics'],
        realized_action=observation['realized_action'],
        student_checkpoint_sha256=visit['student_sha256'], lesson_grade=context['grade'],
        diagnostic_context_key=context.get('diagnostic_context_key'),
        checkpoint_retirement_policy=context.get(
            'checkpoint_retirement_policy', LEGACY_CHECKPOINT_RETIREMENT_POLICY))
    credit = learning_experiment.selection_credit(deltas[cap], causal, feedback)
    historical_teacher_policy.observe(selected, context['grade'], key, credit)
    plasticity_escape.record_school_visit(selected, retained=retained)
    record = selected['causal_experiment']['contexts'][
        cap + '|' + context['phase'] + '|' + context['curriculum_scope']][key]
    for name, value in (
            ('target_delta_sum', deltas[cap]),
            ('protected_net_delta_sum', sum(deltas[name] for name in protected)),
            ('worst_protected_loss_sum', max((max(0., -deltas[name]) for name in protected), default=0.)),
            ('attempted_steps_sum', observation['attempted_steps'])):
        record[name] = record.get(name, 0) + value
    from bilqis_mlx.learning.teacher_realized_action import (
        weakness_delivery_facts, weakness_delivery_totals,
    )
    from bilqis_mlx.runtime.structural_weakness_ledger import (
        record_scored_resolutions, record_weakness_exposure,
    )
    facts = observation.get('weakness_delivery', [])
    controls = [{} for _ in range(observation['attempted_steps'])]
    for fact in facts:
        ordinal = fact['step']
        if type(ordinal) is not int or not 1 <= ordinal <= len(controls) or controls[ordinal - 1]:
            invalid()
        controls[ordinal - 1] = {
            'weakness_class_matches': fact['matches'],
            'weakness_unavailable': fact['unavailable'],
        }
    if weakness_delivery_facts(controls) != facts:
        invalid()
    exposure, unavailable = weakness_delivery_totals(facts)
    features = (observation.get('realized_action') or {}).get('features', {})
    if (features.get('weakness_class_exposures', {}) != exposure
            or features.get('weakness_unavailable_steps', {}) != unavailable
            or (facts and (
                features.get('weakness_targets_delivered') != sum(exposure.values())
                or features.get('priority_weakness_targets_delivered') != sum(exposure.values())))):
        invalid()
    record_weakness_exposure(selected, exposure)
    record_scored_resolutions(selected, observation)
    prior['applied'][attempt] = digest
    prior['head'] = digest
    selected['how_outcomes'] = prior
    return selected


def apply_outcome(teacher, observation, *, selected_teacher_override=None):
    """Validate one observation before returning any changed teacher state."""
    try:
        return _apply_outcome(
            teacher, observation,
            selected_teacher_override=selected_teacher_override)
    except (KeyError, TypeError, ValueError, AttributeError):
        invalid()
