"""Deterministic, source-grounded CURRENT v15 acquisition exam construction.

The unit of qualification is a named taught *question family*, not a grade
headline. These deterministic oracle-backed items are a CURRENT curriculum
acquisition panel, not a new unseen language generalization benchmark.
Never substitute historical G528, mixed optimizer steps, or exam maxima.
"""
from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
import random

from bilqis_logic.kernel import digest
from bilqis_micro import data as micro
from bilqis_development import data as development, kernel as semantics
from . import arithmetic, foundation_course_v15 as foundation
from . import lessons, primitive_staircase_v13 as staircase
from . import small_domain_lessons as small, spiral_semantic_bridge as bridge

SCHEMA='bilqis.v15.source-bound-current-exam/v1'
SEED=20261014
EXPECTED_PROGRAM=small.GRADES + tuple(f'G{n:02d}' for n in range(1,23))
MICRO_FAMILIES={
    1:('Boolean',),2:('Boolean',),3:('Boolean',),
    4:('direction','inverse','no_parent_transitivity','symmetric_link',
       'identity','edge_presence'),
    5:('direction','inverse','no_parent_transitivity','symmetric_link',
       'identity','edge_presence'),
    6:('bound_two_hop','relational_composition','exists_distinct_parent',
       'forall_counterexample','nested_binding_witness',
       'nested_binding_counterexample','inverse_quantification'),
    7:('bound_two_hop','relational_composition','exists_distinct_parent',
       'forall_counterexample','nested_binding_witness',
       'nested_binding_counterexample','inverse_quantification'),
    8:('bound_two_hop','relational_composition','exists_distinct_parent',
       'forall_counterexample','nested_binding_witness',
       'nested_binding_counterexample','inverse_quantification'),
    9:('derived_entailment','rule_application','candidate_countermodel',
       'quantified_derivation','rule_implication','declared_rule_presence'),
    10:('evidence_state',),
}
LINEAGE_RELATIONS=('DERIVED_FROM','SUPERSEDES','DEPENDENCY','CURRENT_STATE','REVISES')


def _verify(row):
    """Independent semantic check. Failed or ambiguous oracles cannot graduate."""
    record=row['input']
    if record.get('task')==bridge.VERSION:
        expected=bridge.evaluate(record)
    elif record.get('task')==arithmetic.VERSION:
        expected=arithmetic.evaluate(record['expression'])
        independent=arithmetic.independent_evaluate(record['expression'])
        if expected!=independent:raise ValueError('CURRENT_EXAM_MATH_ORACLE_DISAGREEMENT')
        if row.get('answer_kind')!='numeric':
            expected='TRUE' if expected else 'FALSE'
    else:
        expected=semantics.evaluate(record)
        independent=semantics.independent_evaluate(record)
        if expected!=independent:raise ValueError('CURRENT_EXAM_SEMANTIC_ORACLE_DISAGREEMENT')
    if expected!=row['gold']:
        raise ValueError('CURRENT_EXAM_LABEL_DISAGREEMENT:'+row['id'])
    return row


def _draw(factory,count,seed,description):
    """Take distinct oracle-verified source rows, never manufacture filler."""
    rng=random.Random(seed)
    unique={}
    for _ in range(count*350):
        if len(unique)==count:break
        try:packet=factory(rng)
        except ValueError as error:
            # Some finite worlds are unencodable or invalid inverses by design.
            if any(word in str(error).lower() for word in ('context','inverse is not a function','world exceeds')):
                continue
            raise
        items=packet if isinstance(packet,list) else [packet]
        for item in items:
            _verify(item)
            unique.setdefault(item['id'],item)
            if len(unique)==count:break
    if len(unique)!=count:
        raise ValueError('CURRENT_EXAM_SOURCE_EXHAUSTED:'+description)
    return tuple(unique.values())


def _source_B(grade):
    """Cover every taught arithmetic source, not only the 12 replay questions."""
    groups=defaultdict(list);used=set()
    for i,source in enumerate(small.SOURCES['train']):
        for attempt in range(60):
            rng=(small._replay_rng(grade,source) if source in small.REPLAY_MODES else
                 random.Random(SEED+small.GRADES.index(grade)*27103+i*701+attempt))
            triplet=small.triplet(grade,source,{},rng,split='train',
                                  mode=small.REPLAY_MODES.get(source,i%2),group='current')
            if all(row['id'] not in used for row in triplet):break
        else:raise ValueError('CURRENT_B_TRIPLET_COLLISION:'+grade)
        for row in triplet:
            used.add(row['id'])
            groups[row['course_meta']['projection'].upper()].append(_verify(row))
    if sum(map(len,groups.values()))!=36:raise ValueError('CURRENT_B_SOURCE_INCOMPLETE:'+grade)
    return {key:tuple(rows) for key,rows in groups.items()}


def _numeric_B():
    """Only one shared number panel across seven B visits, 12 trained sources."""
    return tuple(_verify(small._arithmetic_row(small.expression(source),'NUMERIC',
                        'train','replay',0)) for source in small.SOURCES['train'])


def _micro(grade,family,mode):
    stage=0 if grade<=3 else 1 if grade<=5 else 2 if grade<=8 else 3 if grade==9 else 4
    category='composition' if mode=='COMPOSITION' else 'focus'
    sample_size=16 if stage in (0,4) else 6
    expected=('Boolean:'+category if stage==0 else family+
              (':composition' if mode=='COMPOSITION' else ''))
    return _draw(lambda rng: _matching_micro(stage,category,family,expected,rng),
                 sample_size,SEED+grade*1697+sum(map(ord,family))*13+(mode=='COMPOSITION'),
                 f'G{grade:02d}:{family}:{mode}')


def _matching_micro(stage,category,family,expected,rng):
    row=micro.lesson(stage,rng,category=category,varied=False)
    # The source stage generator genuinely samples different families.
    if row['family']!=expected:
        return []
    return row


def _development(grade,family,mode):
    stage=5 if grade<=15 else 6
    category='composition' if mode=='COMPOSITION' else 'focus'
    return _draw(lambda rng:development.lesson(stage,family,rng,category=category,
                                              varied=False),
                 8,SEED+grade*1873+sum(map(ord,family))*19+(mode=='COMPOSITION'),
                 f'G{grade:02d}:{family}:{mode}')


def _lineage(relation):
    library=lessons.TeacherLibrary()
    return _draw(lambda rng:library.relation_pair(relation,rng,depth=2),
                 8,SEED+17*1297+sum(map(ord,relation)),f'G17:{relation}')


def _math(grade,operator):
    def generate(rng):
        row=arithmetic.lesson(grade,rng,correct=bool(rng.randrange(2)),depth=2)
        expr=row['input']['expression']
        selected=expr['name'] if grade==19 else expr['args'][0]['name']
        return row if selected==operator else []
    return _draw(generate,8,SEED+grade*1759+sum(map(ord,operator)),
                 f'G{grade:02d}:{operator}')


def compile_source_rubric():
    """Return manifest and exact questions from executable v15 *teaching* sources."""
    groups={}
    for grade in small.GRADES:
        for family,rows in _source_B(grade).items():
            groups[f'{grade}:{family}']=rows
    groups['B01:NUMERIC_0_3']=_numeric_B()
    for grade in range(1,23):
        ident=f'G{grade:02d}'
        if grade in MICRO_FAMILIES:
            for family in MICRO_FAMILIES[grade]:
                for mode in ('FOCUS','COMPOSITION'):
                    groups[f'{ident}:{family.upper()}_{mode}']=_micro(grade,family,mode)
        elif grade in (11,20,22):
            for family in sorted({row['course_meta']['concept'] for row in foundation.rows(ident)}):
                groups[f'{ident}:{family}']=tuple(_verify(row) for row in foundation.rows(ident)
                                                 if row['course_meta']['concept']==family)
        elif grade==15:
            groups['G15:EDGE']=tuple(_verify(row) for row in staircase.rows(concept='EDGE'))
        elif grade==17:
            for relation in LINEAGE_RELATIONS:
                groups[f'{ident}:{relation}']=_lineage(relation)
        elif grade in (19,21):
            for operator in (('EQ','LT','LE') if grade==19 else ('ADD','SUB','MUL')):
                groups[f'{ident}:{operator}']=_math(grade,operator)
        else:
            for family in lessons.SUPPORTED[grade]:
                for mode in ('FOCUS','COMPOSITION'):
                    groups[f'{ident}:{family.upper().replace("-","_")}_{mode}']=_development(grade,family,mode)
    if {key.split(':',1)[0] for key in groups}!=set(EXPECTED_PROGRAM):
        raise ValueError('CURRENT_EXAM_MISSING_GRADES')
    manifest={}
    for key,rows in groups.items():
        if not rows or len({row['id'] for row in rows})!=len(rows):
            raise ValueError('CURRENT_EXAM_DUPLICATE_OR_EMPTY:'+key)
        manifest[key]={
            'source':'bilqis_school.source_rubric_v15/'+SCHEMA,
            'assessment_role':'CURRENT_TAUGHT_SYLLABUS',
            'evidence_role':'SOURCE_DEFINED_ACQUISITION_NOT_INDEPENDENT_GENERALIZATION',
            'total':len(rows),
            'questions_sha256':digest([[r['id'],r['gold'],r.get('answer_kind','evidence')]
                                      for r in rows]),
        }
    return manifest,groups


@lru_cache(maxsize=1)
def inventory():
    return compile_source_rubric()


def questions(key):
    return inventory()[1][key]
