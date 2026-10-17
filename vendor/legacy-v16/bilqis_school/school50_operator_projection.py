"""Read-only v16 *data* projection into the ONE existing School50 dashboard.

This owns no terminal layout or neural training. The renderer, columns,
score arithmetic, event vocabulary and watcher all remain shared across
revisions. Missing metrics are displayed as missing, not reconstructed from
historical G24 panels or independently optimized micro-champions.
"""
from __future__ import annotations

from pathlib import Path

from .spiral_dashboard import Dashboard


def _candidate(record, totals, reason=None):
    before=record.get('current_before') or {}
    after=record.get('current_after') or {}
    def measure(values):
        return {'correct':sum(values.values()),
                'questions':sum(totals.get(k,0) for k in values),
                'by_family':{k:{'correct':c,'questions':totals.get(k,0)}
                             for k,c in values.items()}}
    return {
        'grade':record.get('grade','?'), 'attempt':record.get('attempt',0),
        'policy_id':record.get('policy_id','-'),
        'bridge_before':measure(before),'bridge_after':measure(after),
        'reward':record.get('teacher_credit'),
        'loss_last':{'objective':record.get('last_loss')},
        'decision':'SELECT' if record.get('selected') else 'REJECT',
        'reason':reason or 'CURRENT RUBRIC; FP32+OWN ADAMW',
    }


def _repair_reason(record, winner):
    """Explain the saved best-positive-gain gate, without changing the decision."""
    gain=record.get('gain')
    if type(gain) is not int:
        return 'NET GAIN UNRECORDED'
    before=record.get('current_before') or {}
    after=record.get('current_after') or {}
    down=sum(after[key]<value for key,value in before.items()
             if key in after)
    if record.get('selected'):
        decision=f'BEST NET {gain:+d}'
    elif gain<=0:
        decision=f'NET {gain:+d}'
    elif winner is None:
        return f'GAIN {gain:+d}; WINNER UNRECORDED'
    elif winner.get('gain',0)>gain:
        decision=f'T{winner["attempt"]} {winner["gain"]:+d} > {gain:+d}'
    elif winner.get('gain')==gain:
        winning=winner.get('current_after') or {}
        winning_rank=tuple(winning[k] for k in sorted(winning))
        candidate_rank=tuple(after[k] for k in sorted(after))
        decision=(f'T{winner["attempt"]} WON FAMILY TIE {gain:+d}'
                  if winning_rank>candidate_rank else
                  f'T{winner["attempt"]} EARLIER EQUAL {gain:+d}')
    else:
        return f'GAIN {gain:+d}; REASON UNRESOLVED'
    return f'{decision}; {down} FAMILY DOWN'


def _repair_reasons(state):
    """Bind each attempt to the winner of its own *completed grade visit*.

    Multiple visits can share the same grade and parent step after no-gain
    rounds. Neither those fields nor the last 30 visible attempts identify
    the visit uniquely, so honor the durable grade ledger's attempt counts.
    """
    if state.get('schema') not in (
        'bilqis.three-grade-repair.native-adamw/v2',
        'bilqis.three-grade-repair.native-adamw/v2-r1',
        'bilqis.quantum-triplets.native-adamw/v17'):
        return {}
    records=state.get('candidate_ledger') or []
    reasons={}
    offset=0
    for visit in state.get('grade_ledger') or []:
        count=visit.get('attempts')
        if type(count) is not int or count<=0 or offset+count>len(records):
            break
        group=records[offset:offset+count]
        if (any(r.get('grade')!=visit.get('grade') for r in group) or
                [r.get('attempt') for r in group]!=list(range(1,count+1))):
            break
        winners=[r for r in group if r.get('selected')]
        winner=winners[0] if len(winners)==1 else None
        for index,record in enumerate(group,offset):
            reasons[index]=_repair_reason(record,winner)
        offset+=count
    return reasons


def _project_sweep(dashboard,state):
    if state['triplets'].get('queue_schema')!='bilqis.triplets.global-remaining/v17':
        return
    queue=state['triplets']
    dashboard.push('system',{'kind':'GLOBAL SWEEP',
        'detail':f'SWEEP {queue["sweep"]}; {len(queue["remaining_program"])} '
                 'grades remain to be selected in this sweep; '
                 'ranked on full same-step 1150-question source'},redraw=False)


def populate(dashboard, run_dir, state):
    """Rebuild from canonical durable receipts, never edited by the viewer."""
    if state.get('mode')!='--triplets':
        raise ValueError('SCHOOL50_TRIPLETS_PROJECTION_REQUIRES_CURRENT_RUN')
    active=state['triplets'].get('active') or {}
    queue=active.get('grades') or []
    next_grade=(queue[active['next_index']]
                if active.get('next_index',0)<len(queue) else '-')
    dashboard.state={
        'phase':state['triplets']['phase'], 'next':next_grade,
        'prefix':state['triplets']['cycles_completed']+1,
        'failures':'-', 'max_failures':'-',
        'step':state['optimizer_step'], 'visits':state['visits'],
        'teacher':(state.get('teacher') or {}).get('events','-'),
        'stop':state.get('last_run_status','-')}
    dashboard.attach_school50(Path(run_dir),state=state,
                              cutoff_visit=state.get('visits',0))
    if dashboard.progress:
        available=dashboard.progress.current
        latest={row['grade']:row for row in state.get('grade_ledger',[])}
        for grade in dashboard.grade_program:
            prior=latest.get(grade)
            score=available.get(grade[0],{}).get(grade)
            dashboard.push('grade',{
                'grade_visit':prior['visit'] if prior else '-',
                'grade':grade,
                'step':(dashboard.progress.observed_steps.get(grade,'-')),
                'eligible':prior.get('attempts',0) if prior else '-',
                'selected':prior['accepted'] if prior else False,
                'prefix':state['triplets']['cycles_completed']+1,
                'outcome':('RETAINED' if prior['accepted'] else 'NOT RETAINED')
                           if prior else 'CURRENT BASELINE',
                'accuracy':100*score if score is not None else None},redraw=False)
        totals=dashboard.progress.total_by_metric
        all_candidates=state.get('candidate_ledger',[])
        candidate_reasons=_repair_reasons(state)
        candidates=all_candidates[-30:]
        first=len(all_candidates)-len(candidates)
        for index,record in enumerate(candidates,first):
            dashboard.push('candidate',_candidate(
                record,totals,reason=candidate_reasons.get(index)),redraw=False)
        if not candidates:
            # Show the established empty instrument panels instead of making
            # categories vanish on a fresh student. These are labels, NOT data.
            dashboard.push('candidate',{'grade':'-','attempt':'-',
                'decision':'WAITING','reason':'NO CANDIDATE EVIDENCE YET'},
                redraw=False)
        if not dashboard.rows['BRIDGE FAMILIES']:
            dashboard.rows['BRIDGE FAMILIES'].append({
                'grade':'-','attempt':'-','family':'WAITING FOR SOURCE METRICS',
                'before':'-','after':'-','gain':'-'})
    else:
        dashboard.push('system',{'kind':'SCORES UNAVAILABLE',
            'detail':'No verified current-source rubric snapshot in this run'},redraw=False)
    if queue:
        detail=f'{" -> ".join(queue)}; NEXT {next_grade}; '
        detail+=f'locked until all 3 complete + explicit same-trio retest'
    else:
        detail=f'{state["triplets"]["phase"]}; full current scores before reselection'
    dashboard.push('system',{'kind':'TRIPLET QUEUE','detail':detail},redraw=False)
    _project_sweep(dashboard,state)
    dashboard.push('system',{'kind':'CURRENT SOURCE',
        'detail':'29 grades; G11/18/20 repaired; N=B01 numeric 12/1150 source; no G24 qualification'},redraw=False)
    if state['triplets']['history']:
        latest=state['triplets']['history'][-1]
        dashboard.push('system',{'kind':'LAST RETEST',
            'detail':(' '.join(f'{g}:{v["correct"]}/{v["total"]}'
                             for g,v in latest.get('after',{}).items())
                      if 'after' in latest else
                      latest.get('kind','SOUP REVIEW'))},redraw=False)
    if state.get('phase')=='GOLDEN_FROZEN':
        dashboard.mode='GOLDEN FROZEN'
    elif state.get('last_run_status')=='STALLED_AWAITING_OPERATOR_REVIEW':
        dashboard.mode='OPERATOR REVIEW'
    return dashboard


def create(run_dir,state,*,stream,title='BILQIS / SCHOOL50 V16 RUN-LOCAL'):
    dashboard=Dashboard(stream=stream,redraw=False,title=title)
    dashboard.log_hint='read-only current-source receipts'
    return populate(dashboard,run_dir,state)
