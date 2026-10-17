"""Human-operated, state-preserving v2-r1 recovery after a JSON tuple readback bug.

Keep the v2 teaching and teacher-selection logic intact. The v2 checkpoint,
teacher observations, and all candidate archives survive this recovery;
only archive slot serialization is made JSON-native. Never edit the sealed
v2 source or its run, or train neural weights on behalf of the human.
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
from . import g12_g13_g14_repair_v2 as teaching
from . import lessons
from . import time_first_runner_v15 as inherited
from . import triplet_operator_v16 as origin
from . import three_grade_repair_operator_v2 as previous

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT/'runs/primitive-consolidation-v16-three-grade-repair-v2-r1'
VERSION = 'bilqis.primitive-consolidation.three-grade-repair/v2-r1'
SCHEMA = 'bilqis.three-grade-repair.native-adamw/v2-r1'
BLOCK = 64
GRADES = teaching.GRADES


def recipe():
    return {'schema':SCHEMA, 'version':VERSION, 'block':BLOCK,
            'instruction_contract':'NOVEL_WORLDS_TEACHER_SELECTED_MODE_AND_KNOBS',
            'grade_program':list(rubric.PROGRAM),
            'parent_rubric_sha256':digest(rubric.inventory()),
            'parent_recipe_sha256':digest(origin._training_recipe()),
            'sources':{'operator':engine._sha(Path(__file__)),
                       'teaching':engine._sha(Path(teaching.__file__)),
                       'sealed_v2_operator':engine._sha(Path(previous.__file__))},
            'recovery_contract':'PRESERVE_V2_FULL_STATE_AND_JSON_NATIVE_ARCHIVE_SLOTS'}


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


def _json_native_archive_slots(archive):
    """Convert only v16 archiver's tuple slots into their durable JSON shape."""
    if archive is None:
        return None
    if any(not isinstance(slot,(tuple,list)) or len(slot)!=3
           for slot in archive['slots']):
        raise ValueError('V2_R1_INVALID_ARCHIVE_SLOT')
    archive['slots']=[list(slot) for slot in archive['slots']]
    return archive


def _assert_v2_source_unchanged(expected_sha):
    if engine._sha(previous.RUN/'state.json')!=expected_sha:
        raise ValueError('V2_R1_PARENT_CHANGED_DURING_PREPARATION')


def prepare():
    """Copy the failed v2 durable grade boundary, not an older student.

    Preserve the entire teacher history, grade/candidate ledgers, and archived
    full-state peak. Immutable checkpoint files are hardlinked, hash-checked,
    and never modified by the successor. No neural update runs here.
    """
    origin._opt_in_authority()
    if RUN.exists() or RUN.is_symlink():
        raise ValueError('FOCUS_REPAIR_ALREADY_PREPARED')
    with origin._run_lock(previous.RUN):
        parent=engine._read(previous.RUN/'state.json')
        previous._verify_state(parent)
        if (parent['phase']!='ACQUISITION' or
                parent['last_run_status']!='DURABLE_REPAIR_GRADE_BOUNDARY' or
                parent['visits']<1 or not parent['candidate_ledger'] or
                parent['repair']['visits']!=parent['visits']):
            raise ValueError('V2_R1_REQUIRES_DURABLE_FAILED_V2_BOUNDARY')
        state_sha=engine._sha(previous.RUN/'state.json')
        student,own_optimizer,graph=previous._load(previous.RUN,parent,'cpu')
        if optimizer_receipt(own_optimizer)['steps']!=[parent['optimizer_step']]:
            raise ValueError('FOCUS_REPAIR_PARENT_ADAMW_DRIFT')
        del student,own_optimizer,graph
        references=[
            (parent['checkpoint'],parent['checkpoint_sha256']),
            (parent['frozen_soup']['file'],parent['frozen_soup']['sha256']),
        ]
        if parent.get('current_teacher'):
            teacher=parent['current_teacher']
            references.append((teacher['file'],teacher['sha256']))
        for archive in parent.get('capability_candidate_archives',[]):
            references.append((archive['file'],archive['sha256']))
        files={}
        for name,sha in references:
            if Path(name).name!=name or name in files and files[name]!=sha:
                raise ValueError('V2_R1_UNSAFE_OR_CONFLICTING_SOURCE_NAME')
            source=previous.RUN/name
            if source.is_symlink() or not source.is_file() or engine._sha(source)!=sha:
                raise ValueError('V2_R1_SOURCE_CHECKPOINT_DRIFT')
            files[name]=sha
        for champions in parent.get('capability_champions',{}).values():
            for champion in champions.values():
                if (files.get(champion['file'])!=champion['checkpoint_sha256'] or
                    any(files.get(tie['file'])!=tie['sha256']
                        for tie in champion['perfect_ties'])):
                    raise ValueError('V2_R1_ARCHIVED_CHAMPION_NOT_PRESERVED')
        temp=RUN.with_name('.'+RUN.name+'.'+uuid.uuid4().hex+'.preparing')
        temp.mkdir(parents=True,exist_ok=False)
        try:
            for name,sha in files.items():
                os.link(previous.RUN/name,temp/name)
                if engine._sha(temp/name)!=sha:
                    raise ValueError('V2_R1_LINKED_CHECKPOINT_DRIFT')
            _assert_v2_source_unchanged(state_sha)
            state=copy.deepcopy(parent)
            state.update(schema=SCHEMA,version=VERSION,config=recipe(),
                         recovery={
                             'kind':'JSON_TUPLE_ARRAY_READBACK_HOTFIX',
                             'source_run':str(previous.RUN),
                             'source_state_sha256':state_sha,
                             'source_version':previous.VERSION,
                             'preserved_grade_visits':parent['visits'],
                             'preserved_attempted_updates':parent['attempted_updates']})
            _save_state(temp,state)
            _load(temp,state,'cpu')
            _assert_v2_source_unchanged(state_sha)
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
            'repair':state['repair'],'run_dir':str(RUN),
            'curriculum':'v2 novel oracle worlds; saved teacher policy retained'}


def preflight():
    """Exercise the real loaded checkpoint, teacher and lesson codec, no update."""
    if (RUN/'state.json').is_file():
        state=engine._read(RUN/'state.json')
        model,optimizer,graph=_load(RUN,state,'cpu')
        source=RUN
    else:
        with origin._run_lock(origin.RUN):
            state=engine._read(origin.RUN/'state.json')
            origin._assert_recipe(state)
            model,optimizer,graph=origin._load(origin.RUN,state,'cpu')
        source=origin.RUN
    before=engine._sha(source/'state.json')
    if optimizer_receipt(optimizer)['steps']!=[state['optimizer_step']]:
        raise ValueError('V2_PREFLIGHT_OPTIMIZER_NOT_NATIVE')
    sampled={}
    for grade in GRADES:
        probe_rng=random.Random(20261014+int(grade[1:])*97)
        teacher_copy=copy.deepcopy(state['teacher'])
        key,policy=engine.pick(teacher_copy,int(grade[1:]),probe_rng)
        rows,counts=teaching.batch(grade,graph,policy,probe_rng)
        sampled[grade]={'policy_id':key,'curriculum':counts,
                         'distinct_oracle_checked':len(rows)}
    if engine._sha(source/'state.json')!=before:
        raise ValueError('V2_PREFLIGHT_SAVED_STATE_CHANGED')
    del model,optimizer
    return {'result':'PREPARED_FOR_HUMAN_NEURAL_TRAINING',
            'status':'READ_ONLY_PREFLIGHT',
            'source_optimizer_step':state['optimizer_step'],
            'source_checkpoint_sha256':state['checkpoint_sha256'],
            'source_state_sha256':before,
            'samples':sampled,'optimizer_steps_executed':0}


def _score(model,graph,grade,device):
    inventory={k:v for k,v in rubric.inventory().items() if k.startswith(grade+':')}
    details=rubric.score_current(model,graph,inventory,device=device)
    return details,sum(details.values()),sum(v['total'] for v in inventory.values())


def _candidate(out,state,model,graph,grade,teacher,device):
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
        training_counts=None
        for _ in range(BLOCK):
            rows,training_counts=teaching.batch(grade,graph,policy,trial_rng)
            losses.append(inherited._train_focus(candidate,optimizer,anchor,
                                                teacher,rows,graph,policy,device))
        if optimizer_receipt(optimizer)['steps']!=[state['optimizer_step']+BLOCK]:
            raise ValueError('V2_REPAIR_NATIVE_OPTIMIZER_STEP_MISMATCH')
        after,value,_=_score(candidate,graph,grade,device)
        gain=value-previous
        engine.observe(state['teacher'],int(grade[1:]),policy_id,2*gain/total)
        record={'grade':grade,'attempt':attempt,'parent_step':state['optimizer_step'],
                'parent_checkpoint_sha256':parent_sha,
                'current_before':before,'current_after':after,
                'gain':gain,'policy_id':policy_id,
                'teacher_credit':2*gain/total,'last_loss':losses[-1],
                'selected':False,
                'teacher_curriculum':training_counts}
        # Preserve ALL newly winning per-family native student+AdamW states,
        # including winners discarded by whole-grade admission.
        archive=_json_native_archive_slots(origin._archive_qualified_candidate(
            out,state,candidate,optimizer,graph,grade,attempt,parent_sha,before,after))
        if archive is not None:
            # The v16 archiver records each slot as a tuple. JSON encodes
            # tuples as arrays, so a strict in-memory == disk readback fails
            # after an otherwise successful durable candidate-archive save.
            # Normalize ONLY the newly authored archive slots, not teacher
            # policies, scores, optimizer state, or the readback guard.
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


def _golden_screen(out,state,model,optimizer,graph,device):
    """Same-step full-source golden verification for this v2 frozen recipe."""
    if (state.get('golden_screen') and
            state['golden_screen'].get('optimizer_step')==state['optimizer_step'] and
            state['golden_screen'].get('checkpoint_sha256')==state['checkpoint_sha256']):
        return False
    _,failing=origin._screen_device(model,graph,device)
    if failing is not None:
        state['golden_screen']={'optimizer_step':state['optimizer_step'],
                                'checkpoint_sha256':state['checkpoint_sha256'],
                                'first_failed':failing}
        _save_state(out,state)
        return False
    reread,own_optimizer,read_graph=_load(out,state,device)
    verified=rubric.score_snapshot(reread,read_graph,
        optimizer_step=state['optimizer_step'],
        checkpoint_sha256=state['checkpoint_sha256'],device=device)
    if not all(m['correct']==m['total'] for m in verified['metrics'].values()):
        raise ValueError('V2_REPAIR_GOLDEN_DOUBLE_CHECK_FAILED')
    from bilqis_ref.model import state_hash
    if (optimizer_receipt(own_optimizer)['steps']!=[state['optimizer_step']] or
            engine._sha(out/state['checkpoint'])!=state['checkpoint_sha256']):
        raise ValueError('V2_REPAIR_GOLDEN_NATIVE_ADAMW_DRIFT')
    state['golden']={'kind':'SAME_CHECKPOINT_ALL_CURRENT_100',
                     'rubric_sha256':digest(rubric.inventory()),
                     'optimizer_step':state['optimizer_step'],
                     'checkpoint':state['checkpoint'],
                     'checkpoint_sha256':state['checkpoint_sha256'],
                     'model_sha256':state_hash(reread),
                     'graph_sha256':digest(read_graph),
                     'metrics':verified['metrics'],
                     'note':'CURRENT_SOURCE_ACQUISITION_NOT_UNSEEN_TRANSFER'}
    state['phase']='GOLDEN_FROZEN'
    state['last_run_status']='GOLDEN_FROZEN_TERMINAL'
    _save_state(out,state)
    return True


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
        start=time.monotonic()
        if _golden_screen(RUN,state,model,optimizer,graph,device):
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
            # A stalled first grade must never prevent the other two from
            # receiving their own complete teacher-selected lessons.
            grade=missing[state['visits']%len(missing)]
            origin._require_checkpoint_headroom(RUN,state)
            before=state['optimizer_step']
            model,new_optimizer,attempts=_candidate(
                RUN,state,model,graph,grade,teacher,device)
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
            if new_optimizer is not None and _golden_screen(
                    RUN,state,model,optimizer,graph,device):
                return status()
            # Avoid the previously observed infinite no-gain loop; an
            # operator review is required before another identical budget.
            if state['repair']['consecutive_no_gain']>=24:
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
