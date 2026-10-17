"""Human-operated, same-rubric rescue of G12/G13/G14 from stopped v16.

This is a distinct source-hash-bound continuation, never an in-place rearm
or alteration of the v16 student, AdamW, checkpoint, rubric, or source state.
It stops once the trio is correct on ONE student, or at a true golden freeze;
it never calls three-grade acquisition an all-grade championship.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import random
import shutil
import signal
import time
import uuid

import torch

from bilqis_logic.kernel import digest
from bilqis_micro.run import optimizer_receipt
from . import engine
from . import current_rubric_v16 as rubric
from . import g12_g13_g14_repair as teaching
from . import lessons
from . import time_first_runner_v15 as inherited
from . import triplet_operator_v16 as origin

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT/'runs/primitive-consolidation-v16-three-grade-repair'
VERSION = 'bilqis.primitive-consolidation.three-grade-repair/v1'
SCHEMA = 'bilqis.three-grade-repair.native-adamw/v1'
BLOCK = 64
GRADES = teaching.GRADES


def recipe():
    return {'schema':SCHEMA, 'version':VERSION, 'block':BLOCK,
            'grade_program':list(rubric.PROGRAM),
            'parent_rubric_sha256':digest(rubric.inventory()),
            'parent_recipe_sha256':digest(origin._training_recipe()),
            'sources':{'operator':engine._sha(Path(__file__)),
                       'teaching':engine._sha(Path(teaching.__file__))}}


def _verify_state(state):
    if (state.get('schema')!=SCHEMA or state.get('version')!=VERSION or
            state.get('config')!=recipe() or state.get('mode')!='--triplets' or
            state.get('phase') not in ('ACQUISITION','GOLDEN_FROZEN','TRIO_COMPLETE') or
            state.get('repair',{}).get('grades')!=list(GRADES)):
        raise ValueError('FOCUS_REPAIR_FROZEN_RECIPE_DRIFT')
    return True


def _load(out,state,device):
    _verify_state(state)
    model, optimizer, graph=inherited._load_student(out,state,device)
    if any(param.dtype!=torch.float32 for param in model.parameters()):
        raise ValueError('FOCUS_REPAIR_LOST_FP32')
    return model,optimizer,graph


def _save_state(out,state):
    engine._atomic_json(out/'state.json',state)
    if engine._read(out/'state.json')!=state:
        raise ValueError('FOCUS_REPAIR_STATE_READBACK_DRIFT')


def prepare():
    """One-time byte-preserving preparation, no optimizer update."""
    origin._opt_in_authority()
    if RUN.exists() or RUN.is_symlink():
        raise ValueError('FOCUS_REPAIR_ALREADY_PREPARED')
    with origin._run_lock(origin.RUN):
        parent=engine._read(origin.RUN/'state.json')
        origin._assert_recipe(parent)
        if (parent['triplets']['phase']!='STALLED_AWAITING_OPERATOR' or
                parent['phase']!='ACQUISITION' or
                parent['triplets']['active'] is not None):
            raise ValueError('FOCUS_REPAIR_SOURCE_NOT_STALLED_AT_BOUNDARY')
        state_sha=engine._sha(origin.RUN/'state.json')
        student,own_optimizer,graph=origin._load(origin.RUN,parent,'cpu')
        if optimizer_receipt(own_optimizer)['steps']!=[parent['optimizer_step']]:
            raise ValueError('FOCUS_REPAIR_PARENT_ADAMW_DRIFT')
        del student,own_optimizer,graph
        files=[parent['checkpoint'],parent['frozen_soup']['file']]
        if parent.get('current_teacher'):
            files.append(parent['current_teacher']['file'])
        temp=RUN.with_name('.'+RUN.name+'.'+uuid.uuid4().hex+'.preparing')
        temp.mkdir(parents=True,exist_ok=False)
        try:
            for name in files:
                if Path(name).name!=name:
                    raise ValueError('FOCUS_REPAIR_UNSAFE_SOURCE_NAME')
                shutil.copyfile(origin.RUN/name,temp/name)
            if (engine._sha(temp/parent['checkpoint'])!=parent['checkpoint_sha256'] or
                    engine._sha(temp/parent['frozen_soup']['file'])!=parent['frozen_soup']['sha256'] or
                    engine._sha(origin.RUN/'state.json')!=state_sha):
                raise ValueError('FOCUS_REPAIR_PARENT_CHANGED_DURING_PREPARATION')
            state=copy.deepcopy(parent)
            state.update(schema=SCHEMA,version=VERSION,config=recipe(),
                         last_run_status='PREPARED_NOT_TRAINED',
                         phase='ACQUISITION',visits=0,attempted_updates=0,
                         retained_updates=0,grade_ledger=[],candidate_ledger=[],
                         golden_screen=None,source={
                            'run':str(origin.RUN),'state_sha256':state_sha,
                            'checkpoint_sha256':parent['checkpoint_sha256'],
                            'optimizer_step':parent['optimizer_step']})
            state['triplets']={
                'phase':'FOCUSED_REPAIR', 'cycles_completed':0,
                'active':None,'history':[],'stagnant_rounds':0}
            # Source archive filenames belong to the preserved source run,
            # never this fork. Keep the parent via its immutable state digest,
            # and start new local archive references rather than pointing at
            # checkpoint files which were not copied to the rescue directory.
            state['capability_champions']={}
            state['capability_candidate_archives']=[]
            state['repair']={'grades':list(GRADES),'visits':0,
                             'consecutive_no_gain':0,'completed':False,
                             'parent_v16_step':parent['optimizer_step'],
                             'parent_checkpoint_sha256':parent['checkpoint_sha256']}
            _save_state(temp,state)
            _load(temp,state,'cpu')
            os.replace(temp,RUN)
            fd=os.open(RUN.parent,os.O_RDONLY)
            try:os.fsync(fd)
            finally:os.close(fd)
        finally:
            if temp.exists():shutil.rmtree(temp)
    return status()


def status():
    if not (RUN/'state.json').is_file():
        return {'status':'NOT_PREPARED','run':str(RUN)}
    state=engine._read(RUN/'state.json')
    _verify_state(state)
    return {'status':state['last_run_status'],'step':state['optimizer_step'],
            'checkpoint':state['checkpoint'],'sha256':state['checkpoint_sha256'],
            'visits':state['visits'],'phase':state['phase'],
            'repair':state['repair']}


def _score(model,graph,grade,device):
    inventory={k:v for k,v in rubric.inventory().items() if k.startswith(grade+':')}
    details=rubric.score_current(model,graph,inventory,device=device)
    return details,sum(details.values()),sum(v['total'] for v in inventory.values())


def _candidate(out,state,model,graph,grade,teacher,library,device):
    before,previous,total=_score(model,graph,grade,device)
    parent_sha=state['checkpoint_sha256']
    source_path=out/state['checkpoint']
    if engine._sha(source_path)!=parent_sha:
        raise ValueError('FOCUS_REPAIR_PARENT_CHECKPOINT_CHANGED')
    rng=random.Random(20261014+state['visits']*7919+int(grade[1:])*104729)
    best=None
    attempts=[]
    seen=set()
    for attempt in range(1,4):
        candidate,optimizer,payload=engine.load_checkpoint(source_path)
        engine._device(candidate,optimizer,device)
        if (digest(payload['graph'])!=state['graph_sha256'] or
                optimizer_receipt(optimizer)['steps']!=[state['optimizer_step']]):
            raise ValueError('FOCUS_REPAIR_CANDIDATE_NOT_SAME_PARENT')
        trial_rng=random.Random(rng.randrange(2**62))
        policy_id,policy=engine.pick(state['teacher'],int(grade[1:]),trial_rng,exclude=seen)
        seen.add(policy_id)
        for group in optimizer.param_groups:group['lr']=policy['lr']
        anchor=copy.deepcopy(candidate).eval()
        for param in anchor.parameters():param.requires_grad_(False)
        losses=[]
        for _ in range(BLOCK):
            rows,_counts=teaching.batch(grade,graph,trial_rng)
            losses.append(inherited._train_focus(candidate,optimizer,anchor,
                                                teacher,rows,graph,policy,device))
        after,value,_=_score(candidate,graph,grade,device)
        gain=value-previous
        engine.observe(state['teacher'],int(grade[1:]),policy_id,2*gain/total)
        record={'grade':grade,'attempt':attempt,'parent_step':state['optimizer_step'],
                'parent_checkpoint_sha256':parent_sha,
                'current_before':before,'current_after':after,
                'gain':gain,'policy_id':policy_id,
                'teacher_credit':2*gain/total,'last_loss':losses[-1],
                'selected':False}
        # Preserve ALL newly winning per-family native student+AdamW states,
        # including winners discarded by whole-grade admission.
        archive=origin._archive_qualified_candidate(
            out,state,candidate,optimizer,graph,grade,attempt,parent_sha,before,after)
        if archive is not None:
            record['complete_capability_candidate_archive']={
                'file':archive['file'],'sha256':archive['sha256'],
                'optimizer_step':archive['optimizer_step']}
        attempts.append(record)
        if gain>0 and (best is None or (gain,tuple(after[k] for k in sorted(after)))>best[0]):
            best=((gain,tuple(after[k] for k in sorted(after))),candidate,optimizer,record)
    if best is None:
        return model,None,attempts
    _,winner,optimizer,record=best
    record['selected']=True
    ref=record.get('complete_capability_candidate_archive')
    if ref is not None:
        filename,sha=ref['file'],ref['sha256']
    else:
        filename,sha=engine._checkpoint(out,winner,optimizer,graph,{
            'step':state['optimizer_step']+BLOCK,'grade':grade,'epoch':VERSION,
            'parent_checkpoint_sha256':parent_sha})
    state['checkpoint']=filename
    state['checkpoint_sha256']=sha
    state['optimizer_step']+=BLOCK
    state['retained_updates']+=BLOCK
    _load(out,state,device)
    return winner,optimizer,attempts


def run(*,minutes=90,device='mps',stop_requested=lambda:False,reporter=None):
    if not 0<minutes<=1440 or device not in ('cpu','mps'):
        raise ValueError('FOCUS_REPAIR_INVALID_OPERATOR_REQUEST')
    if not (RUN/'state.json').is_file():
        prepare()
    with origin._run_lock(RUN):
        state=engine._read(RUN/'state.json')
        model,optimizer,graph=_load(RUN,state,device)
        if state['phase']!='ACQUISITION':
            return status()
        teacher=origin._teacher(RUN,state,model,device)
        library=lessons.TeacherLibrary()
        start=time.monotonic()
        if origin._golden_screen(RUN,state,model,optimizer,graph,device):
            return status()
        while not stop_requested() and time.monotonic()-start<minutes*60:
            scores={grade:_score(model,graph,grade,device) for grade in GRADES}
            missing=[grade for grade in GRADES if scores[grade][1]!=scores[grade][2]]
            if not missing:
                # This passes the original three-grade acquisition criterion,
                # but cannot certify the other 26 grades by implication.
                state['repair']['completed']=True
                state['phase']='TRIO_COMPLETE'
                state['last_run_status']='THREE_GRADE_100_NOT_FULL_GOLDEN'
                _save_state(RUN,state)
                return status()
            grade=missing[0]
            origin._require_checkpoint_headroom(RUN,state)
            before=state['optimizer_step']
            model,new_optimizer,attempts=_candidate(
                RUN,state,model,graph,grade,teacher,library,device)
            state['attempted_updates']+=BLOCK*len(attempts)
            if new_optimizer is not None:
                optimizer=new_optimizer
                state['repair']['consecutive_no_gain']=0
            else:
                state['repair']['consecutive_no_gain']+=1
            state['visits']+=1
            state['repair']['visits']+=1
            state['triplets']['cycles_completed']=state['visits']//3
            state['candidate_ledger'].extend(attempts)
            result={ 'visit':state['visits'],'grade':grade,
                     'whole_lesson_completed':True,'attempts':len(attempts),
                     'accepted':new_optimizer is not None,
                     'optimizer_step':state['optimizer_step'],
                     'checkpoint_sha256':state['checkpoint_sha256'],
                     'current_before':attempts[0]['current_before'],
                     'current_after':next((r['current_after'] for r in attempts if r['selected']),
                                          attempts[0]['current_before']) }
            state['grade_ledger'].append(result)
            state['last_run_status']='DURABLE_REPAIR_GRADE_BOUNDARY'
            _save_state(RUN,state)
            if reporter:reporter('grade',result,state)
            if new_optimizer is not None and origin._golden_screen(
                    RUN,state,model,optimizer,graph,device):
                return status()
            # Avoid the previously observed infinite no-gain loop; an
            # operator review is required before another identical budget.
            if state['repair']['consecutive_no_gain']>=6:
                state['last_run_status']='FOCUS_REPAIR_STALLED_AWAITING_OPERATOR'
                _save_state(RUN,state)
                return status()
        state['last_run_status']='GRACEFUL_OPERATOR_STOP'
        _save_state(RUN,state)
        return status()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--status',action='store_true')
    mode.add_argument('--prepare',action='store_true')
    mode.add_argument('--train',action='store_true')
    parser.add_argument('--device',choices=('cpu','mps'),default='mps')
    parser.add_argument('--minutes',type=float,default=90)
    args=parser.parse_args(argv)
    if args.status:output=status()
    elif args.prepare:output=prepare()
    else:
        stop={'requested':False}
        previous=signal.signal(signal.SIGINT,lambda *_:stop.__setitem__('requested',True))
        try:output=run(device=args.device,minutes=args.minutes,
                       stop_requested=lambda:stop['requested'])
        finally:signal.signal(signal.SIGINT,previous)
    print(json.dumps(output,indent=2,sort_keys=True))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
