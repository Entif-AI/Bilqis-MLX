"""Bounded host-only source inventory, not an issued or certified examination."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys
from bilqis_mlx.control_plane.native_custody import authenticated_history, _read_bound_json
from bilqis_mlx.runtime.source_execution import SourceExecutionContext
from bilqis_mlx.source_adapters.school import live_source_registry
from bilqis_mlx.factory.live_answers import live_answer_registry
from bilqis_mlx.factory.assessment import assessment_scope_contract
from bilqis_mlx.paths import LEGACY_SOURCE

def digest(raw):
    return sha256(raw).hexdigest()

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),default=str).encode()

def exposure_key(row, gold):
    # Exact historical witness key encoding; never change the key to create novelty.
    return digest(json.dumps([row.get('capability'),row.get('tokens'),gold,row.get('answer_kind')],sort_keys=True,default=str).encode())

def semantic_key(row):
    return digest(canonical([row['capability'],row['tokens'],row['answer_kind']]))

def balanced(rows, quota=6):
    strata={gold:[] for gold in ('TRUE','FALSE')}
    for k,entry in sorted(rows.items()):
        strata[entry['row']['gold']].append(entry)
    n=min(quota, *(len(v) for v in strata.values()))
    return [x for gold in strata for x in strata[gold][:n]]

def historical_exposures(root):
    exclusions=set()
    inputs={}
    for source in (root/'control',root/'r3/treatment',root/'r4/treatment'):
        path=source/'deliveries.json'
        raw=path.read_bytes()
        inputs[str(path.relative_to(root))]=digest(raw)
        exclusions.update(k for delivery in json.loads(raw) for k in delivery['row_keys'])
    return exclusions, inputs


def census(context, caps, c, exclusions):
    report={}
    prospective=[]
    retrospective=[]
    draws=256
    for i,cap in enumerate(caps):
        pool={}
        for j in range(draws):
            seed=c['exam_seed']+i*draws+j
            for row in context.draw_rows(seed=seed,capability=cap,each=c['exam_each']):
                assert row['gold'] in ('TRUE','FALSE') and row['capability']==cap
                k=semantic_key(row)
                if k in pool:
                    assert pool[k]['row']['gold']==row['gold'], 'Conflicting label for same input'
                    continue
                pool[k]={'semantic_key':k,'row_key':exposure_key(row,row['gold']),'seed':seed,'each':c['exam_each'],'row':row}
        unexposed={k:e for k,e in pool.items() if not any(exposure_key(e['row'],gold) in exclusions for gold in ('TRUE','FALSE'))}
        past=balanced(unexposed)
        future=balanced(pool)
        def counts(rows):
            return dict(Counter(e['row']['gold'] for e in rows))
        report[cap]={'draws':draws,'unique_input':counts(pool.values()),'unexposed_to_recorded_R2_R3_R4':counts(unexposed.values()),'retrospective_balanced':counts(past),'prospective_balanced':counts(future)}
        retrospective+=past
        prospective+=future
    return report, prospective, retrospective


def main(root):
    r4=root/'r4'
    c=json.loads((r4/'configuration.json').read_text())
    run=r4/'treatment/run'
    ptr=(run/'bamf-state.json').read_bytes()
    g=authenticated_history(run)[-1]
    assert g.manifest_sha256==c['initial_manifest_sha256']
    f=_read_bound_json(run/'bamf-bundles'/g.manifest_sha256,g.manifest['sidecars']['compiler_features'],reason='CENSUS_COMPILER_FEATURE_DRIFT')
    release=f['factory_release_sha256']
    context=SourceExecutionContext.from_admitted_release(run,{'factory_release_sha256':release,'factory_release_file':f'factory-releases/{release}.json'},graph=f['factory_semantic_catalog'],source_root=LEGACY_SOURCE.resolve(),source_registry=live_source_registry(),answer_registry=live_answer_registry())
    assert context.release.semantic_catalog_sha256==f['factory_semantic_catalog_sha256']
    caps=tuple(x.capability_id for x in context.release.execution_plan.capabilities if x.grade_id=='A')
    assert len(caps)==6
    exclusions, inputs = historical_exposures(root)
    report, prospective, retrospective = census(context, caps, c, exclusions)
    assert ptr==(run/'bamf-state.json').read_bytes()
    assert len({e['semantic_key'] for e in prospective})==len(prospective)
    assert not any(exposure_key(e['row'],gold) in exclusions for e in retrospective for gold in ('TRUE','FALSE'))
    contract=assessment_scope_contract(context.release,caps)
    result={'manifest_sha256':g.manifest_sha256,'release_sha256':release,'semantic_graph_sha256':f['factory_semantic_graph_sha256'],'rubric_sha256':contract.rubric_sha256,'generator_version':contract.generator_version,'delivery_input_sha256':inputs,'excluded_witness_keys':len(exclusions),'coverage':report,'retrospective':{'count':len(retrospective),'status':'PARTIAL_RECORDED_EXPOSURE_ONLY_NOT_CERTIFIED','rows':retrospective,'sha256':digest(canonical(retrospective))},'prospective':{'count':len(prospective),'status':'PREPARED_NOT_ISSUED_NOT_INDEPENDENT_UNTIL_EXCLUSION_ENFORCED','rows':prospective,'sha256':digest(canonical(prospective))},'limitations':['Prior unrecorded training exposures are unknown.','Prospective rows require explicit owner-authorized reservation and enforced disjoint train/assessment input identities before any future arm.','No assessment was run; no score-based selection or provider substitution.']}
    print(json.dumps(result,indent=2,default=str))
if __name__=='__main__':
    main(Path(sys.argv[1]))
