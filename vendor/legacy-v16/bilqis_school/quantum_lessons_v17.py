"""Three semantic rungs for the six G12/G13/G14 mathematical families.

The incumbent teacher retains its complete policy and control of the
composition/focus mode, rehearsal, preview and all optimizer parameters.
Every staged pair changes the *target mathematical predicate*, never an
unrelated Boolean disjunct. This is a distinct, not-yet-trained curriculum.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy

from bilqis_development import data as development
from bilqis_development import kernel as semantic
from bilqis_micro import kernel as primitive
from . import g12_g13_g14_repair_v2 as previous
from . import lessons

GRADES=previous.GRADES
FAMILIES=previous.FAMILIES
RUNGS=('easy','medium','hard')
EASY_END=20
MEDIUM_END=42
UPDATES=64
ROWS=32


def rung(update_index,total_updates=UPDATES):
    if total_updates!=UPDATES or type(update_index) is not int or not 0<=update_index<UPDATES:
        raise ValueError('QUANTUM_INVALID_UPDATE_INDEX')
    return RUNGS[0 if update_index<EASY_END else 1 if update_index<MEDIUM_END else 2]


def _c(kind,name):
    return semantic.const(kind,name)


def _op(name,*args):
    return semantic.op(name,*args)


def _world(entities,sets,functions):
    return semantic.world(entities,base=primitive.world(entities),
                          sets=sets,functions=functions)


def _add_distractors(entities,sets,functions,rng,stage,depth,mode):
    if stage=='easy':
        return
    # Distractors add context without replacing the original witness. Keep
    # function inputs AND outputs unique, as the frozen inverse ABI requires.
    if stage=='hard' and mode!='composition':
        for name in ('K0','K1'):
            for entity in entities:
                if rng.random()<.3 and entity not in sets[name]:
                    sets[name].append(entity)
    for name in ('F0','F1'):
        limit=2 if stage=='medium' else 3 if depth<4 else 4
        while len(functions[name])<limit:
            inputs={a for a,b in functions[name]}
            outputs={b for a,b in functions[name]}
            eligible_in=[x for x in entities if x not in inputs]
            eligible_out=[x for x in entities if x not in outputs]
            if not eligible_in or not eligible_out or rng.random()<.35:
                break
            functions[name].append([rng.choice(eligible_in),rng.choice(eligible_out)])


def _case(family,stage,rng,x,y,z,sets,functions):
    if family=='set-intersection':
        sets['K0'].append(x)
        sets['K1'].append(x)
        target=(_op('MEMBER',_c('Entity',x),_c('Set','K0')) if stage=='easy'
                else _op('MEMBER',_c('Entity',x),
                         _op('INTERSECTION',_c('Set','K0'),_c('Set','K1'))))
        mutation=('set','K0',x) if stage=='easy' else ('set','K1',x)
    elif family=='set-difference':
        reverse=stage=='hard' and bool(rng.randrange(2))
        left,right=('K1','K0') if reverse else ('K0','K1')
        sets[left].append(x)
        target=(_op('MEMBER',_c('Entity',x),_c('Set',left)) if stage=='easy'
                else _op('MEMBER',_c('Entity',x),
                         _op('DIFFERENCE',_c('Set',left),_c('Set',right))))
        mutation=('set','remove',left,x) if stage=='easy' else ('set','add',right,x)
    elif family in ('function-domain','function-range','function-inverse'):
        functions['F0']=[[x,y]]
        if family=='function-inverse':
            target=_op('MAPS',_op('INVERSE',_c('Function','F0')),
                       _c('Entity',y),_c('Entity',x))
        elif stage=='easy':
            target=_op('MAPS',_c('Function','F0'),_c('Entity',x),_c('Entity',y))
        else:
            target=_op('MEMBER',_c('Entity',x if family=='function-domain' else y),
                       _op('DOMAIN' if family=='function-domain' else 'RANGE',
                           _c('Function','F0')))
        mutation=('function','F0',x,y)
    elif family=='function-composition':
        reverse=stage=='hard' and bool(rng.randrange(2))
        first,second=('F1','F0') if reverse else ('F0','F1')
        functions[first]=[[x,y]]
        functions[second]=[[y,z]]
        if stage=='easy':
            taught=first if bool(rng.randrange(2)) else second
            u,v=functions[taught][0]
            target=_op('MAPS',_c('Function',taught),_c('Entity',u),_c('Entity',v))
            mutation=('function',taught,u,v)
        else:
            target=_op('MAPS',_op('COMPOSITION',_c('Function',first),
                                  _c('Function',second)),
                       _c('Entity',x),_c('Entity',z))
            mutation=('function',first,x,y)
    else:
        raise ValueError('QUANTUM_UNSUPPORTED_FAMILY')
    return target,mutation


def _composed_query(family,mode,rng,x,y,target,sets,functions):
    if mode!='composition':
        return target
    # A complete, structurally honest composition-mode AST is still offered
    # whenever the incumbent teacher selected composition. Its auxiliary
    # predicate is a real independently defined fact with a *neutral* truth
    # value, so the target semantic contrast is not masked by a disjunct.
    if family.startswith('set-'):
        functions['F1']=[[x,x]]
        auxiliary_true=_op('MEMBER',_c('Entity',x),_op('DOMAIN',_c('Function','F1')))
        auxiliary_false=_op('MEMBER',_c('Entity',y),_op('RANGE',_c('Function','F1')))
    else:
        sets['K0']=[x]
        auxiliary_true=_op('MEMBER',_c('Entity',x),_c('Set','K0'))
        auxiliary_false=_op('MEMBER',_c('Entity',y),_c('Set','K0'))
    return (_op('AND',target,auxiliary_true) if bool(rng.randrange(2))
            else _op('OR',target,auxiliary_false))


def _opposite_world(positive,mutation):
    negative=deepcopy(positive)
    if mutation[0]=='function':
        negative['functions'][mutation[1]].remove([mutation[2],mutation[3]])
    elif len(mutation)==3:
        _,which,member=mutation
        negative['sets'][which].remove(member)
    elif mutation[1]=='remove':
        negative['sets'][mutation[2]].remove(mutation[3])
    else:
        negative['sets'][mutation[2]].append(mutation[3])
        negative['sets'][mutation[2]].sort()
    return negative


def _witness(family,stage,depth,mode,rng):
    size=2 if stage=='easy' else 3 if stage=='medium' else (5 if depth>=4 else 4)
    # Vary object identities even when the easy rung has only two objects.
    entities=sorted(rng.sample(list('ABCDE'),size))
    x,y=rng.sample(entities,2)
    z=rng.choice([v for v in entities if v not in (x,y)] or [x])
    sets={'K0':[],'K1':[]}
    functions={'F0':[],'F1':[]}
    target,mutation=_case(family,stage,rng,x,y,z,sets,functions)
    query=_composed_query(family,mode,rng,x,y,target,sets,functions)

    # The independent neutral condition is intentionally unchanged by the
    # counterfactual. Distractors may vary both operands and entity values.
    if family not in ('set-intersection','set-difference'):
        _add_distractors(entities,sets,functions,rng,stage,depth,mode)
    elif stage!='easy':
        for name in ('K0','K1'):
            for other in entities:
                if other!=x and rng.random()<.3:
                    sets[name].append(other)
    positive=_world(entities,sets,functions)
    negative=_opposite_world(positive,mutation)

    # This guard detects accidental distractor/auxiliary interference at the
    # *mathematical core*, not only at the complete answer label.
    for world,label in ((positive,'TRUE'),(negative,'FALSE')):
        core=semantic.evaluate(semantic.record(world,target))
        full=semantic.evaluate(semantic.record(world,query))
        if core!=label or full!=label:
            raise ValueError('QUANTUM_CORE_AND_GOLD_DIVERGED')
    return positive,negative,query


def _pair(family,stage,policy,rng,seen):
    mode='composition' if policy['contrast']>=.5 else 'focus'
    for _ in range(200):
        try:
            positive,negative,query=_witness(family,stage,policy['depth'],mode,rng)
            pair=[development.row(semantic.record(w,query),5,family)
                  for w in (positive,negative)]
        except ValueError as exc:
            # Finite context and missing injections are sampling constraints,
            # not grounds for accepting a semantically mislabeled example.
            if str(exc)=='QUANTUM_CORE_AND_GOLD_DIVERGED':
                raise
            continue
        if ({r['gold'] for r in pair}=={'TRUE','FALSE'} and
                len({r['id'] for r in pair})==2 and
                all(r['id'] not in seen for r in pair)):
            for row in pair:
                row['answer_kind']='evidence'
                row['course_meta']={'curriculum_role':'current','family':family,
                    'rung':stage,'teacher_mode':mode,'pair_kind':'CORE_FLIP',
                    'sibling':next(p['id'] for p in pair if p['id']!=row['id'])}
                seen.add(row['id'])
            return pair
    raise ValueError('QUANTUM_CANNOT_GENERATE_DISTINCT_SEMANTIC_PAIR:'+family+':'+stage)


def batch(grade,graph,policy,rng,*,update_index,total_updates=UPDATES,excluded=None):
    if grade not in GRADES:
        raise ValueError('QUANTUM_UNKNOWN_GRADE')
    stage=rung(update_index,total_updates)
    old,preview=policy['old'],policy['preview']
    current_count=ROWS-old-preview
    if (type(old) is not int or type(preview) is not int or
            not 0<=old<=20 or not 0<=preview<=4 or
            current_count<2*len(FAMILIES[grade])):
        raise ValueError('QUANTUM_UNSUPPORTED_TEACHER_ALLOCATION')
    seen=set(previous._excluded_exam_ids() if excluded is None else excluded)
    current=[]
    families=list(FAMILIES[grade])
    for family in families:
        current.extend(_pair(family,stage,policy,rng,seen))
    turn=0
    while len(current)+1<current_count:
        current.extend(_pair(families[turn%len(families)],stage,policy,rng,seen))
        turn+=1
    if len(current)<current_count:
        # An odd allocation keeps the target truth balanced across updates,
        # instead of coupling a family permanently to one answer class.
        family=families[turn%len(families)]
        supplement=_pair(family,stage,policy,rng,seen)
        current.append(supplement[rng.randrange(2)])
    mode='composition' if policy['contrast']>=.5 else 'focus'
    varied=policy['depth']>=4
    prior=previous._rehearse(grade,old,mode,rng,seen,varied)
    future=previous._preview(grade,preview,rng,seen,varied)
    rows=current+prior+future
    rng.shuffle(rows)
    if len(rows)!=ROWS or len({r['id'] for r in rows})!=ROWS:
        raise ValueError('QUANTUM_BATCH_SIZE_OR_ID_DRIFT')
    lessons.valid_rows(rows,graph)
    for family in families:
        if {r['gold'] for r in current if r['course_meta']['family']==family}!={'TRUE','FALSE'}:
            raise ValueError('QUANTUM_MISSING_POLARITY:'+family)
    return rows,{'rung':stage,'current':len(current),'old':old,'preview':preview,
                 'teacher_mode':mode,'teacher_depth':policy['depth'],
                 'answers':dict(Counter(r['gold'] for r in current))}
