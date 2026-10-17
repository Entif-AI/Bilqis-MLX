"""Next four *new grade IDs* after v15's first-rung foundation.

These are isolated, typed/oracle-checked teaching inventories. They are NOT
in the currently running v15 program. A next-version runner must explicitly
add grade scheduling, adaptive-teacher IDs, score receipts and optimizer-safe
continuation before any human training can use them.
"""
from __future__ import annotations

from copy import deepcopy
from collections import Counter

from . import arithmetic as math, foundation_course_v15 as earlier
from . import g_primitives_v12 as finite


VERSION='bilqis.school50.foundation-next/v16'
PREREQUISITES={
    'G23':('G11:MEMBER_16_OF_16',),
    'G24':('G23:VARIABLE_WORLD_MEMBERSHIP',),
    'G25':('G20:SMALL_ARITHMETIC_EQ_24_OF_24',),
    'G26':('G22:NESTED_COMPOSITION_16_OF_16','G20:ADD_MUL_EQUATION'),
}
CONCEPTS={'G23':'MEMBER_VARIABLE_WORLDS',
          'G24':'SUBSET_DIRECTION',
          'G25':'MOD_SMALL',
          'G26':'DISTRIBUTIVE_COMPOSITION'}


def _with_meta(row,grade):
    row['course_meta'].update(version=VERSION,grade=grade,
                              concept=CONCEPTS[grade],
                              prerequisites=PREREQUISITES[grade],
                              assessment_role='CURRENT_TAUGHT_GRADE')
    return row


def _finite(grade,pair,world,query):
    return _with_meta(earlier._finite(grade,CONCEPTS[grade],pair,world,query),grade)


def _math(grade,pair,query):
    return _with_meta(earlier._math(grade,CONCEPTS[grade],pair,query),grade)


def _build():
    const=finite._c;op=finite._op;O=math.operation;N=math.atom
    a,b,c=(const('Entity',letter) for letter in 'ABC')
    k0,k1=(const('Set',name) for name in ('K0','K1'))
    records={name:[] for name in PREREQUISITES}
    # G23: present/absent identity contrasts across four independently given
    # worlds. The queried entity, not a hardcoded label, determines truth.
    for index,(first,second) in enumerate((
            (['A'],['B']),(['B'],['A','C']),
            (['A','B'],['C']),(['C'],['A','B']))):
        world=finite._world(entities='ABC',sets={'K0':first,'K1':second})
        for name,setref in (('A',k0),('B',k0),('A',k1),('C',k1)):
            records['G23'].append(_finite('G23',f'w{index}:{name}:{setref["name"]}',
                world,op('MEMBER',const('Entity',name),setref)))
    # G24: SUBSET direction and equality. Boolean true/false varies only in
    # the source/target relationship, not in unintroduced graph operations.
    for index,(first,second) in enumerate((
            (['A'],['A','B']),(['A','B'],['A']),
            (['A'],['B']),(['B'],['A','B']))):
        world=finite._world(entities='ABC',sets={'K0':first,'K1':second})
        for left,right in ((k0,k1),(k1,k0),(k0,k0),(k1,k1)):
            records['G24'].append(_finite('G24',f'sets{index}:{left["name"]}:{right["name"]}',
                world,op('SUBSET',left,right)))
    # G25: MOD is introduced directly with 0..3 numeric results before
    # matched Boolean equality; zero denominator is never introduced here.
    for index,(lhs,rhs,incorrect) in enumerate((
            (2,2,1),(3,2,0),(2,1,2),(3,3,2),
            (1,2,2),(3,1,1),(2,3,1),(0,2,1))):
        expression=O('MOD',N(lhs),N(rhs))
        actual=math.evaluate(expression)
        records['G25'].append(_math('G25',f'mod-direct-{index}',expression))
        records['G25'].append(_math('G25',f'mod-eq-{index}',
            O('EQ',expression,N(actual if index%2==0 else incorrect))))
    # G26: a bounded distributive identity is composed from known small
    # multiplication and addition. Every equality is paired with a concrete
    # wrong comparator; no proof-language tokens are assumed.
    for index,(x,y,z) in enumerate((
            (0,1,2),(1,1,1),(2,1,0),(1,0,2),
            (0,2,1),(2,0,1),(1,2,0),(0,0,3))):
        lhs=O('MUL',N(x),O('ADD',N(y),N(z)))
        rhs=O('ADD',O('MUL',N(x),N(y)),O('MUL',N(x),N(z)))
        # All inner operands are in the 0..3 domain; Boolean EQ readout.
        records['G26'].append(_math('G26',f'distribute-true-{index}',O('EQ',lhs,rhs)))
        records['G26'].append(_math('G26',f'distribute-false-{index}',
            O('EQ',lhs,N(math.evaluate(lhs)+1))))
    for grade,rows in records.items():
        if len(rows)!=16 or len({r['id'] for r in rows})!=16:
            raise ValueError('V16_GRADE_INVENTORY_DUPLICATED:'+grade)
        if Counter(row['gold'] for row in rows if row['answer_kind']=='evidence').get('TRUE',0)==0:
            raise ValueError('V16_GRADE_NO_POSITIVE_EVIDENCE:'+grade)
        if Counter(row['gold'] for row in rows if row['answer_kind']=='evidence').get('FALSE',0)==0:
            raise ValueError('V16_GRADE_NO_NEGATIVE_EVIDENCE:'+grade)
    return {grade:tuple(rows) for grade,rows in records.items()}


_ROWS=_build()


def rows(grade):
    if grade not in _ROWS:raise ValueError('V16_UNKNOWN_NEW_GRADE')
    return deepcopy(_ROWS[grade])
