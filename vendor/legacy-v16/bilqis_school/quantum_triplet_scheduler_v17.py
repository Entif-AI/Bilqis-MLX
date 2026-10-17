"""Globally weakest-three, then the next weakest *remaining* grade trio.

Keep the proven v16 lock/whole-lesson/retest state machine. This small
versioned extension only adds an exhaustive sweep cursor: after a trio is
retested, those grades yield their place to the next weakest unvisited
grades. The last two of the 29-grade program are never stranded.
"""
from __future__ import annotations

from fractions import Fraction

from . import triplet_scheduler_v16 as old

SCHEMA='bilqis.triplets.global-remaining/v17'


def new_state(eligible,rubric):
    # A stall/soup review before the final unvisited grade would defeat the
    # operator's explicit next-three-remaining contract. Keep the incumbent
    # soup behavior, but defer its first no-gain opportunity until every
    # grade has had one lesson this sweep.
    sweepsize=(len(eligible)+old.ROUND_SIZE-1)//old.ROUND_SIZE
    state=old.new_state(eligible,rubric,stall_rounds=max(old.STALL_ROUNDS,sweepsize))
    state.update(queue_schema=SCHEMA,remaining_program=list(eligible),
                 sweep=1)
    return state


def _verify(state,rubric):
    old._verify_state(state,rubric)
    eligible=state['eligible_program']
    rest=state.get('remaining_program')
    if (state.get('queue_schema')!=SCHEMA or
            type(state.get('sweep')) is not int or state['sweep']<1 or
            not isinstance(rest,list) or
            not rest or len(rest)!=len(set(rest)) or
            not set(rest)<=set(eligible)):
        raise ValueError('QUANTUM_TRIPLET_CURSOR_DRIFT')


def _rank(totals,program,eligible):
    positions={grade:i for i,grade in enumerate(eligible)}
    return sorted(program,key=lambda grade: (
        Fraction(totals[grade]['correct'],totals[grade]['total']),
        positions[grade]))


def begin_cycle(state,snapshot,rubric):
    _verify(state,rubric)
    # First run the original exhaustive same-checkpoint authorization gate.
    totals=old._check_snapshot(snapshot,rubric,state['eligible_program'])
    updated=old.begin_cycle(state,snapshot,rubric)
    remaining=list(state['remaining_program'])
    selected=_rank(totals,remaining,state['eligible_program'])[:old.ROUND_SIZE]
    if len(selected)<old.ROUND_SIZE:
        earlier=[grade for grade in state['eligible_program'] if grade not in remaining]
        selected+=_rank(totals,earlier,state['eligible_program'])[
            :old.ROUND_SIZE-len(selected)]
    active=updated['active']
    active['grades']=selected
    active['before']={grade:totals[grade] for grade in selected}
    active['locked_probe_keys']={grade:sorted(
        key for key in rubric if key.startswith(grade+':')) for grade in selected}
    active['locked_question_hashes']={key:rubric[key]['questions_sha256']
       for grade in selected for key in active['locked_probe_keys'][grade]
       if 'questions_sha256' in rubric[key]}
    active['sweep']=state['sweep']
    active['remaining_before']=remaining
    if len(selected)!=old.ROUND_SIZE or len(set(selected))!=old.ROUND_SIZE:
        raise ValueError('QUANTUM_TRIPLET_THREE_DISTINCT_MISSING')
    return updated


def finish_retest(state,snapshot,rubric,*,locked_retest=None):
    _verify(state,rubric)
    completed=old.finish_retest(state,snapshot,rubric,locked_retest=locked_retest)
    selected=state['active']['grades']
    rest=[grade for grade in state['remaining_program'] if grade not in selected]
    if rest:
        completed['remaining_program']=rest
    else:
        completed['remaining_program']=list(state['eligible_program'])
        completed['sweep']=state['sweep']+1
    completed['history'][-1]['sweep']=state['sweep']
    completed['history'][-1]['next_remaining']=len(rest)
    return completed
