"""V15 acquisition rungs for G11/G20/G22, without new tokens or oracles.

The historical G24/G48 panels remain untouched and are separate comparators.
This versioned course teaches exact primitive/numeric and matched equality
questions before requiring broader composition. All rows are *exposed teaching
replays*, never independent qualification or proof of transfer.
"""
from __future__ import annotations

import copy
from collections import Counter

import torch

from . import arithmetic as math
from . import g_primitives_v12 as previous
from . import lessons
from . import numeric_answer_contract as numeric
from . import primitive_staircase_v13 as staircase
from . import spiral_staged_runner as staged


VERSION='bilqis.school50.foundation-course/v15'
FOCUSED=('G11','G20','G22')


def _tag(row,concept):
    row['course_meta'].update(version=VERSION,concept=concept,
                              assessment_role='TRAINING_REPLAY_NOT_GENERALIZATION',
                              rung='DIRECT_THEN_MATCHED_COMPOSITION')
    return row


def _finite(grade,concept,pair,world,expression):
    return _tag(previous._finite(grade,concept.lower(),'direct',pair,0,
                                 world,expression),concept)


def _math(grade,concept,pair,expression):
    return _tag(previous._math(grade,concept.lower(),'direct',pair,0,
                               expression),concept)


def _build():
    a=previous._c('Entity','A');b=previous._c('Entity','B');c=previous._c('Entity','C')
    k0=previous._c('Set','K0');k1=previous._c('Set','K1')
    op=previous._op
    G11=[_tag(x,'MEMBER') for x in staircase.rows(concept='MEMBER')]
    w1=previous._world(entities='ABC',sets={'K0':['A'],'K1':['B','C']})
    w2=previous._world(entities='ABC',sets={'K0':['A','B'],'K1':['B']})
    for index,(world,entity,setref) in enumerate((
            (w1,a,k1),(w1,b,k1),(w1,c,k1),
            (w1,a,k0),(w1,b,k0),(w1,c,k0),
            (w2,a,k1),(w2,b,k1))):
        G11.append(_finite('G11','MEMBER',f'K0K1-variable-world-{index}',
                           world,op('MEMBER',entity,setref)))

    N=math.atom;O=math.operation
    G20=[_tag(x,x['course_meta']['concept']) for cpt in ('SUB','MUL','ADD')
         for x in staircase.rows(concept=cpt)]
    for name,a,b,actual,incorrect in (
            ('SUB',2,1,1,2),('MUL',2,1,2,3),
            ('MUL',1,1,1,0),('SUB',3,1,2,1)):
        inner=O(name,N(a),N(b))
        G20.extend((
            _math('G20','EQ_BRIDGE',f'{name}-{a}-{b}-true',
                  O('EQ',inner,N(actual))),
            _math('G20','EQ_BRIDGE',f'{name}-{a}-{b}-false',
                  O('EQ',inner,N(incorrect)))))

    G22=[_tag(x,'NESTED_NUMERIC' if x['answer_kind']=='numeric' else 'NESTED_EQ')
         for x in previous.rows('G22')]
    for index,expr in enumerate((
            O('ADD',O('ADD',N(0),N(0)),N(0)),
            O('ADD',O('SUB',N(2),N(1)),N(0)),
            O('ADD',O('MUL',N(1),N(2)),N(0)),
            O('ADD',O('MUL',N(1),N(3)),N(0)))):
        G22.append(_math('G22','NESTED_NUMERIC',f'new-inner-{index}',expr))
    for index,expr in enumerate((
            O('EQ',O('ADD',O('ADD',N(0),N(0)),N(0)),N(0)),
            O('EQ',O('ADD',O('ADD',N(0),N(0)),N(0)),N(1)),
            O('EQ',O('ADD',O('SUB',N(2),N(1)),N(0)),N(1)),
            O('EQ',O('ADD',O('SUB',N(2),N(1)),N(0)),N(2)))):
        G22.append(_math('G22','NESTED_EQ',f'new-equality-{index}',expr))

    inventory={'G11':tuple(G11),'G20':tuple(G20),'G22':tuple(G22)}
    expected={'G11':16,'G20':24,'G22':16}
    for grade,items in inventory.items():
        if len(items)!=expected[grade] or len({x['id'] for x in items})!=len(items):
            raise ValueError('V15_FOUNDATION_INVENTORY_DUPLICATED:'+grade)
        if grade in ('G20','G22'):
            kinds={r['answer_kind'] for r in items}
            if kinds!={'numeric','evidence'}:
                raise ValueError('V15_FOUNDATION_MISSING_TYPED_BRIDGE:'+grade)
    if Counter(row['gold'] for row in G11)!={'TRUE':8,'FALSE':8}:
        raise ValueError('V15_FOUNDATION_G11_BALANCE')
    if Counter(r['gold'] for r in G20 if r['course_meta']['concept']=='EQ_BRIDGE') != {'TRUE':4,'FALSE':4}:
        raise ValueError('V15_FOUNDATION_EQ_BRIDGE_BALANCE')
    return inventory


_ROWS=_build()


def rows(grade):
    if grade not in _ROWS:raise ValueError('V15_FOUNDATION_UNKNOWN_GRADE')
    return [copy.deepcopy(row) for row in _ROWS[grade]]


def _old_rows(grade,library,rng,count,seen):
    """Rehearse established early-G content, excluding deferred semantics."""
    result=[]
    for _ in range(400):
        if len(result)==count:break
        earlier=rng.choice(tuple(range(1,11)))
        row=library.one(earlier,rng,depth=2,prefer_composition=False)
        if isinstance(row,list):row=row[0]
        if row['id'] in seen:continue
        row['answer_kind']='evidence'
        result.append(row);seen.add(row['id'])
    if len(result)!=count:
        raise ValueError('V15_FOUNDATION_OLD_G_REHEARSAL_SHORTAGE')
    return result


def batch(grade,library,graph,policy,rng):
    """32 canonical typed rows; G11 cannot silently reimport SUBSET/DOMAIN."""
    direct=rows(grade)
    old=[];seen={r['id'] for r in direct}
    if grade=='G22':
        # Before testing nested arithmetic, rehearse direct prerequisites;
        # prior B training also runs separately on every complete spiral.
        old=[_tag(x,x['course_meta']['concept']) for x in
             staircase.rows(concept='SUB')[:4]+staircase.rows(concept='MUL')[:4]]
        if len({r['id'] for r in old})!=8 or seen.intersection(r['id'] for r in old):
            raise ValueError('V15_G22_PREREQUISITE_REHEARSAL_COLLISION')
        seen.update(r['id'] for r in old)
    old.extend(_old_rows(grade,library,rng,32-len(direct)-len(old),seen))
    full=direct+old
    if len(full)!=32 or len({r['id'] for r in full})!=32:
        raise ValueError('V15_FOCUS_BATCH_DUPLICATION')
    previous.validate_rows([r for r in full if 'course_meta' in r],graph)
    lessons.valid_rows([r for r in full if 'course_meta' not in r],graph)
    return full,{'current':len(direct),'old':len(old),'preview':0}


@torch.no_grad()
def measure(model,graph,grade,device):
    """Exact exposed-acquisition evidence. Never a historical G champion gate."""
    numbers=numeric.numeric_token_ids(graph)[:4]
    result={'by_concept':{},'total':0,'correct':0}
    was_training=model.training
    model.eval()
    try:
        for name in sorted({r['course_meta']['concept'] for r in _ROWS[grade]}):
            group=[r for r in rows(grade) if r['course_meta']['concept']==name]
            count=0
            for kind in ('numeric','evidence'):
                selection=[r for r in group if r['answer_kind']==kind]
                if not selection:continue
                ids,lengths=staged._input(selection,graph,device)
                logits=numeric.readout(model,ids,lengths,answer_kind=kind,
                                       number_ids=numbers)
                gold=staged._gold(selection,kind,device)
                count+=int((logits.argmax(-1)==gold).sum().item())
            result['by_concept'][name]={'correct':count,'total':len(group)}
            result['correct']+=count
            result['total']+=len(group)
    finally:
        if was_training:model.train()
    return result
