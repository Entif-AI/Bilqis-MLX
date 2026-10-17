"""Three repaired next-version lessons, from known primitive to composition.

G18 now teaches a *bounded* current-versus-historical evidence distinction
by controlled snapshot changes and explicit supersession, not general tense,
event chronology, or mutable world state. Those broader semantics stay HELD.
No historical exam is overwritten, and no new tokenizer/AST ABI is invented.
"""
from __future__ import annotations

from copy import deepcopy

from . import foundation_course_v15 as foundation
from . import g_primitives_v12 as primitive
from . import lessons

VERSION = 'bilqis.school50.repaired-lessons/v16'
ENABLED = ('G11', 'G18', 'G20')
HELD_G18_EXTENSIONS = ('EVENT_TIME_ORDER', 'DYNAMIC_STATE_MUTATION',
                       'REFERENCE_SCOPE', 'TEMPORAL_TENSE')
FOUNDATIONAL_CONTEXT = {
    'G11': ('G05:IDENTITY_FOCUS', 'TYPED_ENTITY_SET'),
    'G20': ('B01:NUMERIC_0_3', 'G19:EQ', 'BOUNDED_ADD_SUB_MUL'),
    'G18': ('G10:EVIDENCE_STATE_FOCUS', 'G17:SUPERSEDES',
            'G17:CURRENT_STATE', 'STATIC_SNAPSHOT_ONLY_NO_TIME_INFERENCE'),
}


def _tag(rows, stage, *, enabled):
    tagged = deepcopy(rows)
    for item in tagged:
        item.setdefault('course_meta', {}).update({
            'version': VERSION, 'lesson_stage': stage,
            'assessment_role': ('TRAINING_REPLAY_NOT_GENERALIZATION' if enabled
                                else 'REVIEW_ONLY_NOT_CURRENT_SYLLABUS'),
            'instructional_progression': ('CURRENT_STAGE_WITH_EARLIER_CONTEXT' if enabled
                                          else 'HELD')})
    return tuple(tagged)


def _g18_first_rung():
    """Controlled snapshot worlds make prerequisite mechanics inspectable.

    Same proposition J0 throughout; no inference from lexical E1 > E0.
    Only an explicit SUPERSEDES edge changes which event is current.
    """
    P = primitive._c('Proposition', 'J0')
    E0 = primitive._c('Event', 'E0')
    E1 = primitive._c('Event', 'E1')
    O = primitive._op
    mk = primitive._world
    none = mk(entities='AB', props=True)
    support = mk(entities='AB', props=True,
                 events=[['E0', 'ASSERT', 'S0', 'J0', 'support']])
    refute = mk(entities='AB', props=True,
                events=[['E0', 'ASSERT', 'S0', 'J0', 'refute']])
    events = [['E0', 'ASSERT', 'S0', 'J0', 'support'],
              ['E1', 'OBSERVE', 'S1', 'J0', 'refute']]
    unlinked = mk(entities='AB', props=True, events=events)
    unlinked_alt = mk(entities='AB', props=True,
        events=[['E1','ASSERT','S0','J0','support'],
                ['E2','OBSERVE','S1','J0','refute']])
    linked = mk(entities='AB', props=True, events=events,
                links=[['SUPERSEDES', 'E1', 'E0']])
    reversed_polarity = mk(entities='AB', props=True,
        events=[['E0', 'ASSERT', 'S0', 'J0', 'refute'],
                ['E1', 'OBSERVE', 'S1', 'J0', 'support']],
        links=[['SUPERSEDES', 'E1', 'E0']])
    same_polarity = mk(entities='AB', props=True,
        events=[['E0', 'ASSERT', 'S0', 'J0', 'support'],
                ['E1', 'OBSERVE', 'S1', 'J0', 'support']],
        links=[['SUPERSEDES', 'E1', 'E0']])
    same_polarity_variant = mk(entities='AB', props=True,
        events=[['E0', 'ASSERT', 'S0', 'J0', 'support'],
                ['E1', 'ASSERT', 'S2', 'J0', 'support']],
        links=[['SUPERSEDES', 'E1', 'E0']])

    def make(stage, pairs):
        result = []
        for pair, ((a, qa), (b, qb)) in enumerate(pairs):
            for variant, (world, query) in enumerate(((a, qa), (b, qb))):
                row = primitive._finite('G18', 'EVENT_EVIDENCE_PREVIEW',
                                        stage, f'{stage}-{pair}', variant,
                                        world, query)
                result.append(row)
        return _tag(result, stage, enabled=True)

    return (
        ('EVIDENCE_BASE', make('EVIDENCE_BASE', [
            ((none, O('CURRENT_STATE', P)), (support, O('CURRENT_STATE', P))),
            ((refute, O('CURRENT_STATE', P)),
             (unlinked_alt, O('CURRENT_STATE', P))),
            ((support, O('HISTORICAL_STATE', P)),
             (refute, O('HISTORICAL_STATE', P))),
            ((none, O('HISTORICAL_STATE', P)),
             (unlinked_alt, O('HISTORICAL_STATE', P)))])),
        ('EVENT_RELATION', make('EVENT_RELATION', [
            ((unlinked, O('SUPERSEDES', E1, E0)), (linked, O('SUPERSEDES', E1, E0))),
            ((linked, O('IS_CURRENT', E0)), (linked, O('IS_CURRENT', E1))),
            ((linked, O('REVISES', E1, E0)), (unlinked, O('REVISES', E1, E0))),
            ((unlinked, O('IS_CURRENT', E0)),
             (reversed_polarity, O('IS_CURRENT', E0))),
            ((same_polarity, O('SUPERSEDES', E1, E0)),
             (same_polarity, O('REVISES', E1, E0))),
            ((reversed_polarity, O('REVISES', E1, E0)),
             (same_polarity_variant, O('REVISES', E1, E0)))])),
        ('STATE_CONTRAST', make('STATE_CONTRAST', [
            ((unlinked, O('CURRENT_STATE', P)), (linked, O('CURRENT_STATE', P))),
            ((reversed_polarity, O('CURRENT_STATE', P)),
             (reversed_polarity, O('HISTORICAL_STATE', P))),
            ((unlinked, O('HISTORICAL_STATE', P)), (linked, O('HISTORICAL_STATE', P)))])),
    )


def lesson(grade):
    """Return ordered stages; G18 remains disabled regardless of presence."""
    if grade == 'G11':
        existing = foundation.rows('G11')
        stages = (('MEMBER_ONE_SET', _tag(existing[:8], 'MEMBER_ONE_SET', enabled=True)),
                  ('MEMBER_TWO_SETS', _tag(existing[8:], 'MEMBER_TWO_SETS', enabled=True)))
    elif grade == 'G20':
        existing = foundation.rows('G20')
        direct = [r for r in existing if r['course_meta']['concept'] != 'EQ_BRIDGE']
        bridge = [r for r in existing if r['course_meta']['concept'] == 'EQ_BRIDGE']
        stages = (('NUMERIC_DIRECT_0_3', _tag(direct, 'NUMERIC_DIRECT_0_3', enabled=True)),
                  ('MATCHED_EQ_0_3', _tag(bridge, 'MATCHED_EQ_0_3', enabled=True)))
    elif grade == 'G18':
        stages = _g18_first_rung()
    else:
        raise ValueError('V16_NOT_ONE_OF_THREE_REPAIRED_LESSONS')
    ids = [row['id'] for _, rows in stages for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError('V16_LESSON_DUPLICATE_QUESTION_ID')
    return {'grade': grade, 'version': VERSION,
            'status': ('CURRENT_RESTRICTED_EVENT_EVIDENCE_RUNG' if grade == 'G18'
                       else 'CURRENT_FIRST_RUNG'),
            'deferred_expansion': HELD_G18_EXTENSIONS if grade == 'G18' else (),
            # References for arranging examples, NOT an unsupported claim that
            # earlier grades have achieved 100% at this student checkpoint.
            'supporting_context': FOUNDATIONAL_CONTEXT[grade],
            'prior_grade_mastery_gate': False,
            'stages': tuple({'name': name, 'rows': rows} for name, rows in stages),
            'total_exposed': len(ids)}


def current_rows(grade):
    if grade not in ENABLED:
        raise ValueError('V16_REPAIRED_LESSON_NOT_IN_CURRENT_PROGRAM')
    return [deepcopy(r) for stage in lesson(grade)['stages'] for r in stage['rows']]


def batch(grade, library, graph, policy, rng, *, update_index, total_updates):
    """Stage a whole 64-update lesson without jumping to hard wrappers first.

    The first half shows direct anchors; the second half rehearses those
    anchors WITH the next bounded contrast. No change to tokenizer or oracle.
    Each update still has 32 rows, with early-G retention filling open slots.
    """
    if grade not in ENABLED:
        raise ValueError('V16_ONLY_THE_THREE_REPAIRED_GRADES_ARE_CURRENT')
    if (type(update_index) is not int or type(total_updates) is not int or
            not 0 <= update_index < total_updates or total_updates < 2):
        raise ValueError('V16_BAD_LESSON_UPDATE_CURSOR')
    stages = lesson(grade)['stages']
    # Every stage is a full trainable prerequisite tranche, not a detached
    # assessment. Exposure cumulatively grows through the whole 64-update
    # visit. In G18 this introduces evidence -> explicit links -> contrast.
    stage_count = max(1, min(len(stages),
                  (update_index * len(stages))//total_updates + 1))
    current = [deepcopy(r) for stage in stages[:stage_count]
               for r in stage['rows']]
    seen = {r['id'] for r in current}
    old = foundation._old_rows(grade, library, rng, 32-len(current), seen)
    for r in old:
        r['answer_kind'] = 'evidence'
    rows = current + old
    if len(rows) != 32 or len({r['id'] for r in rows}) != 32:
        raise ValueError('V16_REPAIRED_BATCH_DUPLICATED')
    primitive.validate_rows([r for r in rows if 'course_meta' in r], graph)
    lessons.valid_rows([r for r in rows if 'course_meta' not in r], graph)
    return rows, {'current': len(current), 'old': len(old), 'preview': 0}
