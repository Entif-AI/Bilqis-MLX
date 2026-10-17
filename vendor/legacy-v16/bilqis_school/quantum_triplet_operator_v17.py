"""Human-operated global weakest-three, semantic staircase v17.

Version-distinct from all frozen v16 runs. Select a *single* independently
measured pre-repair full FP32 student with its own native AdamW, retain the
incumbent adaptive teacher, and use the old global three-lesson state machine
with newly graded G12/G13/G14 examples. This module never trains by itself;
only the human-owned root CLI may call run().
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import random
import shutil
import time
import uuid

import torch

from bilqis_logic.kernel import digest
from bilqis_micro.run import optimizer_receipt
from bilqis_ref.model import state_hash
from . import engine, lessons
from . import current_rubric_v16 as rubric
from . import quantum_lessons_v17 as curriculum
from . import quantum_triplet_scheduler_v17 as queue
from . import triplet_operator_v16 as origin
from . import time_first_runner_v15 as inherited

VERSION='bilqis.primitive-consolidation.quantum-triplets/v17'
SCHEMA='bilqis.quantum-triplets.native-adamw/v17'
ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/primitive-consolidation-v17-quantum-triplets'
SOURCE=origin.RUN
SOURCE_RECEIPT=ROOT/'docs/development/QUANTUM_TRIPLETS_V17_PARENT.json'
AUDIT=ROOT/'docs/development/QUANTUM_TRIPLETS_V17_AUDIT.jsonl'
BLOCK=origin.BLOCK


def parent_receipt():
    if SOURCE_RECEIPT.is_symlink() or not SOURCE_RECEIPT.is_file():
        raise ValueError('QUANTUM_MISSING_VERIFIED_PRE_REPAIR_PARENT')
    receipt=engine._read(SOURCE_RECEIPT)
    if (receipt.get('source_run')!=str(SOURCE) or
            receipt.get('rubric_sha256')!=digest(rubric.inventory()) or
            not AUDIT.is_file() or AUDIT.is_symlink() or
            receipt.get('audit_sha256')!=engine._sha(AUDIT) or
            type(receipt.get('source_optimizer_step')) is not int or
            type(receipt.get('score')) is not int or
            receipt.get('total')!=1150 or
            receipt.get('measured_count')!=receipt.get('checkpoint_count') or
            not 0<=receipt['score']<=receipt['total'] or
            not isinstance(receipt.get('checkpoint_sha256'),str) or
            len(receipt['checkpoint_sha256'])!=64):
        raise ValueError('QUANTUM_INVALID_PARENT_RUBRIC_OR_AUDIT_RECEIPT')
    name=receipt.get('checkpoint')
    if not isinstance(name,str) or Path(name).name!=name or not name.startswith('student-'):
        raise ValueError('QUANTUM_PARENT_FILE_IDENTITY_INVALID')
    return receipt


def recipe():
    origin._opt_in_authority()
    p=parent_receipt()
    paths={'runner':__file__,
           'lesson_staircase':curriculum.__file__,
           'global_queue':queue.__file__,
           'frozen_triplet_operator':origin.__file__,
           'frozen_v2_oracle':curriculum.previous.__file__}
    return {'version':VERSION,'schema':SCHEMA,
            'teaching':'SIX_FAMILIES_THREE_RUNGS_TARGET_PREDICATE_CONTRAST',
            'scheduling':'GLOBAL_WORST_THREE_THEN_NEXT_REMAINING',
            'source_receipt_sha256':engine._sha(SOURCE_RECEIPT),
            'current_rubric_sha256':digest(rubric.inventory()),
            'source_v16_recipe_sha256':digest(origin._frozen_configuration()),
            'source_hashes':{key:engine._sha(Path(path)) for key,path in paths.items()},
            'native_optimizer_only':True,'human_only':True,'block':BLOCK}


def _verify_state(state):
    if (state.get('schema')!=SCHEMA or state.get('version')!=VERSION or
            state.get('mode')!='--triplets' or state.get('config')!=recipe() or
            state.get('graph_sha256')!=state.get('source',{}).get('graph_sha256')):
        raise ValueError('QUANTUM_FROZEN_RECIPE_OR_GRAPH_DRIFT')
    queue._verify(state['triplets'],rubric.inventory())
    if state['phase'] not in ('ACQUISITION','GOLDEN_FROZEN'):
        raise ValueError('QUANTUM_UNKNOWN_TRAINING_PHASE')
    return True


def _load(out,state,device):
    model,optimizer,graph=origin._load(out,state,device)
    if (optimizer_receipt(optimizer)['steps']!=[state['optimizer_step']] or
            digest(graph)!=state['graph_sha256']):
        raise ValueError('QUANTUM_NATIVE_STUDENT_ADAMW_OR_GRAPH_DRIFT')
    return model,optimizer,graph


def _save(out,state):
    # Canonicalize the inherited v16 archiver's tuple-valued metadata BEFORE
    # comparing the strict JSON readback. Do not weaken verification.
    canonical=json.loads(json.dumps(state,sort_keys=True,allow_nan=False))
    engine._atomic_json(out/'state.json',canonical)
    if engine._read(out/'state.json')!=canonical:
        raise ValueError('QUANTUM_DURABLE_STATE_READBACK_DRIFT')


def status():
    if not (RUN/'state.json').is_file():
        return {'status':'NOT_PREPARED','mode':'--triplets',
                'run_dir':str(RUN),'eligible_grades':len(rubric.PROGRAM)}
    state=engine._read(RUN/'state.json')
    _verify_state(state)
    current=state['triplets']
    return {'status':state['last_run_status'],'phase':state['phase'],
            'optimizer_step':state['optimizer_step'],'checkpoint_sha256':state['checkpoint_sha256'],
            'visits':state['visits'],'cycles_completed':current['cycles_completed'],
            'triplets_phase':current['phase'],'locked_three':(current['active'] or {}).get('grades'),
            'next_lesson':origin.scheduler.next_lesson(current),
            'remaining_this_sweep':len(current['remaining_program']),
            'sweep':current['sweep'],'source':state['source'],
            'last_grade_visit':state['grade_ledger'][-1] if state['grade_ledger'] else None,
            'student_was_not_weight_soup':True,
            'graduation':'ORIGINAL_1150_SAME_CHECKPOINT_REQUIRED'}


def _check_parent(source,source_state,receipt):
    origin._assert_recipe(source_state)
    if (source_state.get('phase')!='ACQUISITION' or
            source_state.get('triplets',{}).get('phase')!='STALLED_AWAITING_OPERATOR' or
            engine._sha(source/'state.json')!=receipt['source_state_sha256']):
        raise ValueError('QUANTUM_SOURCE_STATE_NOT_FROZEN_PRE_REPAIR')
    path=source/receipt['checkpoint']
    if (path.is_symlink() or not path.is_file() or
            engine._sha(path)!=receipt['checkpoint_sha256']):
        raise ValueError('QUANTUM_PRE_REPAIR_PARENT_CHECKPOINT_CHANGED')
    model,optimizer,payload=engine.load_checkpoint(path)
    if (optimizer_receipt(optimizer)['steps']!=[receipt['source_optimizer_step']] or
            digest(payload['graph'])!=source_state['graph_sha256'] or
            any(p.dtype!=torch.float32 for p in model.parameters())):
        raise ValueError('QUANTUM_PARENT_NOT_FULL_FP32_NATIVE_ADAMW')
    actual=rubric.score_current(model,payload['graph'],rubric.inventory(),device='cpu')
    if sum(actual.values())!=receipt['score']:
        raise ValueError('QUANTUM_PARENT_FULL_RUBRIC_SCORE_NOT_REPRODUCED')
    return model,optimizer,payload['graph']


def prepare():
    """Human-run source clone; no neural updates, no mutations of ancestors."""
    if RUN.exists() or RUN.is_symlink():
        raise ValueError('QUANTUM_ALREADY_PREPARED')
    receipt=parent_receipt()
    with origin._source_read_lock(SOURCE):
        parent=engine._read(SOURCE/'state.json')
        initial_sha=engine._sha(SOURCE/'state.json')
        model,optimizer,graph=_check_parent(SOURCE,parent,receipt)
        frozen=parent['frozen_soup']
        teacher_file=SOURCE/frozen['file']
        if teacher_file.is_symlink() or engine._sha(teacher_file)!=frozen['sha256']:
            raise ValueError('QUANTUM_ORIGINAL_TEACHER_CHANGED')
        staging=RUN.with_name('.'+RUN.name+'.'+uuid.uuid4().hex+'.preparing')
        staging.mkdir(parents=True,exist_ok=False)
        try:
            for name,sha in ((receipt['checkpoint'],receipt['checkpoint_sha256']),
                             (frozen['file'],frozen['sha256'])):
                if Path(name).name!=name:
                    raise ValueError('QUANTUM_UNSAFE_SOURCE_FILE_NAME')
                # Do not share inode with the running model's mutable cache.
                shutil.copyfile(SOURCE/name,staging/name)
                if engine._sha(staging/name)!=sha:
                    raise ValueError('QUANTUM_PARENT_COPY_DRIFT')
            state={'schema':SCHEMA,'version':VERSION,'mode':'--triplets',
                'phase':'ACQUISITION','last_run_status':'PREPARED_NOT_TRAINED',
                'optimizer_step':receipt['source_optimizer_step'],
                'checkpoint':receipt['checkpoint'],
                'checkpoint_sha256':receipt['checkpoint_sha256'],
                'graph_sha256':parent['graph_sha256'],
                'teacher':copy.deepcopy(parent['teacher']),
                'frozen_soup':copy.deepcopy(frozen),'current_teacher':None,
                'source':{'run':str(SOURCE),'state_sha256':initial_sha,
                          'checkpoint_sha256':receipt['checkpoint_sha256'],
                          'optimizer_step':receipt['source_optimizer_step'],
                          'graph_sha256':parent['graph_sha256'],
                          'model_sha256':state_hash(model),
                          'teacher_events':parent['teacher']['events'],
                          'parent_current_correct':receipt['score'],
                          'parent_current_total':receipt['total']},
                'config':recipe(),
                'triplets':queue.new_state(rubric.PROGRAM,rubric.inventory()),
                'visits':0,'attempted_updates':0,'retained_updates':0,
                'grade_ledger':[],'candidate_ledger':[],
                'capability_champions':{},'capability_candidate_archives':[],
                'soup_history':[],'golden_screen':None}
            _save(staging,state)
            _verify_state(engine._read(staging/'state.json'))
            restored,restored_opt,read_graph=_load(staging,state,'cpu')
            if state_hash(restored)!=state['source']['model_sha256']:
                raise ValueError('QUANTUM_CLONED_MODEL_IDENTITY_DRIFT')
            if engine._sha(SOURCE/'state.json')!=initial_sha:
                raise ValueError('QUANTUM_SOURCE_CHANGED_DURING_PREPARATION')
            os.replace(staging,RUN)
            fd=os.open(RUN.parent,os.O_RDONLY)
            try:os.fsync(fd)
            finally:os.close(fd)
            del restored,restored_opt,read_graph,model,optimizer
            return status()
        except BaseException:
            if staging.is_dir() and not staging.is_symlink():
                shutil.rmtree(staging)
            raise


def preflight():
    """Validate all three lesson rungs, origin, and teacher without training."""
    receipt=parent_receipt()
    if (RUN/'state.json').is_file():
        state=engine._read(RUN/'state.json')
        _verify_state(state)
        model,optimizer,graph=_load(RUN,state,'cpu')
    else:
        with origin._source_read_lock(SOURCE):
            parent=engine._read(SOURCE/'state.json')
            model,optimizer,graph=_check_parent(SOURCE,parent,receipt)
            state={'teacher':parent['teacher'],'optimizer_step':receipt['source_optimizer_step']}
    full=rubric.score_snapshot(
        model,graph,optimizer_step=state['optimizer_step'],
        checkpoint_sha256=(state['checkpoint_sha256']
                           if 'checkpoint_sha256' in state
                           else receipt['checkpoint_sha256']),device='cpu')
    if (RUN/'state.json').is_file():
        proposal=(state['triplets']['active'] or {}).get('grades')
        if proposal is None and state['triplets']['phase']=='SELECT_READY':
            proposal=queue.begin_cycle(state['triplets'],full,rubric.inventory())[
                'active']['grades']
    else:
        proposal=queue.begin_cycle(
            queue.new_state(rubric.PROGRAM,rubric.inventory()),full,rubric.inventory()
        )['active']['grades']
    sample={}
    for grade in curriculum.GRADES:
        observed=[]
        for index in (0,20,42):
            policy_id,policy=next(iter(state['teacher']['strategies'].items()))
            rows,counts=curriculum.batch(grade,graph,policy,
                  random.Random(1701+int(grade[1:])*17+index),update_index=index)
            observed.append({'rung':counts['rung'],'oracle_rows':len(rows),
                             'mode':counts['teacher_mode']})
        sample[grade]=observed
    del model,optimizer
    return {'result':'PREPARED_FOR_HUMAN_NEURAL_TRAINING',
            'optimizer_steps_executed':0,'source_checkpoint':receipt['checkpoint'],
            'source_optimizer_step':receipt['source_optimizer_step'],
            'full_rubric_score':sum(v['correct'] for v in full['metrics'].values()),
            'source_full_rubric_score':receipt['score'],
            'full_rubric_total':receipt['total'],
            'global_eligible':len(rubric.PROGRAM),
            'proposed_first_three':proposal,
            'source_hash_bound':True,'samples':sample}


def _candidate_attempt(out,state,grade,attempt,before,graph,teacher,device,
                       trial_rng,parent_path,parent_step,parent_sha,seen):
    candidate,optim,payload=engine.load_checkpoint(parent_path)
    engine._device(candidate,optim,device)
    if (optimizer_receipt(optim)['steps']!=[parent_step] or
            digest(payload['graph'])!=state['graph_sha256']):
        raise ValueError('QUANTUM_CANDIDATE_NOT_OWN_NATIVE_PARENT')
    policy_id,policy=engine.pick(state['teacher'],int(grade[1:]),
                                trial_rng,exclude=seen)
    seen.add(policy_id)
    for group in optim.param_groups:
        group['lr']=policy['lr']
    anchor=copy.deepcopy(candidate).eval()
    for parameter in anchor.parameters():
        parameter.requires_grad_(False)
    exposures={stage:0 for stage in curriculum.RUNGS}
    losses=[]
    for update in range(BLOCK):
        rows,counts=curriculum.batch(grade,graph,policy,trial_rng,
                                    update_index=update,total_updates=BLOCK)
        exposures[counts['rung']]+=counts['current']
        losses.append(inherited._train_focus(
            candidate,optim,anchor,teacher,rows,graph,policy,device))
    if optimizer_receipt(optim)['steps']!=[parent_step+BLOCK]:
        raise ValueError('QUANTUM_NATIVE_OPTIMIZER_UPDATES_MISSING')
    after=origin._score_grade(candidate,graph,grade,device)
    gain=sum(after.values())-sum(before.values())
    credit=2*gain/sum(v['total'] for v in origin._grade_rubric(grade).values())
    engine.observe(state['teacher'],int(grade[1:]),policy_id,credit)
    item={'grade':grade,'attempt':attempt,'parent_step':parent_step,
          'parent_checkpoint_sha256':parent_sha,'candidate_step':parent_step+BLOCK,
          'current_before':before,'current_after':after,
          'gain':gain,'policy_id':policy_id,'teacher_credit':credit,
          'selected':False,'last_loss':losses[-1],
          'three_rung_current_exposures':exposures}
    archive=origin._archive_qualified_candidate(
        out,state,candidate,optim,graph,grade,attempt,parent_sha,before,after)
    if archive is not None:
        item['complete_capability_candidate_archive']={
            'file':archive['file'],'sha256':archive['sha256'],
            'optimizer_step':archive['optimizer_step'],
            'slots':[list(v) for v in archive['slots']]}
    state['attempted_updates']+=BLOCK
    return candidate,optim,item


def _quantum_visit(out,state,model,optimizer,graph,teacher,device):
    grade=origin.scheduler.next_lesson(state['triplets'])
    if grade not in curriculum.GRADES:
        raise ValueError('QUANTUM_UNEXPECTED_LESSON')
    before=origin._score_grade(model,graph,grade,device)
    parent_step=state['optimizer_step']
    parent_sha=state['checkpoint_sha256']
    parent_path=out/state['checkpoint']
    if engine._sha(parent_path)!=parent_sha:
        raise ValueError('QUANTUM_PARENT_CHECKPOINT_DRIFT')
    seed=origin.SEED+state['visits']*71993+state['triplets']['cycles_completed']*1000003
    rng=random.Random(seed)
    best=None
    attempts=[]
    seen=set()
    for attempt in range(1,4):
        candidate,optim,item=_candidate_attempt(
            out,state,grade,attempt,before,graph,teacher,device,
            random.Random(rng.randrange(2**62)),
            parent_path,parent_step,parent_sha,seen)
        attempts.append(item)
        after=item['current_after']
        rank=(item['gain'],tuple(after[k] for k in sorted(after)))
        if item['gain']>0 and (best is None or rank>best[0]):
            best=(rank,candidate,optim,item)
    selected=best is not None
    if selected:
        _,model,optimizer,chosen=best
        chosen['selected']=True
        archived=chosen.get('complete_capability_candidate_archive')
        if archived is None:
            name,sha=engine._checkpoint(out,model,optimizer,graph,{
                'step':parent_step+BLOCK,'grade':grade,'epoch':VERSION,
                'parent_checkpoint_sha256':parent_sha})
        else:
            name,sha=archived['file'],archived['sha256']
        state['checkpoint']=name
        state['checkpoint_sha256']=sha
        state['optimizer_step']=parent_step+BLOCK
        state['retained_updates']+=BLOCK
        _load(out,state,device)
    state['visits']+=1
    for archive in state.get('capability_candidate_archives',[]):
        if (archive['parent_checkpoint_sha256']==parent_sha and
                archive['grade']==grade and
                archive['admission']=='UNDECIDED_UNTIL_WHOLE_GRADE_END'):
            archive['admission']=('RETAINED_CAUSAL_STUDENT' if selected and
                chosen.get('complete_capability_candidate_archive',{}).get('sha256')==archive['sha256']
                else 'REJECTED_FOR_CAUSAL_STUDENT')
    state['candidate_ledger'].extend(attempts)
    state['triplets']=origin.scheduler.record_lesson(
        state['triplets'],grade=grade,parent_step=parent_step,
        parent_checkpoint_sha256=parent_sha,
        result_step=state['optimizer_step'],
        result_checkpoint_sha256=state['checkpoint_sha256'],completed=True)
    receipt={'visit':state['visits'],'grade':grade,'whole_lesson_completed':True,
            'attempts':len(attempts),'accepted':selected,
            'optimizer_step':state['optimizer_step'],
            'checkpoint_sha256':state['checkpoint_sha256'],
            'current_before':before,
            'current_after':chosen['current_after'] if selected else before}
    state['grade_ledger'].append(receipt)
    state['last_run_status']='DURABLE_GRADE_BOUNDARY'
    _save(out,state)
    return model,optimizer,receipt


def run(*,minutes=90,device='mps',stop_requested=lambda:False,reporter=None):
    if device not in ('cpu','mps') or not 0<minutes<=1440:
        raise ValueError('QUANTUM_OPERATOR_INVALID_ARGUMENT')
    if not (RUN/'state.json').is_file():
        raise ValueError('QUANTUM_START_WITH_HUMAN_OPERATOR_PREPARATION')
    with origin._run_lock(RUN):
        state=engine._read(RUN/'state.json')
        _verify_state(state)
        model,optimizer,graph=_load(RUN,state,device)
        library=lessons.TeacherLibrary()
        if origin._golden_screen(RUN,state,model,optimizer,graph,device):
            return status()
        start=time.monotonic()
        while not stop_requested() and time.monotonic()-start<minutes*60:
            phase=state['triplets']['phase']
            if phase=='SELECT_READY':
                current=rubric.score_snapshot(model,graph,
                     optimizer_step=state['optimizer_step'],
                     checkpoint_sha256=state['checkpoint_sha256'],device=device)
                state['triplets']=queue.begin_cycle(state['triplets'],current,rubric.inventory())
                state['last_run_status']='TRIO_LOCKED'
                _save(RUN,state)
            elif phase=='LESSONS':
                origin._require_checkpoint_headroom(RUN,state)
                teacher=origin._teacher(RUN,state,model,device)
                grade=origin.scheduler.next_lesson(state['triplets'])
                if grade in curriculum.GRADES:
                    model,optimizer,record=_quantum_visit(
                        RUN,state,model,optimizer,graph,teacher,device)
                else:
                    model,optimizer,record=origin._visit(
                        RUN,state,model,optimizer,graph,teacher,library,device)
                if reporter:reporter('grade',record,state)
                if origin._golden_screen(RUN,state,model,optimizer,graph,device):
                    return status()
            elif phase=='RETEST_REQUIRED':
                active=state['triplets']['active']
                frozen={}
                for grade in active['grades']:
                    found=origin._score_grade(model,graph,grade,device)
                    if set(found)!=set(active['locked_probe_keys'][grade]):
                        raise ValueError('QUANTUM_LOCKED_RETEST_KEY_DRIFT')
                    frozen.update(found)
                current=rubric.score_snapshot(model,graph,
                     optimizer_step=state['optimizer_step'],
                     checkpoint_sha256=state['checkpoint_sha256'],device=device)
                state['triplets']=queue.finish_retest(
                    state['triplets'],current,rubric.inventory(),locked_retest=frozen)
                state['last_run_status']='TRIO_RETEST_COMPLETE'
                _save(RUN,state)
                if reporter:reporter('retest',state['triplets']['history'][-1],state)
            elif phase=='SOUP_REVIEW_REQUIRED':
                decision=origin._soup_review(RUN,state,model,graph,device)
                if decision=='NO_ELIGIBLE_SOUP':
                    return status()
            elif phase=='STALLED_AWAITING_OPERATOR':
                return status()
            else:
                raise ValueError('QUANTUM_UNKNOWN_TRIPLET_PHASE')
        state['last_run_status']='GRACEFUL_OPERATOR_STOP'
        _save(RUN,state)
        return status()
