"""A checkpoint-coherent, three-lesson queue for the v16 successor.

This is the scheduling state machine, not an alternative neural trainer.
Callers supply verified, source-defined CURRENT rubric scores for a single
FP32+own-AdamW checkpoint. Historical G24 panels and personal bests have no
standing in this queue. Nothing here mutates a model or optimizer.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from fractions import Fraction

from bilqis_logic.kernel import digest


SCHEMA = 'bilqis.triplets.scheduler/v16'
SNAPSHOT_SCHEMA = 'bilqis.triplets.current-probe-snapshot/v1'
ROUND_SIZE = 3
STALL_ROUNDS = 2
ASSESSMENT_ROLE = 'CURRENT_TAUGHT_SYLLABUS'


def _check_snapshot(snapshot, rubric, eligible, *, expected_step=None,
                    expected_checkpoint=None):
    """Reject stale, partial, historical, cross-step or mismatched scoring."""
    if snapshot.get('schema') != SNAPSHOT_SCHEMA:
        raise ValueError('TRIPLETS_UNKNOWN_SNAPSHOT_SCHEMA')
    if snapshot.get('current_rubric_sha256') != digest(rubric):
        raise ValueError('TRIPLETS_RUBRIC_IDENTITY_DRIFT')
    step = snapshot.get('optimizer_step')
    sha = snapshot.get('checkpoint_sha256')
    if type(step) is not int or step < 0 or not isinstance(sha, str) or len(sha) != 64:
        raise ValueError('TRIPLETS_MISSING_CHECKPOINT_IDENTITY')
    if expected_step is not None and step != expected_step:
        raise ValueError('TRIPLETS_RETEST_WRONG_OPTIMIZER_STEP')
    if expected_checkpoint is not None and sha != expected_checkpoint:
        raise ValueError('TRIPLETS_RETEST_WRONG_CHECKPOINT')
    if not eligible or len(eligible) != len(set(eligible)):
        raise ValueError('TRIPLETS_INVALID_ELIGIBLE_PROGRAM')
    grouped = defaultdict(lambda: [0, 0])
    expected_keys = {key for key in rubric if key.split(':', 1)[0] in eligible}
    if set(snapshot.get('metrics', {})) != expected_keys:
        raise ValueError('TRIPLETS_INCOMPLETE_OR_EXTRANEOUS_PROBES')
    for key in expected_keys:
        entry = rubric[key]
        if (entry.get('assessment_role') != ASSESSMENT_ROLE or
                entry.get('evidence_role') != 'SOURCE_DEFINED_ACQUISITION_NOT_INDEPENDENT_GENERALIZATION'):
            raise ValueError('TRIPLETS_HISTORICAL_OR_UNAPPROVED_PROBE:' + key)
        actual = snapshot['metrics'][key]
        correct, total = actual.get('correct'), actual.get('total')
        if (type(total) is not int or total <= 0 or
                type(correct) is not int or not 0 <= correct <= total or
                total != entry['total']):
            raise ValueError('TRIPLETS_INVALID_SCORE:' + key)
        if (actual.get('optimizer_step') != step or
                actual.get('checkpoint_sha256') != sha):
            raise ValueError('TRIPLETS_MIXED_CHECKPOINT_SCORES:' + key)
        pair = grouped[key.split(':', 1)[0]]
        pair[0] += correct
        pair[1] += total
    if set(grouped) != set(eligible):
        raise ValueError('TRIPLETS_MISSING_GRADE_PROBES')
    return {grade: {'correct': c, 'total': t} for grade, (c, t) in grouped.items()}


def selection(snapshot, rubric, eligible):
    """Lowest actual taught accuracy wins; ties follow curricular order."""
    if len(eligible) < ROUND_SIZE:
        raise ValueError('TRIPLETS_REQUIRES_THREE_ELIGIBLE_GRADES')
    totals = _check_snapshot(snapshot, rubric, eligible)
    positions = {grade: i for i, grade in enumerate(eligible)}
    return tuple(sorted(eligible, key=lambda grade: (
        Fraction(totals[grade]['correct'], totals[grade]['total']),
        positions[grade]))[:ROUND_SIZE])


def new_state(eligible, rubric, *, stall_rounds=STALL_ROUNDS):
    """Create an inert new-version queue. No selection without a full snapshot."""
    if len(eligible) < ROUND_SIZE or len(eligible) != len(set(eligible)):
        raise ValueError('TRIPLETS_REQUIRES_THREE_ELIGIBLE_GRADES')
    if type(stall_rounds) is not int or stall_rounds < 1:
        raise ValueError('TRIPLETS_INVALID_STALL_POLICY')
    return {'schema': SCHEMA, 'mode': '--triplets', 'phase': 'SELECT_READY',
            'eligible_program': list(eligible), 'rubric_sha256': digest(rubric),
            'round_size': ROUND_SIZE, 'stall_rounds': stall_rounds,
            'stagnant_rounds': 0, 'cycles_completed': 0,
            'active': None, 'history': [], 'latest_snapshot': None}


def _verify_state(state, rubric):
    if (state.get('schema') != SCHEMA or state.get('mode') != '--triplets' or
            state.get('round_size') != ROUND_SIZE or
            state.get('rubric_sha256') != digest(rubric)):
        raise ValueError('TRIPLETS_FROZEN_RECIPE_MISMATCH')


def begin_cycle(state, snapshot, rubric):
    """Choose once. The same three stay locked until all visits AND retest."""
    _verify_state(state, rubric)
    if state['phase'] != 'SELECT_READY' or state['active'] is not None:
        raise ValueError('TRIPLETS_RESELECTION_BEFORE_RETEST')
    if state['latest_snapshot'] is not None:
        latest = state['latest_snapshot']
        if (snapshot['checkpoint_sha256'] != latest['checkpoint_sha256'] or
                snapshot['optimizer_step'] != latest['optimizer_step']):
            raise ValueError('TRIPLETS_UNEXPLAINED_STEP_BETWEEN_CYCLES')
    eligible = state['eligible_program']
    grades = selection(snapshot, rubric, eligible)
    scores = _check_snapshot(snapshot, rubric, eligible)
    updated = deepcopy(state)
    updated['active'] = {'cycle': state['cycles_completed'] + 1,
                         'grades': list(grades), 'next_index': 0,
                         'locked_probe_keys': {grade: sorted(key for key in rubric
                             if key.startswith(grade + ':')) for grade in grades},
                         'locked_question_hashes': {key: rubric[key]['questions_sha256']
                             for key in rubric if key.split(':',1)[0] in grades
                             and 'questions_sha256' in rubric[key]},
                         'before': {grade: scores[grade] for grade in grades},
                         'start_step': snapshot['optimizer_step'],
                         'start_checkpoint_sha256': snapshot['checkpoint_sha256'],
                         'last_step': snapshot['optimizer_step'],
                         'last_checkpoint_sha256': snapshot['checkpoint_sha256'],
                         'visits': []}
    updated['phase'] = 'LESSONS'
    return updated


def next_lesson(state):
    """Only a selected grade can be scheduled; no polling-based reselection."""
    if state['phase'] != 'LESSONS' or state['active'] is None:
        return None
    active = state['active']
    return active['grades'][active['next_index']]


def record_lesson(state, *, grade, parent_step, parent_checkpoint_sha256,
                  result_step, result_checkpoint_sha256, completed):
    """Advance only after a whole lesson and its durable grade boundary."""
    if next_lesson(state) != grade or completed is not True:
        raise ValueError('TRIPLETS_LESSON_MISSING_OR_OUT_OF_ORDER')
    active = state['active']
    if (parent_step != active['last_step'] or
            parent_checkpoint_sha256 != active['last_checkpoint_sha256']):
        raise ValueError('TRIPLETS_LESSON_PARENT_LINEAGE_MISMATCH')
    if (type(result_step) is not int or result_step < parent_step or
            not isinstance(result_checkpoint_sha256, str) or
            len(result_checkpoint_sha256) != 64):
        raise ValueError('TRIPLETS_INVALID_LESSON_RESULT')
    if result_step == parent_step and result_checkpoint_sha256 != parent_checkpoint_sha256:
        raise ValueError('TRIPLETS_UNRECEIPTED_SAME_STEP_MUTATION')
    updated = deepcopy(state)
    active = updated['active']
    active['visits'].append({'grade': grade, 'parent_step': parent_step,
                            'parent_checkpoint_sha256': parent_checkpoint_sha256,
                            'result_step': result_step,
                            'result_checkpoint_sha256': result_checkpoint_sha256,
                            'whole_lesson_completed': True})
    active['last_step'] = result_step
    active['last_checkpoint_sha256'] = result_checkpoint_sha256
    active['next_index'] += 1
    if active['next_index'] == ROUND_SIZE:
        updated['phase'] = 'RETEST_REQUIRED'
    return updated


def finish_retest(state, snapshot, rubric, *, locked_retest=None):
    """Evaluate the locked trio again, all on the FINAL student checkpoint.

    A complete current-program snapshot is required because the NEXT three
    must be ranked against equally fresh evidence, not mixed-step maxima.
    """
    _verify_state(state, rubric)
    if state['phase'] != 'RETEST_REQUIRED' or state['active'] is None:
        raise ValueError('TRIPLETS_RETEST_BEFORE_THREE_WHOLE_LESSONS')
    active = state['active']
    keys={key for grade in active['grades'] for key in active['locked_probe_keys'][grade]}
    if any(rubric[key].get('questions_sha256') != question_hash
           for key, question_hash in active['locked_question_hashes'].items()):
        raise ValueError('TRIPLETS_LOCKED_QUESTION_IDENTITY_DRIFT')
    if locked_retest is not None and (
            set(locked_retest) != keys or
            any(type(value) is not int or value < 0 or
                value > rubric[key]['total'] for key,value in locked_retest.items()) or
            any(snapshot.get('metrics',{}).get(key,{}).get('correct') != value
                for key,value in locked_retest.items())):
        raise ValueError('TRIPLETS_NOT_THE_SAME_THREE_PROBES_RETESTED')
    scores = _check_snapshot(snapshot, rubric, state['eligible_program'],
                             expected_step=active['last_step'],
                             expected_checkpoint=active['last_checkpoint_sha256'])
    after = {grade: scores[grade] for grade in active['grades']}
    # Fractions avoid treating differing denominators as interchangeable.
    gains = {grade: (Fraction(after[grade]['correct'], after[grade]['total']) -
                     Fraction(active['before'][grade]['correct'],
                              active['before'][grade]['total']))
             for grade in active['grades']}
    stagnant = all(gain <= 0 for gain in gains.values())
    updated = deepcopy(state)
    updated['history'].append({'cycle': active['cycle'],
                               'grades': list(active['grades']),
                               'start_step': active['start_step'],
                               'end_step': snapshot['optimizer_step'],
                               'end_checkpoint_sha256': snapshot['checkpoint_sha256'],
                               'before': active['before'], 'after': after,
                               'locked_probe_keys': active['locked_probe_keys'],
                               'locked_question_hashes': active['locked_question_hashes'],
                               'explicit_same_trio_retest': locked_retest is not None,
                               'gains': {k: str(v) for k, v in gains.items()},
                               'stagnant': stagnant, 'visits': active['visits']})
    updated['cycles_completed'] += 1
    updated['stagnant_rounds'] = (state['stagnant_rounds'] + 1 if stagnant else 0)
    updated['latest_snapshot'] = {'optimizer_step': snapshot['optimizer_step'],
                                  'checkpoint_sha256': snapshot['checkpoint_sha256']}
    updated['active'] = None
    updated['phase'] = ('SOUP_REVIEW_REQUIRED' if
                        updated['stagnant_rounds'] >= state['stall_rounds']
                        else 'SELECT_READY')
    return updated


def soup_review_completed(state, *, outcome, evidence_ref):
    """Record the post-stall soup decision; never graft weights onto AdamW.

    The separately verified soup evaluator may return a teacher candidate.
    Installing a causal student still requires a complete checkpoint and
    its OWN optimizer, which this scheduler deliberately cannot synthesize.
    """
    if state['phase'] != 'SOUP_REVIEW_REQUIRED':
        raise ValueError('TRIPLETS_SOUP_NOT_TRIGGERED')
    if outcome not in ('TEACHER_ONLY', 'NO_ELIGIBLE_SOUP', 'RESEARCH_ONLY'):
        raise ValueError('TRIPLETS_SOUP_CANNOT_REPLACE_STUDENT')
    if not isinstance(evidence_ref, str) or not evidence_ref:
        raise ValueError('TRIPLETS_SOUP_EVIDENCE_REQUIRED')
    updated = deepcopy(state)
    updated['history'].append({'kind': 'SOUP_REVIEW', 'outcome': outcome,
                               'evidence_ref': evidence_ref})
    updated['stagnant_rounds'] = 0
    # A proved no-improvement soup is not permission for an infinite loop of
    # the same stuck curriculum. Stop for an operator decision instead.
    updated['phase'] = ('STALLED_AWAITING_OPERATOR' if
                         outcome == 'NO_ELIGIBLE_SOUP' else 'SELECT_READY')
    return updated
