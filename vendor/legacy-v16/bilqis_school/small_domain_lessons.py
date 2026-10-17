"""Four-value B curriculum: rehearsed arithmetic, relations and compositions.

All *new* B rows use only numerals 0..3, including outputs and equality
candidates. The original G01-G22 historical lessons remain outside this tiny
domain to preserve retention measurement. Held-out ownership is by exact
ADD/SUB source expression (not number value). The two acquisition panels
intentionally replay EXACT questions taught every update. Reserved sources
are not examined or used for candidate selection at this learning stage.
"""
from __future__ import annotations

import copy
import random

from bilqis_development import kernel as finite
from bilqis_logic.kernel import digest
from . import arithmetic, lessons
from . import acquisition_lessons as inherited
from . import spiral_numeric_lessons as numeric
from . import spiral_primitive_lessons as primitive
from . import spiral_semantic_bridge as bridge

VERSION='bilqis.school50.small-domain-lessons/v1'
GRADES=inherited.GRADES
TOPICS=inherited.TOPICS
MAX_NUM=3
PANEL_ROWS=6
TOTAL_BRIDGE_ROWS=len(GRADES)*2*PANEL_ROWS
NUMERIC_ROWS_PER_B_BATCH=6

# All twenty nonnegative two-operand ADD/SUB forms with operands and results
# inside 0..3. The small teaching universe includes every replay item.
# Future development/sealed sources are reserved, NOT consulted during early
# acquisition; their existence is not a reason to withhold taught examples.
SOURCES={
    'train':(('ADD',0,0),('ADD',1,0),('ADD',1,1),('ADD',0,3),
             ('ADD',1,2),('ADD',2,0),('SUB',0,0),('SUB',1,0),
             ('SUB',1,1),('SUB',2,1),('SUB',3,0),('SUB',3,1)),
    'development':(('ADD',0,1),('SUB',2,0),('ADD',2,1),('SUB',2,2)),
    'sealed':(('ADD',0,2),('SUB',3,2),('ADD',3,0),('SUB',3,3)),
}
SOURCE_OWNER={source:split for split,entries in SOURCES.items() for source in entries}
assert sum(map(len,SOURCES.values()))==len(SOURCE_OWNER)==20
assert all(0<=a<=3 and 0<=b<=3 and 0<=
           (a+b if op=='ADD' else a-b)<=3 for op,a,b in SOURCE_OWNER)

# One direct-number target for each of 0,1,2,3, rehearsed on EVERY B update.
# In the B panel, each source also has three exact operator/proposition views.
REPLAY_SOURCES=(('ADD',0,0),('ADD',1,0),('ADD',1,1),('ADD',0,3))
REPLAY_MODES={source:index%2 for index,source in enumerate(REPLAY_SOURCES)}
assert all(source in SOURCES['train'] for source in REPLAY_SOURCES)


def _replay_rng(grade,source):
    """Stable rendered examples, including finite-set world construction."""
    return random.Random(712017+GRADES.index(grade)*65537+
                         REPLAY_SOURCES.index(source)*8191)


def expression(source):
    if source not in SOURCE_OWNER:
        raise ValueError('SMALL_DOMAIN_UNKNOWN_SOURCE')
    op,a,b=source
    return arithmetic.operation(op,arithmetic.atom(a),arithmetic.atom(b))


def _owner(expr):
    if (expr.get('kind')!='op' or expr.get('name') not in ('ADD','SUB') or
            len(expr.get('args',[]))!=2 or
            any(node.get('kind')!='number' for node in expr['args'])):
        raise ValueError('SMALL_DOMAIN_NOT_AN_OWNED_SOURCE')
    source=(expr['name'],expr['args'][0]['value'],expr['args'][1]['value'])
    if source not in SOURCE_OWNER or expression(source)!=expr:
        raise ValueError('SMALL_DOMAIN_SOURCE_NOT_OWNED')
    return source


def _source_id(expr):
    return digest(['small-arithmetic-source/v1',expr])


def _wrong(value):
    return (value+1)%4


def _eq(expr,target,*,mirror=False):
    if target not in range(4):raise ValueError('SMALL_DOMAIN_COMPARISON_OUTSIDE_0_3')
    return arithmetic.operation('EQ',arithmetic.atom(target),copy.deepcopy(expr)) if mirror else \
           arithmetic.operation('EQ',copy.deepcopy(expr),arithmetic.atom(target))


def _evidence(record,grade,expr,split,group,projection,family,variant):
    if record.get('task')==arithmetic.VERSION:
        row=arithmetic.row(record['expression'],20)
    elif record.get('task')==bridge.VERSION:
        row={'id':digest(record),'input':record,'gold':bridge.evaluate(record)}
    else:
        row={'id':digest(record),'input':record,'gold':finite.evaluate(record)}
    row.update(answer_kind='evidence',family=f'small-domain:{grade}',
               course_meta={'grade':grade,'split':split,'source_split':split,
                            'triplet_id':digest([VERSION,grade,_source_id(expr),variant]),
                            'semantic_source_id':_source_id(expr),
                            'bridge_family':family,'projection':projection,
                            'tranche':group,'small_domain':True})
    return row


def _arithmetic_row(expr,grade,split,group,variant):
    value=arithmetic.evaluate(expr)
    record={'task':arithmetic.VERSION,'expression':copy.deepcopy(expr)}
    return {'id':digest(record),'input':record,'gold':value,
            'answer_kind':'numeric','family':'small-domain:basic-arithmetic',
            'course_meta':{'grade':grade,'split':split,'source_split':split,
                           'triplet_id':digest([VERSION,'arithmetic',_source_id(expr),variant]),
                           'semantic_source_id':_source_id(expr),
                           'bridge_family':'basic_arithmetic',
                           'projection':'standalone_numeric',
                           'tranche':group,'small_domain':True}}


def triplet(grade,source,graph,rng,*,split='train',mode=0,group='current'):
    """Atomic relation, independent relation and composite, with both labels."""
    if grade not in GRADES or SOURCE_OWNER.get(source)!=split or mode not in (0,1):
        raise ValueError('SMALL_DOMAIN_WRONG_GRADE_OR_SPLIT')
    expr=expression(source)
    value=arithmetic.evaluate(expr)
    wrong=_wrong(value)
    positive=_eq(expr,value)
    negative=_eq(expr,wrong)
    if grade in ('B01','B02'):
        # Symmetry and alternate candidate are elementary equality only.
        records=(positive,negative,_eq(expr,value,mirror=True)) if mode==0 else \
                (positive,negative,_eq(expr,wrong,mirror=True))
        family='equality'
        projections=('standalone_relation','standalone_relation','standalone_relation')
    elif grade=='B03':
        # LT and LE only; even the maximum 3 needs no out-of-range 4.
        true_a=arithmetic.operation('LE',copy.deepcopy(expr),arithmetic.atom(value))
        true_b=arithmetic.operation('LE',arithmetic.atom(value),copy.deepcopy(expr))
        false_a=arithmetic.operation('LT',copy.deepcopy(expr),arithmetic.atom(value))
        false_b=arithmetic.operation('LT',arithmetic.atom(3),copy.deepcopy(expr))
        records=(true_a,false_a,true_b) if mode==0 else (false_a,false_b,true_a)
        family='ordering'
        projections=('standalone_relation',)*3
    elif grade in ('B04','B05'):
        family='iff_math' if grade=='B04' else 'implies_math'
        rewritten=arithmetic.operation('ADD',copy.deepcopy(expr),arithmetic.atom(0))
        consequent=_eq(rewritten,value if mode==0 else wrong)
        logical=bridge.record(expr,value,'IFF' if grade=='B04' else 'IMPLIES',
                              {'kind':'math','record':consequent})
        records=(positive,negative,logical)
        projections=('standalone_arithmetic','standalone_arithmetic',
                     'cross_domain_composition')
    else:
        family='membership' if grade=='B06' else 'subset'
        # Independently own set projections by the original set-record digest,
        # preventing an identical finite world from leaking across splits.
        truth=(mode==1)
        for _ in range(500):
            set_record=bridge._set_record(expr,family,rng,truth)
            if bridge.split_of(set_record)==split:
                break
        else:
            raise ValueError('SMALL_DOMAIN_SET_SOURCE_PARTITION_EXHAUSTED')
        left_candidate=wrong
        composed=bridge.record(expr,left_candidate,'IFF',
                               {'kind':'set','record':set_record})
        records=(positive if mode==0 else negative,set_record,composed)
        projections=('standalone_arithmetic','standalone_relation',
                     'cross_domain_composition')
    result=[]
    for record,projection in zip(records,projections):
        if record.get('task') in (None,arithmetic.VERSION) and \
                record.get('kind')=='op':
            record={'task':arithmetic.VERSION,'expression':record}
        result.append(_evidence(record,grade,expr,split,group,projection,family,mode))
    if (len({r['id'] for r in result})!=3 or
            {r['gold'] for r in result}!={'TRUE','FALSE'}):
        raise ValueError('SMALL_DOMAIN_CONTRAST_OR_IDENTITY_FAILURE')
    return result


def _literal_values(node):
    if isinstance(node,dict):
        if node.get('kind')=='number':
            yield node['value']
        for value in node.values():
            yield from _literal_values(value)
    elif isinstance(node,(list,tuple)):
        for part in node:yield from _literal_values(part)


def _math_sources(record):
    if record.get('task')==arithmetic.VERSION:
        expr=record['expression']
        if expr.get('name') in ('EQ','LT','LE'):
            operands=expr['args']
            return [operand for operand in operands if operand.get('kind')=='op'
                    and operand.get('name') in ('ADD','SUB')]
        return [expr]
    if record.get('task')==bridge.VERSION:
        return [record['math_expression']]
    return []


def validate_rows(rows,graph,*,split,expected=None):
    if not rows or split not in SOURCES:
        raise ValueError('SMALL_DOMAIN_INVALID_PANEL')
    if expected is not None and len(rows)!=expected:
        raise ValueError('SMALL_DOMAIN_WRONG_ROW_COUNT')
    mapping={token:i for i,token in enumerate(graph['tokens'])}
    seen=set()
    for row in rows:
        if row['id'] in seen:raise ValueError('SMALL_DOMAIN_DUPLICATE_ROW')
        seen.add(row['id'])
        meta=row.get('course_meta',{})
        if meta.get('tranche')=='random_old':
            if row.get('answer_kind')!='evidence':
                raise ValueError('SMALL_DOMAIN_HISTORICAL_REHEARSAL_MUST_BE_EVIDENCE')
            lessons.valid_rows([row],graph)
            continue
        if not meta.get('small_domain') or meta.get('split')!=split:
            raise ValueError('SMALL_DOMAIN_SOURCE_SPLIT_LEAK')
        if (any(type(n)!=int or n<0 or n>MAX_NUM for n in _literal_values(row['input'])) or
                (row['answer_kind']=='numeric' and
                 (type(row['gold'])!=int or not 0<=row['gold']<=MAX_NUM))):
            raise ValueError('SMALL_DOMAIN_NUMERIC_LITERAL_OUT_OF_RANGE')
        record=row['input']
        if record.get('task')==arithmetic.VERSION:
            expr=record['expression']
            arithmetic.verify(expr)
            actual=arithmetic.evaluate(expr)
            gold=actual if type(actual)==int else 'TRUE' if actual else 'FALSE'
            encoded=arithmetic.encode(record,mapping)
            if meta['semantic_source_id'] not in {
                _source_id(expression(s)) for s in SOURCES[split]}:
                raise ValueError('SMALL_DOMAIN_UNKNOWN_ARITHMETIC_OWNER')
        elif record.get('task')==bridge.VERSION:
            gold=bridge.evaluate(record)
            encoded=bridge.encode(record,graph)
            source=_owner(record['math_expression'])
            if SOURCE_OWNER[source]!=split:
                raise ValueError('SMALL_DOMAIN_COMPOSITE_SOURCE_LEAK')
        else:
            gold=finite.evaluate(record)
            if gold!=finite.independent_evaluate(record) or bridge.split_of(record)!=split:
                raise ValueError('SMALL_DOMAIN_STANDALONE_SET_LEAK')
            encoded=lessons.encode(row,graph)
        if row['gold']!=gold or not encoded or len(encoded)>96:
            raise ValueError('SMALL_DOMAIN_GOLD_OR_ENCODING_INVALID')
    return True


def compile_batch(grade,library,graph,rng,*,method='standard'):
    if grade not in GRADES or method not in ('standard','structural_equivalence',
                                             'minimal_counterfactual'):
        raise ValueError('SMALL_DOMAIN_INVALID_INSTRUCTION')
    # Materialize the four exact replay exemplars FIRST. A randomly generated
    # finite-set record can alias a later fixed set question even if its
    # arithmetic source differs; ordinary lessons must yield to the replay.
    sources=[source for source in SOURCES['train'] if source not in REPLAY_MODES]
    rng.shuffle(sources)
    if method=='structural_equivalence':
        sources.sort(key=lambda src:src[0]!='ADD')
    elif method=='minimal_counterfactual':
        sources.sort(key=lambda src:(abs(src[1]-src[2]),src[0]))
    sources=list(REPLAY_SOURCES)+sources
    result=[];seen=set()
    for i,source in enumerate(sources):
        for trial in range(60):
            replay=source in REPLAY_MODES
            proposal=triplet(grade,source,graph,
                             _replay_rng(grade,source) if replay else rng,
                             mode=REPLAY_MODES[source] if replay else i%2,
                             group='current')
            if not any(row['id'] in seen for row in proposal):break
        else:
            raise ValueError('SMALL_DOMAIN_EXHAUSTED_CONTRAST_IDENTITY')
        seen.update(row['id'] for row in proposal)
        result.extend(proposal)
    # Six direct-number arithmetic examples, without an equality/logic/set
    # wrapper. All supervised among existing embeddings for number tokens 0..3.
    direct=list(REPLAY_SOURCES)+[
        source for source in sources if source not in REPLAY_MODES
    ][:NUMERIC_ROWS_PER_B_BATCH-len(REPLAY_SOURCES)]
    for source in direct:
        row=_arithmetic_row(expression(source),grade,'train','current',0)
        if row['id'] in seen:raise ValueError('SMALL_DOMAIN_DUPLICATE_DIRECT_NUMBER')
        result.append(row);seen.add(row['id'])
    for index in range(2):
        origin=inherited.HISTORICAL_REHEARSAL[(GRADES.index(grade)*3+index+
                  rng.randrange(len(inherited.HISTORICAL_REHEARSAL)))%
                  len(inherited.HISTORICAL_REHEARSAL)]
        for _ in range(300):
            rows=numeric.earlier_triplet(library,graph,rng,(f'G{origin:02d}',),depth=2)
            row_ids=[row['id'] for row in rows]
            if len(set(row_ids))!=len(row_ids) or any(
                    row_id in seen for row_id in row_ids) or not all(
                    primitive.admissible_rehearsal(row) for row in rows):
                continue
            for row in rows:
                row['answer_kind']='evidence'
                row['course_meta']['retention']=True
                row['course_meta']['tranche']='random_old'
            result.extend(rows);seen.update(row['id'] for row in rows)
            break
        else:raise ValueError('SMALL_DOMAIN_HISTORICAL_REHEARSAL_EXHAUSTED')
    counts={'current':42,'random_old':6,'preview':0}
    validate_rows(result,graph,split='train',expected=48)
    if sum(row['answer_kind']=='numeric' for row in result)!=6:
        raise ValueError('SMALL_DOMAIN_NOT_SIX_DIRECT_NUMERICS')
    return result,counts


def panel(grade,graph,*,fold,seed=20261013):
    """Two TRAINING REPLAY slices, not independent confirmation exams."""
    if grade not in GRADES or fold not in ('primary','confirm'):
        raise ValueError('SMALL_DOMAIN_UNKNOWN_FOLD')
    sources=REPLAY_SOURCES[:2] if fold=='primary' else REPLAY_SOURCES[2:]
    rows=[];seen=set()
    for source in sources:
        attempt=triplet(grade,source,graph,_replay_rng(grade,source),
                        split='train',mode=REPLAY_MODES[source],group='replay')
        if any(row['id'] in seen for row in attempt):
            raise ValueError('SMALL_DOMAIN_REPLAY_DUPLICATE')
        rows.extend(attempt);seen.update(row['id'] for row in attempt)
    validate_rows(rows,graph,split='train',expected=PANEL_ROWS)
    if sum(row['gold']=='TRUE' for row in rows)!=3:
        raise ValueError('SMALL_DOMAIN_PANEL_BALANCE_DRIFT')
    return rows


def numeric_panel(graph,*,fold):
    """Four exact direct-number questions supervised each B optimizer update."""
    if fold not in ('primary','confirm'):
        raise ValueError('SMALL_DOMAIN_UNKNOWN_FOLD')
    sources=REPLAY_SOURCES[:2] if fold=='primary' else REPLAY_SOURCES[2:]
    rows=[_arithmetic_row(expression(source),'NUMERIC','train','replay',0)
          for source in sources]
    validate_rows(rows,graph,split='train',expected=2)
    return rows
