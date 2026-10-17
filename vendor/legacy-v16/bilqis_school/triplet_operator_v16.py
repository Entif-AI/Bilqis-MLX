"""Isolated, opt-in successor runner. Human starts training with --triplets.

Every lesson completes on one candidate's FP32 model + native AdamW before
the next grade is scheduled. The v15 training recipe and original run are
read-only ancestors, NEVER modified. This is NOT a golden-model promotion.
"""
from __future__ import annotations

import argparse
import copy
import fcntl
import json
import os
from pathlib import Path
import random
import shutil
import signal
import sys
import time
import uuid
from contextlib import contextmanager

import torch

from bilqis_logic.kernel import digest
from bilqis_micro.run import optimizer_receipt
from bilqis_ref.model import state_hash
from . import engine, lessons, small_domain_lessons as small
from . import time_first_runner_v15 as inherited
from . import graduation_stop_v15 as graduation
from . import current_rubric_v16 as rubric
from . import repaired_lessons_v16 as course
from . import triplet_scheduler_v16 as scheduler
from . import source_rubric_v15 as source_exam
from . import foundation_course_v15 as focused_course
from . import arithmetic, numeric_answer_contract as numeric, spiral_staged_runner as typed
from bilqis_development import kernel as development


VERSION = 'bilqis.primitive-consolidation.triplets/v16'
ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT/'runs/primitive-consolidation-v16-triplets'
BLOCK = 64
SEED = 20261014
SCHEMA = 'bilqis.v16.native-fp32-adamw-triplets/v1'
OPT_IN_MANIFEST=ROOT/'training_versions/v16/triplets-manifest.json'
OPT_IN_SCHEMA='bilqis.v16.triplets-experimental-operator/v1'


def _training_recipe():
    """Snapshot real executable sources, not just scoring-question identity."""
    files={'operator':__file__,'scheduler':scheduler.__file__,
           'repaired_lessons':course.__file__,'current_rubric':rubric.__file__,
           'source_rubric_v15':source_exam.__file__,
           'foundation_course_v15':focused_course.__file__,
           'school50_engine':engine.__file__,
           'typed_loss':typed.__file__,'numeric_readout':numeric.__file__,
           'arithmetic_oracle':arithmetic.__file__,
           'development_oracle':development.__file__}
    return {'v16_sources':{key:engine._sha(Path(path)) for key,path in files.items()},
            'inherited_frozen_v15_recipe':inherited.recipe()}


def _opt_in_authority():
    """Separate explicit authorization, not an escape hatch in v16 scaffold."""
    if OPT_IN_MANIFEST.is_symlink() or not OPT_IN_MANIFEST.is_file():
        raise ValueError('V16_TRIPLETS_NO_REVIEWED_OPT_IN_MANIFEST')
    manifest=engine._read(OPT_IN_MANIFEST)
    if (manifest.get('schema')!=OPT_IN_SCHEMA or
            manifest.get('status')!='EXPERIMENTAL_HUMAN_OPERATOR' or
            manifest.get('human_only') is not True or
            manifest.get('required_flag')!='--triplets' or
            manifest.get('source_recipe_sha256')!=digest(_training_recipe()) or
            manifest.get('current_rubric_sha256')!=digest(rubric.inventory()) or
            manifest.get('frozen_v15_unchanged') is not True or
            manifest.get('golden_stop')!='SAME_CHECKPOINT_FP32_OWN_ADAMW_ALL_CURRENT_100'):
        raise ValueError('V16_TRIPLETS_OPT_IN_AUTHORITY_OR_RECIPE_MISMATCH')
    return manifest


def _frozen_configuration():
    # The manifest contains tuples in-process but lists on disk. Compare the
    # JSON-serializable form, not incompatible pre/post-serialization types.
    return {'block':BLOCK, 'seed':SEED,
            'rubric_sha256':digest(rubric.inventory()),
            'source_manifest':json.loads(json.dumps(rubric.identity())),
            'training_recipe':_training_recipe(),
            'opt_in_manifest_sha256':engine._sha(OPT_IN_MANIFEST)
             if OPT_IN_MANIFEST.is_file() else None}


@contextmanager
def _run_lock(out):
    path = out.with_name(out.name + '.writer.lock')
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('V16_TRIPLETS_ALREADY_HAS_WRITER') from error
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


@contextmanager
def _source_read_lock(source):
    """Prevent a concurrent v15 training writer changing the copied parent."""
    lock=source.with_name(source.name+'.writer.lock')
    # The v15 owner already supplies this lock. A read-only inspection must
    # not create *any* file in the source run if it happens to be missing.
    if lock.is_symlink() or not lock.is_file():
        raise ValueError('V16_TRIPLETS_SOURCE_WRITER_LOCK_NOT_ESTABLISHED')
    fd=os.open(lock,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    try:
        try:
            fcntl.flock(fd,fcntl.LOCK_SH|fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('V16_TRIPLETS_SOURCE_HAS_ACTIVE_TRAINER') from error
        yield
    finally:
        fcntl.flock(fd,fcntl.LOCK_UN)
        os.close(fd)


def _configured_run(run_dir):
    out = Path(run_dir).expanduser().resolve(strict=False)
    if out != RUN.resolve(strict=False):
        raise ValueError('V16_TRIPLETS_REQUIRES_OWN_CANONICAL_RUN')
    return out


def _assert_recipe(state):
    _opt_in_authority()
    if (state.get('schema') != SCHEMA or state.get('version') != VERSION or
            state.get('mode') != '--triplets' or
            state.get('config') != _frozen_configuration()):
        raise ValueError('V16_TRIPLETS_FROZEN_RUN_CONFIG_DRIFT')
    if state.get('phase') == 'GOLDEN_FROZEN':
        raise ValueError('V16_TRIPLETS_GOLDEN_LINEAGE_TERMINAL')
    if state.get('phase') != 'ACQUISITION':
        raise ValueError('V16_TRIPLETS_INVALID_PHASE')


def _load(out, state, device):
    # This inherited utility verifies checkpoint bytes, saved model identity,
    # the graph digest, AND the optimizer's own native step.
    model, optimizer, graph = inherited._load_student(out, state, device)
    if any(p.dtype != torch.float32 for p in model.parameters()):
        raise ValueError('V16_TRIPLETS_STUDENT_MUST_BE_FP32')
    return model, optimizer, graph


def _validate_v15_source_recipe(state):
    """Source full-state hashes alone cannot certify a frozen v15 recipe."""
    if not isinstance(state.get('config'),dict):
        raise ValueError('V16_TRIPLETS_SOURCE_MISSING_FROZEN_CONFIG')
    saved=state['config']
    try:
        frozen=inherited.configuration(block=saved['block'],seed=saved['seed'],
                          champion_boundary=saved['champion_boundary'])
        inherited._assert_frozen(state,frozen)
    except (KeyError,ValueError) as error:
        raise ValueError('V16_TRIPLETS_SOURCE_V15_RECIPE_DRIFT') from error
    origin=state.get('v15_origin')
    if (not isinstance(origin,dict) or
            origin.get('next_recipe')!=saved['recipe'] or
            type(state.get('optimizer_step')) is not int or
            type(origin.get('source_optimizer_step')) is not int or
            state['optimizer_step'] < origin['source_optimizer_step']):
        raise ValueError('V16_TRIPLETS_SOURCE_V15_ORIGIN_DRIFT')
    return True


def prepare(*,source_run,run_dir=RUN):
    """A separately versioned full-state copy. No training or source writes."""
    _opt_in_authority()
    source = Path(source_run).expanduser().resolve(strict=True)
    out = _configured_run(run_dir)
    if (out.exists() or source == out or
            source in out.parents or out in source.parents or
            not (source/'state.json').is_file()):
        raise ValueError('V16_TRIPLETS_BAD_SOURCE_OR_ALREADY_PREPARED')
    out.parent.mkdir(parents=True,exist_ok=True)
    with _run_lock(out):
        if out.exists():
            raise ValueError('V16_TRIPLETS_SUCCESSOR_ALREADY_PREPARED')
        with _source_read_lock(source):
            return _prepare_locked(source, out)


def _reconcile_staging(stage,marker):
    """Retry only our own, identical, unpublished preparation staging dir."""
    if stage.is_symlink():
        raise ValueError('V16_TRIPLETS_UNSAFE_PREPARATION_STAGING')
    if stage.exists():
        if not stage.is_dir() or not (stage/'_stage-ownership.json').is_file():
            raise ValueError('V16_TRIPLETS_UNRECOGNIZED_STAGING_NEEDS_REVIEW')
        prior=engine._read(stage/'_stage-ownership.json')
        if prior!=marker:
            raise ValueError('V16_TRIPLETS_STAGING_FROM_DIFFERENT_SOURCE')
        # Only an unpublished, marked successor scratch directory is removed.
        # The v15 parent and already-published v16 state are never targets.
        shutil.rmtree(stage)
    stage.mkdir(parents=False,exist_ok=False)
    engine._atomic_json(stage/'_stage-ownership.json',marker)


def _prepare_locked(source, out):
    source_state = engine._read(source/'state.json')
    if (source_state.get('version') != inherited.VERSION or
            source_state.get('phase') != 'ACQUISITION' or
            (source/'sealed-evaluation.json').exists()):
        raise ValueError('V16_TRIPLETS_SOURCE_NOT_UNSEALED_V15')
    _validate_v15_source_recipe(source_state)
    original_state_sha = engine._sha(source/'state.json')
    model, optimizer, graph = inherited._load_student(source,source_state,'cpu')
    if any(p.dtype != torch.float32 for p in model.parameters()):
        raise ValueError('V16_TRIPLETS_SOURCE_NOT_FP32')
    if optimizer_receipt(optimizer)['steps'] != [source_state['optimizer_step']]:
        raise ValueError('V16_TRIPLETS_SOURCE_NOT_NATIVE_ADAMW')
    parent = source/source_state['checkpoint']
    soup_name = source_state['frozen_soup']['file']
    soup_path = source/soup_name
    if (engine._sha(parent) != source_state['checkpoint_sha256'] or
            engine._sha(soup_path) != source_state['frozen_soup']['sha256'] or
            engine._sha(source/'state.json') != original_state_sha):
        raise ValueError('V16_TRIPLETS_SOURCE_CHANGED_DURING_PREPARE')
    # A crashed preparation must never leave the FINAL directory present but
    # unbootable. Stage and verify privately, then publish with atomic rename.
    stage=out.with_name('.'+out.name+'.preparing')
    _reconcile_staging(stage,{
        'schema':'bilqis.v16.triplets.preparation-staging/v1',
        'source_state_sha256':original_state_sha,
        'source_checkpoint_sha256':source_state['checkpoint_sha256'],
        'destination':str(out)})
    try:
        shutil.copyfile(parent, stage/parent.name)
        shutil.copyfile(soup_path, stage/soup_name)
        if (engine._sha(stage/parent.name) != source_state['checkpoint_sha256'] or
                engine._sha(stage/soup_name) != source_state['frozen_soup']['sha256']):
            raise ValueError('V16_TRIPLETS_COPY_HASH_MISMATCH')
        state = {
            'schema':SCHEMA, 'version':VERSION, 'mode':'--triplets',
            'phase':'ACQUISITION','last_run_status':'PREPARED_NOT_TRAINED',
            'optimizer_step':source_state['optimizer_step'],
            'checkpoint':parent.name,
            'checkpoint_sha256':source_state['checkpoint_sha256'],
            'graph_sha256':source_state['graph_sha256'],
            'teacher':copy.deepcopy(source_state['teacher']),
            'frozen_soup':copy.deepcopy(source_state['frozen_soup']),
            'current_teacher':None,
            'source':{'run':str(source),'state_sha256':original_state_sha,
                      'checkpoint_sha256':source_state['checkpoint_sha256'],
                      'model_sha256':state_hash(model),
                      'optimizer_step':source_state['optimizer_step']},
            'config':_frozen_configuration(),
            'triplets':scheduler.new_state(rubric.PROGRAM,rubric.inventory()),
            'visits':0, 'attempted_updates':0,'retained_updates':0,
            'grade_ledger':[],'candidate_ledger':[], 'soup_history':[],
            'golden_screen':None}
        engine._atomic_json(stage/'state.json',state)
        restored = engine._read(stage/'state.json')
        _assert_recipe(restored)
        _load(stage,restored,'cpu')
        if engine._sha(source/'state.json')!=original_state_sha:
            raise ValueError('V16_TRIPLETS_SOURCE_CHANGED_BEFORE_ATOMIC_PUBLISH')
        os.replace(stage,out)
        fd=os.open(out.parent,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
        return status(out)
    except BaseException:
        # Ordinary failures clean scratch; a hard kill can leave the marker
        # for exact-identity reconciliation on the next explicit prepare.
        if stage.is_dir() and not stage.is_symlink():
            shutil.rmtree(stage)
        raise


def status(run_dir=RUN):
    out = _configured_run(run_dir)
    if not (out/'state.json').is_file():
        return {'status':'NOT_PREPARED','mode':'--triplets',
                'run_dir':str(out),'eligible_grades':len(rubric.PROGRAM),
                'held_semantics':list(course.HELD_G18_EXTENSIONS)}
    state = engine._read(out/'state.json')
    if state.get('phase')!='GOLDEN_FROZEN':
        _assert_recipe(state)
    current = state['triplets']
    last_retest=next((item for item in reversed(current['history'])
                      if 'after' in item),None)
    return {'status':state['last_run_status'],'phase':state['phase'],
            'optimizer_step':state['optimizer_step'],
            'checkpoint_sha256':state['checkpoint_sha256'],
            'visits':state['visits'],'cycles_completed':current['cycles_completed'],
            'triplets_phase':current['phase'],
            'locked_three':(current['active'] or {}).get('grades'),
            'next_lesson':scheduler.next_lesson(current),
            'stagnant_rounds':current['stagnant_rounds'],
            'soup_reviews':len(state['soup_history']),
            'last_triplet_retest':last_retest,
            'last_grade_visit':state['grade_ledger'][-1]
            if state['grade_ledger'] else None,
            'source_evidence':'CURRENT_TAUGHT_ACQUISITION_NOT_HISTORICAL_G24',
            'held_semantics':list(course.HELD_G18_EXTENSIONS),
            'historical_G24_is_not_a_current_probe':True}


def preview(*,source_run):
    """Read-only preview of first three against the live source checkpoint.

    Does NOT prepare a successor, train, write a model, promote a teacher, or
    change the old state. Lock acquisition keeps concurrent v15 writes out.
    """
    source=Path(source_run).expanduser().resolve(strict=True)
    if not (source/'state.json').is_file():
        raise ValueError('V16_TRIPLETS_NO_SOURCE_FOR_PREVIEW')
    with _source_read_lock(source):
        state=engine._read(source/'state.json')
        source_state_sha=engine._sha(source/'state.json')
        if state.get('version')!=inherited.VERSION:
            raise ValueError('V16_TRIPLETS_PREVIEW_SOURCE_NOT_V15')
        model,own_adamw,graph=inherited._load_student(source,state,'cpu')
        if any(p.dtype!=torch.float32 for p in model.parameters()):
            raise ValueError('V16_TRIPLETS_PREVIEW_SOURCE_NOT_FP32')
        if optimizer_receipt(own_adamw)['steps']!=[state['optimizer_step']]:
            raise ValueError('V16_TRIPLETS_PREVIEW_WRONG_NATIVE_ADAMW')
        scores=rubric.score_snapshot(model,graph,
            optimizer_step=state['optimizer_step'],
            checkpoint_sha256=state['checkpoint_sha256'],device='cpu')
        totals=scheduler._check_snapshot(scores,rubric.inventory(),rubric.PROGRAM)
        chosen=scheduler.selection(scores,rubric.inventory(),rubric.PROGRAM)
        if engine._sha(source/'state.json')!=source_state_sha:
            raise ValueError('V16_TRIPLETS_SOURCE_CHANGED_WHILE_PREVIEWING')
        return {'status':'READ_ONLY_NOT_TRAINED',
                'source_step':state['optimizer_step'],
                'source_checkpoint_sha256':state['checkpoint_sha256'],
                'rubric_sha256':digest(rubric.inventory()),
                'grade_aggregates':totals,
                'proposed_first_three':list(chosen),
                'this_is_not_a_graduation_receipt':True,
                'held_semantics':list(course.HELD_G18_EXTENSIONS)}


def _teacher(out, state, student, device):
    choice=state['current_teacher']
    if choice is None:
        return inherited._soup(out,state,student,device)
    source=out/choice['file']
    if (source.is_symlink() or not source.is_file() or
            engine._sha(source)!=choice['sha256']):
        raise ValueError('V16_TRIPLETS_SOUP_SOURCE_CHANGED')
    payload=torch.load(source, map_location='cpu', weights_only=True)
    if (payload.get('graph_sha256')!=state['graph_sha256'] or
            payload.get('recipe')!='V16_STALL_SOUP_PURE_TEACHER_V1'):
        raise ValueError('V16_TRIPLETS_SOUP_MANIFEST_MISMATCH')
    result=copy.deepcopy(student)
    result.load_state_dict(payload['weights'], strict=True)
    result.to(device).eval()
    for p in result.parameters():p.requires_grad_(False)
    if state_hash(result)!=choice['model_sha256']:
        raise ValueError('V16_TRIPLETS_SOUP_TEACHER_DRIFT')
    return result


def _grade_rubric(grade):
    return {key: entry for key,entry in rubric.inventory().items()
            if key.startswith(grade+':')}


def _score_grade(model,graph,grade,device):
    return rubric.score_current(model,graph,_grade_rubric(grade),device=device)


def _require_checkpoint_headroom(out,state,*,max_candidate_archives=4):
    """Stop BEFORE training if whole-AdamW preservation could fill the disk.

    Never prune unique peaks or hard-won ties to satisfy this budget. Check
    again every durable grade, using the actual native checkpoint byte size.
    """
    checkpoint=out/state['checkpoint']
    if checkpoint.is_symlink() or not checkpoint.is_file():
        raise ValueError('V16_TRIPLETS_MISSING_NATIVE_CHECKPOINT_FOR_BUDGET')
    required=max(2*1024**3,checkpoint.stat().st_size*(max_candidate_archives+2))
    free=shutil.disk_usage(out).free
    if free < required:
        raise ValueError('V16_TRIPLETS_LOW_DISK_REFUSE_BEFORE_LESSON:free='+str(free)+
                         ':required='+str(required))
    return {'free':free,'required':required,
            'checkpoint_bytes':checkpoint.stat().st_size}


def _candidate_champion_slots(state,grade,before,after):
    """Capture true per-capability improvements and perfect-score ties.

    A net-losing attempt can still win a capability. Never throw that complete
    model+own-AdamW state away merely because aggregate admission rejected it.
    """
    tracked=state.setdefault('capability_champions',{}).setdefault(grade,{})
    totals={key:entry['total'] for key,entry in _grade_rubric(grade).items()}
    slots=[]
    for key,score in sorted(after.items()):
        previous=tracked.get(key)
        best=max(before[key],previous['correct'] if previous else 0)
        if score>best or (previous and score==best==totals[key]):
            slots.append((key,score,'NEW_PEAK' if score>best else 'PERFECT_TIE'))
    return slots


def _archive_qualified_candidate(out,state,candidate,optim,graph,grade,
                                 attempt,parent_sha,before,after):
    slots=_candidate_champion_slots(state,grade,before,after)
    if not slots:return None
    name,sha=engine._checkpoint(out,candidate,optim,graph,{
        'step':state['optimizer_step']+BLOCK,'grade':grade,'epoch':VERSION,
        'kind':'COMPLETE_FP32_OWN_ADAMW_CAPABILITY_CANDIDATE',
        'attempt':attempt,'parent_checkpoint_sha256':parent_sha,
        'triplet_cycle':state['triplets']['cycles_completed']+1,
        'current_rubric_sha256':digest(rubric.inventory()),
        'candidate_slots':[slot[0] for slot in slots]})
    record={'file':name,'sha256':sha,'model_sha256':state_hash(candidate),
            'optimizer_step':state['optimizer_step']+BLOCK,
            'parent_checkpoint_sha256':parent_sha,'grade':grade,
            'attempt':attempt,'slots':slots,
            'native_optimizer_receipt':optimizer_receipt(optim),
            'admission':'UNDECIDED_UNTIL_WHOLE_GRADE_END'}
    state.setdefault('capability_candidate_archives',[]).append(record)
    entries=state.setdefault('capability_champions',{}).setdefault(grade,{})
    for key,score,reason in slots:
        previous=entries.get(key)
        if reason=='NEW_PEAK':
            entries[key]={'correct':score,'total':_grade_rubric(grade)[key]['total'],
                          'checkpoint_sha256':sha,'file':name,'perfect_ties':[]}
        else:
            previous['perfect_ties'].append({'file':name,'sha256':sha})
    return record


def _visit(out,state,model,optimizer,graph,teacher,library,device):
    grade=scheduler.next_lesson(state['triplets'])
    if grade is None or grade not in rubric.PROGRAM:
        raise ValueError('V16_TRIPLETS_INVALID_QUEUED_GRADE')
    parent_step=state['optimizer_step']
    parent_sha=state['checkpoint_sha256']
    parent_path=out/state['checkpoint']
    if engine._sha(parent_path)!=parent_sha:
        raise ValueError('V16_TRIPLETS_CHANGED_PARENT')
    before=_score_grade(model,graph,grade,device)
    rng=random.Random(SEED+state['visits']*71993+
                      state['triplets']['cycles_completed']*1000003)
    numeric_grade=2001+small.GRADES.index(grade) if grade.startswith('B') else int(grade[1:])
    focused=grade in ('G11','G18','G20','G15','G22')
    count=3 if grade in course.ENABLED else 1
    best=None
    attempts=[]
    seen=set()
    for attempt in range(1,count+1):
        candidate,optim,payload=engine.load_checkpoint(parent_path)
        engine._device(candidate,optim,device)
        if (optimizer_receipt(optim)['steps']!=[parent_step] or
                digest(payload['graph'])!=state['graph_sha256']):
            raise ValueError('V16_TRIPLETS_ATTEMPT_NOT_NATIVE_SAME_PARENT')
        trial_rng=random.Random(rng.randrange(2**62))
        policy_id,policy=engine.pick(state['teacher'],numeric_grade,
                                     trial_rng,exclude=seen)
        seen.add(policy_id)
        for group in optim.param_groups:group['lr']=policy['lr']
        anchor=copy.deepcopy(candidate).eval()
        for p in anchor.parameters():p.requires_grad_(False)
        losses=[]
        for update in range(BLOCK):
            if grade in course.ENABLED:
                rows,counts=course.batch(grade,library,graph,policy,trial_rng,
                                          update_index=update,total_updates=BLOCK)
                losses.append(inherited._train_focus(candidate,optim,anchor,
                                                      teacher,rows,graph,policy,device))
            elif focused:
                rows,counts=inherited._focus_batch(grade,library,graph,policy,trial_rng)
                losses.append(inherited._train_focus(candidate,optim,anchor,
                                                      teacher,rows,graph,policy,device))
            elif grade.startswith('B'):
                rows,counts=small.compile_batch(grade,library,graph,trial_rng,
                                                 method='standard')
                losses.append(inherited._train_small_step(candidate,optim,anchor,
                                                           teacher,rows,graph,policy,device))
            else:
                rows,counts=lessons.compose_batch(library,int(grade[1:]),
                                                  policy,graph,trial_rng)
                losses.append(engine._train(candidate,optim,anchor,graph,rows,
                                             counts,policy,device,
                                             consensus_teacher=teacher,
                                             consensus_weight=engine.CONSOLIDATION_WEIGHT))
        if optimizer_receipt(optim)['steps']!=[parent_step+BLOCK]:
            raise ValueError('V16_TRIPLETS_ATTEMPT_OPTIMIZER_STEP_MISMATCH')
        after=_score_grade(candidate,graph,grade,device)
        gain=sum(after.values())-sum(before.values())
        teacher_credit=2*gain/sum(entry['total'] for entry in _grade_rubric(grade).values())
        engine.observe(state['teacher'],numeric_grade,policy_id,teacher_credit)
        item={'grade':grade,'attempt':attempt,'parent_step':parent_step,
              'parent_checkpoint_sha256':parent_sha,
              'candidate_step':parent_step+BLOCK,'current_before':before,
              'current_after':after,'gain':gain,'policy_id':policy_id,
              'teacher_credit':teacher_credit,'selected':False,
              'last_loss':losses[-1]}
        archive=_archive_qualified_candidate(
            out,state,candidate,optim,graph,grade,attempt,parent_sha,before,after)
        if archive is not None:
            item['complete_capability_candidate_archive']={
                'file':archive['file'],'sha256':archive['sha256'],
                'optimizer_step':archive['optimizer_step'],
                'slots':archive['slots']}
        attempts.append(item)
        state['attempted_updates']+=BLOCK
        if gain>0 and (best is None or
                        (gain,tuple(after[k] for k in sorted(after)))>best[0]):
            best=((gain,tuple(after[k] for k in sorted(after))),candidate,optim,item)
    selected=best is not None
    if selected:
        _,model,optimizer,chosen=best
        chosen['selected']=True
        if 'complete_capability_candidate_archive' in chosen:
            ref=chosen['complete_capability_candidate_archive']
            name,sha=ref['file'],ref['sha256']
        else:
            name,sha=engine._checkpoint(out,model,optimizer,graph,{
                'step':parent_step+BLOCK,'grade':grade,'epoch':VERSION,
                'parent_checkpoint_sha256':parent_sha,
                'triplet_cycle':state['triplets']['cycles_completed']+1})
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
    state['triplets']=scheduler.record_lesson(
        state['triplets'],grade=grade,parent_step=parent_step,
        parent_checkpoint_sha256=parent_sha,
        result_step=state['optimizer_step'],
        result_checkpoint_sha256=state['checkpoint_sha256'],completed=True)
    receipt={'visit':state['visits'],'grade':grade,'whole_lesson_completed':True,
             'attempts':len(attempts),'accepted':selected,
             'optimizer_step':state['optimizer_step'],
             'checkpoint_sha256':state['checkpoint_sha256'],
             'current_before':before,
             'current_after':chosen['current_after'] if selected else before,
             'historical_G24_only':'ARCHIVAL_NOT_ADMISSION_OR_REWARD'}
    state['grade_ledger'].append(receipt)
    state['last_run_status']='DURABLE_GRADE_BOUNDARY'
    engine._atomic_json(out/'state.json',state)
    return model,optimizer,receipt


def _golden_screen(out,state,model,optimizer,graph,device):
    if (state['golden_screen'] and
            state['golden_screen'].get('optimizer_step')==state['optimizer_step'] and
            state['golden_screen'].get('checkpoint_sha256')==state['checkpoint_sha256']):
        return False
    scores,failing=_screen_device(model,graph,device)
    if failing is not None:
        state['golden_screen']={'optimizer_step':state['optimizer_step'],
                                'checkpoint_sha256':state['checkpoint_sha256'],
                                'first_failed':failing}
        engine._atomic_json(out/'state.json',state)
        return False
    # A perfect check is replayed on the exact saved complete FP32+AdamW pair.
    reread,own_optimizer,read_graph=_load(out,state,device)
    second=rubric.score_snapshot(reread,read_graph,
        optimizer_step=state['optimizer_step'],
        checkpoint_sha256=state['checkpoint_sha256'],device=device)
    if not all(entry['correct']==entry['total']
               for entry in second['metrics'].values()):
        raise ValueError('V16_TRIPLETS_GOLDEN_DOUBLE_CHECK_FAILED')
    if (optimizer_receipt(own_optimizer)['steps']!=[state['optimizer_step']] or
            engine._sha(out/state['checkpoint'])!=state['checkpoint_sha256']):
        raise ValueError('V16_TRIPLETS_GOLDEN_NATIVE_ADAMW_NOT_FROZEN')
    state['golden']={'kind':'SAME_CHECKPOINT_ALL_CURRENT_100',
                     'rubric_sha256':digest(rubric.inventory()),
                     'optimizer_step':state['optimizer_step'],
                     'checkpoint':state['checkpoint'],
                     'checkpoint_sha256':state['checkpoint_sha256'],
                     'model_sha256':state_hash(reread),
                     'graph_sha256':digest(read_graph),
                     'metrics':second['metrics'],
                     'note':'CURRENT_SOURCE_ACQUISITION_NOT_UNSEEN_GENERALIZATION'}
    state['phase']='GOLDEN_FROZEN'
    state['last_run_status']='GOLDEN_FROZEN_TERMINAL'
    engine._atomic_json(out/'state.json',state)
    if engine._read(out/'state.json')['golden']!=state['golden']:
        raise ValueError('V16_TRIPLETS_GOLDEN_NOT_DURABLE')
    return True


def _screen_device(model,graph,device):
    """Fail fast, same saved model step; never use mixed-step G24 extrema."""
    results={}
    for key,entry in sorted(rubric.inventory().items()):
        measured=rubric.score_current(model,graph,{key:entry},device=device)[key]
        if measured!=entry['total']:
            return None,{'key':key,'correct':measured,'total':entry['total']}
        results[key]=measured
    return results,None


def _publish_soup_teacher(out,state,student,winner):
    """Idempotent verified soup publication across crash-before-state-save.

    A prepared artifact may survive a crash as an orphan; reusing it is safe
    only when its exact MODEL identity and source graph match the recomputed
    winner. Otherwise fail closed rather than clobber it or stall forever.
    """
    name=f'soup-teacher-cycle-{state["triplets"]["cycles_completed"]:04d}.pt'
    destination=out/name
    model_sha=state_hash(winner)
    if not destination.exists():
        temp=out/('.'+name+'.'+uuid.uuid4().hex+'.tmp')
        try:
            with temp.open('xb') as stream:
                torch.save({'recipe':'V16_STALL_SOUP_PURE_TEACHER_V1',
                            'graph_sha256':state['graph_sha256'],
                            'weights':{key:value.detach().cpu().clone()
                                       for key,value in winner.state_dict().items()}},stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp,destination)
            dfd=os.open(out,os.O_RDONLY)
            try:os.fsync(dfd)
            finally:os.close(dfd)
        finally:
            temp.unlink(missing_ok=True)
    if destination.is_symlink() or not destination.is_file():
        raise ValueError('V16_TRIPLETS_SOUP_UNSAFE_EXISTING_ARTIFACT')
    payload=torch.load(destination,map_location='cpu',weights_only=True)
    if (payload.get('recipe')!='V16_STALL_SOUP_PURE_TEACHER_V1' or
            payload.get('graph_sha256')!=state['graph_sha256']):
        raise ValueError('V16_TRIPLETS_SOUP_RESUME_MANIFEST_DRIFT')
    sample=copy.deepcopy(student)
    sample.load_state_dict(payload['weights'],strict=True)
    if state_hash(sample)!=model_sha:
        raise ValueError('V16_TRIPLETS_SOUP_RESUME_IS_DIFFERENT_CANDIDATE')
    return {'file':name,'sha256':engine._sha(destination),
            'model_sha256':model_sha,'teacher_only':True}


def _soup_review(out,state,student,graph,device):
    """After two stalled COMPLETE trios, evaluate weight soup as TEACHER only."""
    prior=_teacher(out,state,student,device)
    contenders=[('FROZEN_BASE_TEACHER',prior)]
    for alpha in (.25,.5,.75):
        mixed=copy.deepcopy(student).eval()
        with torch.no_grad():
            for mine,theirs in zip(mixed.parameters(),prior.parameters(),strict=True):
                if (mine.shape!=theirs.shape or mine.dtype!=torch.float32 or
                        theirs.dtype!=torch.float32):
                    raise ValueError('V16_TRIPLETS_SOUP_GEOMETRY_MISMATCH')
                mine.mul_(alpha).add_(theirs,alpha=1-alpha)
        for parameter in mixed.parameters():parameter.requires_grad_(False)
        contenders.append((f'SOUP_{alpha}',mixed))
    entries=rubric.inventory()
    def grade(model):
        scores=rubric.score_current(model,graph,entries,device=device)
        return sum(scores.values()),scores
    parent_score,_=grade(prior)
    student_score,_=grade(student)
    best=(max(parent_score,student_score),'NO_PROMOTION',None,None)
    evaluations=[]
    for name,model in contenders:
        score,points=grade(model)
        evaluations.append({'name':name,'current_correct':score,
                            'current_total':sum(e['total'] for e in entries.values())})
        if name!='FROZEN_BASE_TEACHER' and score>best[0]:
            best=(score,name,model,points)
    if best[1]=='NO_PROMOTION':
        decision='NO_ELIGIBLE_SOUP'
        evidence='NO_GAIN_VERSUS_BOTH_STUDENT_AND_FROZEN_TEACHER'
    else:
        state['current_teacher']=_publish_soup_teacher(
            out,state,student,best[2])
        _teacher(out,state,student,device)
        decision='TEACHER_ONLY'
        evidence=state['current_teacher']['sha256']
    state['soup_history'].append({
        'cycle':state['triplets']['cycles_completed'],'decision':decision,
        'candidate_evaluations':evaluations,
        'student_optimizer_unchanged':True,'evidence_ref':evidence})
    state['triplets']=scheduler.soup_review_completed(
        state['triplets'],outcome=decision,evidence_ref=evidence)
    engine._atomic_json(out/'state.json',state)
    return decision


def run(*,run_dir=RUN,device='mps',minutes=90,stop_requested=lambda:False,
        reporter=None):
    if device not in ('mps','cpu') or not 0<minutes<=1440:
        raise ValueError('V16_TRIPLETS_INVALID_RUN_OPTIONS')
    out=_configured_run(run_dir)
    if not (out/'state.json').is_file():
        raise ValueError('V16_TRIPLETS_NOT_PREPARED')
    with _run_lock(out):
        state=engine._read(out/'state.json')
        _assert_recipe(state)
        model,optimizer,graph=_load(out,state,device)
        library=lessons.TeacherLibrary()
        # Preserve the terminal golden stop even if the initial v15-derived
        # checkpoint already satisfies the successor syllabus. No optional
        # contender or soup probes may run after its complete qualification.
        if _golden_screen(out,state,model,optimizer,graph,device):
            return status(out)
        started=time.monotonic()
        while True:
            if stop_requested() or time.monotonic()-started>=minutes*60:
                state['last_run_status']='GRACEFUL_OPERATOR_STOP'
                engine._atomic_json(out/'state.json',state)
                return status(out)
            phase=state['triplets']['phase']
            if phase=='SELECT_READY':
                current=rubric.score_snapshot(model,graph,
                    optimizer_step=state['optimizer_step'],
                    checkpoint_sha256=state['checkpoint_sha256'],device=device)
                state['triplets']=scheduler.begin_cycle(
                    state['triplets'],current,rubric.inventory())
                state['last_run_status']='TRIO_LOCKED'
                engine._atomic_json(out/'state.json',state)
            elif phase=='LESSONS':
                _require_checkpoint_headroom(out,state)
                teacher=_teacher(out,state,model,device)
                model,optimizer,record=_visit(
                    out,state,model,optimizer,graph,teacher,library,device)
                if reporter:reporter('grade',record,state)
                if _golden_screen(out,state,model,optimizer,graph,device):
                    return status(out)
            elif phase=='RETEST_REQUIRED':
                active=state['triplets']['active']
                # Independently retest the frozen three lesson probes before
                # scanning the full CURRENT corpus for the *next* selection.
                locked_retest={}
                for grade in active['grades']:
                    actual=_score_grade(model,graph,grade,device)
                    if set(actual)!=set(active['locked_probe_keys'][grade]):
                        raise ValueError('V16_TRIPLETS_LOCKED_RETEST_QUESTION_SET_DRIFT')
                    locked_retest.update(actual)
                current=rubric.score_snapshot(model,graph,
                    optimizer_step=state['optimizer_step'],
                    checkpoint_sha256=state['checkpoint_sha256'],device=device)
                state['triplets']=scheduler.finish_retest(
                    state['triplets'],current,rubric.inventory(),
                    locked_retest=locked_retest)
                state['last_run_status']='TRIPLET_RETEST_COMPLETE'
                engine._atomic_json(out/'state.json',state)
                if reporter:reporter('retest',state['triplets']['history'][-1],state)
            elif phase=='SOUP_REVIEW_REQUIRED':
                _require_checkpoint_headroom(out,state)
                _soup_review(out,state,model,graph,device)
            elif phase=='STALLED_AWAITING_OPERATOR':
                state['last_run_status']='STALLED_AWAITING_OPERATOR_REVIEW'
                engine._atomic_json(out/'state.json',state)
                return status(out)
            else:
                raise ValueError('V16_TRIPLETS_UNKNOWN_PHASE')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--triplets',action='store_true',required=True)
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--preview',action='store_true')
    parser.add_argument('--source-run',type=Path)
    parser.add_argument('--train',action='store_true')
    parser.add_argument('--status',action='store_true')
    parser.add_argument('--device',choices=('cpu','mps'),default='mps')
    parser.add_argument('--minutes',type=float,default=90)
    args=parser.parse_args(argv)
    if sum(map(bool,(args.prepare,args.train,args.status,args.preview)))!=1:
        parser.error('choose exactly one of --prepare, --train, --status, --preview')
    if args.source_run is not None and not (args.prepare or args.preview):
        parser.error('--source-run applies only to --prepare or --preview')
    if (args.prepare or args.preview) and args.source_run is None:
        parser.error('--prepare/--preview requires --source-run')
    if args.status:
        result=status()
    elif args.preview:
        result=preview(source_run=args.source_run)
    elif args.prepare:
        result=prepare(source_run=args.source_run)
    else:
        stopped={'requested':False}
        def stop(*_):stopped['requested']=True
        signal.signal(signal.SIGINT,stop)
        result=run(device=args.device,minutes=args.minutes,
                   stop_requested=lambda:stopped['requested'],
                   reporter=lambda kind,record,state:print(json.dumps(
                       {'kind':kind,'record':record,'step':state['optimizer_step']},
                       sort_keys=True),flush=True))
    print(json.dumps(result,indent=2,sort_keys=True))


if __name__ == '__main__':
    main()
