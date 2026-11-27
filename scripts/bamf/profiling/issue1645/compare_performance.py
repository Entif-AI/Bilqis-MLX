"""Derive measured rates and causal limitations from unchanged R2-R4 receipts."""
from collections import Counter, defaultdict
import argparse, hashlib, json, math
from pathlib import Path
from statistics import median

def read(p):
    raw=p.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()

def summary(vals):
    vals=sorted(vals)
    return {'n':len(vals),'p50':median(vals) if vals else None,'p95':vals[math.ceil(.95*len(vals))-1] if vals else None}

def analyze_arm(d):
    t,th=read(d/'training.json')
    ds,dh=read(d/'deliveries.json')
    obs,oh=read(d/'run/trainer-observed.json')
    observer,orh=read(d/'observer/receipt.json')
    o=t['operator']; outcomes=t['outcomes']
    steps=sum(x['attempted_steps'] for x in outcomes)
    assert steps==len(ds)==o['pipeline_submitted_steps']
    retained=sum(x['retained_steps'] for x in outcomes)
    assert len(outcomes)==o['accepted']+o['rejected']
    by_attempt=defaultdict(list)
    for row in ds:
        by_attempt[row['attempt_id']].append(row)
    assert set(by_attempt)=={x['attempt_id'] for x in outcomes}
    reasons=Counter(x['decision'].get('reason') for x in outcomes)
    v=[x for x in obs['visits'] if x['outcome'] in ('REJECTED','ACCEPTED')]
    scopes=Counter()
    for x in outcomes:
        for cap,before,after,total in x['scores']:
            if cap!=x['teacher_visit']['capability_id'] and after<before:
                scopes[cap]+=1
    geometry=Counter(tuple(sorted(x['roles'].items())) for x in ds)
    scores=Counter(x['teacher_visit']['capability_id'] for x in outcomes)
    selected_distill=sum(float(x['selected_policy'].get('distill',0) or 0)>0 for x in outcomes)
    # Count only explicit timed measurements. Terminal decisions are not eval calls.
    evals=[x['retention_wall_seconds'] for x in v if x.get('retention_wall_seconds') is not None]
    memory=t['memory_low_water']
    return {'training_sha256':th,'delivery_sha256':dh,'observer_data_sha256':oh,'observer_receipt_sha256':orh,
        'operator_seconds':o['elapsed_seconds'],'wall_seconds':t['seconds'],'attempted_steps':steps,'retained_steps':retained,
        'attempted_steps_per_operator_minute':60*steps/o['elapsed_seconds'],'attempted_steps_per_arm_minute':60*steps/t['seconds'],
        'retained_steps_per_operator_minute':60*retained/o['elapsed_seconds'],
        'terminal_candidate_decisions':len(outcomes),'terminal_candidate_decisions_per_operator_minute':60*len(outcomes)/o['elapsed_seconds'],
        'neutral_skips':len(t['skipped']),'reasons':dict(reasons),'selected_capability_counts':dict(scores),
        'protected_score_drop_observations':dict(scopes),
        'delivered_geometry':[{'roles':dict(k),'steps':n} for k,n in geometry.items()],
        'selected_nonzero_distill_visits':selected_distill,'actual_guidance_steps':sum(bool(x['guidance']) for x in ds),
        'delivered_weakness_targets':sum(x['realized_action']['features'].get('weakness_targets_delivered',0) for x in outcomes),
        'completed_visit_duration_seconds':summary([x['elapsed_ms']/1000 for x in v]),
        'assessment_duration_seconds':summary(evals),'actual_candidate_evaluation_calls_per_minute':None,
        'visit_timing_scope':'terminal trainer ring, not complete run',
        'memory':{'sample_count':len(memory),'max_low_water_footprint':max(x['physical_footprint'] for x in memory),
            'max_low_water_rss':max(x['rss'] for x in memory),'peak_mlx_bytes':max(x['peak'] for x in memory),
            'final_discarded_candidates_alive':memory[-1]['discarded_candidates_alive'],
            'final_issued_evaluations_alive':memory[-1]['issued_evaluations_alive'],
            'final_forward_records':memory[-1]['forward_records'],'final_tokens':memory[-1]['tokens'],
            'max_trainer_ring_rss':max((x['peak_rss_bytes'] for x in v if x.get('peak_rss_bytes') is not None),default=None),
            'observer_peak_tree_rss_sum_kib':observer.get('peak_observer_tree_rss_sum_kib'),'swap_bytes_attributable':None},
        'observer':{'failure':observer.get('failure'),'observed_training_proven':observer.get('observed_training_proven')}}

def analyze(root, manual_receipt):
    result = {name: analyze_arm(d) for name, d in (
        ("R2", root/"control"), ("R3", root/"r3/treatment"),
        ("R4", root/"r4/treatment"))}
    comparisons={}
    for name in ('r3','r4'):
        c,ch=read(root/name/'comparison.json')
        comparisons[name]={'sha256':ch,'qualification':c['qualification'],'limitations':c['comparison_limitations'],'arms':{}}
        for arm,a in c['arms'].items():
            b,z=a['independent_exam_before'],a['independent_exam_after']
            assert b['cohort_sha256']==z['cohort_sha256']
            comparisons[name]['arms'][arm]={'correct_before':b['correct'],'correct_after':z['correct'],'coverage':b['total'],'expected_coverage':72,'gain_per_wall_minute':a['gain_per_minute'],'retained_steps':a['retained_steps'],'manifest_before':b['manifest_sha256'],'manifest_after':z['manifest_sha256']}
    manual,mh=read(manual_receipt)
    return {'arms':result,'comparisons':comparisons,'manual':{'sha256':mh,'attempted_steps_per_minute':manual['attempted_steps_per_minute'],'retained_steps_per_minute':manual['retained_steps_per_minute'],'terminal_rejection_events_per_minute':60*manual['authenticated_rejections']/manual['stop']['elapsed_seconds'],'distinct_visit_ids':manual['authenticated_rejections']-manual['duplicate_visit_ids'],'visit_seconds':manual['visit_seconds'],'assessment_seconds':manual['assessment_seconds'],'actual_candidate_evaluation_calls_per_minute':None,'peak_rss_bytes':manual['peak_rss_bytes'],'attributable_swap_bytes':None,'training_executable_identity':None},'limitations':['No matched observer-free arm.','Full assessment-only timings and actual evaluation call counts not present.','Raw score changes do not identify optimizer-level causal interference.','Memory snapshots are not process-attributed swap measurements.','Manual stop suffix lacks explicit start and actual training executable identity.']}
if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--manual-receipt', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.root, args.manual_receipt), indent=2))
