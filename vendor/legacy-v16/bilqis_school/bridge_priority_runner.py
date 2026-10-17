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


VERSION = "bilqis.school50.bridge-priority/v1"
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "bilqis-school50-hybrid-acquisition-v6/runs/school50-hybrid-acquisition-v6"
RUN = ROOT / "runs/school50-bridge-priority-v7"
P43 = ROOT.parent / ("bilqis-auto-curriculum50/runs/school50-continuous-v1/"
                      "student-67800-2cf61275e081.pt")
PROGRAM = course.GRADES + tuple(f"G{n:02d}" for n in engine.REPORT_GRADES)
OLD_MEAN_PAUSE = .01
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
    return {"version":VERSION,"block":block,"seed":seed,"bridge_attempts":3,"historic_attempts":1,
            "recipe":recipe(),"source_champion_sha256":pilot.CHAMPION_SHA256,
            "grade_program":list(PROGRAM),
            "max_old_mean_debt":OLD_MEAN_PAUSE,
            "max_old_grade_debt":OLD_GRADE_PAUSE}



def _assert_source(source):
    """Import only the explicitly stopped v6 production lineage."""
    if not source.is_dir():
        raise FileNotFoundError("BRIDGE_PRIORITY_STOPPED_V6_SOURCE_MISSING")
    lock=source.with_name(source.name+".writer.lock")
    fd=os.open(lock,os.O_CREAT|os.O_RDWR|getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        try:
            fcntl.flock(fd,fcntl.LOCK_SH|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("BRIDGE_PRIORITY_V6_SOURCE_STILL_RUNNING") from exc
        old=engine._read(source/"state.json")
        if (old.get("version")!="bilqis.school50.hybrid-acquisition/v1" or
                old.get("last_run_status")!="GRACEFUL_OPERATOR_STOP" or
                old.get("phase")!="ACQUISITION" or
                old.get("source",{}).get("p43_sha256")!=pilot.CHAMPION_SHA256):
            raise ValueError("BRIDGE_PRIORITY_REQUIRES_STOPPED_V6_LINEAGE")
        if not old.get("grade_ledger") or old["grade_ledger"][-1]["grade"]!=                PROGRAM[(old["grade_index"]-1)%len(PROGRAM)]:
            raise ValueError("BRIDGE_PRIORITY_V6_GRADE_BOUNDARY_UNPROVEN")
        if old["optimizer_step"]<=67800 or old["teacher"]["events"]<=1562:
            raise ValueError("BRIDGE_PRIORITY_V6_SOURCE_NOT_TRAINED")
        artifacts={old["checkpoint"]:old["checkpoint_sha256"],
                   old["frozen_soup"]["file"]:old["frozen_soup"]["sha256"]}
        artifacts[old["holistic_anchor"]["checkpoint"]]=            old["holistic_anchor"]["checkpoint_sha256"]
        for archive in ("grade_champions","bridge_champions",
                        "provisional_bridge_champions"):
            for champion in old[archive].values():
                if champion.get("location")=="research":
                    artifacts[champion["checkpoint"]]=champion["checkpoint_sha256"]
        for name,sha in artifacts.items():
            if (name!=Path(name).name or (source/name).is_symlink() or
                    engine._sha(source/name)!=sha):
                raise ValueError("BRIDGE_PRIORITY_V6_ARTIFACT_HASH_DRIFT:"+name)
        if engine._sha(P43)!=pilot.CHAMPION_SHA256:
            raise ValueError("BRIDGE_PRIORITY_P43_REFERENCE_MUTATED")
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
    """Fork v6's stopped student and independently trained teacher with 0 copied bytes."""
    staging=Path(tempfile.mkdtemp(prefix=".bridge-priority-init-",dir=out.parent))
    try:
        if old["checkpoint"]==P43.name:
            raise ValueError("BRIDGE_PRIORITY_SOURCE_NOT_DISTINCT_FROM_P43")
        for name,sha in sorted(old["_import_artifacts"].items()):
            if name==old["frozen_soup"]["file"]:
                # Name this inherited soup distinctly from locally rebuilt
                # epoch-1 soup. Otherwise second-pass rollover collides.
                target="soup-inherited-v6-"+sha[:12]+".pt"
            else:
                target=name
            _link_immutable(source/name,staging/target,sha)
        _link_immutable(P43,staging/P43.name,pilot.CHAMPION_SHA256)
        if engine._sha(source/"state.json")!=old["_source_state_sha256_at_read"]:
            raise ValueError("BRIDGE_PRIORITY_SOURCE_STATE_CHANGED_DURING_IMPORT")
        model,optimizer,payload=engine.load_checkpoint(staging/old["checkpoint"])
        engine._device(model,optimizer,device)
        graph=payload["graph"]
        if (digest(graph)!=old["graph_sha256"] or
                optimizer_receipt(optimizer)["steps"]!=[old["optimizer_step"]]):
            raise ValueError("BRIDGE_PRIORITY_STUDENT_ADAMW_IMPORT_FAILED")
        inherited_soup=copy.deepcopy(old["frozen_soup"])
        inherited_soup["file"]="soup-inherited-v6-"+inherited_soup["sha256"][:12]+".pt"
        baselines=_bridges(model,graph,_panels(graph,config["seed"]),device)
        source_ref={"directory":str(source),
                    "checkpoint":old["checkpoint"],
                    "checkpoint_sha256":old["checkpoint_sha256"],
                    "optimizer_step":old["optimizer_step"],
                    "teacher_events":old["teacher"]["events"],
                    "state_sha256":old["_source_state_sha256_at_read"],
                    "p43_sha256":pilot.CHAMPION_SHA256,
                    "abandoned_partial_pass":{
                        "visits":old["visits"],"passes_completed":old["passes_completed"],
                        "grade_index":old["grade_index"],"next_grade":
                        PROGRAM[old["grade_index"]]}}
        state={
            "version":VERSION,"config":config,
            "checkpoint":old["checkpoint"],
            "checkpoint_sha256":old["checkpoint_sha256"],
            "optimizer_step":old["optimizer_step"],
            "graph_sha256":old["graph_sha256"],
            "teacher":copy.deepcopy(old["teacher"]),"source":source_ref,
            "frozen_soup":inherited_soup,"soup_epoch":0,
            "soup_history":[dict(inherited_soup,inherited_from="stopped-v6")],
            "grade_champions":copy.deepcopy(old["grade_champions"]),
            "bridge_champions":copy.deepcopy(old["bridge_champions"]),
            "provisional_bridge_champions":copy.deepcopy(
                old["provisional_bridge_champions"]),
            "rollback_count":0,
            "source_old_scores":copy.deepcopy(old["source_old_scores"]),
            "baseline_bridge":baselines,
            "grade_index":0,"visits":0,"passes_completed":0,
            "attempted_updates":0,"retained_updates":0,
            "grade_ledger":[],"pass_ledger":[],"candidate_ledger":[],
            "pass_start_old":None,"phase":"ACQUISITION",
            "last_run_status":"READY","last_session":None,
            "research_champion":copy.deepcopy(old.get("research_champion")),
            "holistic_anchor":copy.deepcopy(old["holistic_anchor"])}
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
    severe=(old_mean<anchor["old_mean"]-OLD_MEAN_PAUSE+1e-9 or
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
        # Preserve the rejected-pass checkpoint in the pass ledger and
        # qualified grade champions independently. Restore only the live
        # student and AdamW pointer. Never rewind the teaching history.
        report["disposition"]="ROLLED_BACK_TO_HOLISTIC_CHAMPION"
        report["restored_checkpoint"]=anchor["checkpoint"]
        state["checkpoint"]=anchor["checkpoint"]
        state["checkpoint_sha256"]=anchor["checkpoint_sha256"]
        state["optimizer_step"]=anchor["optimizer_step"]
        state["rollback_count"]=state.get("rollback_count",0)+1
        # Original School50 did not close a lineage after a failed spiral.
        # Restore model+AdamW, retain teacher/champions, then continue onto
        # the next B01 with a refreshed frozen soup at the next boundary.
        state["phase"]="ACQUISITION"
    elif old_mean>anchor["old_mean"]:
        state["holistic_anchor"]={"checkpoint":state["checkpoint"],
                                   "checkpoint_sha256":state["checkpoint_sha256"],
                                   "optimizer_step":state["optimizer_step"],
                                   "old_mean":old_mean}
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
    return report


def _prune(out,state,*,keep_recent=8,keep_passes=4):
    """Prune only this run's redundant binaries AFTER the atomic state save."""
    records=state["grade_ledger"]
    keep={state["checkpoint"],state["source"]["checkpoint"],
          state["holistic_anchor"]["checkpoint"],P43.name}
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
                return finish("RETENTION_OPERATOR_REVIEW")
            if max_grade_visits is not None and visits>=max_grade_visits:
                return finish("EXPLICIT_GRADE_VISIT_CAP")
            if time.monotonic()-begun>=minutes*60:
                return finish("TIME_BUDGET_EXHAUSTED")
            if state["soup_epoch"]!=state["passes_completed"]:
                soup=_refresh_soup(out,state,model,device)
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
        screen=Dashboard(stream=sys.stdout,title="BILQIS / SCHOOL50 V7")
        screen.log_hint=str(args.log_file.name) if args.log_file else "-"
        log_path=args.log_file or args.run_dir.with_suffix(".log")
        log_path.parent.mkdir(parents=True,exist_ok=True)
        with log_path.open("a",encoding="utf-8",buffering=1) as log:
            screen.push("system",{"kind":"SCHOOL50 BRIDGE PRIORITY",
                "detail":"Three B candidates per grade, one G candidate; original G retention gate"})
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
