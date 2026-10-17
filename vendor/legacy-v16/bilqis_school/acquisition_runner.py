"""School50-style cumulative acquisition of new bridge semantics.

Research only. One FP32 student and its inherited AdamW are taught a full
B01-B07, G01-G22 spiral. Grade visits are 64 optimizer updates by default,
not ten-update promotion auditions. Strict development-panel mastery is
measured, not used as a gate on every acquisition step. Historical P43 and
all predecessor research runs remain read-only.
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
import tempfile
import time
import uuid

import torch

from bilqis_logic.kernel import digest
from bilqis_micro.run import optimizer_receipt
from bilqis_ref.model import state_hash
from . import acquisition_lessons as course
from . import bridge_foundation_runner as precursor
from . import engine, lessons, numeric_answer_pilot as pilot
from . import spiral_staged_runner as staged


VERSION = "bilqis.school50.cumulative-acquisition/v1"
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "bilqis-school50-bridge-foundation-v4/runs/school50-bridge-foundation-v4"
RUN = ROOT / "runs/school50-cumulative-acquisition-v5"
P43 = ROOT.parent / ("bilqis-auto-curriculum50/runs/school50-continuous-v1/"
                      "student-67800-2cf61275e081.pt")
PROGRAM = course.GRADES + tuple(f"G{n:02d}" for n in engine.REPORT_GRADES)
OLD_MEAN_PAUSE = .05
OLD_GRADE_PAUSE = 3/24


def recipe():
    return {key:engine._sha(path) for key,path in {
        "runner":__file__,
        "acquisition_lessons":course.__file__,
        "school50_engine":engine.__file__,
        "school50_lessons":lessons.__file__,
        "staged_training":staged.__file__,
        "foundation_oracle":course.foundation.__file__,
        "bridge_oracle":course.bridge.__file__,
        "primitive_oracle":course.primitive.__file__,
    }.items()}


def configuration(*,block=64,seed=20261013):
    if not 1<=block<=256:
        raise ValueError("ACQUISITION_INVALID_GRADE_BLOCK")
    return {"version":VERSION,"block":block,"seed":seed,
            "recipe":recipe(),"source_champion_sha256":pilot.CHAMPION_SHA256,
            "grade_program":list(PROGRAM),
            "max_old_mean_debt":OLD_MEAN_PAUSE,
            "max_old_grade_debt":OLD_GRADE_PAUSE}


def _assert_source(source):
    """Read an already-stopped source, never its active writer's state."""
    if not source.is_dir():
        raise FileNotFoundError("ACQUISITION_V4_SOURCE_NOT_FOUND")
    source_lock=source.with_name(source.name+".writer.lock")
    fd=os.open(source_lock,os.O_CREAT|os.O_RDWR|getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        try:fcntl.flock(fd,fcntl.LOCK_SH|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("ACQUISITION_SOURCE_HAS_ACTIVE_WRITER") from exc
        old=engine._read(source/"state.json")
        stage=old.get("bridge_stage",{})
        if (old.get("version")!=precursor.VERSION or
                stage.get("phase")!="STALLED_OPERATOR_REVIEW" or
                old.get("last_run_status")!="BRIDGE_OPERATOR_PHASE_BOUNDARY" or
                old.get("bootstrap",{}).get("protected_p43_sha256")!=
                pilot.CHAMPION_SHA256):
            raise ValueError("ACQUISITION_V4_NOT_VERIFIED_STOPPED_LINEAGE")
        checkpoint=source/old["checkpoint"]
        if (Path(old["checkpoint"]).name!=old["checkpoint"] or
                engine._sha(checkpoint)!=old["checkpoint_sha256"]):
            raise ValueError("ACQUISITION_V4_STUDENT_HASH_MISMATCH")
        frozen=old.get("soup_snapshot")
        if (not frozen or Path(frozen["file"]).name!=frozen["file"] or
                engine._sha(source/frozen["file"])!=frozen["sha256"]):
            raise ValueError("ACQUISITION_FROZEN_SOUP_NOT_PROVEN")
        if (not P43.is_file() or engine._sha(P43)!=pilot.CHAMPION_SHA256):
            raise ValueError("ACQUISITION_P43_REFERENCE_MUTATED")
        old["_source_state_sha256_at_read"]=engine._sha(source/"state.json")
        return old
    finally:
        os.close(fd)


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


def _bridges(model,graph,panels,device):
    return {grade:{fold:precursor.evaluate_panel(model,rows,graph,device)
                   for fold,rows in variants.items()}
            for grade,variants in panels.items()}


def _old(model,graph,library,device):
    return engine._probe_all_grades(model,graph,library,device=device)


def _initialize(out,source,old,config,device):
    """Copy the exact v4 continuing student, optimizer and frozen soup once."""
    staging=Path(tempfile.mkdtemp(prefix=".acquisition-init-",dir=out.parent))
    try:
        for name in (old["checkpoint"],old["soup_snapshot"]["file"]):
            shutil.copy2(source/name,staging/name)
        if (engine._sha(staging/old["checkpoint"])!=old["checkpoint_sha256"] or
                engine._sha(staging/old["soup_snapshot"]["file"])!=
                old["soup_snapshot"]["sha256"] or
                engine._sha(source/"state.json")!=
                old["_source_state_sha256_at_read"]):
            raise ValueError("ACQUISITION_SOURCE_COPY_CORRUPTED_OR_RACED")
        model,optimizer,payload=engine.load_checkpoint(staging/old["checkpoint"])
        engine._device(model,optimizer,device)
        graph=payload["graph"]
        if (digest(graph)!=old["graph_sha256"] or
                optimizer_receipt(optimizer)["steps"]!=[old["optimizer_step"]]):
            raise ValueError("ACQUISITION_IMPORTED_ADAMW_INVALID")
        baselines=_bridges(model,graph,_panels(graph,config["seed"]),device)
        state={
        "version":VERSION,"config":config,"checkpoint":old["checkpoint"],
        "checkpoint_sha256":old["checkpoint_sha256"],
        "optimizer_step":old["optimizer_step"],"graph_sha256":old["graph_sha256"],
        "teacher":copy.deepcopy(old["teacher"]),
        "source": {"directory":str(source),"checkpoint":old["checkpoint"],
                   "checkpoint_sha256":old["checkpoint_sha256"],
                   "optimizer_step":old["optimizer_step"],
                   "teacher_events":old["teacher"]["events"],
                   "state_sha256":old["_source_state_sha256_at_read"],
                   "p43_sha256":pilot.CHAMPION_SHA256},
        "frozen_soup":copy.deepcopy(old["soup_snapshot"]),
        "soup_epoch":0,"soup_history":[copy.deepcopy(old["soup_snapshot"])],
        "grade_champions":copy.deepcopy(old["grade_champions"]),
        "bridge_champions":{},
        "source_old_scores":copy.deepcopy(old["source_scores"]),
        "baseline_bridge":baselines,
        "grade_index":0,"visits":0,"passes_completed":0,
        "attempted_updates":0,"retained_updates":0,
        "grade_ledger":[],"pass_ledger":[],
        "pass_start_old":None,"phase":"ACQUISITION",
        "last_run_status":"READY","last_session":None,
        "research_champion":None}
        engine._atomic_json(staging/"state.json",state)
        os.replace(staging,out)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    _load_student(out,state,device)
    return state


def _assert_frozen(state,config):
    if state.get("version")!=VERSION or state.get("config")!=config:
        raise ValueError("ACQUISITION_FROZEN_RECIPE_DRIFT_USE_NEW_RUN")
    if state.get("phase") not in ("ACQUISITION","RETENTION_OPERATOR_REVIEW"):
        raise ValueError("ACQUISITION_LINEAGE_CLOSED")


def _refresh_soup(out,state,student,device):
    """Start the NEXT full cycle with one new frozen grade-weighted teacher.

    Reuse the existing School50 source/research champion mixing algorithm.
    Its numeric_champions input is a generic extra-grade map in that helper;
    here it receives separately labeled, evidence-only B-grade champions.
    This does not introduce numeric-answer targets or optimizer averaging.
    """
    if state["passes_completed"]==state["soup_epoch"]:
        return _soup(out,state,student,device)
    if state["passes_completed"]!=state["soup_epoch"]+1 or state["grade_index"]!=0:
        raise ValueError("ACQUISITION_SOUP_EPOCH_NOT_AT_PASS_BOUNDARY")
    next_epoch=state["passes_completed"]
    temporary_state={
        "grade_champions":state["grade_champions"],
        "numeric_champions":state["bridge_champions"],
        "soup_epoch":next_epoch}
    source=pilot._ancestor(P43.parent)
    teacher,manifest=staged._build_grade_weighted_teacher(
        source,out,temporary_state,device)
    if manifest["epoch"]!=next_epoch or manifest["votes"]!=(
            len(state["grade_champions"])+len(state["bridge_champions"])):
        raise ValueError("ACQUISITION_GRADE_SOUP_VOTE_DRIFT")
    name=f"soup-stage-{next_epoch:04d}.pt"
    target=out/name
    if target.exists():
        # Crash-safe reconciliation: the prior invocation may have written
        # the complete new soup but died BEFORE the atomic state-pointer
        # update. Never overwrite it, and never assume it was this recipe.
        previous=torch.load(target,map_location="cpu",weights_only=True)
        if (previous["manifest"]!=manifest or
                previous["graph_sha256"]!=state["graph_sha256"] or
                set(previous["weights"])!=set(teacher.state_dict()) or
                any(not torch.equal(previous["weights"][k],
                                     teacher.state_dict()[k].detach().cpu())
                    for k in previous["weights"])):
            raise ValueError("ACQUISITION_EXISTING_SOUP_EPOCH_CONFLICT")
    else:
        tmp=out/f".{name}.{uuid.uuid4().hex}.tmp"
        try:
            torch.save({"weights":{k:v.detach().cpu()
                                   for k,v in teacher.state_dict().items()},
                        "manifest":manifest,"graph_sha256":state["graph_sha256"]},tmp)
            os.replace(tmp,target)
        finally:
            if tmp.exists():
                tmp.unlink()
    record={"epoch":next_epoch,"file":name,
            "sha256":engine._sha(target),"manifest":manifest}
    state["frozen_soup"]=record
    state["soup_epoch"]=next_epoch
    state["soup_history"].append(record)
    engine._atomic_json(out/"state.json",state)
    # Read back the same frozen teacher the next session will use.
    check=_soup(out,state,student,device)
    if state_hash(check)!=state_hash(teacher):
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


def _pass_report(state,model,graph,lib,panels,device):
    prior=state["pass_start_old"]
    if prior is None:
        raise ValueError("ACQUISITION_PASS_START_MISSING")
    after=_old(model,graph,lib,device)
    p43=state["source_old_scores"]
    if set(after)!=set(prior) or set(after)!=set(p43) or len(after)!=22:
        raise ValueError("ACQUISITION_HISTORIC_PANEL_INCOMPLETE")
    development=_bridges(model,graph,panels,device)
    baseline=state["baseline_bridge"]
    old_mean=sum(after.values())/22
    original_mean=sum(p43.values())/22
    worst=min((after[g]-p43[g] for g in p43))
    bridge_before=sum(x["correct"] for grade in baseline.values()
                      for x in grade.values())
    bridge_after=sum(x["correct"] for grade in development.values()
                     for x in grade.values())
    contrasts=sum(x["paired_contrasts"] for grade in development.values()
                  for x in grade.values())
    severe=(old_mean<original_mean-OLD_MEAN_PAUSE-1e-9 or
            worst<=-OLD_GRADE_PAUSE+1e-9)
    qualified=(not severe and old_mean>=original_mean-1e-9 and
               bridge_after>=bridge_before+3 and
               all(sum(f["paired_contrasts"] for f in folds.values())>=1
                   for folds in development.values()))
    report={
        "pass":state["passes_completed"],"checkpoint":state["checkpoint"],
        "checkpoint_sha256":state["checkpoint_sha256"],
        "optimizer_step":state["optimizer_step"],
        "old_scores":after,"old_mean":old_mean,
        "p43_mean":original_mean,"old_mean_vs_p43":old_mean-original_mean,
        "old_mean_vs_pass_start":old_mean-sum(prior.values())/22,
        "worst_old_grade_vs_p43":worst,
        "bridge":development,"bridge_correct":bridge_after,
        "bridge_initial_correct":bridge_before,"bridge_contrasts":contrasts,
        "research_qualified":qualified,
        "disposition":("RETENTION_OPERATOR_REVIEW" if severe else
                       "RESEARCH_QUALIFIED_NOT_PUBLISHED" if qualified else
                       "ACQUISITION_CONTINUES")}
    state["pass_ledger"].append(report)
    if qualified and (state["research_champion"] is None or
                      bridge_after>state["research_champion"]["bridge_correct"]):
        state["research_champion"]={
            "pass":state["passes_completed"],"optimizer_step":state["optimizer_step"],
            "checkpoint":state["checkpoint"],
            "checkpoint_sha256":state["checkpoint_sha256"],
            "bridge_correct":bridge_after,"old_mean":old_mean}
    if severe:
        # Preserve experimental student and optimizer for diagnosis, but
        # disallow any next visit until the operator reviews historic debt.
        state["phase"]="RETENTION_OPERATOR_REVIEW"
    state["pass_start_old"]=None
    return report


def _prune(out,state,*,keep_recent=8,keep_passes=4):
    """Prune only this run's redundant binaries AFTER the atomic state save."""
    records=state["grade_ledger"]
    keep={state["checkpoint"],state["source"]["checkpoint"]}
    keep.update(r["checkpoint"] for r in records[-keep_recent:])
    keep.update(r["checkpoint"] for r in state["pass_ledger"][-keep_passes:])
    champion=state.get("research_champion")
    if champion:
        keep.add(champion["checkpoint"])
    for kind in ("grade_champions","bridge_champions"):
        keep.update(item["checkpoint"] for item in state[kind].values()
                    if item.get("location")=="research")
    for path in out.glob("student-*.pt"):
        if path.name not in keep:
            path.unlink()


def _grade_visit(out,state,model,optimizer,graph,soup,lib,panels,device):
    grade=PROGRAM[state["grade_index"]]
    n=state["visits"]
    rng=random.Random(state["config"]["seed"]+n*71993+
                      state["passes_completed"]*1000003)
    key,policy=engine.pick(state["teacher"],
                           2000+course.GRADES.index(grade)+1
                           if grade in course.GRADES else int(grade[1:]),rng)
    for group in optimizer.param_groups:
        group["lr"]=policy["lr"]  # use School50's actual adaptive LR, not v4's half cap
    anchor=copy.deepcopy(model).eval()
    for parameter in anchor.parameters():
        parameter.requires_grad_(False)
    before_old={}
    after_old={}
    method=None
    if grade.startswith("B"):
        method=staged._choose_instruction(state["teacher"],grade,rng)
        prior={fold:precursor.evaluate_panel(model,rows,graph,device)
               for fold,rows in panels[grade].items()}
        # Representative historical guards; comprehensive 528-item checking
        # is at each FULL spiral, after G01-G22 repair.
        for g in (9,10):
            before_old[f"G{g:02d}"]=engine._scores(
                model,lib,graph,g,170003+g*617,count=12,device=device)
    else:
        number=int(grade[1:])
        seed=170003+number*617
        before_grade=engine._scores(model,lib,graph,number,seed,device=device)
        guards=[g for g in (1,10,13,16,17,19) if g<number]
        for g in guards:
            before_old[f"G{g:02d}"]=engine._scores(
                model,lib,graph,g,170003+g*617,count=12,device=device)
    trace=[];exposures={"current":0,"random_old":0,"preview":0}
    for _ in range(state["config"]["block"]):
        if grade.startswith("B"):
            rows,counts=course.compile_batch(grade,lib,graph,rng,method=method)
            metrics=staged.train_step(model,optimizer,anchor,soup,rows,graph,
                                      {},policy,device)
        else:
            rows,counts=lessons.compose_batch(lib,number,policy,graph,rng)
            # The original School50 _train path is deliberately retained,
            # including its 32-row current/old/preview allocation.
            metrics=engine._train(model,optimizer,anchor,graph,rows,counts,
                                  policy,device,consensus_teacher=soup,
                                  consensus_weight=engine.CONSOLIDATION_WEIGHT)
        trace.append(metrics)
        for kind,value in counts.items():
            mapped="random_old" if kind=="old" else kind
            exposures[mapped]+=value
    expected=state["optimizer_step"]+state["config"]["block"]
    if optimizer_receipt(optimizer)["steps"]!=[expected]:
        raise ValueError("ACQUISITION_ADAMW_STEP_NOT_CUMULATIVE")
    if grade.startswith("B"):
        after={fold:precursor.evaluate_panel(model,rows,graph,device)
               for fold,rows in panels[grade].items()}
        before=sum(profile["correct"] for profile in prior.values())
        now=sum(profile["correct"] for profile in after.values())
        immediate=(now-before)/24
    else:
        now_grade=engine._scores(model,lib,graph,number,seed,device=device)
        prior=before_grade
        after=now_grade
        immediate=now_grade-before_grade
    for gid in before_old:
        g=int(gid[1:])
        after_old[gid]=engine._scores(
            model,lib,graph,g,170003+g*617,count=12,device=device)
    old_mean=(sum(after_old[k]-before_old[k] for k in before_old) /
              len(before_old)) if before_old else 0
    reward=2*immediate+.6*old_mean
    teacher_key=2000+course.GRADES.index(grade)+1 if grade.startswith("B") else number
    engine.observe(state["teacher"],teacher_key,key,reward)
    if grade.startswith("B"):
        staged._observe_instruction(state["teacher"],grade,method,reward)
    filename,sha=engine._checkpoint(out,model,optimizer,graph,
                                   {"step":expected,"grade":grade,
                                    "epoch":VERSION,"pass":state["passes_completed"]+1})
    if engine._sha(out/filename)!=sha:
        raise ValueError("ACQUISITION_SAVED_CHECKPOINT_HASH_MISMATCH")
    state["checkpoint"]=filename
    state["checkpoint_sha256"]=sha
    state["optimizer_step"]=expected
    state["attempted_updates"]+=state["config"]["block"]
    state["retained_updates"]+=state["config"]["block"]
    state["visits"]+=1
    if grade.startswith("B"):
        grade_score=now/24
        champions=state["bridge_champions"]
    else:
        # Preserve the original grade-specific 48-question champion panel,
        # distinct from the routine 24-question teaching probe.
        grade_score=engine._grade_champion_score(
            model,graph,lib,number,device=device)
        champions=state["grade_champions"]
    previous=champions.get(grade)
    personal_best=previous is None or grade_score>previous["score"]
    if personal_best:
        champions[grade]={
            "score":grade_score,"checkpoint":filename,
            "checkpoint_sha256":sha,"optimizer_step":expected,
            "source_pass":state["passes_completed"]+1,
            "location":"research"}
    complete=_advance(state)
    record={"visit":state["visits"],"grade":grade,
            "pass":state["passes_completed"] if complete else state["passes_completed"]+1,
            "optimizer_step":expected,"checkpoint":filename,"checkpoint_sha256":sha,
            "updates":state["config"]["block"],"policy_id":key,
            "policy":policy,"method":method,"row_exposures":exposures,
            "development_before":prior,"development_after":after,
            "old_before":before_old,"old_after":after_old,
            "reward":reward,"teacher_events":state["teacher"]["events"],
            "last_loss":trace[-1],"grade_champion_score":grade_score,
            "new_grade_champion":personal_best,
            "disposition":"RETAINED_FOR_ACQUISITION"}
    state["grade_ledger"].append(record)
    report=None
    if complete:
        report=_pass_report(state,model,graph,lib,panels,device)
    state["last_run_status"]="GRADE_BOUNDARY"
    engine._atomic_json(out/"state.json",state)
    _prune(out,state)
    return record,report


def status(run_dir=RUN):
    path=Path(run_dir).expanduser()/"state.json"
    if not path.is_file():
        return {"status":"NOT_STARTED","run_dir":str(path.parent)}
    state=engine._read(path)
    return {"status":state["last_run_status"],"phase":state["phase"],
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
            "last_session":state.get("last_session")}


def run(*,run_dir=RUN,source_dir=SOURCE,device="mps",minutes=90,
        max_grade_visits=None,block=64,seed=20261013,
        initialize_only=False,stop_requested=lambda:False,reporter=None):
    if (not 0<minutes<=1440 or device not in ("cpu","mps") or
            (max_grade_visits is not None and max_grade_visits<1)):
        raise ValueError("ACQUISITION_INVALID_SESSION_BUDGET")
    config=configuration(block=block,seed=seed)
    out=Path(run_dir).expanduser().resolve(strict=False)
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
            old=_assert_source(source)
            state=_initialize(out,source,old,config,device)
        else:
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
        if state["pass_start_old"] is None:
            state["pass_start_old"]=_old(model,graph,lib,device)
            engine._atomic_json(out/"state.json",state)
        begun=time.monotonic();visits=0
        def finish(reason):
            if engine._sha(P43)!=pilot.CHAMPION_SHA256:
                raise ValueError("ACQUISITION_PROTECTED_P43_CHANGED")
            state["last_run_status"]=reason
            state["last_session"]={"stop_reason":reason,
                "elapsed_seconds":round(time.monotonic()-begun,2),
                "visits":visits,
                "retained_updates":visits*block,
                "attempted_updates":visits*block}
            engine._atomic_json(out/"state.json",state)
            return status(out)
        while True:
            if stop_requested():
                return finish("GRACEFUL_OPERATOR_STOP")
            if state["phase"]!="ACQUISITION":
                return finish("RETENTION_OPERATOR_REVIEW")
            if max_grade_visits is not None and visits>=max_grade_visits:
                return finish("EXPLICIT_GRADE_VISIT_CAP")
            if time.monotonic()-begun>=minutes*60:
                return finish("TIME_BUDGET_EXHAUSTED")
            if state["soup_epoch"]!=state["passes_completed"]:
                soup=_refresh_soup(out,state,model,device)
            record,report=_grade_visit(out,state,model,optimizer,graph,soup,lib,
                                       panels,device)
            visits+=1
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
                          f"{report['bridge_correct']}/{len(course.GRADES)*24} "
                          f"contrasts={report['bridge_contrasts']} "
                          f"{report['disposition']}",flush=True)
    finally:
        os.close(fd)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir",type=Path,default=RUN)
    parser.add_argument("--source-dir",type=Path,default=SOURCE)
    parser.add_argument("--device",choices=("cpu","mps"),default="mps")
    parser.add_argument("--minutes",type=float,default=90)
    parser.add_argument("--max-grade-visits",type=int)
    parser.add_argument("--block",type=int,default=64)
    parser.add_argument("--seed",type=int,default=20261013)
    parser.add_argument("--initialize-only",action="store_true")
    parser.add_argument("--status",action="store_true")
    parser.add_argument("--dashboard",action="store_true")
    parser.add_argument("--log-file",type=Path)
    args=parser.parse_args()
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
                     max_grade_visits=args.max_grade_visits,block=args.block,
                     seed=args.seed,initialize_only=args.initialize_only,
                     stop_requested=lambda:interrupted["stop"])
        if not args.dashboard or args.initialize_only:
            print(json.dumps(run(**options),indent=2,sort_keys=True))
            return
        if not sys.stdout.isatty():
            raise ValueError("ACQUISITION_DASHBOARD_REQUIRES_TTY")
        from .spiral_dashboard import Dashboard
        screen=Dashboard(stream=sys.stdout)
        screen.log_hint=str(args.log_file.name) if args.log_file else "-"
        log_path=args.log_file or args.run_dir.with_suffix(".log")
        log_path.parent.mkdir(parents=True,exist_ok=True)
        with log_path.open("a",encoding="utf-8",buffering=1) as log:
            screen.push("system",{"kind":"SCHOOL50 ACQUIRE",
                "detail":"B01-B07 then G01-G22; 64 updates per grade; no per-visit mastery veto"})
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
                    p=record["development_before"] if g.startswith("B") else {}
                    a=record["development_after"] if g.startswith("B") else {}
                    screen.push("candidate",{
                        "grade":g,"attempt":1,"policy_id":record["policy_id"],
                        "instruction_method":record["method"],
                        "bridge_before":p.get("primary"),
                        "bridge_after":a.get("primary"),
                        "bridge_confirm_before":p.get("confirm"),
                        "bridge_confirm_after":a.get("confirm"),
                        "old_before":record["old_before"],
                        "old_after":record["old_after"],
                        "teacher_credit":record["reward"],"reward":record["reward"],
                        "loss_last":record["last_loss"],
                        "allocation":record["row_exposures"],
                        "decision":"RETAIN","reason":"ACQUISITION_NOT_MASTERY"})
                    screen.push("grade",{
                        "grade_visit":record["visit"],"grade":g,
                        "step":record["optimizer_step"],"eligible":"-",
                        "selected":True,"prefix":state["passes_completed"]+1,
                        "outcome":"CUMULATIVE_ACQUISITION",
                        "next":PROGRAM[state["grade_index"]]})
                else:
                    screen.push("system",{"kind":"FULL PASS",
                        "detail":f"{record['pass']}: old {100*record['old_mean']:.2f}% "
                                 f"bridge {record['bridge_correct']}/168 "
                                 f"{record['disposition']}"})
            try:
                result=run(**options,reporter=report)
                log.write(json.dumps({"kind":"summary","record":result},
                                     sort_keys=True)+"\n")
                screen.mode="FINISHED"
            except BaseException as exc:
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
