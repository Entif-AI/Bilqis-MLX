"""Run-scoped School50 champion evidence and measured soup construction.

One run is a human-started training session, possibly crossing many complete
B/G spirals. It has exactly one starting student+AdamW geometry/graph identity.
Every attempted candidate can become a *run-local* grade champion, regardless
of its acceptance into the continuing student. Equal grade scores are held
until the run ends and then decided by the same holistic G528/B84/N4 panel.

This module never replaces the causal student, never promotes research grade
qualifications, and never reads the sealed evaluation. Run-local model weights
are distinct from the full student+AdamW checkpoints.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import uuid

import torch

from bilqis_ref.model import state_hash
from . import engine, lessons


SCHEMA='bilqis.run-local-grade-champions/v1'
RECIPE='SESSION_PB48_G_PB12_B_TIES_GBN_AND_INDEPENDENT_SOUP_EVALUATION'
WEIGHTS_B=(0.0,.25,.35,.5,.65,.75,1.0)
BOUNDARIES=('session','complete-program')


def geometry_signature(weights):
    shape=[(k,list(v.shape),str(v.dtype)) for k,v in sorted(weights.items())]
    return hashlib.sha256(json.dumps(shape,separators=(',',':')).encode()).hexdigest()


def grade_decision(previous,score):
    """Pure decision; do not use admission or cross-session PB as a veto."""
    if not isinstance(score,int) or score<0:
        raise ValueError('RUN_LOCAL_INVALID_EXAM_COUNT')
    if previous is None or score>previous:
        return 'NEW_HIGH'
    return 'TIE' if score==previous else 'LOWER'


def holistic_rank(measurement,identity):
    """Equal-domain across-the-board rank, deterministic at every tie."""
    return (measurement['gbn_macro'], measurement['g_percent'],
            measurement['b_correct'],measurement['n_correct'],
            measurement['complete_contrasts'],identity)


def choose_finalist(records):
    if not records:
        raise ValueError('RUN_LOCAL_EMPTY_TIE_GROUP')
    if any(r.get('whole_program') is None for r in records):
        raise ValueError('RUN_LOCAL_TIE_NOT_SCORED')
    return max(records,key=lambda r:holistic_rank(r['whole_program'],r['file']))


def _weights_record(out,item,graph_sha,geometry):
    path=out/item['file']
    if (not path.is_file() or path.is_symlink() or
            engine._sha(path)!=item['sha256']):
        raise ValueError('RUN_LOCAL_ARCHIVED_WEIGHT_SHA_DRIFT')
    archive=torch.load(path,map_location='cpu',weights_only=True)
    if (archive['graph_sha256']!=graph_sha or
            archive['geometry_signature']!=geometry or
            archive['run_id']!=item['run_id'] or
            archive['grade']!=item['grade'] or
            archive['grade_correct']!=item['grade_correct'] or
            archive['grade_total']!=item['grade_total']):
        raise ValueError('RUN_LOCAL_ARCHIVED_WEIGHT_RECEIPT_DRIFT')
    if geometry_signature(archive['weights'])!=geometry:
        raise ValueError('RUN_LOCAL_ARCHIVED_MODEL_ABI_DRIFT')
    return archive['weights']


def _read_model(template,out,item,graph_sha,geometry):
    model=copy.deepcopy(template).cpu().eval()
    model.load_state_dict(_weights_record(out,item,graph_sha,geometry),strict=True)
    for p in model.parameters():p.requires_grad_(False)
    if state_hash(model)!=item['model_sha256']:
        raise ValueError('RUN_LOCAL_MODEL_HASH_DRIFT')
    return model


def _freeze_candidate(out,model,item,graph_sha,geometry):
    dest=out/item['file']
    dest.parent.mkdir(parents=True,exist_ok=True)
    weights={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
    if geometry_signature(weights)!=geometry:
        raise ValueError('RUN_LOCAL_CANDIDATE_GEOMETRY_CHANGED')
    payload={'weights':weights,'graph_sha256':graph_sha,
             'geometry_signature':geometry,'run_id':item['run_id'],
             'grade':item['grade'],'grade_correct':item['grade_correct'],
             'grade_total':item['grade_total']}
    if dest.exists() or dest.is_symlink():
        if not dest.is_file() or dest.is_symlink():
            raise ValueError('RUN_LOCAL_CANDIDATE_PATH_UNSAFE')
        prior=torch.load(dest,map_location='cpu',weights_only=True)
        if (set(prior)!=set(payload) or
                any(prior[k]!=payload[k] for k in payload if k!='weights') or
                set(prior['weights'])!=set(weights) or
                any(not torch.equal(prior['weights'][k],v)
                    for k,v in weights.items())):
            raise ValueError('RUN_LOCAL_CANDIDATE_REPLAY_CONFLICT')
        # A crash after snapshot creation but before the grade's state.json
        # commit may replay this same attempt. Recover exact bytes only.
        item['sha256']=engine._sha(dest)
        item['model_sha256']=state_hash(model)
        return
    tmp=dest.parent/f'.{dest.name}.{uuid.uuid4().hex}.tmp'
    try:
        torch.save(payload,tmp)
        os.replace(tmp,dest)
    finally:
        if tmp.exists():tmp.unlink()
    item['sha256']=engine._sha(dest)
    item['model_sha256']=state_hash(model)


def _average(out,items,graph_sha,geometry,template):
    if not items:raise ValueError('RUN_LOCAL_NO_INGREDIENTS')
    total={}
    exact={}
    for item in items:
        weights=_weights_record(out,item,graph_sha,geometry)
        for k,v in weights.items():
            if torch.is_floating_point(v):
                if k not in total:total[k]=v.float().clone()
                else:total[k].add_(v.float())
            elif k in exact:
                if not torch.equal(exact[k],v):
                    raise ValueError('RUN_LOCAL_NONFLOAT_BUFFER_DRIFT')
            else:exact[k]=v.clone()
    for k in total:total[k].div_(len(items))
    merged={**total,**exact}
    model=copy.deepcopy(template).cpu().eval()
    model.load_state_dict(merged,strict=True)
    for p in model.parameters():p.requires_grad_(False)
    return model


def _score_model(model,graph,panels,lib,label):
    # Reuse the exact v11 scorer, with its exposed replay disclaimers.
    from scripts import school50_soup_probe_v11 as scoring
    if isinstance(model,PredictionLogitEnsemble):
        from . import time_first_runner_v15 as v15
        with torch.inference_mode():
            b=v15._bridges(model,graph,panels,'cpu')
            n=v15._basic_numeric(model,graph,'cpu')
            old=v15._old(model,graph,lib,'cpu')
        result={'name':label,'g_mean':sum(old.values())/len(old),
                'g_scores':old,
                'b_correct':sum(r['correct'] for folds in b.values()
                                for r in folds.values()),
                'b_by_grade':{grade:sum(r['correct'] for r in folds.values())
                              for grade,folds in b.items()},
                'complete_contrasts':sum(r['paired_contrasts']
                       for folds in b.values() for r in folds.values()),
                'n_correct':sum(r['four_way']['correct'] for r in n.values()),
                'n_full101':sum(r['full_101']['correct'] for r in n.values()),
                'assessment_role':'G_FIXED_B_AND_N_EXPOSED_REPLAY'}
        result.update(scoring.joint_scores(result))
        return result
    return scoring.measure(model,graph,panels,lib,label)


class PredictionLogitEnsemble:
    """Evaluation-only output ensemble; never a weight soup or causal student."""

    def __init__(self,g_model,b_model):
        if geometry_signature(g_model.state_dict())!=geometry_signature(b_model.state_dict()):
            raise ValueError('RUN_LOCAL_ENSEMBLE_GEOMETRY_MISMATCH')
        self.members=(g_model.eval(),b_model.eval())
        self.training=False

    def eval(self):
        for member in self.members:member.eval()
        return self

    @torch.no_grad()
    def __call__(self,ids,lengths):
        return (self.members[0](ids,lengths)+self.members[1](ids,lengths))*.5

    @torch.no_grad()
    def typed_logits(self,ids,lengths,*,answer_kind,number_ids):
        from . import numeric_answer_contract as contract
        return (contract.readout(self.members[0],ids,lengths,
                                 answer_kind=answer_kind,number_ids=number_ids)+
                contract.readout(self.members[1],ids,lengths,
                                 answer_kind=answer_kind,number_ids=number_ids))*.5


def _frozen_soup(out,model,name,manifest,graph_sha):
    path=out/name
    weights={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
    manifest['teacher_digest']=state_hash(model)
    if path.exists():
        data=torch.load(path,map_location='cpu',weights_only=True)
        if data['manifest']!=manifest or data['graph_sha256']!=graph_sha:
            raise ValueError('RUN_LOCAL_FROZEN_SOUP_CONFLICT')
    else:
        tmp=path.with_name(f'.{path.name}.{uuid.uuid4().hex}.tmp')
        try:
            torch.save({'weights':weights,'manifest':manifest,
                        'graph_sha256':graph_sha},tmp)
            os.replace(tmp,path)
        finally:
            if tmp.exists():tmp.unlink()
    return {'file':name,'sha256':engine._sha(path),'manifest':manifest}


class RunChampionPolicy:
    """Optional v15 policy hook; never substitutes an existing v14 trainer."""

    def __init__(self,runner):
        self.runner=runner

    def configuration(self,*,block,seed):
        conf=self.runner.configuration(block=block,seed=seed)
        conf['run_champion_policy']=RECIPE
        conf['run_champion_version']=SCHEMA
        conf['session_soup_refresh']='AFTER_OPERATOR_SESSION_ONLY'
        return conf

    def begin(self,out,state,model):
        control=state['run_local_champions']
        if control['schema']!=SCHEMA:
            raise ValueError('RUN_LOCAL_SCHEMA_DRIFT')
        existing=control.get('active')
        if existing is not None:
            if existing['status']!='ACTIVE':
                raise ValueError('RUN_LOCAL_PREVIOUS_SESSION_FINALIZATION_PENDING')
            # Recover receipts for weight files saved before the interrupted
            # grade's state.json commit. Such files remain evidence, not
            # automatically accepted winners or counted optimizer updates.
            self._reconcile_uncommitted(out,state,existing)
            return existing
        identifier=uuid.uuid4().hex[:16]
        geometry=geometry_signature(model.state_dict())
        session={
            'id':identifier,'status':'ACTIVE','start_step':state['optimizer_step'],
            'start_grade':state['config']['grade_program'][state['grade_index']],
            'start_visit':state['visits'],'start_pass':state['passes_completed'],
            'start_student_checkpoint_sha256':state['checkpoint_sha256'],
            'source_run_sha256':state['v15_origin']['source_state_sha256'],
            'graph_sha256':state['graph_sha256'],'geometry_signature':geometry,
            'grade_pools':{},'superseded':[],'selected':{},'measurements':{},
            'soup':None}
        control['active']=session
        engine._atomic_json(out/'state.json',state)
        return session

    def _reconcile_uncommitted(self,out,state,session):
        known={item['file'] for pool in session['grade_pools'].values()
               for item in pool['contenders']}
        known.update(item['file'] for item in session['superseded'])
        known.update(item['file'] for item in session.get('uncommitted_snapshots',[]))
        found=[]
        folder=out/'run-local'/session['id']
        for path in sorted(folder.glob('*.pt')):
            if path.name.startswith('soup-'):
                continue
            relative=path.relative_to(out).as_posix()
            if relative in known:continue
            if path.is_symlink() or not path.is_file():
                raise ValueError('RUN_LOCAL_ORPHAN_SNAPSHOT_UNSAFE')
            found.append({'file':relative,'sha256':engine._sha(path),
                          'status':'INTERRUPTED_UNCOMMITTED_GRADE_EVIDENCE',
                          'eligible_for_champion':False})
        if found:
            session.setdefault('uncommitted_snapshots',[]).extend(found)
            engine._atomic_json(out/'state.json',state)
        return found

    def capture(self,out,state,model,record,grade_correct,grade_total):
        """Called for EVERY trained trial before any student-admission veto."""
        session=state['run_local_champions']['active']
        if session is None or session['status']!='ACTIVE':
            raise ValueError('RUN_LOCAL_NO_ACTIVE_SESSION')
        grade=record['grade']
        if grade_total not in (12,engine.GRADE_CHAMPION_COUNT) or not 0<=grade_correct<=grade_total:
            raise ValueError('RUN_LOCAL_BAD_EXAM')
        pool=session['grade_pools'].get(grade)
        decision=grade_decision(None if pool is None else pool['best'],grade_correct)
        record['run_local_grade_correct']=grade_correct
        record['run_local_grade_total']=grade_total
        record['run_local_admission_independent']=True
        record['run_local_decision']=decision
        if decision=='LOWER':
            return
        item={'run_id':session['id'],'grade':grade,'grade_correct':grade_correct,
              'grade_total':grade_total,'visit':state['visits']+1,
              'attempt':record['attempt'],'parent_step':record['parent_step'],
              'parent_checkpoint_sha256':record.get('parent_checkpoint_sha256',
                                                    state['checkpoint_sha256']),
              'candidate_step':record['candidate_step'],
              'admission_decision':record['decision'],
              'file':(f'run-local/{session["id"]}/{grade}-visit{state["visits"]+1:06d}'
                      f'-a{record["attempt"]}-{state_hash(model)[:16]}.pt')}
        _freeze_candidate(out,model,item,state['graph_sha256'],session['geometry_signature'])
        record['run_local_checkpoint']=item['file']
        if decision=='NEW_HIGH':
            if pool:
                session['superseded'].extend(pool['contenders'])
            session['grade_pools'][grade]={'best':grade_correct,
                                           'denominator':grade_total,
                                           'contenders':[item]}
        else:
            pool['contenders'].append(item)

    def before_pass(self,out,state,soup):
        """Do not average different sessions into an in-progress v15 run."""
        return soup

    def complete_program_covered(self,state):
        session=state['run_local_champions']['active']
        return (session is not None and session['status']=='ACTIVE' and
                set(session['grade_pools'])==set(self.runner.PROGRAM))

    def operator_stop(self,out,state,model,graph,lib,panels,device,reason):
        """Operator-session stops are not necessarily logical epoch ends.

        The selected boundary is an explicit frozen operator configuration,
        not an agent's unilateral interpretation of 'run'.
        """
        boundary=state['config']['champion_boundary']
        if boundary not in BOUNDARIES:
            raise ValueError('RUN_LOCAL_UNKNOWN_BOUNDARY_POLICY')
        if boundary=='session':
            return self.finish(out,state,model,graph,lib,panels,device,reason)
        session=state['run_local_champions']['active']
        if session is None:
            return None  # Last full program may have finalized just now.
        if self.complete_program_covered(state):
            return self.finish(out,state,model,graph,lib,panels,device,reason)
        session.setdefault('operator_stops',[]).append({
            'reason':reason,'step':state['optimizer_step'],
            'visits':state['visits'],'cursor':state['grade_index']})
        engine._atomic_json(out/'state.json',state)
        return None

    def finish(self,out,state,model,graph,lib,panels,device,reason):
        """Commit ties and stage verified, same-run soups at operator stop."""
        control=state['run_local_champions']
        session=control['active']
        if session is None:
            raise ValueError('RUN_LOCAL_NO_SESSION_TO_FINALIZE')
        if session['status']=='ACTIVE':
            session['status']='FINALIZING'
            session['end_step']=state['optimizer_step']
            session['end_visit']=state['visits']
            session['stop_reason']=reason
            engine._atomic_json(out/'state.json',state)
        if session['status']!='FINALIZING':
            raise ValueError('RUN_LOCAL_UNEXPECTED_FINALIZATION_STATE')
        template=copy.deepcopy(model).cpu().eval()
        geometry=session['geometry_signature']
        for grade,pool in sorted(session['grade_pools'].items()):
            if grade in session['selected']:continue
            contenders=pool['contenders']
            for candidate in contenders:
                if 'whole_program' in candidate:continue
                snapshot=_read_model(template,out,candidate,state['graph_sha256'],geometry)
                candidate['whole_program']=_score_model(snapshot,graph,panels,lib,
                    f'RUN_{session["id"]}_{grade}_VISIT_{candidate["visit"]}_A_{candidate["attempt"]}')
                engine._atomic_json(out/'state.json',state)
            winning=choose_finalist(contenders)
            session['selected'][grade]=copy.deepcopy(winning)
            engine._atomic_json(out/'state.json',state)
        if set(session['selected'])==set(self.runner.PROGRAM):
            if session['soup'] is None:
                session['soup']=self._make_measured_soup(out,state,template,graph,lib,panels,session)
                engine._atomic_json(out/'state.json',state)
        else:
            session['soup']={'status':'INCOMPLETE_RUN_GRADE_COVERAGE',
                'present':sorted(session['selected']),
                'missing':sorted(set(self.runner.PROGRAM)-set(session['selected']))}
        session['status']='FINISHED'
        control['completed'].append(copy.deepcopy(session))
        control['active']=None
        engine._atomic_json(out/'state.json',state)
        # Archive only winning grade weights. All losing metadata stays in
        # the ledger, but surplus weight files do not accumulate forever.
        winning={v['file'] for v in session['selected'].values()}
        discarded=(session['superseded']+
                   [r for g,p in session['grade_pools'].items()
                    for r in p['contenders'] if r['file'] not in winning])
        for entry in discarded:
            p=out/entry['file']
            if p.is_file() and engine._sha(p)==entry['sha256']:
                p.unlink()
        return session

    def _make_measured_soup(self,out,state,template,graph,lib,panels,session):
        winners=session['selected']
        b=[winners[k] for k in sorted(winners) if k.startswith('B')]
        g=[winners[k] for k in sorted(winners) if k.startswith('G')]
        base={'run_id':session['id'],'source_state_sha256':session['source_run_sha256'],
              'start_student_checkpoint_sha256':session['start_student_checkpoint_sha256'],
              'geometry_signature':session['geometry_signature'],
              'graph_sha256':session['graph_sha256'],
              'assessments':'G_PB48_AND_EXPOSED_B_PB12',
              'research_qualification':False,
              'grade_votes':{'G':len(g),'B':len(b)}}
        b_model=_average(out,b,state['graph_sha256'],session['geometry_signature'],template)
        g_model=_average(out,g,state['graph_sha256'],session['geometry_signature'],template)
        sdir=out/'run-local'/session['id']
        from scripts.school50_soup_probe_v11 import mix_parameters
        components={}
        for name,m,ingredients in [('B',b_model,b),('G',g_model,g)]:
            manifest={**base,'kind':f'RUN_LOCAL_{name}_COHORT',
                      'votes':len(ingredients),
                      'grade_assignments':{i['grade']:{
                         'file':i['file'],'sha256':i['sha256'],
                         'grade_correct':i['grade_correct'],
                         'grade_total':i['grade_total'],
                         'run_id':i['run_id']}
                         for i in ingredients}}
            components[name]=_frozen_soup(out,m,
                f'run-local/{session["id"]}/soup-{name}.pt',manifest,state['graph_sha256'])
        candidates=[]
        student_score=_score_model(template,graph,panels,lib,'LIVE_STUDENT_AT_RUN_END')
        for weight_b in WEIGHTS_B:
            mixture=copy.deepcopy(template).cpu().eval()
            mixture.load_state_dict(mix_parameters(
                b_model.state_dict(),g_model.state_dict(),weight_b),strict=True)
            scored=_score_model(mixture,graph,panels,lib,f'B{weight_b:.2f}_G{1-weight_b:.2f}')
            candidates.append({'weight_B':weight_b,'weight_G':1-weight_b,
                               'scores':scored})
        ranked=sorted(candidates,key=lambda x:holistic_rank(
            x['scores'],f'B{x["weight_B"]:.2f}'),reverse=True)
        prediction_control=_score_model(
            PredictionLogitEnsemble(g_model,b_model),graph,panels,lib,
            'B50_G50_PREDICTION_LOGIT_ENSEMBLE_CONTROL')
        best=ranked[0]
        chosen=copy.deepcopy(template).cpu().eval()
        chosen.load_state_dict(mix_parameters(
            b_model.state_dict(),g_model.state_dict(),best['weight_B']),strict=True)
        manifest={**base,'kind':'MEASURED_SAME_RUN_DOMAIN_WEIGHT_SOUP',
                  'votes':2,'domain_weights':{'B':best['weight_B'],'G':best['weight_G']},
                  'cohorts':components,
                  'unique_ingredient_checkpoints':len({i['sha256'] for i in b+g}),
                  'grade_assignments':{i['grade']:{
                     'file':i['file'],'sha256':i['sha256'],
                     'grade_correct':i['grade_correct'],
                     'grade_total':i['grade_total'],'run_id':session['id']}
                     for i in b+g}}
        proposed=_frozen_soup(out,chosen,
            f'run-local/{session["id"]}/soup-measured.pt',manifest,state['graph_sha256'])
        return {'status':'MEASURED_NOT_PROMOTED',
                'G_cohort':components['G'],'B_cohort':components['B'],
                'proposed':proposed,'student':student_score,
                'interpolation':candidates,'best':best,
                'prediction_ensemble_control':{
                    'kind':'TWO_MODEL_EQUAL_LOGIT_ENSEMBLE',
                    'scores':prediction_control,'weight_B':.5,'weight_G':.5,
                    'teacher_eligible':False},
                'beats_student_GBN':best['scores']['gbn_macro']>student_score['gbn_macro'],
                'teacher_selected_for_next_run':False,
                'note':'Exposed B84/N4; no sealed or independent transfer exam.'}
