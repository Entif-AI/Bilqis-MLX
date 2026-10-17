"""Proposed focused acquisition batches for the three stalled v16 grades.

This is an opt-in *source compiler*, not a change to the hash-locked v16
trainer, its 1,150-question rubric, or its running student. A separately
versioned operator must explicitly adopt this compiler before it can train.
All examples are exposed teaching material, never held-out certification.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy

from bilqis_development import data as development
from . import current_rubric_v16 as rubric
from . import g_primitives_v12 as primitives
from . import lessons

GRADES = ('G12', 'G13', 'G14')
FAMILIES = {
    'G12': ('set-intersection', 'set-difference'),
    'G13': ('function-domain', 'function-range', 'function-inverse'),
    'G14': ('function-composition',),
}
MODES = ('FOCUS', 'COMPOSITION')
CURRENT_COUNT = 24
REHEARSAL_COUNT = 8


def _source_key(grade, family, mode):
    return f'{grade}:{family.upper().replace("-", "_")}_{mode}'


def _fresh(family, mode, gold, rng, seen):
    for _ in range(1024):
        try:
            row = development.lesson(5, family, rng,
                category=mode.lower(), varied=False)
        except ValueError as error:
            if 'context' in str(error).lower() or 'inverse is not a function' in str(error).lower():
                continue
            raise
        if row['gold'] == gold and row['id'] not in seen:
            row = deepcopy(row)
            row['answer_kind'] = 'evidence'
            row['course_meta'] = {
                'tranche': 'new_oracle_checked_focus_repair',
                'assessment_role': 'EXPOSED_TEACHING_NOT_INDEPENDENT_TRANSFER',
                'family': family, 'mode': mode,
            }
            return row
    raise ValueError(f'FOCUS_REPAIR_NO_{gold}_CONTRAST:{family}:{mode}')


def _source_or_fresh(grade, family, mode, gold, rng, seen):
    candidates = [row for row in rubric.questions(_source_key(grade,family,mode))
                  if row['gold'] == gold and row['id'] not in seen]
    if candidates:
        row = deepcopy(rng.choice(candidates))
        row['answer_kind'] = 'evidence'
        row['course_meta'] = {
            'tranche': 'unchanged_v16_source_acquisition_replay',
            'assessment_role': 'EXPOSED_TEACHING_NOT_INDEPENDENT_TRANSFER',
            'family': family, 'mode': mode,
        }
        return row
    return _fresh(family, mode, gold, rng, seen)


def batch(grade, graph, rng):
    """32 unique verified rows, with direct and composite TRUE/FALSE coverage.

    24 target-grade rows include the historically approved primitive contrasts;
    the remaining eight rehearse four B and four prior-G source examples.
    Unlike the old one-mode policy, each update teaches both modes and signs.
    """
    if grade not in GRADES:
        raise ValueError('FOCUS_REPAIR_UNSUPPORTED_GRADE')
    rows = primitives.rows(grade)
    seen = {row['id'] for row in rows}
    if len(rows) >= CURRENT_COUNT:
        raise ValueError('FOCUS_REPAIR_PRIMITIVE_OVERFULL')
    remaining = CURRENT_COUNT - len(rows)
    buckets = [(family,mode) for family in FAMILIES[grade] for mode in MODES]
    for index, (family,mode) in enumerate(buckets):
        # Spread any remainder by a deterministic rotating allocation.
        count = remaining // len(buckets) + (index < remaining % len(buckets))
        for item in range(count):
            gold = ('TRUE', 'FALSE')[(item + index) % 2]
            row = _source_or_fresh(grade,family,mode,gold,rng,seen)
            rows.append(row)
            seen.add(row['id'])

    # Explicitly rehearse B and prerequisites without making them alternative
    # winners or fabricating mixed-checkpoint retention scores.
    # The shared legacy G loss/validator does not understand the later
    # cross-domain bridge records. Rehearse B01-B03 arithmetic evidence here;
    # the ordinary B-grade curriculum retains ownership of the other forms.
    bgrade = rng.choice(('B01','B02','B03'))
    bkeys = [key for key in rubric.inventory() if key.startswith(bgrade+':')
             and 'NUMERIC' not in key]
    bpool = [row for key in bkeys for row in rubric.questions(key)]
    rng.shuffle(bpool)
    prior = 'G12' if grade == 'G14' else 'G11'
    gkeys = [key for key in rubric.inventory() if key.startswith(prior+':')]
    gpool = [row for key in gkeys for row in rubric.questions(key)]
    rng.shuffle(gpool)
    for pool in (bpool,gpool):
        added = 0
        for candidate in pool:
            if candidate['id'] in seen:
                continue
            row = deepcopy(candidate)
            row.setdefault('answer_kind','evidence')
            rows.append(row)
            seen.add(row['id'])
            added += 1
            if added == REHEARSAL_COUNT//2:
                break
        if added != REHEARSAL_COUNT//2:
            raise ValueError('FOCUS_REPAIR_REHEARSAL_EXHAUSTED')
    if len(rows)!=32 or len(seen)!=32:
        raise ValueError('FOCUS_REPAIR_BATCH_IDENTITY')
    primitives.validate_rows(primitives.rows(grade),graph)
    lessons.valid_rows(rows,graph)
    current = rows[:CURRENT_COUNT]
    counts = Counter(row['gold'] for row in current)
    if not (counts['TRUE'] >= 8 and counts['FALSE'] >= 8):
        raise ValueError('FOCUS_REPAIR_CLASS_COLLAPSE')
    return rows, {'current':CURRENT_COUNT,'old':REHEARSAL_COUNT,
                  'preview':0,'teacher_target':grade}
