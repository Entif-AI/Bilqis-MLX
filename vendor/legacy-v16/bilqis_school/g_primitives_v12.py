"""Versioned small, exact, oracle-grounded remediation lessons for weak G grades.

These are *teaching* examples deliberately repeated at identical ASTs, worlds,
inputs and question IDs. They are not independent development/transfer exams.
They do not alter the frozen v11 recipe, tokenizer, model head or saved state.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy

from bilqis_logic.kernel import digest
from bilqis_micro import kernel as micro
from bilqis_development import kernel as finite
from . import arithmetic, lessons


VERSION='bilqis.school50.g-primitives/v1'
GRADES=('G11','G12','G13','G14','G15','G18','G20','G21','G22')
PREREQUISITES={
    'G11':('G05',),
    'G12':('G11',),
    'G13':('G11',),
    'G14':('G13',),
    'G15':('G04',),
    'G18':('G17',),
    'G20':('B01','B02','B03'),
    'G21':('G20',),
    'G22':('G20','G21'),
}


def _world(entities='ABCD',*,sets=None,functions=None,edges=(),events=(),links=(),props=False):
    declared={'J0':micro.relation('PARENT',micro.entity('A'),micro.entity('B'))} if props else {}
    base=micro.world(list(entities),propositions=declared)
    return finite.world(list(entities),base=base,sets=sets,functions=functions,
                        edges=edges,events=events,links=links)


def _c(kind,name):
    return finite.const(kind,name)


def _op(name,*arguments):
    return finite.op(name,*arguments)


def _meta(grade,concept,stage,pair,variant):
    return {'version':VERSION,'grade':grade,'mechanic':concept,
            'stage':stage,'pair':pair,'variant':variant,'tranche':'replay',
            'assessment_role':'TRAINING_REPLAY_NOT_GENERALIZATION',
            'exposure':'VERBATIM_EACH_GRADE_UPDATE'}


def _finite(grade,concept,stage,pair,variant,w,q):
    r=finite.record(w,q)
    expected=finite.evaluate(r)
    if expected!=finite.independent_evaluate(r):
        raise ValueError('G_PRIMITIVE_ORACLES_DISAGREE')
    encoded=finite.encode(r)
    if finite.decode(encoded)!=r:
        raise ValueError('G_PRIMITIVE_CODEC_ROUNDTRIP')
    return {'id':digest(r),'input':r,'gold':expected,'answer_kind':'evidence',
            'family':concept,'course_meta':_meta(grade,concept,stage,pair,variant)}


def _math(grade,concept,stage,pair,variant,e):
    arithmetic.verify(e)
    result=arithmetic.evaluate(e)
    if type(result) is int and 0<=result<=3:
        kind='numeric';gold=result
    elif type(result) is bool:
        kind='evidence';gold='TRUE' if result else 'FALSE'
    else:
        raise ValueError('G_PRIMITIVE_NUMERIC_RESULT_OUTSIDE_0_TO_3')
    r={'task':arithmetic.VERSION,'expression':e}
    return {'id':digest(r),'input':r,'gold':gold,'answer_kind':kind,
            'family':concept,'course_meta':_meta(grade,concept,stage,pair,variant)}


def _build(grade):
    result=[]
    def add(concept,stage,pair,*examples):
        for variant,(w,q) in enumerate(examples):
            if w is None:
                row=_math(grade,concept,stage,pair,variant,q)
            else:
                row=_finite(grade,concept,stage,pair,variant,w,q)
            result.append(row)
    a,b,c,d=(_c('Entity',letter) for letter in 'ABCD')
    k0,k1=(_c('Set',key) for key in ('K0','K1'))
    f0,f1=(_c('Function',key) for key in ('F0','F1'))
    if grade=='G11':
        w=_world(sets={'K0':['A'],'K1':['A','B']})
        add('element-membership','primitive','membership-A-vs-B',
            (w,_op('MEMBER',a,k0)),(w,_op('MEMBER',b,k0)))
        add('directed-subset','primitive','subset-forward-vs-reverse',
            (w,_op('SUBSET',k0,k1)),(w,_op('SUBSET',k1,k0)))
    elif grade=='G12':
        w=_world(sets={'K0':['A','B'],'K1':['B']})
        intersection=_op('INTERSECTION',k0,k1)
        difference=_op('DIFFERENCE',k0,k1)
        add('intersection-membership','primitive','intersection-B-vs-A',
            (w,_op('MEMBER',b,intersection)),(w,_op('MEMBER',a,intersection)))
        add('directed-difference','primitive','difference-A-vs-B',
            (w,_op('MEMBER',a,difference)),(w,_op('MEMBER',b,difference)))
    elif grade=='G13':
        w=_world(functions={'F0':[['A','B']]})
        add('function-input-domain','primitive','domain-A-vs-B',
            (w,_op('MEMBER',a,_op('DOMAIN',f0))),
            (w,_op('MEMBER',b,_op('DOMAIN',f0))))
        add('function-output-range','primitive','range-B-vs-A',
            (w,_op('MEMBER',b,_op('RANGE',f0))),
            (w,_op('MEMBER',a,_op('RANGE',f0))))
        add('function-inverse-direction','primitive','inverse-B-A-vs-A-B',
            (w,_op('MAPS',_op('INVERSE',f0),b,a)),
            (w,_op('MAPS',_op('INVERSE',f0),a,b)))
    elif grade=='G14':
        w=_world(functions={'F0':[['A','B'],['C','D']],
                            'F1':[['B','C'],['D','A']]})
        combined=_op('COMPOSITION',f0,f1)
        backwards=_op('COMPOSITION',f1,f0)
        add('composition-forward','composition','A-C-vs-reversed-order',
            (w,_op('MAPS',combined,a,c)),(w,_op('MAPS',backwards,a,c)))
        add('composition-second-path','composition','C-A-vs-reversed-order',
            (w,_op('MAPS',combined,c,a)),(w,_op('MAPS',backwards,c,a)))
    elif grade=='G15':
        w=_world(edges=[['A','B'],['B','C']])
        add('directed-edge','primitive','forward-vs-backward-edge',
            (w,_op('EDGE',a,b)),(w,_op('EDGE',b,a)))
        add('two-hop-directed-path','primitive','path-vs-missing-direct-edge',
            (w,_op('PATH',a,c)),(w,_op('EDGE',a,c)))
        add('neighbors-not-reachability','primitive','direct-neighbor-vs-two-hop',
            (w,_op('MEMBER',b,_op('NEIGHBORS',a))),
            (w,_op('MEMBER',c,_op('NEIGHBORS',a))))
        add('path-direction','primitive','A-B-vs-C-A',
            (w,_op('PATH',a,b)),(w,_op('PATH',c,a)))
    elif grade=='G18':
        p=_c('Proposition','J0')
        p1=_c('Proposition','J1')
        one=_world(entities='AB',props=True,
                   events=[['E0','ASSERT','S0','J0','support']])
        two=_world(entities='AB',props=True,
                   events=[['E0','ASSERT','S0','J0','support'],
                           ['E1','OBSERVE','S1','J0','refute']],
                   links=[['SUPERSEDES','E1','E0']])
        add('one-report-evidence','primitive','current-TRUE-vs-UNKNOWN',
            (one,_op('CURRENT_STATE',p)),(one,_op('CURRENT_STATE',p1)))
        add('evidence-replacement','primitive','current-FALSE-vs-historical-CONFLICT',
            (two,_op('CURRENT_STATE',p)),(two,_op('HISTORICAL_STATE',p)))
        add('which-event-is-current','primitive','new-current-vs-old-superseded',
            (two,_op('IS_CURRENT',_c('Event','E1'))),
            (two,_op('IS_CURRENT',_c('Event','E0'))))
        add('original-report-retained','primitive','historical-TRUE-vs-UNKNOWN',
            (one,_op('HISTORICAL_STATE',p)),
            (one,_op('HISTORICAL_STATE',p1)))
    elif grade=='G20':
        N=arithmetic.atom
        O=arithmetic.operation
        add('direct-multiplication','primitive','two-times-one-vs-zero',
            (None,O('MUL',N(2),N(1))),(None,O('MUL',N(2),N(0))))
        add('multiplication-identity','primitive','three-times-one-vs-zero',
            (None,O('MUL',N(3),N(1))),(None,O('MUL',N(3),N(0))))
        add('modulo-remainder','primitive','three-mod-two-vs-three',
            (None,O('MOD',N(3),N(2))),(None,O('MOD',N(3),N(3))))
        add('modulo-quotient','primitive','two-mod-three-vs-two',
            (None,O('MOD',N(2),N(3))),(None,O('MOD',N(2),N(2))))
        add('simple-add-sub-rehearsal','primitive','add-vs-sub',
            (None,O('ADD',N(1),N(2))),(None,O('SUB',N(3),N(2))))
        add('multiplication-equality','composition','MUL-EQ-TRUE-vs-FALSE',
            (None,O('EQ',O('MUL',N(2),N(1)),N(2))),
            (None,O('EQ',O('MUL',N(2),N(1)),N(3))))
    elif grade=='G21':
        N=arithmetic.atom;O=arithmetic.operation
        add('add-commutativity','composition','correct-vs-off-by-one',
            (None,O('EQ',O('ADD',N(1),N(2)),O('ADD',N(2),N(1)))),
            (None,O('EQ',O('ADD',N(1),N(2)),O('ADD',N(1),N(1)))))
        add('mul-commutativity','composition','correct-vs-zero',
            (None,O('EQ',O('MUL',N(2),N(1)),O('MUL',N(1),N(2)))),
            (None,O('EQ',O('MUL',N(2),N(1)),O('MUL',N(2),N(0)))))
        add('subtraction-identity','composition','correct-vs-wrong-target',
            (None,O('EQ',O('SUB',N(3),N(1)),O('ADD',N(1),N(1)))),
            (None,O('EQ',O('SUB',N(3),N(1)),O('ADD',N(1),N(0)))))
    elif grade=='G22':
        N=arithmetic.atom;O=arithmetic.operation
        add('add-after-multiply','composition','mult-then-add-zero-vs-one',
            (None,O('ADD',O('MUL',N(2),N(1)),N(0))),
            (None,O('ADD',O('MUL',N(2),N(1)),N(1))))
        add('add-after-subtract','composition','sub-then-add-zero-vs-one',
            (None,O('ADD',O('SUB',N(3),N(1)),N(0))),
            (None,O('ADD',O('SUB',N(3),N(1)),N(1))))
        add('add-after-add','composition','add-then-add-zero-vs-one',
            (None,O('ADD',O('ADD',N(1),N(1)),N(0))),
            (None,O('ADD',O('ADD',N(1),N(1)),N(1))))
        add('nested-equality','composition','nested-EQ-TRUE-vs-FALSE',
            (None,O('EQ',O('ADD',O('MUL',N(1),N(2)),N(1)),N(3))),
            (None,O('EQ',O('ADD',O('MUL',N(1),N(2)),N(1)),N(2))))
    else:
        raise ValueError('G_PRIMITIVE_UNKNOWN_GRADE')
    ids=[r['id'] for r in result]
    if len(set(ids))!=len(ids):
        raise ValueError('G_PRIMITIVE_DUPLICATE_SOURCE')
    return result


_PANELS={grade:tuple(_build(grade)) for grade in GRADES}


def rows(grade,*,stage=None):
    if grade not in _PANELS:
        raise ValueError('G_PRIMITIVE_GRADE_NOT_SUPPORTED')
    return [deepcopy(row) for row in _PANELS[grade]
            if stage is None or row['course_meta']['stage']==stage]


def validate_rows(items,graph):
    if not items:raise ValueError('G_PRIMITIVE_EMPTY')
    seen=set();mapping={token:i for i,token in enumerate(graph['tokens'])}
    for row in items:
        if row['id'] in seen:raise ValueError('G_PRIMITIVE_DUPLICATE_IN_BATCH')
        seen.add(row['id'])
        meta=row['course_meta']
        if meta['tranche']!='replay' or meta['assessment_role']!='TRAINING_REPLAY_NOT_GENERALIZATION':
            raise ValueError('G_PRIMITIVE_ASSESSMENT_MISLABELED')
        r=row['input']
        if r['task']==arithmetic.VERSION:
            arithmetic.verify(r['expression'])
            value=arithmetic.evaluate(r['expression'])
            gold=value if type(value) is int else 'TRUE' if value else 'FALSE'
            encoded=arithmetic.encode(r,mapping)
        elif r['task']=='development':
            gold=finite.evaluate(r)
            if gold!=finite.independent_evaluate(r) or finite.decode(finite.encode(r))!=r:
                raise ValueError('G_PRIMITIVE_DEVELOPMENT_ORACLE_DRIFT')
            encoded=finite.encode(r)
        else:
            raise ValueError('G_PRIMITIVE_UNSUPPORTED_SOURCE')
        if (gold!=row['gold'] or not encoded or len(encoded)>96 or
                max(encoded)>=len(graph['tokens']) or digest(r)!=row['id']):
            raise ValueError('G_PRIMITIVE_GOLD_OR_TOKEN_ABI_DRIFT')
    return True
