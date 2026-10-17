"""A small multi-concept acquisition rung, reachable from established skills.

Teach direct set membership, directed edges, 0..3 subtraction repair and
multiplication from previously taught addition in ONE 32-row course. Concepts
whose prerequisite is not yet reliable (subset, paths, modulo, nested maths,
variables, temporal state) await an evidence-based later rung. All questions
are exposed teaching replays, not independent research qualification.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy

from bilqis_logic.kernel import digest
from . import arithmetic, g_primitives_v12 as v12

VERSION = 'bilqis.primitive-staircase/v13'
CONCEPTS = ('MEMBER','EDGE','SUB','MUL')
PREREQUISITES = {
    'MEMBER': ('G05:identity',),
    'EDGE': ('G04:direction', 'G08:relations'),
    'SUB': ('B:direct_add', 'G19:equality'),
    'MUL': ('B:direct_add',),
}
DEFERRED = {
    'SUBSET':'MEMBER must first be demonstrably acquired',
    'NEIGHBORS':'MEMBER and EDGE must first be demonstrably acquired',
    'PATH':'EDGE and relational sequencing must first be demonstrably acquired',
    'MOD':'SUB and grouping must first be demonstrably acquired',
    'G22':'direct arithmetic must first be acquired before nesting',
    'NEXT':'requires an explicit ordered-sequence context and new token/AST',
    'METAVARIABLE':'requires distinct typed binding and reference mechanics',
    'G18':'requires temporal order and state-change foundations',
}


def _finite(concept, group, w, q):
    grade = 'G11' if concept == 'MEMBER' else 'G15'
    row = v12._finite(grade, concept.lower(), 'direct', group, 0, w, q)
    row['course_meta'].update(version=VERSION, concept=concept,
                              prerequisites=PREREQUISITES[concept],
                              acquisition_group='DIRECT_PATH_FOUNDATION')
    return row


def _math(concept, a, b, *, retention=False):
    expr = arithmetic.operation(concept, arithmetic.atom(a), arithmetic.atom(b))
    row = v12._math('G20' if not retention else 'B02',
                    concept.lower(), 'direct', concept+'-'+str(a)+'-'+str(b), 0, expr)
    row['course_meta'].update(version=VERSION, concept=concept,
                              prerequisites=PREREQUISITES.get(concept,()),
                              acquisition_group='DIRECT_PATH_FOUNDATION',
                              retention=retention)
    return row


def _build():
    rows=[]
    c=v12._c
    op=v12._op
    # Every subset of {A,B}; the membership of either entity is queried.
    # All four presence/absence combinations are directly visible in input.
    for members in ((),('A',),('B',),('A','B')):
        world=v12._world(entities='AB',sets={'K0':list(members)})
        for name in ('A','B'):
            row=_finite('MEMBER','set:'+','.join(members)+':'+name,
                        world,op('MEMBER',c('Entity',name),c('Set','K0')))
            row['course_meta']['world_members']=list(members)
            row['course_meta']['queried_entity']=name
            rows.append(row)
    # Four tiny graphs, one edge per graph; positive and reversed queries.
    # Changing edge direction reverses which query is true.
    for source,target in (('A','B'),('B','A'),('A','C'),('C','A')):
        world=v12._world(entities='ABC',edges=[[source,target]])
        ordered=(('A','B'),('B','A')) if {source,target}=={'A','B'} else (('A','C'),('C','A'))
        for left,right in ordered:
            rows.append(_finite('EDGE',f'edge:{source}{target}:{left}{right}',
                                world,op('EDGE',c('Entity',left),c('Entity',right))))
    # Direct results only, all within the existing four-number output domain.
    # Matched SUB(2,1) / MUL(2,1) distinguishes operator meanings.
    for a,b in ((0,0),(1,0),(1,1),(2,1),(3,1),(3,0)):
        rows.append(_math('SUB',a,b))
    for a,b in ((2,0),(2,1),(1,2),(1,1),(3,1),(0,3)):
        rows.append(_math('MUL',a,b))
    # Four historically successful, repeatedly seen ADD results; these are
    # explicit retention anchors from the existing B arithmetic curriculum.
    for a,b in ((0,0),(1,0),(1,1),(0,3)):
        rows.append(_math('ADD',a,b,retention=True))
    if (len(rows)!=32 or len({row['id'] for row in rows})!=32 or
            Counter(r['course_meta']['concept'] for r in rows) !=
            {'MEMBER':8,'EDGE':8,'SUB':6,'MUL':6,'ADD':4}):
        raise ValueError('V13_DIRECT_PATH_INVENTORY_CHANGED')
    return tuple(rows)


_ROWS=_build()


def rows(*,concept=None):
    if concept is not None and concept not in CONCEPTS+('ADD',):
        raise ValueError('V13_UNSUPPORTED_CONCEPT')
    return [deepcopy(r) for r in _ROWS
            if concept is None or r['course_meta']['concept']==concept]


def checks():
    """Single-factor flips and invariances needed to reject shallow shortcuts."""
    r=rows()
    lookup={}
    for x in r:
        meta=x['course_meta']
        if meta['concept']=='MEMBER':
            lookup[('member',tuple(meta['world_members']),meta['queried_entity'])]=x
        if meta['concept']=='EDGE':
            world=tuple(tuple(e) for e in x['input']['world']['edges'])
            query=tuple(arg['name'] for arg in x['input']['query']['args'])
            lookup[('edge',world,query)]=x
        if meta['concept'] in ('SUB','MUL'):
            operands=tuple(v['value'] for v in x['input']['expression']['args'])
            lookup[(meta['concept'],operands)]=x
    result=[]
    def add(name,kind,a,b):
        x=lookup[a];y=lookup[b]
        same=x['gold']==y['gold']
        if same != (kind=='invariant'):
            raise ValueError('V13_BAD_CONTRAST_OR_INVARIANT')
        result.append({'name':name,'kind':kind,'concept':x['course_meta']['concept'],
                       'ids':(x['id'],y['id'])})
    for name in ('A','B'):
        other='B' if name=='A' else 'A'
        add('member-'+name+'-empty-to-single','flip',
            ('member',(),name),('member',(name,),name))
        add('member-'+name+'-other-to-both','flip',
            ('member',(other,),name),('member',('A','B'),name))
        add('member-'+name+'-irrelevant-added','invariant',
            ('member',(),name),('member',(other,),name))
        add('member-'+name+'-irrelevant-while-present','invariant',
            ('member',(name,),name),('member',('A','B'),name))
    for a,b in (('A','B'),('A','C')):
        add('edge-'+a+b+'-forward-reverse','flip',
            ('edge',((a,b),),(a,b)),('edge',((a,b),),(b,a)))
        add('edge-'+a+b+'-reverse-world','flip',
            ('edge',((a,b),),(a,b)),('edge',((b,a),),(a,b)))
    add('same-operands-sub-versus-mul','flip',('SUB',(2,1)),('MUL',(2,1)))
    return result


def validate(graph):
    """Check both independent oracles, codec, hashes, labels and ABI."""
    v12.validate_rows(rows(),graph)
    for x in rows():
        if x['course_meta']['assessment_role']!='TRAINING_REPLAY_NOT_GENERALIZATION':
            raise ValueError('V13_REPLAY_ROLE_MISSING')
        if x['course_meta']['concept'] in CONCEPTS and x['course_meta'].get('retention'):
            raise ValueError('V13_TARGET_MISMARKED_AS_RETENTION')
    for group in ('MEMBER','EDGE'):
        labels=Counter(r['gold'] for r in rows(concept=group))
        if labels != {'TRUE':4,'FALSE':4}:
            raise ValueError('V13_BOOLEAN_SHORTCUT_UNBALANCED')
    for c in ('SUB','MUL'):
        if {r['gold'] for r in rows(concept=c)}!={0,1,2,3}:
            raise ValueError('V13_NUMERIC_TARGET_COLLAPSE')
    if len(checks())!=13:
        raise ValueError('V13_INCOMPLETE_CONTRAST_INVENTORY')
    return True
