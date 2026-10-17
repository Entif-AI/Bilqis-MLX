"""Current taught curriculum scores from saved selected-candidate receipts.

This has no dependencies on a neural runner and never reads checkpoints.
The latest observed focused result is not silently represented as a new
evaluation of the present student at a later optimizer step.
"""

FOCUSED={'G11':'MEMBER', 'G20':'ARITHMETIC_EQ', 'G22':'NESTED_COMPOSITION'}


def focused_rows(state, *, cutoff_visit=None):
    """Return latest retained first-rung result per grade and its provenance."""
    latest={}
    # Grade ledger links a retained student to its selected trial. Exclude
    # rejected attempts and results from grades not yet committed.
    selected={(r['grade'],r['candidate_step'],r['attempt']):r
              for r in state.get('candidate_ledger',[])
              if r.get('selected') and r.get('grade') in FOCUSED and
              isinstance(r.get('direct_path_after'),dict)}
    for visit in state.get('grade_ledger',[]):
        grade=visit.get('grade')
        if grade not in FOCUSED or not visit.get('updates'):continue
        if cutoff_visit is not None and visit['visit']>cutoff_visit:continue
        attempt=visit.get('accepted_attempt')
        key=(grade,visit.get('optimizer_step'),attempt)
        record=selected.get(key)
        if record is None:continue
        parts=record['direct_path_after']
        if not parts or any(not isinstance(part,dict) or
                            'correct' not in part or 'total' not in part
                            for part in parts.values()):
            continue
        correct=sum(part['correct'] for part in parts.values())
        total=sum(part['total'] for part in parts.values())
        if total<=0 or not 0<=correct<=total:continue
        latest[grade]={'grade':grade,'concept':FOCUSED[grade],
                       'correct':correct,'total':total,
                       'percent':round(correct*100/total,1),
                       'mastered':correct==total,
                       'optimizer_step':visit['optimizer_step'],
                       'visit':visit['visit'],
                       'assessment':'CURRENT_FIRST_RUNG_LAST_RETAINED'}
    return latest


def summary(records):
    return 'LAST-RETAINED FIRST RUNG (MIXED STEPS; NOT GRADUATION): '+ ' '.join(
        f'{grade} {records[grade]["correct"]}/{records[grade]["total"]}'
        for grade in sorted(FOCUSED) if grade in records)


def graduation_line(state):
    """Do not present personal-best or mixed-step success as a golden student."""
    step=state.get('optimizer_step')
    sha=state.get('checkpoint_sha256')
    screen=state.get('graduation_screen') or {}
    if (screen.get('optimizer_step')==step and
        screen.get('checkpoint_sha256')==sha and
        screen.get('failed_metric')):
        return (f'SAME-STEP GOLDEN GATE @ {step}: '
                f'{screen["failed_metric"]} {screen.get("correct")}/{screen.get("total")} '
                'NOT GOLDEN; full-exam totals are from an earlier step')
    receipt=state.get('mastery_completion') or {}
    if (receipt.get('optimizer_step')==step and
        receipt.get('checkpoint_sha256')==sha and
        isinstance(receipt.get('metrics'),dict)):
        metrics=receipt['metrics']
        passed=sum(type(v.get('correct')) is int and
                   type(v.get('total')) is int and v['correct']==v['total']
                   for v in metrics.values() if isinstance(v,dict))
        certified=(passed==len(metrics) and len(metrics)>0 and
                   state.get('last_run_status')=='ALL_CURRENT_METRICS_100_PERCENT')
        return (f'SAME-STEP CURRENT EXAM @ {step}: {passed}/{len(metrics)} '
                'capability groups perfect; '+
                ('GOLDEN FROZEN' if certified else 'NOT GOLDEN'))
    previous=receipt.get('optimizer_step')
    return (f'SAME-STEP GOLDEN GATE @ {step}: NOT ASSESSED; '
            f'last full exam step {previous or "-"}; NOT GOLDEN')


def advancement(records):
    """Display first-rung prerequisites, never imply v16 authorization."""
    complete=lambda grade:bool(records.get(grade,{}).get('mastered'))
    return ('NEW G23 '+('FIRST-RUNG ONLY' if complete('G11') else 'WAIT G11')+
            ' | G24 AFTER G23'+
            ' | G25 '+('FIRST-RUNG ONLY' if complete('G20') else 'WAIT G20')+
            ' | G26 '+('FIRST-RUNG ONLY' if complete('G20') and complete('G22')
                     else 'WAIT G20+G22')+
            ' | V16 CURRICULUM HOLD')
