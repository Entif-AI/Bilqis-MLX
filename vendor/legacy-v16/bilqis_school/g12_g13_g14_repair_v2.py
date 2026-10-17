"""Oracle-closed, teacher-selected G12/G13/G14 teaching; no exam replay.

This is a new curriculum version. Neither the frozen v16 source exam nor
the previously prepared, hash-locked v1 rescue is modified. The existing
adaptive teacher chooses composition, depth, old and preview allocations.
The compiler varies *the world, operands and truth conditions*, and requires
both answer classes for every current semantic family on every batch.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from types import MappingProxyType

from bilqis_development import data as development
from . import current_rubric_v16 as rubric
from . import lessons
from . import small_domain_lessons as small

GRADES=('G12','G13','G14')
FAMILIES={grade:lessons.SUPPORTED[int(grade[1:])] for grade in GRADES}
NEXT=MappingProxyType({'G12':'G13','G13':'G14','G14':'G15'})
COUNTS=32


def _excluded_exam_ids():
    return {row['id'] for key in rubric.inventory() for row in rubric.questions(key)}


def _generate(family,category,rng,seen,*,truth=None,varied=False):
    """Generate unseen finite-world tasks; independent oracles agree on gold."""
    for _ in range(4096):
        try:
            row=development.lesson(5,family,rng,category=category,varied=varied)
        except ValueError as error:
            if any(word in str(error).lower() for word in (
                    'context','inverse is not a function','world exceeds')):
                continue
            raise
        if row['id'] in seen or (truth is not None and row['gold']!=truth):
            continue
        row=deepcopy(row)
        row['answer_kind']='evidence'
        row['course_meta']={'tranche':'v2_new_world',
                            'assessment_role':'TEACHING_NOT_INDEPENDENT_TRANSFER',
                            'family':family,'teacher_mode':category.upper()}
        seen.add(row['id'])
        return row
    raise ValueError('V2_NO_NOVEL_ORACLE_WORLD:'+family+':'+str(truth))


def _pair(family,category,rng,seen,*,varied=False):
    """A positive and negative within one task family, often one-step apart."""
    for _ in range(48):
        before=_generate(family,category,rng,seen,varied=varied)
        try:
            mutated=development.perturb(before)
        except ValueError:
            mutated=None
        if mutated is not None:
            after,factor=mutated
            if (after['id'] not in seen and
                    after['gold']!=before['gold']):
                after=deepcopy(after)
                after['answer_kind']='evidence'
                after['course_meta']={**before['course_meta'],
                    'tranche':'v2_counterfactual_contrast',
                    'contrast_factor':factor,'sibling':before['id']}
                before['course_meta']['sibling']=after['id']
                seen.add(after['id'])
                return [before,after]
    return [_generate(family,category,rng,seen,truth=truth,varied=varied)
            for truth in ('TRUE','FALSE')]


def _b_rehearsal(rng,seen):
    """Preserve older B-class relations without replaying exam identities."""
    for _ in range(100):
        grade=rng.choice(('B01','B02','B03'))
        source=rng.choice(small.SOURCES['train'])
        rows=small.triplet(grade,source,{},rng,split='train',
                           mode=rng.randrange(2),group='rehearsal')
        available=[row for row in rows if row['id'] not in seen]
        if not available:
            continue
        row=deepcopy(rng.choice(available))
        row['course_meta']['curriculum_role']='old'
        row['course_meta']['teacher_mode']='rehearsal'
        seen.add(row['id'])
        return row
    raise ValueError('V2_REPAIR_B_REHEARSAL_EXHAUSTED')


def _rehearse(grade,count,category,rng,seen,varied):
    """Keep a real B anchor and preceding semantic forms in teacher's quota."""
    rows=[]
    for i in range(count):
        if i%4==0:
            rows.append(_b_rehearsal(rng,seen))
            continue
        family=(lessons.SUPPORTED[11] if grade=='G12' else
                lessons.SUPPORTED[12] if grade=='G13' else
                lessons.SUPPORTED[13] if i%2 else lessons.SUPPORTED[12])
        row=_generate(rng.choice(family),category,rng,seen,varied=varied)
        row['course_meta']['curriculum_role']='old'
        rows.append(row)
    return rows


def _preview(grade,count,rng,seen,varied):
    family=lessons.SUPPORTED[int(NEXT[grade][1:])]
    rows=[]
    for _ in range(count):
        row=_generate(rng.choice(family),'focus',rng,seen,varied=varied)
        row['course_meta']['curriculum_role']='preview'
        rows.append(row)
    return rows


def batch(grade,graph,policy,rng,*,excluded=None):
    """One 32-row batch, following all four original teacher curriculum knobs.

    The teacher still decides the mode (contrast), difficulty (depth),
    proportion of old rehearsal, and amount of future preview. Guardrails
    enforce lesson-to-exam semantic/answer coverage, not teacher policy.
    """
    if grade not in GRADES:
        raise ValueError('V2_REPAIR_UNKNOWN_GRADE')
    old_count=policy['old']
    preview_count=policy['preview']
    current_count=COUNTS-old_count-preview_count
    if (type(old_count) is not int or type(preview_count) is not int or
            not 0<=old_count<=20 or not 0<=preview_count<=4 or
            current_count<2*len(FAMILIES[grade])):
        raise ValueError('V2_REPAIR_TEACHER_ALLOCATION_UNSUPPORTED')
    category='composition' if policy['contrast']>=.5 else 'focus'
    varied=policy['depth']>=4
    forbidden=_excluded_exam_ids() if excluded is None else set(excluded)
    seen=set(forbidden)
    current=[]
    for family in FAMILIES[grade]:
        current.extend(_pair(family,category,rng,seen,varied=varied))
    remaining=current_count-len(current)
    for i in range(remaining):
        family=FAMILIES[grade][i%len(FAMILIES[grade])]
        current.append(_generate(family,category,rng,seen,
                                 truth=('TRUE','FALSE')[i%2],varied=varied))
    for row in current:
        row['course_meta']['curriculum_role']='current'
    prior=_rehearse(grade,old_count,category,rng,seen,varied)
    future=_preview(grade,preview_count,rng,seen,varied)
    rows=current+prior+future
    rng.shuffle(rows)
    if len(rows)!=COUNTS or len({row['id'] for row in rows})!=COUNTS:
        raise ValueError('V2_REPAIR_BATCH_IDENTITY_COLLAPSE')
    if {row['id'] for row in rows}&forbidden:
        raise ValueError('V2_REPAIR_EXAM_QUESTION_LEAKAGE')
    lessons.valid_rows(rows,graph)
    for family in FAMILIES[grade]:
        answers={r['gold'] for r in current if r['course_meta']['family']==family}
        if answers!={'TRUE','FALSE'}:
            raise ValueError('V2_REPAIR_UNTAUGHT_ANSWER_CLASS:'+family)
    counts={'current':current_count,'old':old_count,'preview':preview_count,
            'teacher_mode':category,'teacher_depth':policy['depth'],
            'answers':dict(Counter(r['gold'] for r in current))}
    return rows,counts
