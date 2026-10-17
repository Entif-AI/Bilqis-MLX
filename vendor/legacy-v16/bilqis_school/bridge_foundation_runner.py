"""Isolated FP32 School50 bridge-only teaching experiment.

Uses *only* evidence-state supervision until human review. A protected
continuing student+AdamW, independently evolving School50 teacher,
same-parent competing candidates, frozen School50 grade soup and explicit
historical repair/retention survive. This does not graduate M01 or M02.
"""
from __future__ import annotations

import argparse
import copy
import fcntl
import json
import math
import os
from pathlib import Path
import random
import shutil
import signal
import sys
import tempfile
import time

import torch
from torch.nn import functional as F

from bilqis_logic.kernel import digest
from bilqis_micro.graph import STATES
from bilqis_micro.run import optimizer_receipt
from bilqis_ref.model import state_hash
from . import engine, lessons, arithmetic, numeric_answer_contract as contract
from . import numeric_answer_pilot as pilot
from . import bridge_foundation_lessons as course
from . import spiral_primitive_lessons as primitive
from . import spiral_semantic_bridge as bridge
from . import spiral_staged_runner as original

VERSION="bilqis.school50.bridge-foundation/v1"
RUN=Path(__file__).resolve().parents[1]/"runs/school50-bridge-foundation-v4"
V3=Path(__file__).resolve().parents[2]/(
    "bilqis-school50-primitive-bridge-v3/runs/school50-mastery-v5-v3/state.json")
GRADE_KEY=2001
RESTORE_GRADES=(9,10,9,10,11,12,19,20)


def recipe():
    files={"bridge_runner":__file__,"bridge_lessons":course.__file__,
           "original_school50":engine.__file__,"semantic_bridge":bridge.__file__,
           "original_lessons":lessons.__file__,"numerical_abi":contract.__file__,
           "original_v3":original.__file__,"primitive_sources":primitive.__file__}
    return {key:engine._sha(value) for key,value in files.items()}


def configuration(*,block=8,recovery=2,attempts=3,seed=20261013,
                  device="mps",max_stalled_visits=12):
    if not(1<=block<=64 and 1<=recovery<=8 and 1<=attempts<=8 and
           1<=max_stalled_visits<=100 and device in ("cpu","mps")):
        raise ValueError("BRIDGE_INVALID_FROZEN_RECIPE")
    return {"version":VERSION,"block":block,"recovery":recovery,
            "attempts":attempts,"seed":seed,"device":device,
            "max_stalled_visits":max_stalled_visits,"recipe":recipe(),
            "source_sha256":pilot.CHAMPION_SHA256}


def _stopped_v3():
    """Never import from a process holding the protected v3 writer lock."""
    if not V3.is_file():
        raise FileNotFoundError("BRIDGE_V3_DURABLE_SOURCE_MISSING")
    lock=V3.parent.with_name(V3.parent.name+".writer.lock")
    fd=os.open(lock,os.O_CREAT|os.O_RDWR|getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        try:fcntl.flock(fd,fcntl.LOCK_SH|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("BRIDGE_V3_STILL_HAS_ACTIVE_WRITER") from exc
        prior=engine._read(V3)
        if (prior.get("version")!="bilqis.school50.mastery-v5/v3" or
                prior.get("last_run_status") not in
                ("GRACEFUL_OPERATOR_STOP","TIME_BUDGET_EXHAUSTED",
                 "EXPLICIT_GRADE_VISIT_CAP","MASTERY_PHASE_BOUNDARY_STOPPED") or
                prior.get("checkpoint") is None):
            raise ValueError("BRIDGE_V3_SOURCE_NOT_STOPPED_OR_NO_STUDENT")
        return prior
    finally:
        os.close(fd)


def _initialize(out,source,graph,config):
    previous=_stopped_v3()
    if (previous["source_checkpoint_sha256"]!=pilot.CHAMPION_SHA256 or
            previous["source_state_sha256"]!=source["state_sha256"] or
            previous["graph_sha256"]!=digest(graph)):
        raise ValueError("BRIDGE_ORIGINAL_FP32_SOURCE_DRIFT")
    origin=V3.parent/previous["checkpoint"]
    if (Path(previous["checkpoint"]).name!=previous["checkpoint"] or
            engine._sha(origin)!=previous["checkpoint_sha256"]):
        raise ValueError("BRIDGE_V3_STUDENT_CHECKPOINT_DRIFT")
    model,optimizer,payload=engine.load_checkpoint(origin)
    if (digest(payload["graph"])!=digest(graph) or
            state_hash(model)!=payload["state_sha256"] or
            optimizer_receipt(optimizer)["steps"]!=[previous["optimizer_step"]]):
        raise ValueError("BRIDGE_V3_STUDENT_OPTIMIZER_DRIFT")
    state=copy.deepcopy(previous)
    state.update({"version":VERSION,"config":config,"grade_visits":0,
        "attempted_updates":0,"accepted_updates":0,
        "candidate_ledger":[],"grade_ledger":[],"mastery_events":[],
        "pass_reports":[],"last_run_status":"READY","last_session":None,
        "soup_snapshot":None,"soup_history":[],"soup_epoch":0,
        "teacher_import":{"source":"V3_STOPPED_TEACHER_CONTINUATION",
            "events":previous["teacher"]["events"],
            "state_sha256":engine._sha(V3)},
        "bootstrap":{"source":"V3_STOPPED_STUDENT_AND_ADAMW",
            "optimizer_step":previous["optimizer_step"],
            "checkpoint_sha256":previous["checkpoint_sha256"],
            "parent_state_sha256":engine._sha(V3),
            "protected_p43_sha256":pilot.CHAMPION_SHA256},
        "bridge_stage":{"phase":"BRIDGE_ONLY","failed_visits":0,
            "accepted_correct_visits":0,"ce_only_streak":0,
            "qualification":None,"events":[]},
        "baseline_bridge":None,"last_candidate":None})
    out.mkdir(parents=True,exist_ok=False)
    filename="bridge-parent-"+previous["checkpoint"]
    shutil.copyfile(origin,out/filename)
    if engine._sha(out/filename)!=previous["checkpoint_sha256"]:
        raise ValueError("BRIDGE_BOOTSTRAP_COPY_MISMATCH")
    state["checkpoint"]=filename
    engine._atomic_json(out/"state.json",state)
    return state


def _load(out,source,state,config,device):
    if (state["version"]!=VERSION or state["config"]!=config or
            state["source_checkpoint_sha256"]!=pilot.CHAMPION_SHA256 or
            state["source_state_sha256"]!=source["state_sha256"]):
        raise ValueError("BRIDGE_RESUME_RECIPE_OR_SOURCE_CHANGED")
    model,optimizer,graph,numbers=original._load_student(out,source,state,device)
    return model,optimizer,graph,numbers


@torch.no_grad()
def evaluate_panel(model,rows,graph,device):
    """Include balanced-label and *paired contrast* success, not just score."""
    course.validate_rows(rows,graph,split=rows[0]["course_meta"]["split"])
    model.eval()
    inputs,lengths=original._input(rows,graph,device)
    logits=contract.readout(model,inputs,lengths,answer_kind="evidence",
                            number_ids=contract.numeric_token_ids(graph))
    labels=original._gold(rows,"evidence",device)
    pred=logits.argmax(-1)
    outcomes=(pred==labels).cpu().tolist()
    predictions=pred.cpu().tolist()
    by_family={}
    by_source={}
    for row,correct in zip(rows,outcomes):
        family=row["course_meta"].get("bridge_family","old")
        family_entry=by_family.setdefault(family,{"correct":0,"questions":0})
        family_entry["questions"]+=1
        family_entry["correct"]+=int(correct)
        group=by_source.setdefault(row["course_meta"].get("triplet_id",row["id"]),[])
        group.append((row["gold"],bool(correct)))
    contrasts=sum(1 for group in by_source.values() if
                  {label for label,_ in group}=={"TRUE","FALSE"} and
                  all(correct for _,correct in group))
    return {"correct":sum(outcomes),"questions":len(rows),
            "accuracy":sum(outcomes)/len(rows),
            "ce":float(F.cross_entropy(logits,labels).item()),
            "paired_contrasts":contrasts,
            "predicted_true":predictions.count(STATES.index("TRUE")),
            "predicted_false":predictions.count(STATES.index("FALSE")),
            "by_family":by_family}


def _historically_safe(parent,after,champion,secondary_before,secondary_after):
    if (len(parent)!=22 or len(after)!=22 or len(champion)!=22 or
            set(parent)!=set(after) or set(parent)!=set(champion)):
        raise ValueError("BRIDGE_INCOMPLETE_HISTORICAL_PANEL")
    deltas={g:round((after[g]-parent[g])*24) for g in parent}
    if min(deltas.values())<=-3:
        return False,"BRIDGE_PARENT_GRADE_CRASH"
    if sum(after.values())<sum(parent.values())-.01*22-1e-9:
        return False,"BRIDGE_HISTORICAL_MEAN_DEBT"
    if sum(after.values())<sum(champion.values())-.01*22-1e-9:
        return False,"BRIDGE_P43_MEAN_FLOOR"
    if any(after[g]<champion[g]-3/24-1e-9 for g in parent):
        return False,"BRIDGE_P43_GRADE_FLOOR"
    if not original._secondary_safety(secondary_before,secondary_after,
                                      numeric_phase=False):
        return False,"BRIDGE_INDEPENDENT_RETENTION_VETO"
    return True,"BRIDGE_HISTORICAL_SAFE"


def candidate_decision(before,after,confirmation_before,confirmation_after,
                       *,historic_safe,old_reason,numeric_before,numeric_after,
                       ce_only_streak):
    if not historic_safe:
        return "REJECT",old_reason
    if (numeric_after["correct"]<numeric_before["correct"]-1 or
            numeric_after["ce"]>numeric_before["ce"]+.15):
        return "REJECT","BRIDGE_NUMERIC_OBSERVATION_DAMAGED"
    for profile in (after,confirmation_after):
        if (profile["predicted_true"]<3 or profile["predicted_false"]<3 or
                profile["predicted_true"]+profile["predicted_false"]<
                profile["questions"]-2):
            return "REJECT","BRIDGE_ANSWER_CLASS_COLLAPSE"
    a=after["correct"]-before["correct"]
    b=confirmation_after["correct"]-confirmation_before["correct"]
    delta_pairs=(after["paired_contrasts"]-before["paired_contrasts"]+
                 confirmation_after["paired_contrasts"]-
                 confirmation_before["paired_contrasts"])
    ce_a=before["ce"]-after["ce"]
    ce_b=confirmation_before["ce"]-confirmation_after["ce"]
    if a>=0 and b>=0 and a+b>=2 and delta_pairs>=1 and ce_a>=-.04 and ce_b>=-.04:
        return "ELIGIBLE","BRIDGE_CONFIRMED_RELATIONAL_GAIN"
    if a>=0 and b>=0 and a+b>=1 and ce_a>=.005 and ce_b>=.005:
        return "ELIGIBLE","BRIDGE_CROSS_PANEL_CE_AND_ACCURACY_GAIN"
    if (ce_only_streak<2 and a>=-1 and b>=-1 and a+b>=0 and
            delta_pairs>=-1 and ce_a>=.07 and ce_b>=.07 and
            ce_a+ce_b>=.16):
        # Exactly the early-learning geometry observed in the clean v4 smoke:
        # primary 13->12, confirm 13->14, with strong CE gains in *both*
        # held-out panels and bounded old-grade loss. This is incubation,
        # NOT a new answer-level mastery result; two consecutive such
        # promotions are the limit without discrete correctness progress.
        return "ELIGIBLE","BRIDGE_CE_GEOMETRY_INCUBATION"
    if (ce_only_streak<2 and a>=0 and b>=0 and
            ce_a>=.012 and ce_b>=.012 and ce_a+ce_b>=.035):
        return "ELIGIBLE","BRIDGE_CE_ONLY_BOUNDED_INCUBATION"
    return "REJECT","BRIDGE_NO_REPLICATED_PROGRESS"


def qualified(primary,confirmation,baseline):
    if any(profile["accuracy"]<.67 or profile["paired_contrasts"]<2
           for profile in (primary,confirmation)):
        return False
    if primary["correct"]+confirmation["correct"]<(
            baseline["primary"]["correct"]+baseline["confirm"]["correct"]+3):
        return False
    for family in bridge.FAMILIES:
        if (primary["by_family"].get(family,{}).get("correct",0)<1 or
                confirmation["by_family"].get(family,{}).get("correct",0)<1):
            return False
    return True


def _restoration_rows(library,graph,rng,policy,grade):
    rows,counts=lessons.compose_batch(library,grade,policy,graph,rng,
                                       admissible=primitive.admissible_rehearsal)
    for row in rows:
        row["answer_kind"]="evidence"
        row["course_meta"]={"tranche":"historical_recovery","retention":True,
                            "source_grade":f"G{grade:02d}"}
    lessons.valid_rows(rows,graph)
    return rows,counts


def status(run_dir=RUN):
    path=Path(run_dir).expanduser()/"state.json"
    if not path.is_file():return {"status":"NOT_STARTED","run_dir":str(path.parent)}
    state=engine._read(path)
    phase=state["bridge_stage"]
    return {"status":state["last_run_status"],"phase":phase["phase"],
        "visits":state["grade_visits"],"failed_visits":phase["failed_visits"],
        "ce_only_streak":phase["ce_only_streak"],
        "accepted_correct_visits":phase["accepted_correct_visits"],
        "optimizer_step":state["optimizer_step"],
        "accepted_updates":state["accepted_updates"],
        "attempted_updates":state["attempted_updates"],
        "teacher_events":state["teacher"]["events"],
        "bootstrap":state["bootstrap"],
        "last_candidate":state.get("last_candidate"),
        "qualification":phase["qualification"],
        "last_session":state.get("last_session")}


def _second_scores(model,graph,library,device):
    return {f"G{grade:02d}":engine._scores(model,library,graph,grade,
             770013+grade*7919,count=24,device=device)
            for grade in engine.REPORT_GRADES}


def _session(out,source,state,config,*,minutes,max_visits,
             max_attempted_updates,device,stop_requested,reporter=None):
    library=lessons.TeacherLibrary()
    parent,_,graph,numbers=_load(out,source,state,config,device)
    ancestor,_,_,_=pilot._load(source,device)
    if state["source_scores"]!=engine._probe_all_grades(
            ancestor,graph,library,device=device):
        raise ValueError("BRIDGE_P43_EXAM_PROFILE_DRIFT")
    soup,_=original._consolidation_teacher(source,out,state,device)
    primary_rows=course.panel(graph,split="development",fold="primary",
                              seed=config["seed"])
    confirmation_rows=course.panel(graph,split="development",fold="confirm",
                                   seed=config["seed"])
    numeric_rows=[row for row in primitive.panel("identity",graph,
                  split="development",seed=config["seed"]) if
                  row["answer_kind"]=="numeric"]
    if state["baseline_bridge"] is None:
        state["baseline_bridge"]={
            "primary":evaluate_panel(parent,primary_rows,graph,device),
            "confirm":evaluate_panel(parent,confirmation_rows,graph,device)}
    engine._atomic_json(out/"state.json",state)
    begun=time.monotonic();visits=0;attempted=0;accepted=0

    def finish(reason):
        elapsed=time.monotonic()-begun
        state["last_run_status"]=reason
        state["last_session"]={"stop_reason":reason,
            "elapsed_seconds":round(elapsed,2),"visits":visits,
            "attempted_updates":attempted,"accepted_updates":accepted}
        if (pilot._sha(source["checkpoint"])!=pilot.CHAMPION_SHA256 or
                pilot._sha(source["state_path"])!=source["state_sha256"]):
            raise ValueError("BRIDGE_PROTECTED_P43_MUTATED")
        engine._atomic_json(out/"state.json",state)
        return status(out)

    while True:
        if stop_requested():return finish("GRACEFUL_OPERATOR_STOP")
        if state["bridge_stage"]["phase"]!="BRIDGE_ONLY":
            return finish("BRIDGE_OPERATOR_PHASE_BOUNDARY")
        if time.monotonic()-begun>=minutes*60:
            return finish("TIME_BUDGET_EXHAUSTED")
        if visits>=max_visits:
            return finish("EXPLICIT_GRADE_VISIT_CAP")
        if (attempted+config["attempts"]*(config["block"]+config["recovery"])>
                max_attempted_updates):
            return finish("ATTEMPTED_UPDATE_BUDGET_EXHAUSTED")
        parent,_,graph,numbers=_load(out,source,state,config,device)
        historic_before=engine._probe_all_grades(parent,graph,library,device=device)
        secondary_before=_second_scores(parent,graph,library,device)
        before=evaluate_panel(parent,primary_rows,graph,device)
        confirm_before=evaluate_panel(parent,confirmation_rows,graph,device)
        number_before=original.evaluate_numeric(parent,numeric_rows,graph,numbers,device)
        champion=state["source_scores"]
        history=[];winner=None;best_rank=None
        used_strategies=set();used_methods=set()
        base_seed=config["seed"]+state["grade_visits"]*71993+GRADE_KEY*9973
        with tempfile.TemporaryDirectory(prefix="bilqis-bridge-foundation-") as temp:
            candidate_file=Path(temp)/"selected.pt"
            for attempt in range(1,config["attempts"]+1):
                rng=random.Random(base_seed+attempt*104729)
                key,policy=engine.pick(state["teacher"],GRADE_KEY,rng,
                                       exclude=used_strategies)
                used_strategies.add(key)
                method=original._choose_instruction(state["teacher"],"B01",rng,
                                                     used_methods)
                used_methods.add(method)
                student,optimizer,other_graph,other_numbers=_load(
                    out,source,state,config,device)
                if state_hash(student)!=state_hash(parent):
                    raise ValueError("BRIDGE_CANDIDATE_NOT_FROM_IDENTICAL_PARENT")
                teaching=copy.deepcopy(policy)
                teaching["lr"]=min(policy["lr"],.00016)*.5
                for group in optimizer.param_groups:group["lr"]=teaching["lr"]
                anchor=copy.deepcopy(parent).eval()
                for weight in anchor.parameters():weight.requires_grad_(False)
                trace=[]
                for _ in range(config["block"]):
                    rows,_=course.compile_batch(library,graph,rng,method=method)
                    if any(row["answer_kind"]!="evidence" for row in rows):
                        raise ValueError("BRIDGE_NUMERIC_SUPERVISION_ATTEMPT")
                    trace.append(original.train_step(student,optimizer,anchor,soup,
                                   rows,other_graph,other_numbers,teaching,device))
                for recovery in range(config["recovery"]):
                    grade=RESTORE_GRADES[(state["grade_visits"]+recovery)%len(RESTORE_GRADES)]
                    rows,_=_restoration_rows(library,graph,rng,policy,grade)
                    trace.append(original.train_step(student,optimizer,anchor,soup,
                                   rows,other_graph,other_numbers,teaching,device))
                updated=optimizer_receipt(optimizer)["steps"]
                expected=state["optimizer_step"]+config["block"]+config["recovery"]
                if updated!=[expected]:
                    raise ValueError("BRIDGE_CANDIDATE_ADAMW_STEP_DRIFT")
                historic_after=engine._probe_all_grades(student,graph,library,device=device)
                secondary_after=_second_scores(student,graph,library,device)
                after=evaluate_panel(student,primary_rows,graph,device)
                confirm_after=evaluate_panel(student,confirmation_rows,graph,device)
                number_after=original.evaluate_numeric(student,numeric_rows,
                                                      graph,numbers,device)
                safe,why=_historically_safe(historic_before,historic_after,champion,
                                             secondary_before,secondary_after)
                decision,reason=candidate_decision(before,after,confirm_before,
                    confirm_after,historic_safe=safe,old_reason=why,
                    numeric_before=number_before,numeric_after=number_after,
                    ce_only_streak=state["bridge_stage"]["ce_only_streak"])
                delta=(after["correct"]-before["correct"]+
                    confirm_after["correct"]-confirm_before["correct"])
                delta_ce=(before["ce"]-after["ce"]+
                    confirm_before["ce"]-confirm_after["ce"])
                delta_old=(sum(historic_after.values())-sum(historic_before.values()))/22
                reward=.7*delta/48+.12*delta_ce+.5*delta_old
                credit=(reward if decision=="ELIGIBLE" else
                        min(reward,-.025) if not safe else reward)
                engine.observe(state["teacher"],GRADE_KEY,key,credit)
                original._observe_instruction(state["teacher"],"B01",method,credit)
                record={"grade":"B01","attempt":attempt,"policy_id":key,
                    "instruction_method":method,"policy":teaching,
                    "parent_step":state["optimizer_step"],"candidate_step":updated[0],
                    "candidate_model_sha256":state_hash(student),
                    "numeric_before":number_before,"numeric_after":number_after,
                    "bridge_before":before,"bridge_after":after,
                    "bridge_confirm_before":confirm_before,
                    "bridge_confirm_after":confirm_after,
                    "old_before":historic_before,"old_after":historic_after,
                    "secondary_old_before":secondary_before,
                    "secondary_old_after":secondary_after,
                    "decision":decision,"reason":reason,
                    "reward":reward,"teacher_credit":credit,
                    "loss_last":trace[-1],"allocation":course.ALLOCATION,
                    "selection":"REJECTED","supervised_numeric_items":0,
                    "bridge_updates":config["block"],
                    "historical_recovery_updates":config["recovery"]}
                history.append(record)
                if reporter:reporter("candidate",record,state)
                if decision=="ELIGIBLE":
                    rank=(delta,after["paired_contrasts"]-before["paired_contrasts"]+
                           confirm_after["paired_contrasts"]-
                           confirm_before["paired_contrasts"],delta_ce,
                          delta_old,-attempt)
                    if winner is None or rank>best_rank:
                        engine.save_checkpoint(candidate_file,student,optimizer,graph,
                         {"epoch":VERSION,"grade":"B01","candidate_attempt":attempt,
                          "no_external_promotion":True})
                        winner=record;best_rank=rank
            if winner is not None:
                best,optimizer,payload=engine.load_checkpoint(candidate_file)
                engine._device(best,optimizer,device)
                if (state_hash(best)!=winner["candidate_model_sha256"] or
                        optimizer_receipt(optimizer)["steps"]!=[winner["candidate_step"]]):
                    raise ValueError("BRIDGE_SELECTED_STUDENT_ADAMW_READBACK_DRIFT")
                filename,sha=engine._checkpoint(out,best,optimizer,graph,
                    {"step":winner["candidate_step"],"grade":"B01","epoch":VERSION})
                if engine._sha(out/filename)!=sha:
                    raise ValueError("BRIDGE_DURABLE_STUDENT_CHECKSUM_DRIFT")
                state["checkpoint"]=filename
                state["checkpoint_sha256"]=sha
                state["optimizer_step"]=winner["candidate_step"]
                state["accepted_updates"]+=config["block"]+config["recovery"]
                accepted+=config["block"]+config["recovery"]
                winner["selection"]="SELECTED"
                for record in history:
                    if record is not winner and record["decision"]=="ELIGIBLE":
                        record["selection"]="ELIGIBLE_SUPERSEDED"
                if winner["reason"] in ("BRIDGE_CE_ONLY_BOUNDED_INCUBATION",
                                        "BRIDGE_CE_GEOMETRY_INCUBATION"):
                    state["bridge_stage"]["ce_only_streak"]+=1
                else:
                    state["bridge_stage"]["ce_only_streak"]=0
                if (winner["bridge_after"]["correct"]+
                    winner["bridge_confirm_after"]["correct"]>
                    before["correct"]+confirm_before["correct"]):
                    state["bridge_stage"]["accepted_correct_visits"]+=1
                    state["bridge_stage"]["failed_visits"]=0
                else:
                    state["bridge_stage"]["failed_visits"]+=1
                if qualified(winner["bridge_after"],winner["bridge_confirm_after"],
                             state["baseline_bridge"]):
                    state["bridge_stage"]["phase"]="OPERATOR_REVIEW"
                    state["bridge_stage"]["qualification"]={
                        "primary":winner["bridge_after"],
                        "confirm":winner["bridge_confirm_after"],
                        "checkpoint_sha256":sha,"optimizer_step":state["optimizer_step"]}
            else:
                state["bridge_stage"]["failed_visits"]+=1
        state["candidate_ledger"].extend(history)
        state["grade_visits"]+=1
        state["attempted_updates"]+=config["attempts"]*(config["block"]+config["recovery"])
        visits+=1
        attempted+=config["attempts"]*(config["block"]+config["recovery"])
        status_reason=("BRIDGE_QUALIFIED_OPERATOR_REVIEW" if
            state["bridge_stage"]["phase"]=="OPERATOR_REVIEW" else
            "BRIDGE_RETAINED" if winner is not None else "BRIDGE_UNCHANGED")
        if (state["bridge_stage"]["failed_visits"]>=config["max_stalled_visits"] and
                state["bridge_stage"]["phase"]=="BRIDGE_ONLY"):
            state["bridge_stage"]["phase"]="STALLED_OPERATOR_REVIEW"
            status_reason="BRIDGE_BOUNDED_STAGNATION"
        grade_record={"grade":"B01","grade_visit":state["grade_visits"],
            "candidate_attempts":len(history),"eligible":sum(
                x["decision"]=="ELIGIBLE" for x in history),
            "selected":winner is not None,"optimizer_step":state["optimizer_step"],
            "outcome":status_reason,"next":"B01"}
        state["grade_ledger"].append(grade_record)
        state["last_candidate"]={"decision":winner["reason"] if winner else
            "NO_CANDIDATE_SELECTED","primary":winner["bridge_after"] if winner else before,
            "confirm":winner["bridge_confirm_after"] if winner else confirm_before}
        state["bridge_stage"]["events"].append({
            "visit":state["grade_visits"],"outcome":status_reason,
            "failed_visits":state["bridge_stage"]["failed_visits"],
            "selected":winner is not None,"optimizer_step":state["optimizer_step"]})
        state["last_run_status"]="DURABLE_BRIDGE_BOUNDARY"
        engine._atomic_json(out/"state.json",state)
        if reporter:reporter("grade",grade_record,state)
        else:print(f"[bridge-foundation] visit={state['grade_visits']} "
                   f"eligible={grade_record['eligible']} accepted={winner is not None} "
                   f"step={state['optimizer_step']} outcome={status_reason}",flush=True)


def run(*,source_dir=pilot.SOURCE,run_dir=RUN,minutes=30,max_visits=12,
        max_attempted_updates=10000,block=8,recovery=2,attempts=3,
        seed=20261013,device="mps",max_stalled_visits=12,
        stop_requested=lambda:False,reporter=None):
    if (not 0<minutes<=1440 or not 1<=max_visits<=1000 or
            max_attempted_updates<1):
        raise ValueError("BRIDGE_INVALID_SESSION_BUDGET")
    config=configuration(block=block,recovery=recovery,attempts=attempts,
                         seed=seed,device=device,max_stalled_visits=max_stalled_visits)
    source=pilot._ancestor(source_dir)
    out=Path(run_dir).expanduser().resolve(strict=False)
    if (out==source["source_dir"] or out in source["source_dir"].parents or
            source["source_dir"] in out.parents):
        raise ValueError("BRIDGE_PROTECTED_SOURCE_OVERLAP")
    out.parent.mkdir(parents=True,exist_ok=True)
    lock=out.with_name(out.name+".writer.lock")
    fd=os.open(lock,os.O_CREAT|os.O_RDWR|getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("BRIDGE_RESEARCH_RUN_ALREADY_HAS_WRITER") from exc
        if not out.exists():
            _,_,graph,_=pilot._load(source,device)
            _initialize(out,source,graph,config)
        state=engine._read(out/"state.json")
        _load(out,source,state,config,device)
        return _session(out,source,state,config,minutes=minutes,max_visits=max_visits,
                        max_attempted_updates=max_attempted_updates,
                        device=device,stop_requested=stop_requested,reporter=reporter)
    finally:os.close(fd)


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--run-dir",type=Path,default=RUN)
    cli.add_argument("--source-dir",type=Path,default=pilot.SOURCE)
    cli.add_argument("--device",choices=("cpu","mps"),default="mps")
    cli.add_argument("--minutes",type=float,default=30)
    cli.add_argument("--max-visits",type=int,default=12)
    cli.add_argument("--max-attempted-updates",type=int,default=10000)
    cli.add_argument("--block",type=int,default=8)
    cli.add_argument("--recovery",type=int,default=2)
    cli.add_argument("--attempts",type=int,default=3)
    cli.add_argument("--seed",type=int,default=20261013)
    cli.add_argument("--max-stalled-visits",type=int,default=12)
    cli.add_argument("--dashboard",action="store_true")
    cli.add_argument("--log-file",type=Path)
    cli.add_argument("--summary",action="store_true")
    args=cli.parse_args()
    if args.summary:
        print(json.dumps(status(args.run_dir),indent=2,sort_keys=True))
        return
    interrupted={"stop":False}
    old_sigint=signal.getsignal(signal.SIGINT)
    def interrupt(*_):
        if interrupted["stop"]:raise KeyboardInterrupt("SECOND_CTRL_C")
        interrupted["stop"]=True
        print("[bridge-foundation] graceful stop requested after current visit",flush=True)
    signal.signal(signal.SIGINT,interrupt)
    try:
        options=dict(source_dir=args.source_dir,run_dir=args.run_dir,
             minutes=args.minutes,max_visits=args.max_visits,
             max_attempted_updates=args.max_attempted_updates,
             block=args.block,recovery=args.recovery,attempts=args.attempts,
             seed=args.seed,device=args.device,
             max_stalled_visits=args.max_stalled_visits,
             stop_requested=lambda:interrupted["stop"])
        if not args.dashboard:
            print(json.dumps(run(**options),indent=2,sort_keys=True))
            return
        if not sys.stdout.isatty():
            raise ValueError("BRIDGE_DASHBOARD_REQUIRES_TTY_USE_PLAIN")
        from .spiral_dashboard import Dashboard
        screen=Dashboard(stream=sys.stdout)
        screen.log_hint=Path(args.log_file).name if args.log_file else "-"
        screen.state={"phase":"BRIDGE_ONLY","next":"B01","prefix":1,
                      "failures":0,"max_failures":args.max_stalled_visits,
                      "step":67832,"visits":0,"teacher":"-","stop":"READY"}
        log_path=args.log_file or args.run_dir.with_suffix(".log")
        log_path.parent.mkdir(parents=True,exist_ok=True)
        def show_state(state):
            phase=state["bridge_stage"]
            screen.state={"phase":phase["phase"],"next":"B01","prefix":1,
                 "failures":phase["failed_visits"],"max_failures":args.max_stalled_visits,
                 "step":state["optimizer_step"],"visits":state["grade_visits"],
                 "teacher":state["teacher"]["events"],
                 "stop":state["last_run_status"]}
        with log_path.open("a",encoding="utf-8",buffering=1) as log:
            def report(kind,record,state):
                log.write(json.dumps({"kind":kind,"record":record},sort_keys=True)+"\n")
                if kind=="candidate":screen.push("candidate",record)
                else:
                    show_state(state)
                    screen.push("grade",{
                      "grade_visit":record["grade_visit"],"grade":record["grade"],
                      "step":record["optimizer_step"],"eligible":record["eligible"],
                      "selected":record["selected"],"prefix":1,
                      "outcome":record["outcome"],"next":"B01"})
            try:
                screen.push("system",{"kind":"BRIDGE ONLY","detail":
                     "Supervision=evidence only; numeric answers are monitored, not trained"})
                result=run(**options,reporter=report)
                log.write(json.dumps({"kind":"summary","record":result},sort_keys=True)+"\n")
                path=args.run_dir/"state.json"
                if path.is_file():show_state(engine._read(path))
                screen.mode="FINISHED"
            except BaseException as exc:
                screen.mode="ERROR"
                screen.push("system",{"kind":"TRAINER ERROR","detail":str(exc)},
                            redraw=False)
                raise
            finally:screen.draw()
    finally:signal.signal(signal.SIGINT,old_sigint)


if __name__=="__main__":main()
