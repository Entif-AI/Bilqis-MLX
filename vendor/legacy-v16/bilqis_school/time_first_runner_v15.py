"""V15: v14 training engine plus session-local champions and measured soups.

Research only. One FP32 student and its inherited AdamW are taught a full
B01-B07, G01-G22 spiral. Grade visits are 64 optimizer updates by default,
not ten-update promotion auditions. A manually started session runs toward
its wall-clock ceiling, stopping only at grade boundaries, not after a fixed
number of passes. The historical v11 engine supplies the training, adaptive
teacher and consolidation machinery; focused acquisition is admitted without
premature historical-retention vetoes. Historical P43 and predecessors remain
read-only.
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
import statistics
import sys
import tempfile
import time
import traceback
import uuid

import torch

from bilqis_logic.kernel import digest
from bilqis_micro.run import optimizer_receipt
from bilqis_ref.model import state_hash
from . import small_domain_lessons as course
from . import bridge_foundation_runner as precursor
from . import bridge_foundation_lessons as foundation
from . import engine, lessons, numeric_answer_pilot as pilot
from . import numeric_answer_contract as contract
from . import spiral_staged_runner as staged
from . import foundation_course_v15 as focused_course
from torch.nn import functional as F


VERSION = "bilqis.primitive-consolidation.run-local/v15"
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "bilqis-school50-time-first-v11/runs/school50-time-first-v11"
LEGACY_RUN = ROOT / "runs/primitive-consolidation-v14-time-first"
PREDECESSOR = ROOT / "runs/primitive-consolidation-v14-acquisition-first"
RUN = ROOT / "runs/primitive-consolidation-v15-run-local"
P43 = ROOT.parent / ("bilqis-auto-curriculum50/runs/school50-continuous-v1/"
                      "student-67800-2cf61275e081.pt")
PROGRAM = course.GRADES + tuple(f"G{n:02d}" for n in engine.REPORT_GRADES)
OLD_MEAN_PAUSE = .01
OLD_GRADE_PAUSE = 3/24
SOURCE_SHA256 = "dc93b9f56bdbc7345c48ec0e27ef8c27bc7bd08d34bb00ad5bed7bde85747d67"
SOURCE_PASS10_SHA256 = "0639d2919df5dcb80f6429849644923e8788a5d03e3d3bf209a918dbfd59f72b"
SOURCE_PASS11_SHA256 = "e63948210c1bc798f69c79a2ac2fe52d13ad29bcbd781080f9f0056a12b78aac"
DEFAULT_MINUTES = 90
FOCUSED_G = {"G11": "MEMBER", "G15": "EDGE", "G20": "ARITHMETIC"}
DEVELOPMENTAL_G22 = 'G22'  # One attempt; do not change 29/35 allocation.
from . import run_local_champions_v15 as local_champions


def recipe():
    from . import primitive_staircase_v13 as new_course
    return {key:engine._sha(path) for key,path in {
        "runner":__file__,
        "small_domain_lessons":course.__file__,
        "school50_engine":engine.__file__,
        "school50_lessons":lessons.__file__,
        "staged_training":staged.__file__,
        "foundation_oracle":foundation.__file__,
        "bridge_oracle":course.bridge.__file__,
        "primitive_oracle":course.primitive.__file__,
        "numeric_readout":contract.__file__,
        "historical_B_curriculum":course.inherited.__file__,
        "direct_path_probes":new_course.__file__,
        "focused_graded_acquisition":focused_course.__file__,
        "run_local_champion_policy":local_champions.__file__,
    }.items()}


def configuration(*,block=64,seed=20261013,champion_boundary='session'):
    if not 1<=block<=256:
        raise ValueError("ACQUISITION_INVALID_GRADE_BLOCK")
    if champion_boundary not in local_champions.BOUNDARIES:
        raise ValueError('V15_INVALID_CHAMPION_RUN_BOUNDARY')
    return {"version":VERSION,"block":block,"seed":seed,"bridge_attempts":1,"historic_attempts":1,
            "focused_G_attempts":3,"focused_G":FOCUSED_G,
            "acquisition_policy":"FOCUS_FIRST_HISTORICAL_MONITORED",
            "run_champion_policy":local_champions.RECIPE,
            "run_champion_version":local_champions.SCHEMA,
            "champion_boundary":champion_boundary,
            "holistic_tie_ranking":'PROVISIONAL_EQUAL_DOMAIN_GBN_MACRO_V1_OPERATOR_ACK_REQUIRED',
            "session_soup_refresh":('AFTER_OPERATOR_SESSION_ONLY'
                                    if champion_boundary=='session' else
                                    'ON_FULL_29_GRADE_COLLECTION'),
            "recipe":recipe(),"source_champion_sha256":pilot.CHAMPION_SHA256,
            "grade_program":list(PROGRAM),
            "max_old_mean_debt":OLD_MEAN_PAUSE,
            "max_old_grade_debt":OLD_GRADE_PAUSE,
            "continuation_control":"TIME_FIRST_GRADE_BOUNDARY_NO_PASS_CAP",
            "small_numeral_max":3,
            "numeric_readout":"FOUR_OF_EXISTING_101_NUMBER_EMBEDDINGS",
            "basic_arithmetic_rows_per_B_update":course.NUMERIC_ROWS_PER_B_BATCH,
            "replayed_bridge_question_count":course.TOTAL_BRIDGE_ROWS,
            "heldout_ownership":"EXACT_ARITHMETIC_EXPRESSION_NOT_NUMBER_VALUE",
            "learning_assessment":"TRAINING_REPLAY_EXACT_QUESTIONS_NO_GENERALIZATION_CLAIM"}




def _load_student(out,state,device):
    name=state["checkpoint"]
    if Path(name).name!=name or engine._sha(out/name)!=state["checkpoint_sha256"]:
        raise ValueError("ACQUISITION_CHECKPOINT_HASH_MISMATCH")
    model,optimizer,payload=engine.load_checkpoint(out/name)
    engine._device(model,optimizer,device)
    if (state_hash(model)!=payload["state_sha256"] or
            digest(payload["graph"])!=state["graph_sha256"] or
            optimizer_receipt(optimizer)["steps"]!=[state["optimizer_step"]]):
        raise ValueError("ACQUISITION_STUDENT_ADAMW_CONTINUITY_LOST")
    return model,optimizer,payload["graph"]


def _soup(out,state,student,device):
    record=state["frozen_soup"]
    path=out/record["file"]
    if (Path(record["file"]).name!=record["file"] or
            engine._sha(path)!=record["sha256"]):
        raise ValueError("ACQUISITION_FROZEN_SOUP_HASH_MISMATCH")
    data=torch.load(path,map_location="cpu",weights_only=True)
    if data["manifest"]!=record["manifest"] or data["graph_sha256"]!=state["graph_sha256"]:
        raise ValueError("ACQUISITION_FROZEN_SOUP_MANIFEST_MISMATCH")
    teacher=copy.deepcopy(student)
    teacher.load_state_dict(data["weights"],strict=True)
    teacher.to(device).eval()
    for parameter in teacher.parameters():
        parameter.requires_grad_(False)
    if state_hash(teacher)!=record["manifest"]["teacher_digest"]:
        raise ValueError("ACQUISITION_FROZEN_SOUP_WEIGHTS_MISMATCH")
    return teacher


def _panels(graph,seed):
    return {grade:{fold:course.panel(grade,graph,fold=fold,seed=seed)
                   for fold in ("primary","confirm")}
            for grade in course.GRADES}


def _prediction_readout(model,ids,lengths,*,answer_kind,number_ids):
    """Read-only ensemble control; ordinary students use original readout."""
    if isinstance(model,local_champions.PredictionLogitEnsemble):
        return model.typed_logits(ids,lengths,answer_kind=answer_kind,
                                  number_ids=number_ids)
    return contract.readout(model,ids,lengths,answer_kind=answer_kind,
                            number_ids=number_ids)


@torch.no_grad()
def _small_panel(model,rows,graph,device):
    """Training-replay test of exact, repeatedly taught evidence questions."""
    course.validate_rows(rows,graph,split='train',expected=course.PANEL_ROWS)
    if any(row['course_meta']['tranche']!='replay' for row in rows):
        raise ValueError('SMALL_DOMAIN_REPLAY_EXPECTED')
    ids,lengths=staged._input(rows,graph,device)
    model.eval()
    logits=_prediction_readout(model,ids,lengths,answer_kind='evidence',
                            number_ids=contract.numeric_token_ids(graph))
    labels=staged._gold(rows,'evidence',device)
    predicted=logits.argmax(-1).cpu().tolist()
    correct=(logits.argmax(-1)==labels).cpu().tolist()
    by_source={};by_projection={};by_family={}
    for row,right in zip(rows,correct):
        meta=row['course_meta']
        by_source.setdefault(meta['triplet_id'],[]).append((row['gold'],bool(right)))
        for target,key in ((by_projection,meta['projection']),
                           (by_family,meta['bridge_family'])):
            item=target.setdefault(key,{'correct':0,'questions':0})
            item['correct']+=int(right)
            item['questions']+=1
    complete=sum({answer for answer,_ in members}=={'TRUE','FALSE'}
                 and all(ok for _,ok in members)
                 for members in by_source.values())
    return {'correct':sum(correct),'questions':len(rows),
            'assessment_role':'TRAINING_REPLAY_NOT_INDEPENDENT',
            'accuracy':sum(correct)/len(rows),
            'ce':float(F.cross_entropy(logits,labels).item()),
            'paired_contrasts':complete,
            'predicted_true':sum(idx==staged.STATES.index('TRUE') for idx in predicted),
            'predicted_false':sum(idx==staged.STATES.index('FALSE') for idx in predicted),
            'by_family':by_family,'by_projection':by_projection,
            'distinct_arithmetic_sources':len({row['course_meta']['semantic_source_id']
                                               for row in rows}),
            'majority_label_baseline':max(sum(row['gold']==label for row in rows)
                                          for label in ('TRUE','FALSE'))/len(rows)}


@torch.no_grad()
def _basic_numeric(model,graph,device):
    """Score the exact four numeric expressions rehearsed every B update."""
    model.eval()
    four=contract.numeric_token_ids(graph)[:4]
    full=contract.numeric_token_ids(graph)
    result={}
    for fold in ('primary','confirm'):
        rows=course.numeric_panel(graph,fold=fold)
        ids,lengths=staged._input(rows,graph,device)
        gold=staged._gold(rows,'numeric',device)
        result[fold]={}
        for name,ids_for_readout in (('four_way',four),('full_101',full)):
            logits=_prediction_readout(model,ids,lengths,answer_kind='numeric',
                                    number_ids=ids_for_readout)
            prediction=logits.argmax(-1)
            right=int((prediction==gold).sum().item())
            result[fold][name]={'correct':right,'questions':len(rows),
                                'ce':float(F.cross_entropy(logits,gold).item()),
                                'predictions':prediction.cpu().tolist(),
                                'gold':gold.cpu().tolist()}
    return result


def _train_small_step(student,optimizer,parent,soup,rows,graph,policy,device):
    """Preserve staged typed CE/KL using the tiny expression-ownership validator."""
    course.validate_rows(rows,graph,split='train',expected=48)
    optimizer.zero_grad(set_to_none=True)
    student.train()
    loss,metrics=staged._typed_loss(student,parent,soup,rows,graph,
                                    contract.numeric_token_ids(graph)[:4],policy,device)
    if not bool(torch.isfinite(loss)):
        raise ValueError('SMALL_DOMAIN_NONFINITE_LOSS')
    loss.backward()
    torch.nn.utils.clip_grad_norm_(student.parameters(),1.0)
    optimizer.step()
    metrics['total_loss']=float(loss.detach().cpu())
    return metrics


def _bridges(model,graph,panels,device):
    return {grade:{fold:_small_panel(model,rows,graph,device)
                   for fold,rows in variants.items()}
            for grade,variants in panels.items()}


def _old(model,graph,library,device):
    return engine._probe_all_grades(model,graph,library,device=device)



def _link_immutable(source,destination,expected_sha256):
    """Never materialize another 129 MB blob: same-inode immutable checkpoint."""
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("BRIDGE_PRIORITY_LINK_DESTINATION_EXISTS")
    if source.is_symlink() or not source.is_file():
        raise ValueError("BRIDGE_PRIORITY_INVALID_SOURCE_ARTIFACT")
    if engine._sha(source)!=expected_sha256:
        raise ValueError("BRIDGE_PRIORITY_SOURCE_ARTIFACT_CHANGED")
    try:
        os.link(source,destination,follow_symlinks=False)
    except OSError as exc:
        raise RuntimeError("BRIDGE_PRIORITY_HARDLINK_REQUIRED_NO_DISK_COPY") from exc
    if (source.stat().st_ino!=destination.stat().st_ino or
            source.stat().st_dev!=destination.stat().st_dev or
            engine._sha(destination)!=expected_sha256):
        raise ValueError("BRIDGE_PRIORITY_HARDLINK_PROOF_FAILED")


def _comparison_point(report,*,source):
    """Observable joint outcomes, not a generalization or mastery certificate."""
    return {"pass":report["pass"],"checkpoint":report["checkpoint"],
            "checkpoint_sha256":report["checkpoint_sha256"],
            "optimizer_step":report["optimizer_step"],
            "bridge_correct":report["bridge_correct"],
            "bridge_contrasts":report["bridge_contrasts"],
            "old_mean":report["old_mean"],
            "numeric_four_way":report["basic_numeric_four_way_correct"],
            "numeric_full_101":report["basic_numeric_full_101_correct"],
            "rollback_triggers":copy.deepcopy(report["rollback_triggers"]),
            "source":source,"assessment_role":"TRAINING_REPLAY_NOT_GENERALIZATION"}


JOINT_AXES=("bridge_contrasts","bridge_correct","old_mean","numeric_four_way")


def _joint_rank(point):
    """Descriptive v10-compatible acquisition-first preference, not a gate."""
    return [point["bridge_contrasts"],point["bridge_correct"],
            point["old_mean"],point["numeric_four_way"]]


def _frontier(points):
    """Preserve nondominated B/G combinations without concealing tradeoffs."""
    result=[]
    for point in points:
        values=tuple(point[a] for a in JOINT_AXES)
        if any(tuple(old[a] for a in JOINT_AXES)==values for old in result):
            continue
        if any(all(old[a]>=point[a] for a in JOINT_AXES) and
               any(old[a]>point[a] for a in JOINT_AXES) for old in result):
            continue
        result=[old for old in result if not (
            all(point[a]>=old[a] for a in JOINT_AXES) and
            any(point[a]>old[a] for a in JOINT_AXES))]
        result.append(copy.deepcopy(point))
    return result


def _record_joint(state,report):
    surface=state["time_first"]
    point=_comparison_point(report,source="V11_PASS_BOUNDARY")
    surface["pass_observations"].append(point)
    surface["joint_frontier"]=_frontier(surface["joint_frontier"]+[point])
    if _joint_rank(point)>_joint_rank(surface["best_joint"]):
        surface["best_joint"]=copy.deepcopy(point)
    if (point["old_mean"],point["bridge_contrasts"])>(
            surface["best_historical"]["old_mean"],
            surface["best_historical"]["bridge_contrasts"]):
        surface["best_historical"]=copy.deepcopy(point)




def _assert_v14_parent(source):
    """Admit only the exact, stopped v11 student, not the v13 short pilot."""
    from . import g_primitives_training_v12 as provenance
    if source.resolve()!=SOURCE.resolve():
        raise ValueError('V14_SOURCE_MUST_BE_PINNED_V11')
    old,sha=provenance._assert_source()
    if (old['config']['grade_program']!=list(PROGRAM) or
            old['grade_index']!=1 or old['passes_completed']!=24 or
            old['pass_start_old'] is None or
            old['soup_epoch']!=24 or old['teacher']['events']!=2692 or
            (source/'sealed-evaluation.json').exists()):
        raise ValueError('V14_SOURCE_PROGRAM_OR_CARRY_STATE_DRIFT')
    old['_v14_parent_state_sha256']=sha
    return old


def _initialize_v14(out,source,old,config,device):
    """Copy *all* old student/AdamW/soup/champion bytes by verified hardlink.

    Resume exactly at B02 in v11's active pass 25: B01 was already visited
    there by the parent and will get the new 1-candidate policy next pass.
    Do not restart a pass or discard B01's existing trained contribution.
    """
    from . import primitive_staircase_v13 as direct
    lock=source.with_name(source.name+'.writer.lock')
    fd=os.open(lock,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    try:
        fcntl.flock(fd,fcntl.LOCK_SH|fcntl.LOCK_NB)
        staging=Path(tempfile.mkdtemp(prefix='.v14-candidate-init-',dir=out.parent))
        try:
            old_sha=old['_v14_parent_state_sha256']
            for path in sorted(source.glob('*.pt')):
                if path.is_symlink() or path.name!=Path(path.name).name:
                    raise ValueError('V14_PARENT_HAS_UNSAFE_MODEL_FILE')
                _link_immutable(path,staging/path.name,engine._sha(path))
            if engine._sha(source/'state.json')!=old_sha:
                raise ValueError('V14_PARENT_CHANGED_DURING_COPY')
            state=copy.deepcopy({k:v for k,v in old.items() if not k.startswith('_')})
            state['version']=VERSION
            state['config']=config
            state['last_run_status']='READY_V14_CANDIDATE_COMPETITION'
            state['last_session']=None
            state['v14_origin']={
                'source_run':str(source),'source_state_sha256':old_sha,
                'source_checkpoint':old['checkpoint'],
                'source_checkpoint_sha256':old['checkpoint_sha256'],
                'source_optimizer_step':old['optimizer_step'],
                'source_teacher_events':old['teacher']['events'],
                'source_grade_index':old['grade_index'],
                'source_passes_completed':old['passes_completed'],
                'source_full_program':list(PROGRAM),
                'training_policy':'3_FOCUSED_G_1_EACH_OTHER_B_AND_G'}
            model,optim,graph=_load_student(staging,state,device)
            _soup(staging,state,model,device)
            direct.validate(graph)
            if optimizer_receipt(optim)['steps']!=[78360]:
                raise ValueError('V14_IMPORTED_ADAMW_STEP_DRIFT')
            engine._atomic_json(staging/'state.json',state)
            os.replace(staging,out)
            return state
        finally:
            if staging.exists():shutil.rmtree(staging)
    finally:os.close(fd)

def _assert_frozen(state,config):
    if state.get("version")!=VERSION or state.get("config")!=config:
        raise ValueError("ACQUISITION_FROZEN_RECIPE_DRIFT_USE_NEW_RUN")
    if state.get("phase") not in ("ACQUISITION","DEVELOPMENTAL_REVIEW"):
        raise ValueError("ACQUISITION_LINEAGE_CLOSED")


def prepare_run_local(*,previous=PREDECESSOR,destination=RUN,
                      champion_boundary='session',dry_run=False):
    """Nontraining, independently frozen successor of the stopped v14 student.

    Verify old v14 recipe, exact grade cursor/AdamW and source ledger before
    linking artifacts. No original state, frozen soup or optimizer is changed.
    """
    from . import time_first_runner_v14 as v14
    previous=Path(previous).resolve(strict=True)
    destination=Path(destination).resolve(strict=False)
    if previous!=PREDECESSOR.resolve() or destination!=RUN.resolve():
        raise ValueError('V15_CONTINUATION_REQUIRES_CANONICAL_RUNS')
    destination.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(previous.with_name(previous.name+'.writer.lock'),
               os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    target_fd=None
    try:
        try:fcntl.flock(fd,fcntl.LOCK_SH|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('V15_PREDECESSOR_TRAINING_ACTIVE') from exc
        target_fd=os.open(destination.with_name(destination.name+'.writer.lock'),
                          os.O_CREAT|os.O_RDWR|getattr(os,'O_NOFOLLOW',0),0o600)
        try:fcntl.flock(target_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('V15_SUCCESSOR_WRITER_ACTIVE') from exc
        if destination.exists():
            raise FileExistsError('V15_ALREADY_PREPARED')
        before_bytes=(previous/'state.json').read_bytes()
        before_sha=engine._sha(previous/'state.json')
        before=json.loads(before_bytes)
        if (before.get('version')!=v14.VERSION or
                before.get('config')!=v14.configuration() or
                before.get('phase')!='ACQUISITION' or
                before.get('last_run_status') not in
                  ('TIME_BUDGET_EXHAUSTED','GRACEFUL_OPERATOR_STOP','GRADE_BOUNDARY') or
                before['visits']!=before['grade_ledger'][-1]['visit'] or
                before['config']['grade_program']!=list(PROGRAM)):
            raise ValueError('V15_PREDECESSOR_NOT_VERIFIED_BOUNDARY')
        expected={before['checkpoint']:before['checkpoint_sha256'],
                  before['frozen_soup']['file']:before['frozen_soup']['sha256']}
        for key in ('grade_champions','bridge_champions',
                    'provisional_bridge_champions'):
            for candidate in before[key].values():
                if candidate.get('location')=='research':
                    expected[candidate['checkpoint']]=candidate['checkpoint_sha256']
        for item in before['frozen_soup']['manifest'].get('cohorts',{}).values():
            expected[item['file']]=item['sha256']
        artifacts=sorted(previous.glob('*.pt'))
        if not set(expected).issubset({p.name for p in artifacts}):
            raise ValueError('V15_REQUIRED_SOURCE_MODEL_MISSING')
        staging=Path(tempfile.mkdtemp(prefix='.v15-run-local-',
                                      dir=destination.parent))
        try:
            linked={}
            for path in artifacts:
                if path.is_symlink() or not path.is_file():
                    raise ValueError('V15_UNSAFE_PREDECESSOR_ARTIFACT')
                sha=engine._sha(path)
                if path.name in expected and sha!=expected[path.name]:
                    raise ValueError('V15_PREDECESSOR_CHECKPOINT_DRIFT')
                os.link(path,staging/path.name,follow_symlinks=False)
                if ((path.stat().st_ino,path.stat().st_dev)!=
                    ((staging/path.name).stat().st_ino,(staging/path.name).stat().st_dev)):
                    raise ValueError('V15_MODEL_HARDLINK_IDENTITY_DRIFT')
                linked[path.name]=sha
            if engine._sha(previous/'state.json')!=before_sha:
                raise ValueError('V15_PREDECESSOR_STATE_CHANGED')
            state=copy.deepcopy(before)
            state['version']=VERSION
            state['config']=configuration(champion_boundary=champion_boundary)
            state['last_run_status']='READY_V15_RUN_LOCAL'
            state['last_session']=None
            state['run_local_champions']={
                'schema':local_champions.SCHEMA,'active':None,'completed':[]}
            state['v15_origin']={
                'source_run':str(previous),
                'source_state_sha256':before_sha,
                'source_optimizer_step':before['optimizer_step'],
                'source_student_checkpoint':before['checkpoint'],
                'source_student_checkpoint_sha256':before['checkpoint_sha256'],
                'source_teacher_events':before['teacher']['events'],
                'source_grade_index':before['grade_index'],
                'source_passes_completed':before['passes_completed'],
                'predecessor_recipe':before['config']['recipe'],
                'next_recipe':state['config']['recipe'],
                'optimizer_updates_during_transition':0}
            (staging/'predecessor-state.json').write_bytes(before_bytes)
            _assert_frozen(state,configuration(champion_boundary=champion_boundary))
            student,optim,graph=_load_student(staging,state,'cpu')
            # Verify the inherited soup before setting it aside as evidence.
            _soup(staging,state,student,'cpu')
            if optimizer_receipt(optim)['steps']!=[before['optimizer_step']]:
                raise ValueError('V15_ADAMW_STEP_MISMATCH')
            _initial_v15_teacher(staging,state,student)
            refreshed=_soup(staging,state,student,'cpu')
            if state_hash(refreshed)!=state_hash(student):
                raise ValueError('V15_INITIAL_TEACHER_NOT_STUDENT_COPY')
            engine._atomic_json(staging/'policy-transition.json',{
                'continuation':state['v15_origin'],'linked_artifact_sha256':linked,
                'initial_teacher':state['frozen_soup']})
            engine._atomic_json(staging/'state.json',state)
            if dry_run:
                report=status(staging)
                report['preparation_probe']='VALIDATED_TEMPORARY_STAGING_ONLY'
                report['new_v15_run_created']=False
                return report
            os.replace(staging,destination)
            return status(destination)
        finally:
            if staging.exists():shutil.rmtree(staging)
    finally:
        if target_fd is not None:os.close(target_fd)
        os.close(fd)


def prepare_acquisition_first(*,previous=LEGACY_RUN,destination=RUN):
    """Fork the last durable v14 grade boundary without a single neural update.

    Keep the original frozen recipe and checkpoint directory immutable. All
    weights, AdamW moments, teacher history, grades and soups are inherited;
    checkpoint bytes use verified same-inode hardlinks, not weight averaging.
    """
    previous=Path(previous).resolve(strict=True)
    destination=Path(destination).resolve(strict=False)
    if previous!=LEGACY_RUN.resolve() or destination!=RUN.resolve():
        raise ValueError("V14_POLICY_CONTINUATION_REQUIRES_CANONICAL_PATHS")
    destination.parent.mkdir(parents=True,exist_ok=True)
    previous_lock=previous.with_name(previous.name+'.writer.lock')
    destination_lock=destination.with_name(destination.name+'.writer.lock')
    read_fd=os.open(previous_lock,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    write_fd=None
    try:
        try:fcntl.flock(read_fd,fcntl.LOCK_SH|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("V14_POLICY_SOURCE_TRAINING_ACTIVE") from exc
        write_fd=os.open(destination_lock,
                         os.O_CREAT|os.O_RDWR|getattr(os,'O_NOFOLLOW',0),0o600)
        try:fcntl.flock(write_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("V14_POLICY_DESTINATION_WRITER_ACTIVE") from exc
        if destination.exists():
            raise FileExistsError("V14_POLICY_CONTINUATION_ALREADY_EXISTS")

        original_bytes=(previous/'state.json').read_bytes()
        original_sha=engine._sha(previous/'state.json')
        original=json.loads(original_bytes)
        new_config=configuration()
        previous_config=copy.deepcopy(new_config)
        previous_config.pop('acquisition_policy')
        previous_config['recipe']=original['config']['recipe']
        if (original['version']!=VERSION or
                original['config']!=previous_config or
                original['phase']!='ACQUISITION' or
                original['last_run_status']!='GRADE_BOUNDARY' or
                original['optimizer_step']<78360 or
                original['grade_ledger'][-1]['visit']!=original['visits'] or
                original['config']['grade_program']!=list(PROGRAM)):
            raise ValueError("V14_POLICY_SOURCE_NOT_VERIFIED_GRADE_BOUNDARY")
        old_recipe=original['config']['recipe']
        if any(old_recipe.get(k)!=v for k,v in new_config['recipe'].items()
               if k!='runner') or not old_recipe.get('runner'):
            raise ValueError("V14_POLICY_UNRELATED_FROZEN_RECIPE_DRIFT")
        inherited=original['v14_origin']
        if (engine._sha(SOURCE/'state.json')!=inherited['source_state_sha256'] or
                engine._sha(SOURCE/inherited['source_checkpoint'])!=
                    inherited['source_checkpoint_sha256']):
            raise ValueError("V14_POLICY_ORIGINAL_V11_SOURCE_CHANGED")

        expected={original['checkpoint']:original['checkpoint_sha256'],
                  original['frozen_soup']['file']:
                      original['frozen_soup']['sha256']}
        for group in ('grade_champions','bridge_champions',
                      'provisional_bridge_champions'):
            for champion in original.get(group,{}).values():
                if champion.get('location')=='research' and champion.get('checkpoint_sha256'):
                    expected[champion['checkpoint']]=champion['checkpoint_sha256']
        artifacts=sorted(previous.glob('*.pt'))
        if not artifacts or not set(expected).issubset({p.name for p in artifacts}):
            raise ValueError("V14_POLICY_SOURCE_REQUIRED_CHECKPOINT_MISSING")

        staging=Path(tempfile.mkdtemp(prefix='.v14-acquisition-first-',
                                      dir=destination.parent))
        try:
            linked={}
            for path in artifacts:
                if path.is_symlink() or not path.is_file():
                    raise ValueError("V14_POLICY_SOURCE_SYMLINK_OR_NONFILE")
                sha=engine._sha(path)
                if path.name in expected and expected[path.name]!=sha:
                    raise ValueError("V14_POLICY_SOURCE_CHECKPOINT_HASH_DRIFT")
                target=staging/path.name
                os.link(path,target,follow_symlinks=False)
                if (path.stat().st_dev,path.stat().st_ino)!=(
                        target.stat().st_dev,target.stat().st_ino):
                    raise ValueError("V14_POLICY_HARDLINK_PROOF_FAILED")
                linked[path.name]=sha
            if engine._sha(previous/'state.json')!=original_sha:
                raise ValueError("V14_POLICY_SOURCE_STATE_CHANGED_DURING_LINK")

            state=copy.deepcopy(original)
            state['config']=new_config
            state['last_run_status']='READY_V14_ACQUISITION_FIRST'
            state['policy_continuation']={
                'kind':'V14_ACQUISITION_FIRST_FROM_GRADE_BOUNDARY',
                'source_run':str(previous),
                'source_state_sha256':original_sha,
                'source_checkpoint':original['checkpoint'],
                'source_checkpoint_sha256':original['checkpoint_sha256'],
                'source_optimizer_step':original['optimizer_step'],
                'source_grade_index':original['grade_index'],
                'source_passes_completed':original['passes_completed'],
                'source_visits':original['visits'],
                'source_teacher_events':original['teacher']['events'],
                'source_runner_sha256':old_recipe['runner'],
                'successor_runner_sha256':new_config['recipe']['runner'],
                'training_updates_during_transition':0}
            (staging/'predecessor-state.json').write_bytes(original_bytes)
            engine._atomic_json(staging/'policy-transition.json',{
                'continuation':state['policy_continuation'],
                'linked_artifact_sha256':linked})
            engine._atomic_json(staging/'state.json',state)
            _assert_frozen(state,new_config)
            student,optim,_=_load_student(staging,state,'cpu')
            _soup(staging,state,student,'cpu')
            if optimizer_receipt(optim)['steps']!=[original['optimizer_step']]:
                raise ValueError("V14_POLICY_ADAMW_STEP_DRIFT")
            os.replace(staging,destination)
            return status(destination)
        finally:
            if staging.exists():shutil.rmtree(staging)
    finally:
        if write_fd is not None:os.close(write_fd)
        os.close(read_fd)


def _freeze_soup_record(out,state,epoch,name,teacher,manifest):
    """Publish an immutable soup or verify an identical crash-retry artifact."""
    target=out/name
    weights={k:v.detach().cpu() for k,v in teacher.state_dict().items()}
    if target.exists():
        saved=torch.load(target,map_location="cpu",weights_only=True)
        if (saved['manifest']!=manifest or
                saved['graph_sha256']!=state['graph_sha256'] or
                set(saved['weights'])!=set(weights) or
                any(not torch.equal(saved['weights'][k],weights[k])
                    for k in weights)):
            raise ValueError('ACQUISITION_EXISTING_SOUP_EPOCH_CONFLICT')
    else:
        tmp=out/f'.{name}.{uuid.uuid4().hex}.tmp'
        try:
            torch.save({'weights':weights,'manifest':manifest,
                        'graph_sha256':state['graph_sha256']},tmp)
            os.replace(tmp,target)
        finally:
            if tmp.exists():tmp.unlink()
    return {'epoch':epoch,'file':name,'sha256':engine._sha(target),
            'manifest':manifest}


def _initial_v15_teacher(out,state,student):
    """Freeze the inherited causal student as conservative initial guidance.

    The v14 50:50 B/G mix is preserved as source evidence, but a mixture
    empirically worse than the source student must not silently guide v15.
    This copies weights ONLY for a frozen reference; student+AdamW is intact.
    No research champion or newly mixed teacher is promoted here.
    """
    inherited=copy.deepcopy(state['frozen_soup'])
    state['v15_origin']['inherited_frozen_soup']=inherited
    digest_student=state_hash(student)
    manifest={
        'epoch':state['soup_epoch'],
        'kind':'V15_INITIAL_CUMULATIVE_STUDENT_REFERENCE',
        'assessment_role':'TRAINING_GUIDANCE_NOT_TRANSFER_QUALIFICATION',
        'selection_policy':'NO_UNMEASURED_PARAMETER_AVERAGE',
        'source_optimizer_step':state['optimizer_step'],
        'source_student_checkpoint_sha256':state['checkpoint_sha256'],
        'rejected_guidance_file':inherited['file'],
        'rejected_guidance_sha256':inherited['sha256'],
        'teacher_digest':digest_student,
    }
    frozen=copy.deepcopy(student).cpu().eval()
    for parameter in frozen.parameters():
        parameter.requires_grad_(False)
    state['frozen_soup']=_freeze_soup_record(
        out,state,state['soup_epoch'],
        f'v15-initial-teacher-step-{state["optimizer_step"]}.pt',
        frozen,manifest)
    return state['frozen_soup']


def _B_champion_soup(out,state,student,epoch):
    """Average the saved B personal bests, retaining provisional provenance.

    Their 12-item replays are exposed acquisition evidence. That is enough to
    contribute to the *developmental teacher*, NOT enough to certify transfer.
    """
    assignments={**state.get('provisional_bridge_champions',{}),
                 **state.get('bridge_champions',{})}
    if set(assignments)!=set(course.GRADES):
        raise ValueError('ACQUISITION_B_SOUP_REQUIRES_SEVEN_CHAMPIONS')
    votes={}
    provenance={}
    for grade,record in sorted(assignments.items()):
        if (record['location'] not in ('source','research') or
                not 0<=record['score']<=1 or
                record.get('qualification') not in ('PROVISIONAL','QUALIFIED')):
            raise ValueError('ACQUISITION_B_SOUP_INVALID_PROVENANCE')
        key=(record['location'],record['checkpoint'],record['checkpoint_sha256'])
        votes[key]=votes.get(key,0)+1
        provenance[grade]={
            'location':record['location'],'checkpoint':record['checkpoint'],
            'sha256':record['checkpoint_sha256'],'score':record['score'],
            'paired_contrasts':record.get('paired_contrasts'),
            'qualification':record['qualification'],
            'assessment_role':'EXPOSED_B_PB12_TRAINING_REPLAY'}
    source=pilot._ancestor(P43.parent)
    template=copy.deepcopy(student).cpu()
    sums={};exact={}
    rng=torch.get_rng_state()
    try:
        for (location,name,sha),multiplicity in sorted(votes.items()):
            path=(source['source_dir'] if location=='source' else out)/name
            if engine._sha(path)!=sha:
                raise ValueError('ACQUISITION_B_SOUP_INGREDIENT_CHANGED')
            model,optim,payload=engine.load_checkpoint(path)
            if (model.config!=template.config or
                    digest(payload['graph'])!=state['graph_sha256']):
                raise ValueError('ACQUISITION_B_SOUP_GRAPH_OR_ABI_DRIFT')
            for key,tensor in model.state_dict().items():
                value=tensor.detach().cpu()
                if torch.is_floating_point(value):
                    if key not in sums:
                        sums[key]=value.float()*multiplicity
                    else:
                        sums[key].add_(value.float(),alpha=multiplicity)
                elif key in exact:
                    if not torch.equal(exact[key],value):
                        raise ValueError('ACQUISITION_B_SOUP_NONFLOAT_BUFFER_DRIFT')
                else:exact[key]=value.clone()
            del model,optim,payload
    finally:
        torch.set_rng_state(rng)
    total=len(assignments)
    merged={key:(tensor/total).to(template.state_dict()[key].dtype)
            for key,tensor in sums.items()}
    merged.update(exact)
    template.load_state_dict(merged,strict=True)
    template.eval()
    for param in template.parameters():param.requires_grad_(False)
    manifest={'epoch':epoch,'votes':total,'grade_assignments':provenance,
              'unique_ingredient_checkpoints':len(votes),
              'assessment_role':'PROVISIONAL_EXPOSED_B_REPLAY_NOT_CERTIFICATION',
              'teacher_digest':state_hash(template)}
    return template,manifest


def _equal_domain_weights(g_weights,b_weights):
    """Two explicit *domain* votes, independent of their grade counts."""
    if set(g_weights)!=set(b_weights):
        raise ValueError('ACQUISITION_DOMAIN_SOUP_TENSOR_KEY_DRIFT')
    merged={}
    for name,g in g_weights.items():
        b=b_weights[name]
        if g.shape!=b.shape or g.dtype!=b.dtype:
            raise ValueError('ACQUISITION_DOMAIN_SOUP_TENSOR_ABI_DRIFT')
        if torch.is_floating_point(g):
            merged[name]=((g.detach().cpu().float()+
                           b.detach().cpu().float())*.5).to(g.dtype)
        elif torch.equal(g.detach().cpu(),b.detach().cpu()):
            merged[name]=g.detach().cpu().clone()
        else:
            raise ValueError('ACQUISITION_DOMAIN_SOUP_NONFLOAT_BUFFER_DRIFT')
    return merged


def _domain_soup_manifest(epoch,g_manifest,b_manifest,g_record,b_record,digest):
    """Expose the two domain votes and every provenance-bearing grade vote."""
    g=g_manifest['grade_assignments']
    b=b_manifest['grade_assignments']
    if (set(g)!={f'G{i:02d}' for i in range(1,23)} or
            set(b)!=set(course.GRADES) or
            g_manifest['votes']!=22 or b_manifest['votes']!=7):
        raise ValueError('ACQUISITION_DOMAIN_SOUP_GRADE_VOTE_DRIFT')
    assignments={**g,**b}
    unique={(v['location'],v['checkpoint'],v['sha256'])
            for v in assignments.values()}
    return {
        'epoch':epoch,'kind':'TWO_DOMAIN_DEVELOPMENTAL_SOUP',
        'votes':2,'domain_votes':{'G':1,'B':1},
        'domain_weights':{'G':.5,'B':.5},
        'grade_votes':{'G':22,'B':7},
        'grade_assignments':assignments,
        'cohorts':{'G':g_record,'B':b_record},
        'unique_ingredient_checkpoints':len(unique),
        'assessment_role':'DEVELOPMENTAL_TEACHER_NOT_RESEARCH_QUALIFICATION',
        'teacher_digest':digest}


def _refresh_soup(out,state,student,device):
    """Next pass: 22 G votes and seven B votes, combined as two equal domains.

    Reuse v11's exact G soup builder. B personal bests form a separate frozen
    cohort before a 50:50 G/B teaching blend; none replaces student+AdamW.
    """
    if state["passes_completed"]==state["soup_epoch"]:
        return _soup(out,state,student,device)
    if state["passes_completed"]!=state["soup_epoch"]+1 or state["grade_index"]!=0:
        raise ValueError("ACQUISITION_SOUP_EPOCH_NOT_AT_PASS_BOUNDARY")
    next_epoch=state["passes_completed"]
    temporary_state={"grade_champions":state["grade_champions"],
                     "numeric_champions":{},"soup_epoch":next_epoch}
    source=pilot._ancestor(P43.parent)
    g_teacher,g_manifest=staged._build_grade_weighted_teacher(
        source,out,temporary_state,device)
    if g_manifest['votes']!=len(state['grade_champions']):
        raise ValueError('ACQUISITION_G_SOUP_VOTE_DRIFT')
    b_teacher,b_manifest=_B_champion_soup(out,state,student,next_epoch)
    g_record=_freeze_soup_record(
        out,state,next_epoch,f'soup-G-stage-{next_epoch:04d}.pt',
        g_teacher,g_manifest)
    b_record=_freeze_soup_record(
        out,state,next_epoch,f'soup-B-stage-{next_epoch:04d}.pt',
        b_teacher,b_manifest)
    both=copy.deepcopy(g_teacher).cpu()
    both.load_state_dict(_equal_domain_weights(
        g_teacher.state_dict(),b_teacher.state_dict()),strict=True)
    both.to(device).eval()
    for param in both.parameters():param.requires_grad_(False)
    manifest=_domain_soup_manifest(
        next_epoch,g_manifest,b_manifest,g_record,b_record,state_hash(both))
    record=_freeze_soup_record(
        out,state,next_epoch,f'soup-stage-{next_epoch:04d}.pt',both,manifest)
    state["frozen_soup"]=record
    state["soup_epoch"]=next_epoch
    state["soup_history"].append(record)
    engine._atomic_json(out/"state.json",state)
    # Read back the same frozen teacher the next session will use.
    check=_soup(out,state,student,device)
    if state_hash(check)!=state_hash(both):
        raise ValueError("ACQUISITION_SOUP_ROUNDTRIP_DRIFT")
    return check


def _advance(state):
    """Pure transition: one full new+old spiral, no per-grade graduation."""
    state["grade_index"]+=1
    complete=state["grade_index"]==len(PROGRAM)
    if complete:
        state["grade_index"]=0
        state["passes_completed"]+=1
    return complete


def _ensure_pass_start(out,state,model,graph,library,device):
    """Record exactly which student begins each full new B01 spiral."""
    if state["pass_start_old"] is not None:
        if set(state["pass_start_old"])!=set(engine.REPORT_GRADE_IDS):
            raise ValueError("ACQUISITION_PASS_START_INCOMPLETE")
        if state["grade_index"]==0 and state.get("pass_start_bridge") is None:
            state["pass_start_bridge"]=_bridges(model,graph,_panels(graph,state["config"]["seed"]),device)
            engine._atomic_json(out/"state.json",state)
        return
    if state["grade_index"]!=0:
        raise ValueError("ACQUISITION_MIDPASS_BASELINE_MISSING")
    prior=_old(model,graph,library,device)
    if set(prior)!=set(engine.REPORT_GRADE_IDS):
        raise ValueError("ACQUISITION_PASS_START_PANEL_INCOMPLETE")
    state["pass_start_old"]=prior
    state["pass_start_bridge"]=_bridges(model,graph,_panels(graph,state["config"]["seed"]),device)
    engine._atomic_json(out/"state.json",state)


def _pass_report(out,state,model,graph,lib,panels,device):
    prior=state["pass_start_old"]
    if prior is None:
        raise ValueError("ACQUISITION_PASS_START_MISSING")
    after=_old(model,graph,lib,device)
    p43=state["source_old_scores"]
    if set(after)!=set(prior) or set(after)!=set(p43) or len(after)!=22:
        raise ValueError("ACQUISITION_HISTORIC_PANEL_INCOMPLETE")
    development=_bridges(model,graph,panels,device)
    baseline=state["baseline_bridge"]
    numeric_now=_basic_numeric(model,graph,device)
    old_mean=sum(after.values())/22
    original_mean=sum(p43.values())/22
    worst=min((after[g]-p43[g] for g in p43))
    bridge_before=sum(x["correct"] for grade in baseline.values()
                      for x in grade.values())
    bridge_after=sum(x["correct"] for grade in development.values()
                     for x in grade.values())
    contrasts=sum(x["paired_contrasts"] for grade in development.values()
                  for x in grade.values())
    anchor=state["holistic_anchor"]
    reasons=[]
    for grade in sorted(p43):
        lost=round((p43[grade]-after[grade])*24)
        if lost>=3:
            reasons.append({"kind":"HISTORICAL_GRADE_REGRESSION",
                            "grade":grade,"lost_questions":lost})
    if old_mean<anchor["old_mean"]-OLD_MEAN_PAUSE+1e-9:
        reasons.append({"kind":"HISTORICAL_MEAN_BELOW_ANCHOR",
                        "actual":old_mean,"minimum":anchor["old_mean"]-OLD_MEAN_PAUSE})
    severe=bool(reasons)
    carry=state["carry_forward"]
    window_correct=sum(x["correct"] for folds in carry["window_start_bridge"].values()
                       for x in folds.values())
    window_contrasts=sum(x["paired_contrasts"] for folds in carry["window_start_bridge"].values()
                         for x in folds.values())
    # Replayed, explicitly trained examples are an acquisition measurement,
    # not independently replicated development or research qualification.
    learned_on_replay=bridge_after>window_correct
    qualified=False
    if state["passes_completed"]<=carry["start_passes_completed"]:
        raise ValueError("TIME_FIRST_PASS_DID_NOT_ADVANCE")
    completed=state["passes_completed"]-carry["start_passes_completed"]
    report={
        "pass":state["passes_completed"],"checkpoint":state["checkpoint"],
        "checkpoint_sha256":state["checkpoint_sha256"],
        "optimizer_step":state["optimizer_step"],
        "old_scores":after,"old_mean":old_mean,
        "p43_mean":original_mean,"old_mean_vs_p43":old_mean-original_mean,
        "old_mean_vs_pass_start":old_mean-sum(prior.values())/22,
        "worst_old_grade_vs_p43":worst,
        "bridge":development,"bridge_correct":bridge_after,
        "basic_numeric":numeric_now,
        "basic_numeric_four_way_correct":sum(numeric_now[f]['four_way']['correct']
                                              for f in ('primary','confirm')),
        "basic_numeric_full_101_correct":sum(numeric_now[f]['full_101']['correct']
                                              for f in ('primary','confirm')),
        "basic_numeric_four_way_start":sum(state['numeric_start'][f]['four_way']['correct']
                                            for f in ('primary','confirm')),
        "prerequisite_grades":{g:after[g] for g in
                                 ('G03','G11','G12','G19','G20','G22')},
        "prerequisite_grade_start":state['prerequisite_start'],
        "bridge_initial_correct":bridge_before,"bridge_contrasts":contrasts,
        "bridge_window_start_correct":window_correct,
        "bridge_window_start_contrasts":window_contrasts,
        "bridge_vs_window_start_correct":bridge_after-window_correct,
        "bridge_vs_window_start_contrasts":contrasts-window_contrasts,
        "surviving_v11_optimizer_updates":state["optimizer_step"]-carry["window_start_optimizer_step"],
        "pass_start_bridge":copy.deepcopy(state.get("pass_start_bridge")),
        "rollback_triggers":reasons,
        "would_rollback_under_v8":severe,
        "historical_mean_floor":anchor["old_mean"]-OLD_MEAN_PAUSE,
        "research_qualified":False,
        "assessment_role":"TRAINING_REPLAY_NOT_GENERALIZATION",
        "learned_on_replay":learned_on_replay,
        "disposition":"TIME_FIRST_CARRY_FORWARD"}
    state["pass_ledger"].append(report)
    # No research champion is promoted solely by memorizing exposed drills.
    # best_development still archives the best provisional acquisition state.
    # Evaluation of the old safety gate stays visible. It is not allowed
    # to delete accumulated representation or AdamW during this window.
    # The protected holistic anchor is intentionally never moved.
    candidate_rank=[contrasts,bridge_after,old_mean]
    if candidate_rank>carry["best_development"]["ranking"]:
        carry["best_development"]={
            "checkpoint":state["checkpoint"],
            "checkpoint_sha256":state["checkpoint_sha256"],
            "optimizer_step":state["optimizer_step"],
            "bridge_correct":bridge_after,"bridge_contrasts":contrasts,
            "old_mean":old_mean,"ranking":candidate_rank,
            "source":f"PASS_{state['passes_completed']}"}
    carry["completed_boundaries"]=completed
    carry["reports"].append({"pass":state["passes_completed"],
        "old_mean":old_mean,"bridge_correct":bridge_after,
        "bridge_contrasts":contrasts,"checkpoint":state["checkpoint"],
        "would_rollback_under_v8":severe,
        "rollback_triggers":copy.deepcopy(reasons)})
    _record_joint(state,report)
    surface=state["time_first"]
    report["joint_tracking"]={
        "best_joint":copy.deepcopy(surface["best_joint"]),
        "best_historical":copy.deepcopy(surface["best_historical"]),
        "nondominated":copy.deepcopy(surface["joint_frontier"]),
        "ranking_role":"DESCRIPTIVE_EXPOSED_REPLAY_NOT_QUALIFICATION"}
    # Preserve provisional B micro-champions, but do not qualify them as
    # independent soup votes by scoring exact rehearsed questions.
    state["pass_start_old"]=None
    state["pass_start_bridge"]=None
    return report


def _prune(out,state,*,keep_recent=8,keep_passes=4):
    """Prune only this run's redundant binaries AFTER the atomic state save."""
    records=state["grade_ledger"]
    keep={state["checkpoint"],state["source"]["checkpoint"],
          state["holistic_anchor"]["checkpoint"],P43.name}
    if state.get("carry_forward"):
        carry=state["carry_forward"]
        keep.add(carry["window_start_checkpoint"])
        keep.add(carry["best_development"]["checkpoint"])
    if state.get("time_first"):
        surface=state["time_first"]
        keep.update(p["checkpoint"] for p in surface["source_comparators"].values())
        keep.update(p["checkpoint"] for p in surface["joint_frontier"])
        keep.update(p["checkpoint"] for p in surface["pass_observations"])
        keep.update([surface["best_joint"]["checkpoint"],
                     surface["best_historical"]["checkpoint"]])
    keep.update(r["checkpoint"] for r in records[-keep_recent:])
    keep.update(r["checkpoint"] for r in state["pass_ledger"][-keep_passes:])
    champion=state.get("research_champion")
    if champion:
        keep.add(champion["checkpoint"])
    for kind in ("grade_champions","bridge_champions","provisional_bridge_champions"):
        keep.update(item["checkpoint"] for item in state[kind].values()
                    if item.get("location")=="research")
    for path in out.glob("student-*.pt"):
        if path.name not in keep:
            path.unlink()



def _consolidation_from_scores(before,after):
    """Exact School50 528-item gate with a cached parent evaluation.

    The parent is constant across candidate trials and its 528 answers must
    not be redundantly recomputed. This is behavior-equivalent to the
    original engine._consolidation_confirmation.
    """
    grades=engine.REPORT_GRADE_IDS
    if set(before)!=set(grades) or set(after)!=set(grades):
        raise ValueError("BRIDGE_PRIORITY_FULL_22_PROBE_INCOMPLETE")
    deltas={grade:after[grade]-before[grade] for grade in grades}
    mean_delta=sum(deltas.values())/len(deltas)
    worst=min(deltas,key=deltas.get)
    worst_delta=deltas[worst]
    minimum_net_gain=1/(24*len(grades))
    if mean_delta < minimum_net_gain-1e-12:
        decision,reason="REJECT","CONSOLIDATION_FULL_PROBE_NO_GAIN"
    elif worst_delta <= -(2/24):
        decision,reason="REJECT","CONSOLIDATION_FULL_PROBE_RETENTION_LOSS"
    else:
        decision,reason="PROMOTE","CONSOLIDATION_FULL_PROBE_GAIN"
    return {"decision":decision,"reason":reason,"mean_delta":mean_delta,
            "minimum_net_gain":minimum_net_gain,
            "median_delta":statistics.median(deltas.values()),
            "improved_grades":sum(d>0 for d in deltas.values()),
            "regressed_grades":sum(d<0 for d in deltas.values()),
            "unchanged_grades":sum(d==0 for d in deltas.values()),
            "worst_grade":worst,"worst_grade_delta":worst_delta,
            "deltas":deltas,"before_scores":before,"after_scores":after}


def _developmental_admission(*,focused,focus_gain,grade_gain):
    """Choose cumulative acquisition independently of historical G528 debt.

    This is not a grade-champion or model-soup qualification decision.
    """
    if focused:
        acquired=focus_gain>0
        reason="FOCUSED_PRIMITIVE_ACQUIRED" if acquired else "FOCUSED_PRIMITIVE_NO_GAIN"
    else:
        acquired=grade_gain>0
        reason="HISTORICAL_GRADE_ACQUIRED" if acquired else "HISTORICAL_GRADE_NO_GAIN"
    return {"decision":"PROMOTE" if acquired else "REJECT","reason":reason}


def _bridge_developmental_admission(*,before_pairs,after_pairs,
                                   before_correct,after_correct,
                                   before_numeric,after_numeric):
    """Rehearsal G debt is reported separately, not used as a B admission veto."""
    acquired=(after_pairs>before_pairs or after_correct>before_correct or
              after_numeric>before_numeric)
    return {"decision":"ELIGIBLE" if acquired else "REJECT",
            "reason":("B_DEVELOPMENTAL_ACQUISITION" if acquired else
                      "B_DEVELOPMENTAL_NO_GAIN")}


def _focus_batch(grade,library,graph,policy,rng):
    """32 typed rows: all new exposed primitives plus varied OLD G rehearsal.

    The historical B01-B07 grades are separately visited every full spiral;
    focused visits may therefore spend their remaining rows on legacy G
    retention, instead of mixing every new concept on every update as v13 did.
    """
    if grade in focused_course.FOCUSED:
        return focused_course.batch(grade,library,graph,policy,rng)
    from . import primitive_staircase_v13 as direct
    if grade=='G15':current=direct.rows(concept='EDGE')
    else:raise ValueError('V15_UNKNOWN_FOCUSED_GRADE')
    baseline,_=lessons.compose_batch(library,int(grade[1:]),policy,graph,rng)
    seen={r['id'] for r in current}
    old=[]
    for row in baseline:
        if row['id'] in seen:continue
        old.append(row)
        seen.add(row['id'])
        if len(current)+len(old)==32:break
    if len(current)+len(old)!=32:
        raise ValueError('V14_FOCUSED_BATCH_REPLAY_OR_DUPLICATE_SHORTAGE')
    for row in old:row['answer_kind']='evidence'
    return current+old,{'current':len(current),'old':len(old),'preview':0}


def _train_focus(candidate,optimizer,anchor,soup,rows,graph,policy,device):
    """Same parent-KL, frozen-soup consolidation and AdamW as v11,
    using the inherited typed readout for new numeric outputs.
    """
    optimizer.zero_grad(set_to_none=True)
    candidate.train()
    loss,components=staged._typed_loss(
        candidate,anchor,soup,rows,graph,contract.numeric_token_ids(graph)[:4],
        policy,device)
    if not bool(torch.isfinite(loss)):
        raise ValueError('V14_FOCUSED_NONFINITE_LOSS')
    loss.backward()
    torch.nn.utils.clip_grad_norm_(candidate.parameters(),1.0)
    optimizer.step()
    return dict(components,total_loss=float(loss.detach().cpu()))

def _historic_visit(out,state,model,optimizer,graph,soup,lib,panels,device,observer=None):
    """Mature-grade School50 competition. Every attempt has one immutable parent."""
    grade=PROGRAM[state["grade_index"]]
    assert grade.startswith("G")
    number=int(grade[1:])
    base_step=state["optimizer_step"]
    parent_path=out/state["checkpoint"]
    parent_hash=state["checkpoint_sha256"]
    if engine._sha(parent_path)!=parent_hash:
        raise ValueError("HYBRID_PARENT_CHECKPOINT_CHANGED")
    probe_seed=170003+number*617
    before=engine._scores(model,lib,graph,number,probe_seed,device=device)
    source_before=_old(model,graph,lib,device)
    rng=random.Random(state["config"]["seed"]+state["visits"]*71993+
                      state["passes_completed"]*1000003)
    seen=set(); attempts=[]; best=None; best_rank=None
    from . import primitive_staircase_runner_v13 as scored
    focused=grade in FOCUSED_G or grade==DEVELOPMENTAL_G22
    focus_before=(focused_course.measure(model,graph,grade,device)['by_concept']
                  if grade in focused_course.FOCUSED else
                  scored._score(model,graph,device)['by_concept']
                  if focused else None)
    candidate_count=(state['config']['focused_G_attempts']
                     if grade in FOCUSED_G else state['config']['historic_attempts'])
    for attempt in range(1,candidate_count+1):
        candidate,optim,payload=engine.load_checkpoint(parent_path)
        engine._device(candidate,optim,device)
        if (optimizer_receipt(optim)["steps"]!=[base_step] or
                digest(payload["graph"])!=state["graph_sha256"]):
            raise ValueError("HYBRID_ATTEMPT_NOT_SAME_PARENT")
        trial_rng=random.Random(rng.randrange(2**62))
        key,policy=engine.pick(state["teacher"],number,trial_rng,exclude=seen)
        seen.add(key)
        for group in optim.param_groups:group["lr"]=policy["lr"]
        reference=copy.deepcopy(candidate).eval()
        for param in reference.parameters():param.requires_grad_(False)
        losses=[];allocation={"current":0,"old":0,"preview":0}
        for _ in range(state["config"]["block"]):
            if focused:
                rows,counts=_focus_batch(grade,lib,graph,policy,trial_rng)
                losses.append(_train_focus(candidate,optim,reference,soup,
                                           rows,graph,policy,device))
            else:
                rows,counts=lessons.compose_batch(lib,number,policy,graph,trial_rng)
                losses.append(engine._train(candidate,optim,reference,graph,
                                           rows,counts,policy,device,
                                           consensus_teacher=soup,
                                           consensus_weight=engine.CONSOLIDATION_WEIGHT))
            for k,v in counts.items():allocation[k]+=v
        expected=base_step+state["config"]["block"]
        if optimizer_receipt(optim)["steps"]!=[expected]:
            raise ValueError("HYBRID_ATTEMPT_ADAMW_CONTINUITY")
        after=engine._scores(candidate,lib,graph,number,probe_seed,device=device)
        confirmation=_consolidation_from_scores(source_before,
                                                        _old(candidate,graph,lib,device))
        old_delta=confirmation["mean_delta"]
        focus_after=(focused_course.measure(candidate,graph,grade,device)['by_concept']
                     if grade in focused_course.FOCUSED else
                     scored._score(candidate,graph,device)['by_concept']
                     if focused else None)
        if focused:
            names=(('SUB','MUL','EQ_BRIDGE') if grade=='G20'
                   else ('NESTED_NUMERIC','NESTED_EQ') if grade=='G22'
                   else ('MEMBER',) if grade=='G11'
                   else (FOCUSED_G[grade],))
            before_f=sum(focus_before[name]['correct'] for name in names)
            after_f=sum(focus_after[name]['correct'] for name in names)
            focus_gain=after_f-before_f
        else:
            focus_gain=0
        reward=2*(focus_gain if focused else after-before)+.6*old_delta
        # Acquisition and historical qualification are separate decisions.
        # The full 528-item comparison remains evidence, never a veto on
        # newly acquired focus material.
        gate=_developmental_admission(focused=focused,focus_gain=focus_gain,
                                     grade_gain=after-before)
        credit=engine._candidate_teacher_credit(reward,gate)
        if gate['decision']=='REJECT':
            credit=min(credit,0.0)
        engine.observe(state["teacher"],number,key,credit)
        state["attempted_updates"]+=state["config"]["block"]
        record={"grade":grade,"attempt":attempt,"parent_step":base_step,
                "candidate_step":expected,"policy_id":key,"policy":policy,
                "before":before,"after":after,"raw_reward":reward,
                "teacher_credit":credit,"confirmation":confirmation,
                "historical_qualification_gate":confirmation['decision'],
                "decision":gate["decision"],"reason":gate["reason"],
               "row_exposures":allocation,"last_loss":losses[-1],
               "selected":False}
        if focused:
            record['direct_path_before']=focus_before
            record['direct_path_after']=focus_after
            record['direct_path_correct_gain']=focus_gain
        if observer is not None:
            grade_pb48=engine._grade_champion_score(
                candidate,graph,lib,number,device=device)
            record['run_local_grade_pb48']=grade_pb48
            observer.capture(out,state,candidate,record,
                             int(round(grade_pb48*engine.GRADE_CHAMPION_COUNT)),
                             engine.GRADE_CHAMPION_COUNT)
        attempts.append(record)
        # Rank developmental candidates on acquisition; preserve historical
        # evidence separately for later consolidation and qualification.
        if gate["decision"]=="PROMOTE":
            ranking=((focus_gain if focused else confirmation['mean_delta']),
                     confirmation["mean_delta"],confirmation["worst_grade_delta"],
                     confirmation["median_delta"],reward,after-before,-attempt)
            if best is None or ranking>best_rank:
                best=(candidate,optim,record)
                best_rank=ranking
    state["candidate_ledger"].extend(attempts)
    selected=best is not None
    if selected:
        model,optimizer,selected_record=best
        selected_record["selected"]=True
        new_step=base_step+state["config"]["block"]
        filename,sha=engine._checkpoint(out,model,optimizer,graph,{
            "step":new_step,"grade":grade,"epoch":VERSION,
            "pass":state["passes_completed"]+1,
            "attempt":selected_record["attempt"],
            "parent_checkpoint_sha256":parent_hash})
        state["checkpoint"]=filename
        state["checkpoint_sha256"]=sha
        state["optimizer_step"]=new_step
        state["retained_updates"]+=state["config"]["block"]
        grade_score=engine._grade_champion_score(model,graph,lib,number,
                                                  device=device)
        prior=state["grade_champions"].get(grade)
        # Focus-only gains do not qualify a historical G champion/soup vote.
        qualified=(selected_record['confirmation']['decision']=='PROMOTE')
        promoted=qualified and (prior is None or grade_score>prior["score"])
        if promoted:
            state["grade_champions"][grade]={
                "score":grade_score,"checkpoint":filename,
                "checkpoint_sha256":sha,"optimizer_step":new_step,
                "source_pass":state["passes_completed"]+1,
                "location":"research","qualification":"FULL22_CONFIRMED"}
    else:
        selected_record=None
        promoted=False
        grade_score=None
        # No candidate won. The original parent student and AdamW remain.
        if state["checkpoint"]!=parent_path.name or state["optimizer_step"]!=base_step:
            raise ValueError("HYBRID_REJECTED_PARENT_CHANGED")
    state["visits"]+=1
    completed=_advance(state)
    row={"visit":state["visits"],"grade":grade,
         "pass":state["passes_completed"] if completed else state["passes_completed"]+1,
         "optimizer_step":state["optimizer_step"],
         "checkpoint":state["checkpoint"],
         "checkpoint_sha256":state["checkpoint_sha256"],
         "attempts":len(attempts),"accepted_attempt":
            None if selected_record is None else selected_record["attempt"],
         "updates":state["config"]["block"] if selected else 0,
         "attempted_updates":len(attempts)*state["config"]["block"],
         "development_before":before,
         "development_after":before if not selected else selected_record["after"],
         "old_before":source_before,
         "old_after":source_before if not selected else
                     selected_record["confirmation"]["after_scores"],
         "grade_champion_score":grade_score,"new_grade_champion":promoted,
         "policy_id":None if selected_record is None else selected_record["policy_id"],
         "method":None,"teacher_events":state["teacher"]["events"],
         "reward":0 if selected_record is None else selected_record["raw_reward"],
         "last_loss":None if selected_record is None else selected_record["last_loss"],
         "row_exposures":None if selected_record is None else selected_record["row_exposures"],
         "disposition":("DEVELOPMENTAL_CANDIDATE_RETAINED" if selected else
                        "NO_DEMONSTRATED_DEVELOPMENTAL_GAIN")}
    state["grade_ledger"].append(row)
    report=_pass_report(out,state,model,graph,lib,panels,device) if completed else None
    state["last_run_status"]="GRADE_BOUNDARY"
    engine._atomic_json(out/"state.json",state)
    _prune(out,state)
    if report and report["disposition"].startswith("ROLLED_BACK"):
        model,optimizer,_=_load_student(out,state,device)
    return row,report,model,optimizer



def _bridge_visit(out,state,model,optimizer,graph,soup,lib,panels,device,observer=None):
    """Historical B visit; one independently sampled candidate in v14.

    The inherited v11 optimizer, typed lessons and frozen soup are reused.
    None must immediately pass a mature-grade promotion gate; correctness
    and contrast-sensitive evidence rank eligible acquisitions. The source
    student and AdamW move once, only after the best candidate is selected.
    """
    grade=PROGRAM[state["grade_index"]]
    if not grade.startswith("B"):
        raise ValueError("BRIDGE_PRIORITY_NOT_A_BRIDGE_GRADE")
    index=course.GRADES.index(grade)
    grade_key=2001+index
    base_step=state["optimizer_step"]
    parent=out/state["checkpoint"]
    parent_sha=state["checkpoint_sha256"]
    if engine._sha(parent)!=parent_sha:
        raise ValueError("BRIDGE_PRIORITY_PARENT_CHANGED")
    before={fold:_small_panel(model,rows,graph,device)
            for fold,rows in panels[grade].items()}
    basic_before=_basic_numeric(model,graph,device)
    before_old={f"G{g:02d}":engine._scores(
        model,lib,graph,g,170003+g*617,count=12,device=device)
        for g in (9,10)}
    rng=random.Random(state["config"]["seed"]+
                      state["visits"]*71993+state["passes_completed"]*1000003)
    attempts=[]
    selected=None
    rank=None
    seen=set()
    for attempt in range(1,state["config"]["bridge_attempts"]+1):
        candidate,candidate_optimizer,payload=engine.load_checkpoint(parent)
        engine._device(candidate,candidate_optimizer,device)
        if (optimizer_receipt(candidate_optimizer)["steps"]!=[base_step] or
                digest(payload["graph"])!=state["graph_sha256"]):
            raise ValueError("BRIDGE_PRIORITY_CANDIDATE_NOT_SAME_PARENT")
        trial_rng=random.Random(rng.randrange(2**62))
        key,policy=engine.pick(state["teacher"],grade_key,trial_rng,exclude=seen)
        seen.add(key)
        method=staged._choose_instruction(state["teacher"],grade,trial_rng)
        for group in candidate_optimizer.param_groups:
            group["lr"]=policy["lr"]
        anchor=copy.deepcopy(candidate).eval()
        for param in anchor.parameters():
            param.requires_grad_(False)
        exposures={"current":0,"random_old":0,"preview":0}
        last_loss=None
        for _ in range(state["config"]["block"]):
            rows,counts=course.compile_batch(
                grade,lib,graph,trial_rng,method=method)
            last_loss=_train_small_step(candidate,candidate_optimizer,anchor,soup,
                                         rows,graph,policy,device)
            for kind,value in counts.items():
                exposures[kind]+=value
        expected_step=base_step+state["config"]["block"]
        if optimizer_receipt(candidate_optimizer)["steps"]!=[expected_step]:
            raise ValueError("BRIDGE_PRIORITY_CANDIDATE_ADAMW_STEP_DRIFT")
        after={fold:_small_panel(candidate,rows,graph,device)
               for fold,rows in panels[grade].items()}
        basic_after=_basic_numeric(candidate,graph,device)
        after_old={f"G{g:02d}":engine._scores(
            candidate,lib,graph,g,170003+g*617,count=12,device=device)
            for g in (9,10)}
        old_deltas={g:after_old[g]-before_old[g] for g in before_old}
        old_mean=sum(old_deltas.values())/len(old_deltas)
        total_correct=lambda entries:sum(x["correct"] for x in entries.values())
        total_contrasts=lambda entries:sum(x["paired_contrasts"] for x in entries.values())
        before_correct=total_correct(before)
        after_correct=total_correct(after)
        before_pairs=total_contrasts(before)
        after_pairs=total_contrasts(after)
        ce_improvement=sum(before[f]["ce"]-after[f]["ce"]
                           for f in ("primary","confirm"))
        before_numeric=sum(basic_before[f]['four_way']['correct']
                           for f in ('primary','confirm'))
        after_numeric=sum(basic_after[f]['four_way']['correct']
                          for f in ('primary','confirm'))
        raw_reward=(2*(after_correct-before_correct)/(2*course.PANEL_ROWS)+
                    .25*(after_pairs-before_pairs)/4+
                    .5*(after_numeric-before_numeric)/4+
                    .6*old_mean)
        # Do not carry a B candidate merely because it cleared a nonexistent
        # retention veto: demand acquisition evidence on the focused B grade.
        gate=_bridge_developmental_admission(
            before_pairs=before_pairs,after_pairs=after_pairs,
            before_correct=before_correct,after_correct=after_correct,
            before_numeric=before_numeric,after_numeric=after_numeric)
        guard_safe=gate['decision']=='ELIGIBLE'
        teacher_credit=raw_reward if guard_safe else min(raw_reward,0.0)
        engine.observe(state["teacher"],grade_key,key,teacher_credit)
        staged._observe_instruction(state["teacher"],grade,method,teacher_credit)
        state["attempted_updates"]+=state["config"]["block"]
        record={
            "grade":grade,"attempt":attempt,"parent_step":base_step,
            "parent_checkpoint_sha256":parent_sha,
            "candidate_step":expected_step,"policy_id":key,"policy":policy,
            "instruction_method":method,
            "bridge_before":before,"bridge_after":after,
            "basic_numeric_before":basic_before,"basic_numeric_after":basic_after,
            "old_before":before_old,"old_after":after_old,
            "correct_before":before_correct,"correct_after":after_correct,
            "paired_before":before_pairs,"paired_after":after_pairs,
            "bridge_ce_improvement":ce_improvement,
            "raw_reward":raw_reward,"teacher_credit":teacher_credit,
            "decision":gate['decision'],"reason":gate['reason'],
            "row_exposures":exposures,"last_loss":last_loss,"selected":False}
        if observer is not None:
            observer.capture(out,state,candidate,record,
                             after_correct,2*course.PANEL_ROWS)
        attempts.append(record)
        if guard_safe:
            ranking=(after_pairs,after_correct,after_numeric,
                     ce_improvement,old_mean,-attempt)
            if selected is None or ranking>rank:
                selected=(candidate,candidate_optimizer,record)
                rank=ranking
    state["candidate_ledger"].extend(attempts)
    if selected is None:
        chosen=None
        grade_score=None
        personal_best=False
        after=before
        after_old=before_old
        disposition="B_NO_DEMONSTRATED_ACQUISITION"
        # Rejected trial optimizer and weights never reach the student.
        if (state["checkpoint"]!=parent.name or
                state["optimizer_step"]!=base_step):
            raise ValueError("BRIDGE_PRIORITY_REJECTED_PARENT_MUTATED")
    else:
        model,optimizer,chosen=selected
        chosen["selected"]=True
        new_step=base_step+state["config"]["block"]
        filename,sha=engine._checkpoint(out,model,optimizer,graph,{
            "step":new_step,"grade":grade,"epoch":VERSION,
            "pass":state["passes_completed"]+1,
            "selected_attempt":chosen["attempt"],
            "parent_checkpoint_sha256":parent_sha})
        if engine._sha(out/filename)!=sha:
            raise ValueError("BRIDGE_PRIORITY_B_CHECKPOINT_DRIFT")
        state["checkpoint"]=filename
        state["checkpoint_sha256"]=sha
        state["optimizer_step"]=new_step
        state["retained_updates"]+=state["config"]["block"]
        after=chosen["bridge_after"]
        after_old=chosen["old_after"]
        grade_score=chosen["correct_after"]/(2*course.PANEL_ROWS)
        pairs=chosen["paired_after"]
        previous=state["provisional_bridge_champions"].get(grade)
        personal_best=(previous is None or
                       grade_score>previous["score"] or
                       (grade_score==previous["score"] and
                        pairs>previous.get("paired_contrasts",-1)))
        if personal_best:
            state["provisional_bridge_champions"][grade]={
                "score":grade_score,"paired_contrasts":pairs,
                "checkpoint":filename,"checkpoint_sha256":sha,
                "optimizer_step":new_step,
                "source_pass":state["passes_completed"]+1,
                "location":"research","qualification":"PROVISIONAL"}
        disposition="B_DEVELOPMENTAL_ACQUISITION_RETAINED"
    state["visits"]+=1
    complete=_advance(state)
    row={
        "visit":state["visits"],"grade":grade,
        "pass":state["passes_completed"] if complete else state["passes_completed"]+1,
        "optimizer_step":state["optimizer_step"],
        "checkpoint":state["checkpoint"],
        "checkpoint_sha256":state["checkpoint_sha256"],
        "attempts":len(attempts),
        "accepted_attempt":None if chosen is None else chosen["attempt"],
        "updates":state["config"]["block"] if chosen else 0,
        "attempted_updates":len(attempts)*state["config"]["block"],
         "development_before":before,"development_after":after,
         "basic_numeric_before":basic_before,
         "basic_numeric_after":basic_before if chosen is None else chosen['basic_numeric_after'],
        "old_before":before_old,"old_after":after_old,
        "grade_champion_score":grade_score,
        "new_grade_champion":personal_best,
        "policy_id":None if chosen is None else chosen["policy_id"],
        "method":None if chosen is None else chosen["instruction_method"],
        "teacher_events":state["teacher"]["events"],
        "reward":0 if chosen is None else chosen["raw_reward"],
        "last_loss":None if chosen is None else chosen["last_loss"],
        "row_exposures":None if chosen is None else chosen["row_exposures"],
        "disposition":disposition}
    state["grade_ledger"].append(row)
    report=_pass_report(out,state,model,graph,lib,panels,device) if complete else None
    state["last_run_status"]="GRADE_BOUNDARY"
    engine._atomic_json(out/"state.json",state)
    _prune(out,state)
    if report and report["disposition"].startswith("ROLLED_BACK"):
        model,optimizer,_=_load_student(out,state,device)
    return row,report,model,optimizer


def _grade_visit(out,state,model,optimizer,graph,soup,lib,panels,device,observer=None):
    grade=PROGRAM[state["grade_index"]]
    if grade.startswith("G"):
        return _historic_visit(out,state,model,optimizer,graph,soup,lib,
                               panels,device,observer=observer)
    return _bridge_visit(out,state,model,optimizer,graph,soup,lib,
                         panels,device,observer=observer)

def status(run_dir=RUN):
    path=Path(run_dir).expanduser()/"state.json"
    if not path.is_file():
        return {"status":"NOT_STARTED","run_dir":str(path.parent)}
    state=engine._read(path)
    return {"status":state["last_run_status"],"phase":state["phase"],
            "champion_boundary":state['config'].get('champion_boundary'),
            "run_local_champions":{
                "active_session":(state.get('run_local_champions',{}).get('active') or {}).get('id'),
                "active_status":(state.get('run_local_champions',{}).get('active') or {}).get('status'),
                "completed_sessions":len(state.get('run_local_champions',{}).get('completed',[])),
                "most_recent":({
                    'id':state['run_local_champions']['completed'][-1]['id'],
                    'grade_champions':len(state['run_local_champions']['completed'][-1]['selected']),
                    'soup_status':(state['run_local_champions']['completed'][-1]['soup'] or {}).get('status')}
                    if state.get('run_local_champions',{}).get('completed') else None)},
            "next_grade":PROGRAM[state["grade_index"]],
            "grade_index":state["grade_index"],
            "visits":state["visits"],"passes_completed":state["passes_completed"],
            "optimizer_step":state["optimizer_step"],
            "attempted_updates":state["attempted_updates"],
            "retained_updates":state["retained_updates"],
            "teacher_events":state["teacher"]["events"],
            "source":state["source"],"research_champion":state["research_champion"],
            "soup_epoch":state["soup_epoch"],
            "bridge_champions":len(state["bridge_champions"]),
            "grade_champions":len(state["grade_champions"]),
            "latest_grade":state["grade_ledger"][-1] if state["grade_ledger"] else None,
            "latest_pass":state["pass_ledger"][-1] if state["pass_ledger"] else None,
            "last_session":state.get("last_session"),
            "surviving_v11_optimizer_updates":(
                state["optimizer_step"]-state["carry_forward"]["window_start_optimizer_step"]
                if "carry_forward" in state else None),
            "carry_forward":{
                "completed_boundaries":state["carry_forward"]["completed_boundaries"],
                "stop_rule":"TIME_BUDGET_AT_GRADE_BOUNDARY",
                "starting_grade":"B01",
                "start_passes_completed":state["carry_forward"]["start_passes_completed"],
                "best_development":state["carry_forward"]["best_development"],
                "recent_report":(state["carry_forward"]["reports"][-1]
                                 if state["carry_forward"]["reports"] else None)},
            "time_first":{
                "default_minutes":state["time_first"]["default_minutes"],
                "source_comparators":state["time_first"]["source_comparators"],
                "best_joint":state["time_first"]["best_joint"],
                "best_historical":state["time_first"]["best_historical"],
                "joint_frontier":state["time_first"]["joint_frontier"],
                "completed_new_passes":len(state["time_first"]["pass_observations"])}}


def run(*,run_dir=RUN,source_dir=SOURCE,device="mps",minutes=DEFAULT_MINUTES,
        block=64,seed=20261013,champion_boundary='session',
        initialize_only=False,stop_requested=lambda:False,reporter=None):
    if not 0<minutes<=1440 or device not in ("cpu","mps"):
        raise ValueError("ACQUISITION_INVALID_SESSION_BUDGET")
    config=configuration(block=block,seed=seed,champion_boundary=champion_boundary)
    out=Path(run_dir).expanduser().resolve(strict=False)
    if out!=RUN.resolve():
        raise ValueError('V15_NEEDS_CANONICAL_ISOLATED_RUN_DIR')
    source=Path(source_dir).expanduser().resolve(strict=True)
    if (out==source or out in source.parents or source in out.parents or
            out==P43.parent or P43.parent in out.parents or out in P43.parent.parents):
        raise ValueError("ACQUISITION_SOURCE_DESTINATION_OVERLAP")
    out.parent.mkdir(parents=True,exist_ok=True)
    lock=out.with_name(out.name+".writer.lock")
    fd=os.open(lock,os.O_CREAT|os.O_RDWR|getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("ACQUISITION_ALREADY_HAS_WRITER") from exc
        if not out.exists():
            raise ValueError('V15_REQUIRES_NONTRAINING_PREPARE_RUN_LOCAL')
        state=engine._read(out/"state.json")
        _assert_frozen(state,config)
        if initialize_only:
            _load_student(out,state,device)
            return status(out)
        if state["phase"]!="ACQUISITION":
            return status(out)
        if (out/"sealed-evaluation.json").exists():
            raise ValueError("ACQUISITION_SEALED_LINEAGE_IS_FROZEN")
        model,optimizer,graph=_load_student(out,state,device)
        soup=_soup(out,state,model,device)
        lib=lessons.TeacherLibrary()
        panels=_panels(graph,seed)
        policy=local_champions.RunChampionPolicy(sys.modules[__name__])
        previous=state['run_local_champions'].get('active')
        if previous is not None and previous['status']=='FINALIZING':
            policy.finish(out,state,model,graph,lib,panels,device,
                          previous['stop_reason'])
        policy.begin(out,state,model)
        begun=time.monotonic();visits=0
        attempted_at_start=state["attempted_updates"]
        retained_at_start=state["retained_updates"]
        def finish(reason):
            if engine._sha(P43)!=pilot.CHAMPION_SHA256:
                raise ValueError("ACQUISITION_PROTECTED_P43_CHANGED")
            if (engine._sha(SOURCE/'state.json')!=
                    state['v14_origin']['source_state_sha256'] or
                    engine._sha(SOURCE/state['v14_origin']['source_checkpoint'])!=
                    state['v14_origin']['source_checkpoint_sha256']):
                raise ValueError('V14_PROTECTED_V11_SOURCE_DRIFT')
            if engine._sha(PREDECESSOR/'state.json')!=state['v15_origin']['source_state_sha256']:
                raise ValueError('V15_PROTECTED_V14_PREDECESSOR_CHANGED')
            # After the last grade boundary, measure and archive every run
            # winner and resolve ties. This does not average optimizer moments
            # or install an unqualified teacher in the causal training loop.
            policy.operator_stop(out,state,model,graph,lib,panels,device,reason)
            state["last_run_status"]=reason
            state["last_session"]={"stop_reason":reason,
                "elapsed_seconds":round(time.monotonic()-begun,2),
                "budget_minutes":minutes,"boundary_kind":"GRADE",
                "visits":visits,
                "retained_updates":state["retained_updates"]-retained_at_start,
                "attempted_updates":state["attempted_updates"]-attempted_at_start}
            engine._atomic_json(out/"state.json",state)
            return status(out)
        while True:
            if stop_requested():
                return finish("GRACEFUL_OPERATOR_STOP")
            if state["phase"]!="ACQUISITION":
                return finish("TIME_FIRST_PHASE_CLOSED")
            if time.monotonic()-begun>=minutes*60:
                return finish("TIME_BUDGET_EXHAUSTED")
            if state['run_local_champions']['active'] is None:
                policy.begin(out,state,model)
            # V15 freezes the inherited teacher throughout this operator
            # session, rather than mixing grades from incompatible sessions
            # at every B01 boundary. The new soup is evaluated at run end.
            soup=policy.before_pass(out,state,soup)
            _ensure_pass_start(out,state,model,graph,lib,device)
            record,report,model,optimizer=_grade_visit(out,state,model,optimizer,graph,soup,lib,
                                                       panels,device,observer=policy)
            visits+=1
            if (champion_boundary=='complete-program' and
                    policy.complete_program_covered(state)):
                policy.finish(out,state,model,graph,lib,panels,device,
                              'FULL_29_GRADE_COLLECTION_COMPLETED')
            if reporter:
                reporter("grade",record,state)
                if report:reporter("pass",report,state)
            else:
                delta=(sum(x["correct"] for x in record["development_after"].values())-
                       sum(x["correct"] for x in record["development_before"].values())
                       if record["grade"].startswith("B") else
                       record["development_after"]-record["development_before"])
                print(f"[acquisition] visit={record['visit']} pass={record['pass']} "
                      f"grade={record['grade']} step={record['optimizer_step']} "
                      f"updates=+{record['updates']} delta={delta:+} "
                      f"teacher={record['teacher_events']}",flush=True)
                if report:
                    print(f"[acquisition] PASS {report['pass']} old="
                          f"{100*report['old_mean']:.2f}% bridge="
                          f"{report['bridge_correct']}/{course.TOTAL_BRIDGE_ROWS} "
                          f"contrasts={report['bridge_contrasts']} "
                          f"{report['disposition']} "
                          f"v8_rollback={report['would_rollback_under_v8']} "
                          f"triggers={report['rollback_triggers']}",flush=True)
    finally:
        os.close(fd)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir",type=Path,default=RUN)
    parser.add_argument("--source-dir",type=Path,default=SOURCE)
    parser.add_argument("--device",choices=("cpu","mps"),default="mps")
    parser.add_argument("--minutes",type=float,default=DEFAULT_MINUTES)
    parser.add_argument("--block",type=int,default=64)
    parser.add_argument("--seed",type=int,default=20261013)
    parser.add_argument('--champion-boundary',choices=local_champions.BOUNDARIES,
                        default='session',
                        help='Explicitly choose whether run-local champions end at operator stop or complete grade coverage')
    parser.add_argument('--acknowledge-holistic-tie-policy',action='store_true',
                        help='Explicitly opt in to provisional equal-domain G/B/N champion tie ranking')
    parser.add_argument("--initialize-only",action="store_true")
    parser.add_argument("--prepare-run-local",action="store_true")
    parser.add_argument('--verify-preparation',action='store_true',
                        help='Stage and validate a disposable nontraining successor; do not create v15 run')
    parser.add_argument("--status",action="store_true")
    parser.add_argument("--dashboard",action="store_true")
    parser.add_argument("--log-file",type=Path)
    args=parser.parse_args()
    if (not (args.status or args.verify_preparation) and
            not args.acknowledge_holistic_tie_policy):
        parser.error('V15_REQUIRES_EXPLICIT_OPERATOR_TIE_RANK_POLICY_ACKNOWLEDGEMENT')
    if args.prepare_run_local or args.verify_preparation:
        if (args.initialize_only or args.dashboard or args.status or
                (args.prepare_run_local and args.verify_preparation)):
            parser.error('preparation cannot combine with other run flags')
        report=prepare_run_local(champion_boundary=args.champion_boundary,
                                 dry_run=args.verify_preparation)
        print(json.dumps({k:report.get(k) for k in (
            'status','phase','next_grade','optimizer_step','visits',
            'passes_completed','teacher_events','champion_boundary',
            'preparation_probe','new_v15_run_created')},indent=2,sort_keys=True))
        return
    if args.status:
        print(json.dumps(status(args.run_dir),indent=2,sort_keys=True))
        return
    interrupted={"stop":False}
    old_signal=signal.getsignal(signal.SIGINT)
    def stop(*_):
        if interrupted["stop"]:
            raise KeyboardInterrupt("SECOND_CTRL_C")
        interrupted["stop"]=True
        print("[acquisition] graceful stop requested at grade boundary",flush=True)
    signal.signal(signal.SIGINT,stop)
    try:
        options=dict(run_dir=args.run_dir,source_dir=args.source_dir,
                     device=args.device,minutes=args.minutes,
                     block=args.block,
                     seed=args.seed,champion_boundary=args.champion_boundary,
                     initialize_only=args.initialize_only,
                     stop_requested=lambda:interrupted["stop"])
        if not args.dashboard or args.initialize_only:
            print(json.dumps(run(**options),indent=2,sort_keys=True))
            return
        if not sys.stdout.isatty():
            raise ValueError("ACQUISITION_DASHBOARD_REQUIRES_TTY")
        from .spiral_dashboard import Dashboard
        screen=Dashboard(stream=sys.stdout,title="BILQIS / SCHOOL50 V15 RUN-LOCAL")
        screen.log_hint=str(args.log_file.name) if args.log_file else "-"
        log_path=args.log_file or args.run_dir.with_suffix(".log")
        log_path.parent.mkdir(parents=True,exist_ok=True)
        with log_path.open("a",encoding="utf-8",buffering=1) as log:
            screen.push("system",{"kind":"V15 RUN-LOCAL CHAMPIONS",
                "detail":"Candidate PB48 G / PB12 B independent of admission; ties scored after operator session"})
            def report(kind,record,state):
                log.write(json.dumps({"kind":kind,"record":record},sort_keys=True)+"\n")
                screen.state={
                    "phase":state["phase"],"next":PROGRAM[state["grade_index"]],
                    "prefix":state["passes_completed"]+1,"failures":"-",
                    "max_failures":"-","step":state["optimizer_step"],
                    "visits":state["visits"],"teacher":state["teacher"]["events"],
                    "stop":state["last_run_status"]}
                if kind=="grade":
                    g=record["grade"]
                    attempts=state["candidate_ledger"][-record["attempts"]:]
                    if len(attempts)!=record["attempts"] or any(
                            trial["grade"]!=g for trial in attempts):
                        raise ValueError("BRIDGE_PRIORITY_LOG_ATTEMPT_MISMATCH")
                    for trial in attempts:
                        p=trial.get("bridge_before",{})
                        a=trial.get("bridge_after",{})
                        log.write(json.dumps({"kind":"candidate_attempt",
                                              "record":trial},sort_keys=True)+"\n")
                        screen.push("candidate",{
                            "grade":g,"attempt":trial["attempt"],
                            "policy_id":trial["policy_id"],
                            "instruction_method":trial.get("instruction_method"),
                            "bridge_before":p.get("primary"),
                            "bridge_after":a.get("primary"),
                            "bridge_confirm_before":p.get("confirm"),
                            "bridge_confirm_after":a.get("confirm"),
                            "old_before":trial.get("old_before",record["old_before"]),
                            "old_after":trial.get("old_after",record["old_after"]),
                            "teacher_credit":trial["teacher_credit"],
                            "reward":trial["raw_reward"],
                            "loss_last":trial["last_loss"],
                            "allocation":trial["row_exposures"],
                            "decision":("SELECT" if trial["selected"] else
                                        trial["decision"]),
                            "reason":trial["reason"]})
                    screen.push("grade",{
                        "grade_visit":record["visit"],"grade":g,
                        "step":record["optimizer_step"],
                        "eligible":sum(t["decision"] in ("PROMOTE","ELIGIBLE")
                                       for t in attempts),
                        "selected":record["updates"]>0,
                        "prefix":state["passes_completed"]+1,
                        "outcome":record["disposition"],
                        "next":PROGRAM[state["grade_index"]]})
                    if g.startswith('B'):
                        before_math=record['basic_numeric_before']
                        after_math=record['basic_numeric_after']
                        def tally(result,arm):
                            return sum(result[fold][arm]['correct']
                                       for fold in ('primary','confirm'))
                        screen.push("system",{"kind":"B BASIC REPLAY","grade":g,
                            "detail":f"4-way {tally(before_math,'four_way')}/4 > "
                                     f"{tally(after_math,'four_way')}/4; 101-way "
                                     f"{tally(before_math,'full_101')}/4 > "
                                     f"{tally(after_math,'full_101')}/4; EXPOSED"})
                else:
                    screen.push("system",{"kind":"FULL PASS",
                        "detail":f"{record['pass']}: old {100*record['old_mean']:.2f}% "
                                 f"bridge {record['bridge_correct']}/{course.TOTAL_BRIDGE_ROWS} "
                                 f"{record['disposition']}"})
                    screen.push('system',{'kind':'B REPLAY SCORE',
                        'detail':f"arithmetic {record['basic_numeric_four_way_correct']}/4 four-way, "
                                 f"{record['basic_numeric_full_101_correct']}/4 full-101; "
                                 f"bridge {record['bridge_correct']}/{course.TOTAL_BRIDGE_ROWS} exposed"})
                    for group in (('G03','G11','G12'),('G19','G20','G22')):
                        screen.push('system',{'kind':'G PREREQUISITES',
                            'detail':' '.join(f"{grade} {100*record['prerequisite_grades'][grade]:.0f}%"
                                              for grade in group)})
                    joint=record['joint_tracking']
                    best=joint['best_joint']
                    screen.push('system',{'kind':'B/G JOINT FRONTIER',
                        'detail':f"acquisition peak {best['bridge_correct']}/84, "
                                 f"{best['bridge_contrasts']} contrasts, "
                                 f"old {best['old_mean']*100:.2f}% at pass "
                                 f"{best['pass']}; nondominated "
                                 f"{len(joint['nondominated'])}"})
                    debt=", ".join(
                        f"{item['grade']} -{item['lost_questions']}/24"
                        if item['kind']=="HISTORICAL_GRADE_REGRESSION" else
                        f"MEAN < {100*item['minimum']:.2f}%"
                        for item in record['rollback_triggers']) or "none"
                    screen.push("system",{"kind":"V8 RETENTION",
                        "grade":", ".join(item['grade'] for item in record['rollback_triggers']
                                          if 'grade' in item) or "-",
                        "detail":f"would-rollback: {debt}; student+AdamW carried"})
            try:
                result=run(**options,reporter=report)
                log.write(json.dumps({"kind":"summary","record":result},
                                     sort_keys=True)+"\n")
                screen.mode="FINISHED"
            except BaseException as exc:
                log.write(json.dumps({"kind":"trainer_error","record":{
                    "exception":type(exc).__name__,"message":str(exc),
                    "traceback":traceback.format_exc()}},sort_keys=True)+"\n")
                screen.mode="ERROR"
                screen.push("system",{"kind":"TRAINER ERROR","detail":str(exc)},
                            redraw=False)
                raise
            finally:
                screen.draw()
    finally:
        signal.signal(signal.SIGINT,old_signal)


if __name__=="__main__":
    main()
