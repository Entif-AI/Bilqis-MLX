"""Nontraining specification of *fresh-version* capability champion arbitration.

This module does not open model files, choose a teacher, or alter a trainer.
Do not use it as an authorization to activate the blocked v16 curriculum.
"""
from fractions import Fraction


def validate_candidate(candidate, rubric):
    if set(candidate['scores']) != set(rubric):
        raise ValueError('CAPABILITY_RUBRIC_COVERAGE_MISMATCH')
    if not candidate.get('checkpoint_sha256'):
        raise ValueError('CAPABILITY_CHAMPION_NEEDS_SHA')
    for key, denominator in rubric.items():
        value = candidate['scores'][key]
        if not isinstance(denominator, int) or denominator <= 0:
            raise ValueError('CAPABILITY_INVALID_RUBRIC')
        if not isinstance(value, int) or not 0 <= value <= denominator:
            raise ValueError('CAPABILITY_INVALID_SCORE')


def grade_mean(candidate, rubric):
    validate_candidate(candidate, rubric)
    return sum((Fraction(candidate['scores'][key], denominator)
                for key, denominator in rubric.items()), Fraction()) / len(rubric)


def new_version_registry(version, rubric):
    """New semantics mean new champion pointers, even if a teacher is inherited."""
    if not version or not rubric:
        raise ValueError('CAPABILITY_NO_VERSION_OR_RUBRIC')
    return {'version': version, 'rubric': dict(rubric),
            'champions': {cap: None for cap in rubric}, 'evaluated': []}


def consider_candidate(registry, candidate):
    """Grade-wide 100%-tie arbitration; shared pointers update together.

    A candidate rejected from student admission can still win here. The
    teacher ensemble and causal AdamW student are outside this pure policy.
    """
    if candidate['version'] != registry['version']:
        raise ValueError('CAPABILITY_STALE_VERSION_CANDIDATE')
    rubric = registry['rubric']
    validate_candidate(candidate, rubric)
    trial_mean = grade_mean(candidate, rubric)
    updates = []
    for cap, total in rubric.items():
        previous = registry['champions'][cap]
        if previous is None:
            updates.append(cap)
            continue
        own = candidate['scores'][cap]
        previous_own = previous['scores'][cap]
        if own > previous_own:
            updates.append(cap)
        elif own == previous_own == total and trial_mean > grade_mean(previous, rubric):
            updates.append(cap)
    # One transaction means a common superior checkpoint updates both B and
    # D pointers, without a transient inconsistent two-winner state.
    registry['champions'].update({cap: candidate for cap in updates})
    registry['evaluated'].append({'checkpoint_sha256': candidate['checkpoint_sha256'],
                                  'grade_mean': str(trial_mean),
                                  'updated_capabilities': list(updates)})
    return tuple(updates)


def common_qualified_checkpoint(registry):
    """A possible future baseline/teacher, NOT automatic next-version winner."""
    winners = list(registry['champions'].values())
    if not winners or any(w is None for w in winners):
        return None
    if any(w['checkpoint_sha256'] != winners[0]['checkpoint_sha256'] for w in winners):
        return None
    if any(winners[0]['scores'][cap] != total
           for cap, total in registry['rubric'].items()):
        return None
    return winners[0]
