"""Four-boundary cumulative bridge acquisition without whole-pass student rollback.

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
import statistics
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


VERSION = "bilqis.school50.bridge-carry-forward/v1"
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "bilqis-school50-bridge-priority-v8-recovery/runs/school50-bridge-priority-v8"
RUN = ROOT / "runs/school50-bridge-carry-forward-v9"
P43 = ROOT.parent / ("bilqis-auto-curriculum50/runs/school50-continuous-v1/"
                      "student-67800-2cf61275e081.pt")
PROGRAM = course.GRADES + tuple(f"G{n:02d}" for n in engine.REPORT_GRADES)
OLD_MEAN_PAUSE = .01
OLD_GRADE_PAUSE = 3/24
CARRY_FORWARD_PASSES = 4


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
    return {"version":VERSION,"block":block,"seed":seed,"bridge_attempts":3,"historic_attempts":1,
            "recipe":recipe(),"source_champion_sha256":pilot.CHAMPION_SHA256,
            "grade_program":list(PROGRAM),
            "max_old_mean_debt":OLD_MEAN_PAUSE,
            "max_old_grade_debt":OLD_GRADE_PAUSE,
            "carry_forward_passes":CARRY_FORWARD_PASSES}



def _assert_source(source):
    """Only a fully stopped, recipe-verified v8 B02 continuation is admissible."""
    if not source.is_dir():
        raise FileNotFoundError("BRIDGE_V9_V8_SOURCE_MISSING")
    lock=source.with_name(source.name+".writer.lock")
    fd=os.open(lock,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    try:
        try:
            fcntl.flock(fd,fcntl.LOCK_SH|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("BRIDGE_V9_V8_SOURCE_STILL_RUNNING") from exc
        old=engine._read(source/"state.json")
        config=old.get("config",{})
        if ((source/"sealed-evaluation.json").exists() or
                old.get("version")!="bilqis.school50.bridge-priority-recovery/v2" or
                old.get("phase")!="ACQUISITION" or
                old.get("last_run_status")!="GRACEFUL_OPERATOR_STOP" or
                (config.get("bridge_attempts"),config.get("historic_attempts"),
                 config.get("block"),config.get("seed"))!=(3,1,64,20261013) or
                old.get("source",{}).get("p43_sha256")!=pilot.CHAMPION_SHA256):
            raise ValueError("BRIDGE_V9_EXPECTS_STOPPED_V8_SCHOOL50")
        if (old.get("passes_completed")!=7 or old.get("grade_index")!=1 or
                old.get("visits")!=204 or old.get("optimizer_step")!=68696 or
                old.get("teacher",{}).get("events")!=1961 or
                old.get("attempted_updates")!=19456 or
                old.get("retained_updates")!=4032 or
                old.get("rollback_count")!=5 or
                len(old.get("candidate_ledger",[]))!=304 or
                len(old.get("grade_ledger",[]))!=204 or
                len(old.get("pass_ledger",[]))!=7 or
                old["grade_ledger"][-1].get("grade")!="B01" or
                old["grade_ledger"][-1].get("pass")!=8 or
                set(old.get("pass_start_old") or {})!=set(engine.REPORT_GRADE_IDS) or
                old.get("soup_epoch")!=7 or
                old["frozen_soup"]["manifest"]["votes"]!=23 or
                old["teacher"]["events"]-old["source"]["teacher_events"]!=304):
            raise ValueError("BRIDGE_V9_V8_SOURCE_LEDGER_MISMATCH")
        if ([item["grade"] for item in old["grade_ledger"]]!=
                list(PROGRAM)*7+["B01"] or
                [p["pass"] for p in old["pass_ledger"]]!=list(range(1,8)) or
                sum(x["attempted_updates"] for x in old["grade_ledger"])!=old["attempted_updates"] or
                sum(x["updates"] for x in old["grade_ledger"])!=old["retained_updates"] or
                sum(x["attempts"] for x in old["grade_ledger"])!=len(old["candidate_ledger"])):
            raise ValueError("BRIDGE_V9_V8_SOURCE_ACCOUNTING_MISMATCH")
        source_root=source.parents[1]
        relative={"runner":"bilqis_school/bridge_priority_recovery_runner.py",
                  "acquisition_lessons":"bilqis_school/acquisition_lessons.py",
                  "school50_engine":"bilqis_school/engine.py",
                  "school50_lessons":"bilqis_school/lessons.py",
                  "staged_training":"bilqis_school/spiral_staged_runner.py",
                  "foundation_oracle":"bilqis_school/bridge_foundation_lessons.py",
                  "bridge_oracle":"bilqis_school/spiral_semantic_bridge.py",
                  "primitive_oracle":"bilqis_school/spiral_primitive_lessons.py"}
        if set(relative)!=set(config["recipe"]):
            raise ValueError("BRIDGE_V9_V8_RECIPE_MISSING_KEY")
        for key,path in relative.items():
            if engine._sha(source_root/path)!=config["recipe"][key]:
                raise ValueError("BRIDGE_V9_V8_RECIPE_DRIFT:"+key)
        artifacts={f.name:engine._sha(f) for f in sorted(source.glob("*.pt"))}
        expected={old["checkpoint"]:old["checkpoint_sha256"],
                  old["holistic_anchor"]["checkpoint"]:old["holistic_anchor"]["checkpoint_sha256"],
                  old["frozen_soup"]["file"]:old["frozen_soup"]["sha256"],
                  P43.name:pilot.CHAMPION_SHA256}
        for archive in ("grade_champions","bridge_champions","provisional_bridge_champions"):
            for item in old[archive].values():
                if item.get("location")=="research":
                    expected[item["checkpoint"]]=item["checkpoint_sha256"]
        for name,sha in expected.items():
            if name not in artifacts or artifacts[name]!=sha or Path(name).name!=name:
                raise ValueError("BRIDGE_V9_V8_REFERENCED_ARTIFACT_MISSING:"+name)
        if any(f.is_symlink() for f in source.glob("*.pt")):
            raise ValueError("BRIDGE_V9_V8_SOURCE_SYMLINK")
        if engine._sha(P43)!=pilot.CHAMPION_SHA256:
            raise ValueError("BRIDGE_V9_P43_DRIFT")
        old["_source_state_sha256_at_read"]=engine._sha(source/"state.json")
        old["_import_artifacts"]=artifacts
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


def _initialize(out,source,old,config,device):
    """Import v8 at actual B02 with the original FP32, AdamW and teacher."""
    lock=source.with_name(source.name+".writer.lock")
    fd=os.open(lock,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    try:
        try:
            fcntl.flock(fd,fcntl.LOCK_SH|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("BRIDGE_V9_V8_SOURCE_STILL_RUNNING") from exc
        staging=Path(tempfile.mkdtemp(prefix=".bridge-carry-forward-v9-init-",dir=out.parent))
        try:
            for name,sha in sorted(old["_import_artifacts"].items()):
                _link_immutable(source/name,staging/name,sha)
            if engine._sha(source/"state.json")!=old["_source_state_sha256_at_read"]:
                raise ValueError("BRIDGE_V9_SOURCE_CHANGED_DURING_IMPORT")
            state=copy.deepcopy({k:v for k,v in old.items() if not k.startswith("_")})
            state["version"]=VERSION
            state["config"]=config
            state["last_run_status"]="READY_V9_CARRY_FORWARD_B02"
            state["last_session"]=None
            model,optimizer,graph=_load_student(staging,state,device)
            _soup(staging,state,model,device)
            if optimizer_receipt(optimizer)["steps"]!=[old["optimizer_step"]]:
                raise ValueError("BRIDGE_V9_V8_OPTIMIZER_MISMATCH")
            panels=_panels(graph,config["seed"])
            start_bridge=_bridges(model,graph,panels,device)
            start_old=_old(model,graph,lessons.TeacherLibrary(),device)
            correct=sum(f["correct"] for folds in start_bridge.values() for f in folds.values())
            contrasts=sum(f["paired_contrasts"] for folds in start_bridge.values() for f in folds.values())
            old_mean=sum(start_old.values())/22
            state["carry_origin"]={
                "source_run":str(source),"source_version":old["version"],
                "source_state_sha256":old["_source_state_sha256_at_read"],
                "checkpoint":old["checkpoint"],"checkpoint_sha256":old["checkpoint_sha256"],
                "optimizer_step":old["optimizer_step"],
                "teacher_events":old["teacher"]["events"],
                "visits":old["visits"],"candidate_attempts":len(old["candidate_ledger"]),
                "passed_previous_spirals":old["passes_completed"],
                "starting_grade":"B02","partial_initial_pass":8}
            state["carry_forward"]={
                "start_passes_completed":old["passes_completed"],
                "target_passes_completed":old["passes_completed"]+CARRY_FORWARD_PASSES,
                "completed_boundaries":0,
                "initial_grade_index":old["grade_index"],
                "window_start_checkpoint":old["checkpoint"],
                "window_start_checkpoint_sha256":old["checkpoint_sha256"],
                "window_start_optimizer_step":old["optimizer_step"],
                "window_start_old_scores":start_old,
                "window_start_bridge":start_bridge,
                "pass8_b01_inherited":True,
                "best_development":{
                    "checkpoint":old["checkpoint"],"checkpoint_sha256":old["checkpoint_sha256"],
                    "optimizer_step":old["optimizer_step"],
                    "bridge_correct":correct,"bridge_contrasts":contrasts,
                    "old_mean":old_mean,"ranking":[contrasts,correct,old_mean],
                    "source":"WINDOW_START_B02"},
                "reports":[]}
            # Since B01 of pass 8 was completed by v8, its true pass start
            # old baseline is inherited. No exact B01-start bridge profile
            # exists; do not invent one from the new B02 checkpoint.
            state["pass_start_bridge"]=None
            engine._atomic_json(staging/"state.json",state)
            os.replace(staging,out)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        return state
    finally:
        os.close(fd)

def _assert_frozen(state,config):
    if state.get("version")!=VERSION or state.get("config")!=config:
        raise ValueError("ACQUISITION_FROZEN_RECIPE_DRIFT_USE_NEW_RUN")
    if state.get("phase") not in ("ACQUISITION","DEVELOPMENTAL_REVIEW"):
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
    # Imported v7's 74/168 is historical evidence, not the starting score
    # for the current v8-derived student after repeated rollbacks.
    qualified=(not severe and old_mean>=original_mean-1e-9 and
               bridge_after>=window_correct+3 and
               all(sum(f["paired_contrasts"] for f in folds.values())>=1
                   for folds in development.values()))
    if (state["passes_completed"]<=carry["start_passes_completed"] or
            state["passes_completed"]>carry["target_passes_completed"]):
        raise ValueError("BRIDGE_V9_PASS_OUTSIDE_FROZEN_CARRY_WINDOW")
    completed=state["passes_completed"]-carry["start_passes_completed"]
    last=completed==CARRY_FORWARD_PASSES
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
        "bridge_window_start_correct":window_correct,
        "bridge_window_start_contrasts":window_contrasts,
        "bridge_vs_window_start_correct":bridge_after-window_correct,
        "bridge_vs_window_start_contrasts":contrasts-window_contrasts,
        "surviving_v9_optimizer_updates":state["optimizer_step"]-carry["window_start_optimizer_step"],
        "pass_start_bridge":copy.deepcopy(state.get("pass_start_bridge")),
        "rollback_triggers":reasons,
        "would_rollback_under_v8":severe,
        "historical_mean_floor":anchor["old_mean"]-OLD_MEAN_PAUSE,
        "research_qualified":qualified,
        "disposition":"DEVELOPMENTAL_WINDOW_COMPLETE" if last else
                      "DEVELOPMENTAL_CARRY_FORWARD"}
    state["pass_ledger"].append(report)
    if qualified and (state["research_champion"] is None or
                      bridge_after>state["research_champion"]["bridge_correct"]):
        state["research_champion"]={
            "pass":state["passes_completed"],"optimizer_step":state["optimizer_step"],
            "checkpoint":state["checkpoint"],
            "checkpoint_sha256":state["checkpoint_sha256"],
            "bridge_correct":bridge_after,"old_mean":old_mean}
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
    if last:
        state["phase"]="DEVELOPMENTAL_REVIEW"
    if not severe:
        # The new concept grade enters the soup only on replicated correct
        # contrasts across both independent development panels, plus a
        # strict correct-answer gain. Provisional checkpoints remain archived.
        for grade in course.GRADES:
            proposal=state["provisional_bridge_champions"].get(grade)
            if proposal is None:
                continue
            path=out/proposal["checkpoint"]
            if engine._sha(path)!=proposal["checkpoint_sha256"]:
                raise ValueError("HYBRID_BRIDGE_CHAMPION_CHECKPOINT_CHANGED")
            candidate,_,payload=engine.load_checkpoint(path)
            if digest(payload["graph"])!=state["graph_sha256"]:
                raise ValueError("HYBRID_BRIDGE_CHAMPION_ABI_CHANGED")
            candidate.to(device).eval()
            scored={fold:precursor.evaluate_panel(candidate,rows,graph,device)
                    for fold,rows in panels[grade].items()}
            initial=baseline[grade]
            gain=sum(scored[f]["correct"]-initial[f]["correct"]
                     for f in ("primary","confirm"))
            replicated=all(scored[f]["paired_contrasts"]>=1
                           for f in ("primary","confirm"))
            if gain>=2 and replicated:
                state["bridge_champions"][grade]=dict(
                    proposal,qualification="REPLICATED_DEVELOPMENT")
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

def _historic_visit(out,state,model,optimizer,graph,soup,lib,panels,device):
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
    for attempt in range(1,state["config"]["historic_attempts"]+1):
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
        reward=2*(after-before)+.6*old_delta
        gate={"decision":confirmation["decision"],
              "reason":confirmation["reason"]}
        credit=engine._candidate_teacher_credit(reward,gate)
        engine.observe(state["teacher"],number,key,credit)
        state["attempted_updates"]+=state["config"]["block"]
        record={"grade":grade,"attempt":attempt,"parent_step":base_step,
                "candidate_step":expected,"policy_id":key,"policy":policy,
                "before":before,"after":after,"raw_reward":reward,
                "teacher_credit":credit,"confirmation":confirmation,
                "decision":gate["decision"],"reason":gate["reason"],
                "row_exposures":allocation,"last_loss":losses[-1],
                "selected":False}
        attempts.append(record)
        # Preserve original ordering: rank only candidates that clear the
        # simultaneous old-22 confirmation; a local win alone is insufficient.
        if gate["decision"]=="PROMOTE":
            ranking=(confirmation["mean_delta"],
                     confirmation["worst_grade_delta"],
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
        promoted=prior is None or grade_score>prior["score"]
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
         "disposition":"SELECTED_SAFE_CANDIDATE" if selected else "NO_SAFE_CANDIDATE"}
    state["grade_ledger"].append(row)
    report=_pass_report(out,state,model,graph,lib,panels,device) if completed else None
    state["last_run_status"]="GRADE_BOUNDARY"
    engine._atomic_json(out/"state.json",state)
    _prune(out,state)
    if report and report["disposition"].startswith("ROLLED_BACK"):
        model,optimizer,_=_load_student(out,state,device)
    return row,report,model,optimizer



def _bridge_visit(out,state,model,optimizer,graph,soup,lib,panels,device):
    """Three independent B attempts; keep the best safe acquisition precursor.

    All three attempts inherit exactly the same FP32 student, AdamW moments
    and frozen soup, but have distinct teacher policies and fresh RNG seeds.
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
    before={fold:precursor.evaluate_panel(model,rows,graph,device)
            for fold,rows in panels[grade].items()}
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
            last_loss=staged.train_step(
                candidate,candidate_optimizer,anchor,soup,
                rows,graph,{},policy,device)
            for kind,value in counts.items():
                exposures[kind]+=value
        expected_step=base_step+state["config"]["block"]
        if optimizer_receipt(candidate_optimizer)["steps"]!=[expected_step]:
            raise ValueError("BRIDGE_PRIORITY_CANDIDATE_ADAMW_STEP_DRIFT")
        after={fold:precursor.evaluate_panel(candidate,rows,graph,device)
               for fold,rows in panels[grade].items()}
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
        raw_reward=(2*(after_correct-before_correct)/24+
                    .25*(after_pairs-before_pairs)/8+
                    .6*old_mean)
        guard_safe=all(delta>-3/12+1e-9 for delta in old_deltas.values())
        teacher_credit=(raw_reward if guard_safe else
                        min(raw_reward,-engine.CANDIDATE_CLEAR_REWARD))
        engine.observe(state["teacher"],grade_key,key,teacher_credit)
        staged._observe_instruction(state["teacher"],grade,method,teacher_credit)
        state["attempted_updates"]+=state["config"]["block"]
        record={
            "grade":grade,"attempt":attempt,"parent_step":base_step,
            "parent_checkpoint_sha256":parent_sha,
            "candidate_step":expected_step,"policy_id":key,"policy":policy,
            "instruction_method":method,
            "bridge_before":before,"bridge_after":after,
            "old_before":before_old,"old_after":after_old,
            "correct_before":before_correct,"correct_after":after_correct,
            "paired_before":before_pairs,"paired_after":after_pairs,
            "bridge_ce_improvement":ce_improvement,
            "raw_reward":raw_reward,"teacher_credit":teacher_credit,
            "decision":"ELIGIBLE" if guard_safe else "REJECT",
            "reason":"B_ACQUISITION_GUARD_SAFE" if guard_safe else
                     "B_ACQUISITION_HISTORICAL_GUARD_CRASH",
            "row_exposures":exposures,"last_loss":last_loss,"selected":False}
        attempts.append(record)
        if guard_safe:
            ranking=(after_pairs,after_correct,ce_improvement,old_mean,-attempt)
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
        disposition="B_NO_SAFE_CANDIDATE"
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
        grade_score=chosen["correct_after"]/24
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
        disposition="B_BEST_SAFE_ACQUISITION_RETAINED"
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


def _grade_visit(out,state,model,optimizer,graph,soup,lib,panels,device):
    grade=PROGRAM[state["grade_index"]]
    if grade.startswith("G"):
        return _historic_visit(out,state,model,optimizer,graph,soup,lib,
                               panels,device)
    return _bridge_visit(out,state,model,optimizer,graph,soup,lib,
                         panels,device)

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
            "last_session":state.get("last_session"),
            "surviving_v9_optimizer_updates":(
                state["optimizer_step"]-state["carry_forward"]["window_start_optimizer_step"]
                if "carry_forward" in state else None),
            "carry_forward":{
                "completed_boundaries":state["carry_forward"]["completed_boundaries"],
                "target_boundaries":CARRY_FORWARD_PASSES,
                "target_passes_completed":state["carry_forward"]["target_passes_completed"],
                "starting_grade":"B02",
                "partial_initial_pass":True,
                "best_development":state["carry_forward"]["best_development"],
                "recent_report":(state["carry_forward"]["reports"][-1]
                                 if state["carry_forward"]["reports"] else None)}}


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
        begun=time.monotonic();visits=0
        attempted_at_start=state["attempted_updates"]
        retained_at_start=state["retained_updates"]
        def finish(reason):
            if engine._sha(P43)!=pilot.CHAMPION_SHA256:
                raise ValueError("ACQUISITION_PROTECTED_P43_CHANGED")
            state["last_run_status"]=reason
            state["last_session"]={"stop_reason":reason,
                "elapsed_seconds":round(time.monotonic()-begun,2),
                "visits":visits,
                "retained_updates":state["retained_updates"]-retained_at_start,
                "attempted_updates":state["attempted_updates"]-attempted_at_start}
            engine._atomic_json(out/"state.json",state)
            return status(out)
        while True:
            if stop_requested():
                return finish("GRACEFUL_OPERATOR_STOP")
            if state["phase"]!="ACQUISITION":
                return finish("DEVELOPMENTAL_WINDOW_COMPLETE")
            if max_grade_visits is not None and visits>=max_grade_visits:
                return finish("EXPLICIT_GRADE_VISIT_CAP")
            if time.monotonic()-begun>=minutes*60:
                return finish("TIME_BUDGET_EXHAUSTED")
            if state["soup_epoch"]!=state["passes_completed"]:
                soup=_refresh_soup(out,state,model,device)
            _ensure_pass_start(out,state,model,graph,lib,device)
            record,report,model,optimizer=_grade_visit(out,state,model,optimizer,graph,soup,lib,
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
        screen=Dashboard(stream=sys.stdout,title="BILQIS / SCHOOL50 V9")
        screen.log_hint=str(args.log_file.name) if args.log_file else "-"
        log_path=args.log_file or args.run_dir.with_suffix(".log")
        log_path.parent.mkdir(parents=True,exist_ok=True)
        with log_path.open("a",encoding="utf-8",buffering=1) as log:
            screen.push("system",{"kind":"SCHOOL50 BRIDGE PRIORITY",
                "detail":"3 B / 1 G; research student carries through 4 pass boundaries; protected champion separate"})
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
                else:
                    screen.push("system",{"kind":"FULL PASS",
                        "detail":f"{record['pass']}: old {100*record['old_mean']:.2f}% "
                                 f"bridge {record['bridge_correct']}/168 "
                                 f"{record['disposition']}"})
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
