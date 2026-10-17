"""Isolated, human-launched v12 G-mechanics acquisition research continuation.

The research student inherits v11's real FP32 model + AdamW moments. It never
promotes student weights, provisional acquisition results, grade champions or
soup votes back to the stopped canonical v11 lineage. The mature historical G
candidate gate is reported as a counterfactual, not silently replaced.

Run `--initialize-only`, then manually and visibly launch `--train`.
Stop after a grade boundary or at the wall-clock ceiling. No sealed exam.
"""
from __future__ import annotations

import argparse
import copy
import fcntl
import json
import os
from pathlib import Path
import random
import signal
import time

import torch

from bilqis_logic.kernel import digest
from bilqis_micro.run import optimizer_receipt
from bilqis_ref.model import state_hash
from . import engine, lessons, time_first_runner as old, small_domain_lessons as bcourse
from . import g_primitives_v12 as course, numeric_answer_contract as numeric
from . import spiral_staged_runner as staged


VERSION='bilqis.school50.g-primitives-training/v1'
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT.parent/'bilqis-school50-time-first-v11/runs/school50-time-first-v11'
SOUP=ROOT.parent/'bilqis-school50-time-first-v11/runs/school50-v11-soup-study-refine-20261013'
RUN=ROOT/'runs/school50-g-primitives-v12'
SOURCE_STATE_SHA256='cb70797db9978e98dc13ae74558b8c81ea5839c31b4b7787aaf262276e7b636e'
SOUP_WEIGHTS_SHA256='868f982a5ce7b682ec695210d837ebef8407db421c629ea1a7832fcccd7fd8de'
LESSONS=(
    ('G11','primitive'),('G12','primitive'),('G13','primitive'),
    ('G15','primitive'),('G18','primitive'),('G20','primitive'),
    ('G14','composition'),('G20','composition'),
    ('G21','composition'),('G22','composition'),
)
REHEARSAL_GRADES=(1,2,3,4,5,6,7,8,9,10,16,19)
_stop=False


def recipe():
    return {key:engine._sha(path) for key,path in {
        'runner':__file__,
        'primitive_lessons':course.__file__,
        'school50_engine':engine.__file__,
        'school50_lessons':lessons.__file__,
        'staged_typed_loss':staged.__file__,
        'numeric_readout':numeric.__file__,
        'b_replay':bcourse.__file__,
    }.items()}


def compile_batch(grade,stage,graph,library,rng):
    """All exposed current rows once, twelve old B and four direct numbers."""
    current=course.rows(grade,stage=stage)
    if not current:raise ValueError('V12_NO_STAGE_LESSONS')
    if not hasattr(library,'v12_b_panels'):
        library.v12_b_panels={bgrade:(
            bcourse.panel(bgrade,graph,fold='primary')+
            bcourse.panel(bgrade,graph,fold='confirm'))
            for bgrade in bcourse.GRADES}
        library.v12_b_numeric=(bcourse.numeric_panel(graph,fold='primary')+
                              bcourse.numeric_panel(graph,fold='confirm'))
    bgrade=rng.choice(bcourse.GRADES)
    bitems=copy.deepcopy(library.v12_b_panels[bgrade])
    numeric_rows=copy.deepcopy(library.v12_b_numeric)
    for row in bitems+numeric_rows:
        row['course_meta']['tranche']='b_rehearsal'
        row['course_meta']['retention']=True
    result=current+bitems+numeric_rows
    old_count=32-len(result)
    if old_count<0:raise ValueError('V12_OVERFULL_PRIMITIVE_BATCH')
    if not hasattr(library,'v12_old_bank'):
        bank=[];seeded=random.Random(4012026)
        for origin in REHEARSAL_GRADES:
            for _ in range(4):
                for trial in range(256):
                    proposal=library.one(origin,seeded,depth=2,prefer_composition=False)
                    if isinstance(proposal,list) or any(x['id']==proposal['id'] for x in bank):
                        continue
                    try:lessons.valid_rows([proposal],graph)
                    except ValueError:continue
                    proposal['answer_kind']='evidence'
                    proposal['course_meta']={'tranche':'g_rehearsal',
                                              'grade':f'G{origin:02d}',
                                              'retention':True,
                                              'assessment_role':'HISTORIC_REHEARSAL'}
                    bank.append(proposal);break
                else:raise ValueError('V12_CANNOT_BUILD_HISTORIC_REHEARSAL_BANK')
        library.v12_old_bank=bank
    origins=list(REHEARSAL_GRADES)
    rng.shuffle(origins)
    seen={row['id'] for row in result}
    selected=[]
    shuffled=copy.deepcopy(library.v12_old_bank)
    rng.shuffle(shuffled)
    for row in shuffled:
        if row['id'] in seen:continue
        selected.append(row)
        seen.add(row['id'])
        if len(selected)==old_count:break
    if len(selected)!=old_count:raise ValueError('V12_HISTORIC_REHEARSAL_EXHAUSTED')
    result.extend(selected)
    if len(result)!=32 or len({row['id'] for row in result})!=32:
        raise ValueError('V12_BATCH_CARDINALITY_OR_DUPLICATE')
    course.validate_rows(current,graph)
    return result


def _assert_source():
    raw=(SOURCE/'state.json').read_bytes()
    state=json.loads(raw)
    if (state.get('version')!=old.VERSION or
            state.get('last_run_status')!='TIME_BUDGET_EXHAUSTED' or
            state.get('phase')!='ACQUISITION' or
            state.get('passes_completed')!=24 or
            state.get('optimizer_step')!=78360 or
            state.get('visits')!=697 or
            state['config']['recipe']!=old.recipe()):
        raise ValueError('V12_REQUIRES_EXACT_STOPPED_V11_SOURCE')
    if engine._sha(SOURCE/'state.json')!=SOURCE_STATE_SHA256:
        raise ValueError('V12_STOPPED_SOURCE_STATE_SHA_DRIFT')
    source_file=SOURCE/state['checkpoint']
    if engine._sha(source_file)!=state['checkpoint_sha256']:
        raise ValueError('V12_PARENT_HASH_DRIFT')
    return state,engine._sha(SOURCE/'state.json')


def _assert_teacher():
    study=json.loads((SOUP/'summary.json').read_text())
    path=SOUP/study['artifact']
    if (study['candidate']!='P17_35-P23_65' or
            study['artifact_sha256']!=SOUP_WEIGHTS_SHA256 or
            engine._sha(path)!=SOUP_WEIGHTS_SHA256):
        raise ValueError('V12_REQUIRES_PINNED_EXPERIMENTAL_SOUP')
    return study,path


def initialize(out=RUN,*,block=64,seed=20261013):
    out=Path(out)
    if out.exists():raise FileExistsError('V12_SOURCE_OUTPUT_EXISTS')
    if not 1<=block<=256:raise ValueError('V12_BLOCK_OUT_OF_RANGE')
    source,source_sha=_assert_source()
    study,teacher_path=_assert_teacher()
    model,optimizer,payload=engine.load_checkpoint(SOURCE/source['checkpoint'])
    if (optimizer_receipt(optimizer)['steps']!=[source['optimizer_step']] or
            state_hash(model)!=payload['state_sha256'] or
            digest(payload['graph'])!=source['graph_sha256']):
        raise ValueError('V12_PARENT_MODEL_OR_ADAMW_DRIFT')
    for grade,stage in LESSONS:
        course.validate_rows(course.rows(grade,stage=stage),payload['graph'])
    state={'version':VERSION,'source_run':str(SOURCE),
           'source_state_sha256':source_sha,
           'source_checkpoint_sha256':source['checkpoint_sha256'],
           'source_model_sha256':payload['state_sha256'],
           'source_optimizer_step':source['optimizer_step'],
           'source_teacher_events':source['teacher']['events'],
           'grade_index':0,'grade_ledger':[],'candidate_ledger':[],
           'completed_grade_visits':0,'retained_updates':0,
           'attempted_updates':0,'optimizer_step':source['optimizer_step'],
           'checkpoint':source['checkpoint'],
           'checkpoint_sha256':source['checkpoint_sha256'],
           'graph_sha256':source['graph_sha256'],
           'teacher':copy.deepcopy(source['teacher']),
           'grade_champions':copy.deepcopy(source['grade_champions']),
           'provisional_bridge_champions':copy.deepcopy(source['provisional_bridge_champions']),
           'bridge_champions':copy.deepcopy(source['bridge_champions']),
           'protected_holistic_anchor':copy.deepcopy(source['holistic_anchor']),
           'original_frozen_soup':copy.deepcopy(source['frozen_soup']),
           'experimental_teacher':{'path':str(teacher_path),
                                   'sha256':study['artifact_sha256'],
                                   'qualification':'UNQUALIFIED_RESEARCH_DISTILLATION_TEACHER'},
           'config':{'block':block,'seed':seed,'recipe':recipe(),
                     'lessons':list(LESSONS),'mode':'RESEARCH_ONLY_UNQUALIFIED_CARRY',
                     'mature_G_gate':'REPORT_COUNTERFACTUAL_NEVER_PROMOTE_V11',
                     'acquisition_assessment':'EXACT_EXPOSED_TAUGHT_REPLAY',
                     'sealed_exam':'NOT_USED'},
           'status':'READY_V12_PRIMITIVE_REPAIR',
           'note':'One original FP32 student+AdamW copy, independent teacher copy; research-only G acquisition sandbox.'}
    out.mkdir(parents=True,exist_ok=False)
    destination=out/source['checkpoint']
    os.link(SOURCE/source['checkpoint'],destination,follow_symlinks=False)
    if (destination.stat().st_ino!= (SOURCE/source['checkpoint']).stat().st_ino or
            engine._sha(destination)!=source['checkpoint_sha256']):
        raise ValueError('V12_SOURCE_HARDLINK_PROOF_FAILED')
    engine._atomic_json(out/'state.json',state)
    return state


def _model(out,state,device):
    path=out/state['checkpoint']
    if engine._sha(path)!=state['checkpoint_sha256']:
        raise ValueError('V12_CONTINUATION_CHECKPOINT_HASH_DRIFT')
    student,optimizer,payload=engine.load_checkpoint(path)
    engine._device(student,optimizer,device)
    if (digest(payload['graph'])!=state['graph_sha256'] or
            optimizer_receipt(optimizer)['steps']!=[state['optimizer_step']] or
            state_hash(student)!=payload['state_sha256']):
        raise ValueError('V12_STUDENT_AND_ADAMW_CONTINUITY_LOST')
    return student,optimizer,payload['graph']


def _teacher(student,graph,state,device):
    stored=state['experimental_teacher']
    if engine._sha(stored['path'])!=stored['sha256']:
        raise ValueError('V12_TEACHER_SHA_DRIFT')
    content=torch.load(stored['path'],map_location='cpu',weights_only=True)
    if content['graph_sha256']!=state['graph_sha256']:
        raise ValueError('V12_TEACHER_GRAPH_DRIFT')
    teacher=copy.deepcopy(student)
    teacher.load_state_dict(content['weights'],strict=True)
    teacher.eval()
    for param in teacher.parameters():param.requires_grad_(False)
    return teacher


def _replay_scores(model,graph,device):
    from scripts.school50_g_primitives_probe_v12 import _score, summarize
    entries=[r for g in course.GRADES for r in course.rows(g)]
    return summarize(_score(model,graph,entries,device=device))


def _historical(model,graph,lib,device):
    old_scores=engine._probe_all_grades(model,graph,lib,device=device)
    return {'scores':old_scores,'mean':sum(old_scores.values())/len(old_scores)}


def _visit(out,state,model,optimizer,graph,soup,library,device):
    grade,stage=LESSONS[state['grade_index']]
    parent=copy.deepcopy(model).eval()
    for param in parent.parameters():param.requires_grad_(False)
    before=_replay_scores(model,graph,device)
    before_old=_historical(model,graph,library,device)
    randomizer=random.Random(state['config']['seed']+state['grade_index']*7919)
    key,policy=engine.pick(state['teacher'],int(grade[1:]),randomizer)
    for group in optimizer.param_groups:group['lr']=policy['lr']
    losses=[]
    for update in range(state['config']['block']):
        items=compile_batch(grade,stage,graph,library,randomizer)
        optimizer.zero_grad(set_to_none=True)
        model.train()
        loss,_=staged._typed_loss(model,parent,soup,items,graph,
                                  numeric.numeric_token_ids(graph)[:4],
                                  policy,device)
        if not bool(torch.isfinite(loss)):
            raise ValueError('V12_PRIMITIVE_NONFINITE_LOSS')
        loss.backward()
        norm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)
        if not bool(torch.isfinite(norm)):
            raise ValueError('V12_PRIMITIVE_NONFINITE_GRADIENT')
        optimizer.step()
        losses.append(float(loss.detach().cpu()))
    after=_replay_scores(model,graph,device)
    after_old=_historical(model,graph,library,device)
    after_b=old._bridges(model,graph,old._panels(graph,state['config']['seed']),device)
    after_n=old._basic_numeric(model,graph,device)
    n_correct=sum(after_n[fold]['four_way']['correct'] for fold in ('primary','confirm'))
    b_correct=sum(result['correct'] for folds in after_b.values() for result in folds.values())
    target_before=before['by_grade'][grade]
    target_after=after['by_grade'][grade]
    improvement=target_after['correct']-target_before['correct']
    reward=improvement/max(1,target_before['questions'])+.3*(after_old['mean']-before_old['mean'])
    engine.observe(state['teacher'],int(grade[1:]),key,reward)
    grade_losses={g:round(24*(before_old['scores'][g]-after_old['scores'][g]))
                  for g in before_old['scores']}
    net=sum(round(24*(after_old['scores'][g]-before_old['scores'][g]))
            for g in before_old['scores'])
    guard_pass=net>=1 and all(loss<2 for loss in grade_losses.values())
    start_step=state['optimizer_step']
    step=start_step+state['config']['block']
    if optimizer_receipt(optimizer)['steps']!=[step]:
        raise ValueError('V12_ADAMW_COUNTER_MISMATCH')
    file,sha=engine._checkpoint(out,model,optimizer,graph,{
        'step':step,'grade':grade,'stage':stage,'curriculum':VERSION,
        'status':'RESEARCH_ONLY_NOT_CANONICAL_PROMOTION',
        'parent_checkpoint_sha256':state['checkpoint_sha256']})
    report={'grade':grade,'stage':stage,'visit':state['completed_grade_visits']+1,
            'optimizer_before':start_step,'optimizer_after':step,
            'before_replay':target_before,'after_replay':target_after,
            'all_replay_before':before['overall'],
            'all_replay_after':after['overall'],
            'g_before':before_old['mean'],'g_after':after_old['mean'],
            'g_net_questions':net,'g_individual_lost_questions':grade_losses,
            'mature_G_candidate_gate_would_pass':guard_pass,
            'b_replay_after_correct':b_correct,'numeric_four_way_after_correct':n_correct,
            'method':'EXACT_REPLAY_WITH_B_AND_G_REHEARSAL',
            'teacher_policy_key':key,'teacher_reward':reward,
            'last_loss':losses[-1],'loss_initial':losses[0],
            'checkpoint':file,'checkpoint_sha256':sha,
            'disposition':'RESEARCH_ACQUISITION_CARRY_NOT_G_PROMOTION'}
    state['checkpoint']=file;state['checkpoint_sha256']=sha
    state['optimizer_step']=step
    state['completed_grade_visits']+=1
    state['attempted_updates']+=state['config']['block']
    state['retained_updates']+=state['config']['block']
    state['grade_index']+=1
    state['grade_ledger'].append(report)
    state['candidate_ledger'].append({'grade':grade,'visit':report['visit'],
                                      'teacher_policy_key':key,
                                      'reward':reward,'safe_for_canonical_G':guard_pass,
                                      'research_carried':True})
    state['status']='COMPLETE_DEVELOPMENTAL_REVIEW' if state['grade_index']==len(LESSONS) else 'GRADE_BOUNDARY'
    engine._atomic_json(out/'state.json',state)
    print('GRADE_BOUNDARY',grade,stage,'replay',target_before['correct'],
          '>',target_after['correct'],'/',target_after['questions'],
          'G',f"{100*before_old['mean']:.1f}>{100*after_old['mean']:.1f}%",
          'B',b_correct,'/84','N',n_correct,'/4','G_gate',guard_pass,
          'student',step,flush=True)
    return report


def _sigint(signum,frame):
    global _stop
    _stop=True
    print('STOP_REQUESTED: finish this grade first',flush=True)


def run(out=RUN,*,minutes=90,device='mps',max_grade_visits=None):
    if minutes<=0:raise ValueError('V12_INVALID_SESSION_MINUTES')
    out=Path(out)
    lock=out.with_name(out.name+'.writer.lock')
    fd=os.open(lock,os.O_CREAT|os.O_RDWR|getattr(os,'O_NOFOLLOW',0),0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        state=engine._read(out/'state.json')
        source,source_sha=_assert_source()
        _assert_teacher()
        if (state['version']!=VERSION or
                state['source_state_sha256']!=source_sha or
                state['config']['recipe']!=recipe() or
                state['source_checkpoint_sha256']!=source['checkpoint_sha256']):
            raise ValueError('V12_SOURCE_OR_RECIPE_CHANGED')
        if state['grade_index']==len(LESSONS):
            print('COMPLETE_DEVELOPMENTAL_REVIEW');return state
        model,optimizer,graph=_model(out,state,device)
        soup=_teacher(model,graph,state,device)
        library=lessons.TeacherLibrary()
        start=time.monotonic();since=0
        prior=signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT,_sigint)
        try:
            while state['grade_index']<len(LESSONS):
                if _stop or (max_grade_visits is not None and since>=max_grade_visits) or (
                        since and time.monotonic()-start>=minutes*60):
                    break
                _visit(out,state,model,optimizer,graph,soup,library,device)
                since+=1
        finally:
            signal.signal(signal.SIGINT,prior)
        if state['grade_index']!=len(LESSONS):
            state['status']='READY_RESUME_GRADE_BOUNDARY'
            engine._atomic_json(out/'state.json',state)
        print('V12_SESSION_END',state['status'],'visits',since,
              'step',state['optimizer_step'],'teacher',state['teacher']['events'])
        return state
    finally:os.close(fd)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--initialize-only',action='store_true')
    mode.add_argument('--train',action='store_true')
    mode.add_argument('--status',action='store_true')
    parser.add_argument('--run-dir',type=Path,default=RUN)
    parser.add_argument('--block',type=int,default=64)
    parser.add_argument('--minutes',type=float,default=90)
    parser.add_argument('--device',choices=['cpu','mps'],default='mps')
    parser.add_argument('--max-grade-visits',type=int)
    args=parser.parse_args()
    if args.status:
        state=engine._read(args.run_dir/'state.json')
        print('STATUS',state['status'],'next',(
              LESSONS[state['grade_index']] if state['grade_index']<len(LESSONS) else 'COMPLETE'),
              'step',state['optimizer_step'],'visits',state['completed_grade_visits'],
              'teacher',state['teacher']['events'])
    elif args.initialize_only:
        state=initialize(args.run_dir,block=args.block)
        print('INITIALIZED',state['status'],'source step',state['optimizer_step'],
              'new training updates',state['retained_updates'])
    else:
        if not args.run_dir.is_dir():
            raise RuntimeError('V12_NEEDS_INITIALIZE_ONLY_FIRST')
        run(args.run_dir,minutes=args.minutes,device=args.device,
            max_grade_visits=args.max_grade_visits)


if __name__=='__main__':
    main()
