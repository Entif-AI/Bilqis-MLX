"""Tiny cumulative FP32 acquisition trial over one multi-concept direct-path rung.

The user's immediately reachable concepts train together: MEMBER, directed
EDGE, SUB and MUL, plus four proven ADD replay anchors. No grade-22 cycle or
requirement to split each distinction into its own run. The frozen v11 FP32
student + complete AdamW state is copied by immutable verified hardlink to a
new private run. Candidate training is research-only and cannot vote in soup.

Explicit operator commands: --initialize-only, --status, --train. --train
is bounded to 32 total optimizer updates, with durable 4/16/32 checkpoints.
"""
from __future__ import annotations

import argparse
import copy
from collections import Counter
import fcntl
import json
import os
from pathlib import Path
import signal
import time

import torch
from torch.nn import functional as F

from bilqis_logic.kernel import digest
from bilqis_micro.run import optimizer_receipt
from bilqis_ref.model import state_hash
from . import (engine, lessons, numeric_answer_contract as numeric,
               primitive_staircase_v13 as course,
               g_primitives_training_v12 as v12,
               time_first_runner as earlier,
               spiral_staged_runner as staged)

VERSION='bilqis.primitive-staircase-training/v13'
ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/primitive-staircase-v13'
MILESTONES=(4,16,32)
POLICY={'lr':0.00013,'distill':0.15}
MAX_SECONDS=180
_stop=False


def recipe():
    files={'runner':__file__,'course':course.__file__,
           'engine':engine.__file__,'school50_lessons':lessons.__file__,
           'staged_loss':staged.__file__,'numeric_readout':numeric.__file__,
           'v12_helpers':v12.__file__}
    return {k:engine._sha(v) for k,v in files.items()}


def _score(model,graph,device):
    """Per-exact-question, concept, answer and contrast evidence."""
    items=course.rows()
    course.validate(graph)
    ids={r['id']:r for r in items}
    result=[]
    with torch.inference_mode():
        model.eval()
        for kind in ('evidence','numeric'):
            selected=[r for r in items if r['answer_kind']==kind]
            x,lengths=staged._input(selected,graph,device)
            logits=numeric.readout(model,x,lengths,answer_kind=kind,
                                   number_ids=numeric.numeric_token_ids(graph)[:4])
            labels=staged._gold(selected,kind,device)
            predicted=logits.argmax(-1).tolist()
            losses=F.cross_entropy(logits,labels,reduction='none').tolist()
            for r,p,ce in zip(selected,predicted,losses):
                answer=staged.STATES[p] if kind=='evidence' else p
                result.append({'id':r['id'],'concept':r['course_meta']['concept'],
                               'gold':r['gold'],'prediction':answer,
                               'correct':answer==r['gold'],'cross_entropy':round(ce,5),
                               'retention':bool(r['course_meta'].get('retention'))})
    if set(x['id'] for x in result)!=set(ids):
        raise ValueError('V13_SCORE_QUESTION_LOSS')
    keyed={x['id']:x for x in result}
    families={}
    for name in course.CONCEPTS+('ADD',):
        selected=[r for r in result if r['concept']==name]
        families[name]={'correct':sum(x['correct'] for x in selected),
                        'questions':len(selected),
                        'expected':dict(Counter(str(x['gold']) for x in selected)),
                        'predicted':dict(Counter(str(x['prediction']) for x in selected)),
                        'mean_ce':round(sum(x['cross_entropy'] for x in selected)/len(selected),5),
                        'per_gold':{str(k):{'correct':sum(x['correct'] for x in selected if x['gold']==k),
                                            'questions':sum(x['gold']==k for x in selected)}
                                    for k in sorted(set(x['gold'] for x in selected))}}
    contrasts=[]
    for check in course.checks():
        first,second=(keyed[i] for i in check['ids'])
        relation=(first['prediction']==second['prediction'])==(check['kind']=='invariant')
        contrasts.append(dict(check,relationship_correct=relation,
                              both_questions_correct=first['correct'] and second['correct']))
    return {'assessment_role':'EXACT_EXPOSED_TRAINING_REPLAY_NOT_GENERALIZATION',
            'correct':sum(r['correct'] for r in result),
            'questions':len(result),
            'by_concept':families,
            'contrasts':contrasts,
            'contrasts_both_correct':sum(r['both_questions_correct'] for r in contrasts),
            'contrast_count':len(contrasts),
            'all_primitive_questions_correct':all(r['correct'] for r in result if not r['retention']),
            'records':result}


def _retention(model,graph,device):
    """Only historical diagnostics; never selects, gates, or promotes pilot."""
    lib=lessons.TeacherLibrary()
    scores=engine._probe_all_grades(model,graph,lib,device=device)
    B=earlier._bridges(model,graph,earlier._panels(graph,20261013),device)
    N=earlier._basic_numeric(model,graph,device)
    b_correct=sum(f['correct'] for g in B.values() for f in g.values())
    n_correct=sum(N[fold]['four_way']['correct'] for fold in ('primary','confirm'))
    return {'historical_g_scores':scores,'historical_g_mean':sum(scores.values())/len(scores),
            'b_replay_correct':b_correct,'b_replay_questions':84,
            'direct_add_correct':n_correct,'direct_add_questions':4}


def _read_state(out):
    state=engine._read(out/'state.json')
    if (state['version']!=VERSION or state['config']['recipe']!=recipe() or
            state['config']['course_digest']!=digest([(r['id'],r['gold']) for r in course.rows()]) or
            state['config']['milestones']!=list(MILESTONES) or
            state['source_state_sha256']!=v12.SOURCE_STATE_SHA256 or
            state['status'] not in ('READY_ACQUISITION','READY_RESUME','COMPLETE_REVIEW')):
        raise ValueError('V13_STATE_RECIPE_OR_STATUS_DRIFT')
    return state


def _assert_source():
    source,sha=v12._assert_source()
    study,teacher_file=v12._assert_teacher()
    return source,sha,study,teacher_file


def initialize(out=RUN):
    out=Path(out)
    if out.exists():raise FileExistsError('V13_RUN_ALREADY_EXISTS')
    source,sha,study,teacher_file=_assert_source()
    model,optimizer,payload=engine.load_checkpoint(v12.SOURCE/source['checkpoint'])
    if (optimizer_receipt(optimizer)['steps']!=[source['optimizer_step']] or
            state_hash(model)!=payload['state_sha256'] or
            digest(payload['graph'])!=source['graph_sha256']):
        raise ValueError('V13_PARENT_FP32_ADAMW_OR_GRAPH_DRIFT')
    course.validate(payload['graph'])
    out.mkdir(parents=True,exist_ok=False)
    earlier._link_immutable(v12.SOURCE/source['checkpoint'],
                            out/source['checkpoint'],source['checkpoint_sha256'])
    state={
        'version':VERSION,'status':'READY_ACQUISITION',
        'source_run':str(v12.SOURCE),'source_state_sha256':sha,
        'source_checkpoint_sha256':source['checkpoint_sha256'],
        'source_model_sha256':payload['state_sha256'],
        'source_optimizer_step':source['optimizer_step'],
        'graph_sha256':source['graph_sha256'],
        'experimental_teacher':{'path':str(teacher_file),
                                'sha256':study['artifact_sha256'],
                                'qualification':'UNQUALIFIED_FROZEN_RESEARCH_SOUP'},
        'teacher':copy.deepcopy(source['teacher']),
        'grade_champions':copy.deepcopy(source['grade_champions']),
        'protected_holistic_anchor':copy.deepcopy(source['holistic_anchor']),
        'qualified_bridge_champions':copy.deepcopy(source['bridge_champions']),
        'provisional_bridge_champions':copy.deepcopy(source['provisional_bridge_champions']),
        'original_frozen_soup':copy.deepcopy(source['frozen_soup']),
        'optimizer_step':source['optimizer_step'],
        'checkpoint':source['checkpoint'],
        'checkpoint_sha256':source['checkpoint_sha256'],
        'updates_completed':0,'retained_updates':0,'attempted_updates':0,
        'milestones':[],
        'config':{'recipe':recipe(),
                  'course_digest':digest([(r['id'],r['gold']) for r in course.rows()]),
                  'milestones':list(MILESTONES),'policy':copy.deepcopy(POLICY),
                  'assessment_role':'TRAINING_REPLAY_NOT_GENERALIZATION',
                  'mode':'RESEARCH_ONLY_NO_CANONICAL_PROMOTION',
                  'teacher':'PRESERVED_NO_REWARD_ATTRIBUTION_FOR_FROZEN_POLICY',
                  'g_gate':'HISTORICAL_RETENTION_DIAGNOSTIC_ONLY',
                  'sealed_exam':'NEVER_EXECUTED'},
    }
    engine._atomic_json(out/'state.json',state)
    return state


def _load(out,state,device):
    path=out/state['checkpoint']
    if engine._sha(path)!=state['checkpoint_sha256']:
        raise ValueError('V13_STUDENT_CHECKPOINT_DRIFT')
    student,opt,payload=engine.load_checkpoint(path)
    engine._device(student,opt,device)
    if (digest(payload['graph'])!=state['graph_sha256'] or
            optimizer_receipt(opt)['steps']!=[state['optimizer_step']] or
            state_hash(student)!=payload['state_sha256']):
        raise ValueError('V13_CUMULATIVE_STUDENT_ADAMW_DRIFT')
    return student,opt,payload['graph']


def _stop_requested(signum,frame):
    global _stop
    _stop=True
    print('STOP_REQUESTED: finish current four/16/32-update milestone',flush=True)


def run(out=RUN,*,device='mps',limit=32):
    if limit not in MILESTONES:raise ValueError('V13_STOP_BOUNDARY_MUST_BE_4_16_OR_32')
    out=Path(out)
    lock=out.with_name(out.name+'.writer.lock')
    fd=os.open(lock,os.O_CREAT|os.O_RDWR|getattr(os,'O_NOFOLLOW',0),0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        state=_read_state(out)
        parent,_,_,_=_assert_source()
        if state['source_checkpoint_sha256']!=parent['checkpoint_sha256']:
            raise ValueError('V13_SOURCE_CHECKPOINT_REPLACED')
        if state['updates_completed']>=limit:
            print('V13_NO_NEW_UPDATES',state['updates_completed']);return state
        model,opt,graph=_load(out,state,device)
        parent_model,_,parent_payload=engine.load_checkpoint(v12.SOURCE/parent['checkpoint'])
        if state_hash(parent_model)!=state['source_model_sha256']:
            raise ValueError('V13_STARTING_PARENT_MODEL_CHANGED')
        parent_model.to(device).eval()
        for param in parent_model.parameters():param.requires_grad_(False)
        soup=v12._teacher(model,graph,state,device)
        for group in opt.param_groups:group['lr']=state['config']['policy']['lr']
        policy=state['config']['policy']
        items=course.rows()
        record=out/'events.jsonl'
        previous=signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT,_stop_requested)
        start=time.monotonic()
        try:
            if not state['milestones']:
                replay=_score(model,graph,device)
                retention=_retention(model,graph,device)
                state['baseline']={'replay':replay,'retention':retention,
                                   'optimizer_step':state['optimizer_step']}
                engine._atomic_json(out/'state.json',state)
                print('BASELINE',replay['correct'],'/',replay['questions'],
                      {k:v['correct'] for k,v in replay['by_concept'].items()},flush=True)
            for boundary in MILESTONES:
                if boundary<=state['updates_completed'] or boundary>limit:continue
                if _stop:break
                losses=[]
                for i in range(state['updates_completed'],boundary):
                    model.train()
                    opt.zero_grad(set_to_none=True)
                    loss,_=staged._typed_loss(model,parent_model,soup,items,graph,
                                               numeric.numeric_token_ids(graph)[:4],
                                               policy,device)
                    if not bool(torch.isfinite(loss)):
                        raise ValueError('V13_NONFINITE_LOSS')
                    loss.backward()
                    norm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)
                    if not bool(torch.isfinite(norm)):
                        raise ValueError('V13_NONFINITE_GRADIENT')
                    opt.step()
                    losses.append(float(loss.detach().cpu()))
                step=state['source_optimizer_step']+boundary
                if optimizer_receipt(opt)['steps']!=[step]:
                    raise ValueError('V13_ADAMW_INVARIANT_BROKEN')
                replay=_score(model,graph,device)
                retention=_retention(model,graph,device) if boundary==32 else None
                file,checkpoint_sha=engine._checkpoint(out,model,opt,graph,{
                    'step':step,'curriculum':VERSION,'milestone':boundary,
                    'disposition':'UNQUALIFIED_ACQUISITION_RESEARCH',
                    'parent_source_checkpoint_sha256':state['source_checkpoint_sha256']})
                receipt={'updates':boundary,'optimizer_step':step,
                         'replay':replay,'retention':retention,
                         'loss_first':losses[0],'loss_last':losses[-1],
                         'checkpoint':file,'checkpoint_sha256':checkpoint_sha}
                state['checkpoint']=file
                state['checkpoint_sha256']=checkpoint_sha
                state['optimizer_step']=step
                state['updates_completed']=boundary
                state['retained_updates']=boundary
                state['attempted_updates']=boundary
                state['milestones'].append(receipt)
                state['status']='COMPLETE_REVIEW' if boundary==32 else 'READY_RESUME'
                engine._atomic_json(out/'state.json',state)
                with record.open('a',encoding='utf-8') as log:
                    log.write(json.dumps({'event':'MILESTONE',**receipt},sort_keys=True)+'\n')
                    log.flush();os.fsync(log.fileno())
                print('MILESTONE',boundary,'of',MILESTONES[-1],
                      'replay',replay['correct'],'/',replay['questions'],
                      {k:v['correct'] for k,v in replay['by_concept'].items()},
                      'contrasts',replay['contrasts_both_correct'],'/',replay['contrast_count'],
                      'step',step,flush=True)
                if _stop or time.monotonic()-start>=MAX_SECONDS:break
        finally:
            signal.signal(signal.SIGINT,previous)
        if engine._sha(v12.SOURCE/'state.json')!=state['source_state_sha256']:
            raise ValueError('V13_SOURCE_STATE_MUTATED')
        if engine._sha(v12.SOURCE/parent['checkpoint'])!=state['source_checkpoint_sha256']:
            raise ValueError('V13_SOURCE_MODEL_MUTATED')
        print('V13_SESSION_END',state['status'],'updates',state['updates_completed'],
              'optimizer',state['optimizer_step'],'original_teacher_events',state['teacher']['events'],
              flush=True)
        return state
    finally:
        os.close(fd)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--initialize-only',action='store_true')
    mode.add_argument('--train',action='store_true')
    mode.add_argument('--status',action='store_true')
    p.add_argument('--run-dir',type=Path,default=RUN)
    p.add_argument('--device',choices=('cpu','mps'),default='mps')
    p.add_argument('--limit',type=int,default=32)
    args=p.parse_args()
    if args.initialize_only:
        state=initialize(args.run_dir)
        print('INITIALIZED',state['status'],'step',state['optimizer_step'],
              'new_updates',state['updates_completed'])
    elif args.status:
        state=_read_state(args.run_dir)
        print('STATUS',state['status'],'updates',state['updates_completed'],
              'optimizer',state['optimizer_step'],
              'remaining',32-state['updates_completed'])
    else:
        run(args.run_dir,device=args.device,limit=args.limit)


if __name__=='__main__':main()
