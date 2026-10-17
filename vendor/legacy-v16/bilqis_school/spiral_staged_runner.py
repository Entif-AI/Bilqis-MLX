"""School50 v5: prerequisite-gated domain staircases and hybrid qualification.

Research-only lineage. Reuses the historic teacher mutation and consolidation
mechanisms, rejecting any candidate with significant old-grade regression.
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
import tempfile
import time
import uuid

import torch
from torch.nn import functional as F

from bilqis_logic.kernel import digest
from bilqis_micro.graph import STATES
from bilqis_micro.run import optimizer_receipt
from bilqis_ref.model import batch, state_hash
from . import arithmetic, engine, lessons, numeric_answer_contract as contract
from . import numeric_answer_pilot as pilot, spiral_numeric_lessons as mathcourse
from . import spiral_semantic_bridge as bridge
from . import spiral_mastery as mastery
from . import spiral_fusion as fusion
from . import spiral_primitive_lessons as primitives

VERSION = "bilqis.school50.mastery-v5/v3"
RUN = Path(__file__).resolve().parents[1] / "runs/school50-mastery-v5-v3"
PREVIOUS_V5_V2_TEACHER = (Path(__file__).resolve().parents[2] /
    "bilqis-school50-mastery-v5/runs/school50-mastery-v5-v2/state.json")
PREVIOUS_V5_TEACHER = (Path(__file__).resolve().parents[1] /
    "runs/school50-mastery-v5/state.json")
LEGACY_V4_TEACHER = (Path(__file__).resolve().parents[2] /
    "bilqis-school50-numeric-spiral/runs/school50-cumulative-numeric-spiral-v4/state.json")
OLD_ITEM = 1 / (24 * 22)
OLD_GRADE_ITEM = 1 / 24
NUMERIC_ITEM = 1 / 18
PASS_REGRESSION_THRESHOLD = .01
INSTRUCTIONAL_METHODS = ("standard", "minimal_counterfactual",
                         "structural_equivalence")


def _completed_v2_state():
    """Read v2 only when its real filesystem writer lock is available."""
    if not PREVIOUS_V5_V2_TEACHER.is_file():
        return None
    lock=PREVIOUS_V5_V2_TEACHER.parent.with_name(
        PREVIOUS_V5_V2_TEACHER.parent.name+".writer.lock")
    fd=os.open(lock,os.O_CREAT|os.O_RDWR|getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        try:fcntl.flock(fd,fcntl.LOCK_SH|fcntl.LOCK_NB)
        except BlockingIOError:return None
        state=engine._read(PREVIOUS_V5_V2_TEACHER)
        if state.get("last_run_status") in (None,"READY","DURABLE_GRADE_BOUNDARY"):
            return None
        return state
    finally:
        os.close(fd)

# Every complete pass begins with all eight direct-number math grades,
# followed by the historical G01..G22 curriculum in its original order.
# The later 22-grade recovery phase has a chance to consolidate old skills
# *before* the whole-pass champion decision. The math grades retain M-ids,
# leaving New Ithkuil G23..G33 untouched.
CYCLE = tuple(f"M{i:02d}" for i in range(1,9)) + tuple(
    f"G{i:02d}" for i in range(1,23))
assert len(CYCLE) == 30 and set(CYCLE) == set(mathcourse.CYCLE)


def recipe():
    paths = {"runner": __file__, "lessons": mathcourse.__file__,
             "mastery": mastery.__file__,
             "primitive_lessons": primitives.__file__,
             "fusion": fusion.__file__,
             "semantic_bridge": bridge.__file__,
             "school50": engine.__file__, "original_lessons": lessons.__file__,
             "numeric_readout": contract.__file__}
    return {name: engine._sha(path) for name, path in paths.items()}


def configuration(block, attempts, seed, device, max_stalled_passes=3,
                  max_frontier_failures=36):
    if not (1 <= block <= 128 and 1 <= attempts <= 8 and
            1 <= max_stalled_passes <= 50 and
            1 <= max_frontier_failures <= 256 and device in ("cpu", "mps")):
        raise ValueError("SPIRAL_INVALID_CANDIDATE_BUDGET")
    return {"version": VERSION, "block": block, "attempts": attempts,
            "seed": seed, "device": device, "max_stalled_passes":max_stalled_passes,
            "max_frontier_failures":max_frontier_failures,
            "cycle": list(CYCLE),
            "lesson_allocation": dict(mathcourse.ALLOC), "recipe": recipe(),
            "source_sha256": pilot.CHAMPION_SHA256}


def _input(rows, graph, device):
    mapping = {token:i for i,token in enumerate(graph["tokens"])}
    sequences = [(bridge.encode(r["input"], graph)
                  if r["input"].get("task") == bridge.VERSION else
                  arithmetic.encode(r["input"], mapping)
                  if r.get("answer_kind") == "numeric" else lessons.encode(r, graph))
                 for r in rows]
    if any(len(s)>96 for s in sequences):
        raise ValueError("SPIRAL_INPUT_EXCEEDS_96")
    return batch(sequences, device=device)


def _gold(rows, kind, device):
    return torch.tensor([r["gold"] if kind == "numeric"
                         else STATES.index(r["gold"]) for r in rows],
                        device=device, dtype=torch.long)


@torch.no_grad()
def evaluate_numeric(model, rows, graph, numbers, device):
    model.eval()
    mathcourse.validate_rows(rows, graph)
    inputs, lengths = _input(rows, graph, device)
    logits = contract.readout(model, inputs, lengths,
                              answer_kind="numeric", number_ids=numbers)
    gold = _gold(rows, "numeric", device)
    pred = logits.argmax(-1)
    return {"correct": int((pred == gold).sum().cpu()),
            "questions": len(rows),
            "accuracy": float((pred == gold).float().mean().cpu()),
            "ce": float(F.cross_entropy(logits, gold).cpu()),
            "distinct_predictions": int(pred.unique().numel())}


@torch.no_grad()
def evaluate_primitives(model, rows, graph, numbers, device):
    """Typed 101-way numbers and evidence states in the same primitive exam."""
    model.eval()
    total_correct=0; total_ce=0.; numeric_correct=0; evidence_correct=0
    distinct=set(); evidence_predictions=[]
    for kind in ("numeric","evidence"):
        subset=[row for row in rows if row["answer_kind"]==kind]
        if not subset:continue
        if kind=="numeric":mathcourse.validate_rows(subset,graph)
        else:lessons.valid_rows(subset,graph)
        ids,lengths=_input(subset,graph,device)
        logits=contract.readout(model,ids,lengths,answer_kind=kind,number_ids=numbers)
        labels=_gold(subset,kind,device)
        output=logits.argmax(-1)
        correct=int((output==labels).sum().item())
        total_correct+=correct
        total_ce+=len(subset)*float(F.cross_entropy(logits,labels).item())
        if kind=="numeric":
            numeric_correct=correct
            distinct.update(output.cpu().tolist())
        else:
            evidence_correct=correct
            evidence_predictions=output.cpu().tolist()
    return {"correct":total_correct,"questions":len(rows),
            "accuracy":total_correct/len(rows),"ce":total_ce/len(rows),
            "distinct_predictions":len(distinct),
            "numeric_correct":numeric_correct,"evidence_correct":evidence_correct,
            "evidence_predicted_true":sum(x==STATES.index("TRUE") for x in evidence_predictions),
            "evidence_predicted_false":sum(x==STATES.index("FALSE") for x in evidence_predictions)}


def _primitive_panel(stage,graph,*,seed,exclude=()):
    return primitives.panel(stage,graph,split="development",seed=seed,
                            exclude=exclude)


def _bridge_for_stage(grade,stage,graph,*,seed,exclude=()):
    if grade=="M01":
        return primitives.bridge_panel(stage,graph,split="development",seed=seed,
                                       exclude=exclude)
    return _bridge_panel(grade,graph,split="development",seed=seed)


def _bridge_incubation_gain(before,after,confirm_before,confirm_after,
                            math_before,math_after):
    """Provisional retention, not a grade-mastering numerical promotion.

    Require replication on a *different development source panel*, and a
    positive mathematical-logic relationship rather than merely predicting
    TRUE more often. Never consult the sealed exam to select candidates.
    """
    if not (before and after and confirm_before and confirm_after):
        return False
    if (after["correct"]-before["correct"]<2 or
            confirm_after["correct"]<confirm_before["correct"]+1 or
            after["ce"]>before["ce"]+.03 or
            math_after["correct"]<math_before["correct"] or
            math_after["ce"]>math_before["ce"]+.05):
        return False
    if any(after.get("by_family",{}).get(family,{}).get("correct",0) <
           before.get("by_family",{}).get(family,{}).get("correct",0)-1
           for family in bridge.FAMILIES):
        return False
    if not any(after["by_family"][name]["correct"] >
               before["by_family"][name]["correct"]
               for name in ("iff_math","implies_math")):
        return False
    # TRUE-only/ FALSE-only predictions are not sufficient evidence of
    # arithmetic-logic transfer, especially on twelve binary propositions.
    for metrics in (after,confirm_after):
        if (min(metrics["predicted_true"],metrics["predicted_false"])<2 or
                metrics["predicted_true"]+metrics["predicted_false"]<
                metrics["questions"]-2):
            return False
    return True


def _numeric_candidate_decision(old_before,old_after,old_champion,*,grade,
                                math_before,math_after,bridge_before,
                                bridge_after,bridge_confirm_before=None,
                                bridge_confirm_after=None,primitive_stage=None):
    """Return a reversible student eligibility decision, NOT grade mastery."""
    decision,reason=retention_gate(old_before,old_after,old_champion,
        grade=grade,math_before=math_before,math_after=math_after)
    if (primitive_stage and decision=="REJECT" and
            reason=="NO_NUMERIC_DEVELOPMENT_PROGRESS" and
            _bridge_incubation_gain(bridge_before,bridge_after,
                bridge_confirm_before,bridge_confirm_after,
                math_before,math_after)):
        return "ELIGIBLE","BRIDGE_TRANSFER_INCUBATION_WITH_RETENTION"
    if primitive_stage and decision=="ELIGIBLE" and reason=="NUMERIC_NEW_CORRECT_ANSWER_WITH_RETENTION":
        return "ELIGIBLE","PRIMITIVE_NEW_CORRECT_ANSWER_WITH_RETENTION"
    return decision,reason


def _primitive_progress(stage,before,after,confirm_before,confirm_after):
    """An observed concept improvement, separately checked on a second panel.

    Comparator stages must improve Boolean relational predictions; merely
    guessing another direct numeral does not establish comparator mastery.
    """
    if stage not in primitives.STAGES[:-1]:
        raise ValueError("M01_UNKNOWN_PRIMITIVE_STAGE")
    key="evidence_correct" if stage=="order" else "numeric_correct"
    return (after[key]>before[key] and
            confirm_after[key]>=confirm_before[key] and
            after["correct"]>=before["correct"] and
            confirm_after["correct"]>=confirm_before["correct"])


def _numeric_panel(grade, graph, *, split, seed, count=6):
    buckets = {"train": range(6), "development": (6,7), "sealed": (8,9)}
    if split not in buckets:
        raise ValueError("UNKNOWN_SPIRAL_EXAM_SPLIT")
    rng = random.Random(seed + int(grade[1:])*1009)
    seen = set()
    rows = []
    for _ in range(count):
        for difficulty in mathcourse.DIFFICULTIES:
            for _try in range(12000):
                expression = (mathcourse._nonlocal_expression(grade,rng,difficulty)
                              if rng.randrange(4)==0 else mathcourse._make(grade,rng,difficulty))
                try:
                    mathcourse._numeric(expression)
                except ValueError:
                    continue
                if grade=="M01" and not primitives.admissible_expression_for_split(
                        expression,split):
                    continue
                identity = digest(expression)
                if identity in seen or int(identity[:12],16)%10 not in buckets[split]:
                    continue
                seen.add(identity)
                rows.append(mathcourse._row(grade,expression,difficulty=difficulty,
                                            tranche="novelty",triplet="exam",mode="exam"))
                break
            else:
                raise ValueError("SPIRAL_EXAM_DIVERSITY_EXHAUSTED")
    mathcourse.validate_rows(rows, graph)
    return rows


def _bridge_panel(grade, graph, *, split, seed, count=2):
    """Paired held-out projections of each numerical semantic source.

    The same source expression owns all partitions, and only development
    panels are eligible for teaching-policy feedback. Sealed is never called
    in the training runner.
    """
    candidates=_numeric_panel(grade,graph,split=split,seed=seed,count=count+2)
    output=[]
    seen=set()
    wanted=count*len(mathcourse.DIFFICULTIES)
    for number in candidates:
        expression=number["input"]["expression"]
        if number["gold"] >= arithmetic.MAX_NUMBER:
            continue
        family=bridge.FAMILIES[(len(output)//2) % len(bridge.FAMILIES)]
        family_rng=random.Random(seed+int(digest([grade,expression])[:12],16))
        linked=mathcourse.cross_domain_triplet(grade,graph,family_rng,
            family=family,tranche="exam",split=split,source=expression)
        if any(row["id"] in seen for row in linked[1:]):
            continue
        seen.update(row["id"] for row in linked[1:])
        output.extend(linked[1:])
        if len(output)==2*wanted:
            break
    if len(output)!=2*wanted:
        raise ValueError("BRIDGE_EXAM_SOURCE_DIVERSITY_EXHAUSTED")
    bridge.validate_rows(output,graph,partition=split)
    return output


@torch.no_grad()
def evaluate_bridge(model, rows, graph, device):
    model.eval()
    bridge.validate_rows(rows,graph)
    inputs,lengths=_input(rows,graph,device)
    logits=contract.readout(model,inputs,lengths,answer_kind="evidence",
                            number_ids=contract.numeric_token_ids(graph))
    labels=_gold(rows,"evidence",device)
    predictions=logits.argmax(-1)
    correct=predictions==labels
    groups={}
    for family in bridge.FAMILIES:
        indices=[i for i,r in enumerate(rows) if
                 r["course_meta"]["bridge_family"]==family]
        if indices:
            groups[family]={"correct":int(correct[indices].sum().item()),
                            "questions":len(indices)}
    return {"correct":int(correct.sum().item()), "questions":len(rows),
            "accuracy":float(correct.float().mean().item()),
            "ce":float(F.cross_entropy(logits,labels).item()),
            "by_family":groups,
            "predicted_true":int((predictions==STATES.index("TRUE")).sum().item()),
            "predicted_false":int((predictions==STATES.index("FALSE")).sum().item())}


def _bridge_scores(model, graph, device, seed):
    return {grade:evaluate_bridge(model,_bridge_panel(grade,graph,
               split="development",seed=seed^0x21375,count=4),graph,device)
            for grade in mathcourse.MAP}


def retention_gate(parent, candidate, champion, *, grade,
                   math_before=None, math_after=None):
    """School50's positive old-school gate; numeric requires bounded incubation.

    Both use 528 historical questions. A new numeric grade may temporarily
    perturb the old representation while learning its 101-class readout.
    The later historical recovery phase uses the stricter School50 guard;
    the original champion's complete-pass retention floor remains separate.
    """
    if not len(parent)==len(candidate)==len(champion)==22 or (
            set(parent)!=set(candidate) or set(parent)!=set(champion)):
        raise ValueError("SPIRAL_REQUIRES_ALL_22_GRADES")
    deltas = {g: candidate[g] - parent[g] for g in parent}
    worst = min(deltas.values())
    net = sum(deltas.values()) / 22
    if grade in mathcourse.MAP:
        # During the first eight numerical grades, allow the old representation
        # to bend more than it may at the *end* of a complete pass. The 22
        # historical grades then run in order and repair this temporary debt.
        # The final 1pp/one-item pass guard is never weakened.
        if worst <= -3 * OLD_GRADE_ITEM + 1e-9:
            return "REJECT", "NUMERIC_PHASE_PARENT_GRADE_CRASH"
        if math_before is None or math_after is None:
            raise ValueError("SPIRAL_MATH_EXAM_MISSING")
        # In contrast to an old equality grade, a direct 101-class numeral
        # may initially improve log probability without crossing argmax.
        # Permit a small number of temporarily displaced items while the
        # 101-class readout develops; the recovery and pass guards must repair
        # the old-school debt, not let numerical progress hide a final loss.
        if net < -3 * OLD_ITEM - 1e-9:
            return "REJECT", "NUMERIC_EXCESSIVE_OLD_SCHOOL_DEBT"
        champion_mean = sum(champion.values()) / 22
        if sum(candidate.values()) / 22 < champion_mean - .05 - 1e-9:
            return "REJECT", "NUMERIC_PHASE_CUMULATIVE_DEBT_LIMIT"
        if any(candidate[g] < champion[g] - 3 * OLD_GRADE_ITEM - 1e-9 for g in parent):
            return "REJECT", "NUMERIC_CHAMPION_GRADE_SAFETY_VETO"
        if math_after["correct"] > math_before["correct"]:
            return "ELIGIBLE", "NUMERIC_NEW_CORRECT_ANSWER_WITH_RETENTION"
        if (math_after["correct"] >= math_before["correct"] and
                math_before["ce"] - math_after["ce"] >= .025 and
                math_after["distinct_predictions"] >= math_before["distinct_predictions"]):
            return "ELIGIBLE", "NUMERIC_CE_ONLY_INCUBATION_WITH_RETENTION"
        return "REJECT", "NO_NUMERIC_DEVELOPMENT_PROGRESS"
    if worst <= -2 * OLD_GRADE_ITEM + 1e-9:
        return "REJECT", "PARENT_GRADE_REGRESSION"
    # Original consolidation confirmation: +1 of 528 correct net, and no
    # drop of two of 24 on any individual grade. This is *not* +1pp.
    if net < OLD_ITEM - 1e-9:
        return "REJECT", "CONSOLIDATION_FULL_PROBE_NO_GAIN"
    return "ELIGIBLE", "CONSOLIDATION_FULL_PROBE_GAIN"


def _construct_grade_weighted_teacher(source, out, state, device):
    """Each personal-best grade gives one vote to the next pass's frozen soup.

    Include newly proven numerical grade champions without letting their
    optimizer moments into the student. A streaming CPU average avoids loading
    22 distinct FP32 source models on MPS simultaneously.
    """
    assignments={**state["grade_champions"], **state["numeric_champions"]}
    if not set(state["grade_champions"]) == {f"G{i:02d}" for i in range(1,23)}:
        raise ValueError("SPIRAL_GRADE_CHAMPIONS_INCOMPLETE")
    weights={}
    provenance={}
    for grade,record in sorted(assignments.items()):
        location=record["location"]
        if location not in ("source","research"):
            raise ValueError("SPIRAL_SOUP_UNKNOWN_CHECKPOINT_LOCATION")
        key=(location,record["checkpoint"],record["checkpoint_sha256"])
        weights[key]=weights.get(key,0)+1
        provenance[grade]={"location":location,
                           "checkpoint":record["checkpoint"],
                           "sha256":record["checkpoint_sha256"],
                           "score":record["score"]}
    skeleton,original_optimizer,graph,_=pilot._load(source,"cpu")
    del original_optimizer
    accumulator={}
    exact={}
    total=0
    for (location,name,sha),votes in sorted(weights.items()):
        path=(source["source_dir"] if location=="source" else out)/name
        if engine._sha(path)!=sha:
            raise ValueError("SPIRAL_SOUP_INGREDIENT_CHANGED")
        model,optimizer,payload=engine.load_checkpoint(path)
        if model.config != skeleton.config or digest(payload["graph"])!=digest(graph):
            raise ValueError("SPIRAL_SOUP_MODEL_OR_GRAPH_ABI_DRIFT")
        for key,tensor in model.state_dict().items():
            on_cpu=tensor.detach().cpu()
            if torch.is_floating_point(on_cpu):
                if key not in accumulator:
                    accumulator[key]=on_cpu.float()*votes
                else:
                    accumulator[key].add_(on_cpu.float(),alpha=votes)
            elif key in exact:
                if not torch.equal(exact[key],on_cpu):
                    raise ValueError("SPIRAL_SOUP_NONFLOAT_BUFFER_DIFFERS")
            else:
                exact[key]=on_cpu.clone()
        total+=votes
        del model,optimizer,payload
    new_weights={key:(value/total).to(skeleton.state_dict()[key].dtype)
                 for key,value in accumulator.items()}
    new_weights.update(exact)
    skeleton.load_state_dict(new_weights,strict=True)
    skeleton.to(device)
    skeleton.eval()
    for param in skeleton.parameters():param.requires_grad_(False)
    manifest={"epoch":state["soup_epoch"],
              "votes":total,"grade_assignments":provenance,
              "unique_ingredient_checkpoints":len(weights),
              "teacher_digest":state_hash(skeleton)}
    return skeleton,manifest


def _build_grade_weighted_teacher(source, out, state, device):
    # Model construction/weight loading must not perturb the current
    # student's random/dropout stream. School50's original soup path already
    # preserved this boundary; preserve it for the evolving 30-grade soup.
    rng=torch.get_rng_state()
    try:
        return _construct_grade_weighted_teacher(source,out,state,device)
    finally:
        torch.set_rng_state(rng)


def _consolidation_teacher(source, out, state, device):
    """Freeze and hash an independent teacher for each expanded prefix epoch.

    A restart halfway through a pass reloads the EXACT stored frozen teacher
    even if a new personal-best checkpoint arose earlier in that pass. Only
    after a pass boundary may archived grades change the teacher mixture.
    """
    saved=state.get("soup_snapshot")
    if saved is not None and saved["epoch"] == state["soup_epoch"]:
        path=out/saved["file"]
        if engine._sha(path)!=saved["sha256"]:
            raise ValueError("SPIRAL_FROZEN_SOUP_CHECKPOINT_CHANGED")
        payload=torch.load(path,map_location="cpu",weights_only=True)
        if (payload["manifest"]!=saved["manifest"] or
                payload["graph_sha256"]!=state["graph_sha256"]):
            raise ValueError("SPIRAL_FROZEN_SOUP_MANIFEST_INVALID")
        model,optimizer,_,_=pilot._load(source,device)
        del optimizer
        model.load_state_dict(payload["weights"],strict=True)
        model.eval()
        for param in model.parameters():param.requires_grad_(False)
        if state_hash(model)!=saved["manifest"]["teacher_digest"]:
            raise ValueError("SPIRAL_FROZEN_SOUP_MODEL_READBACK_DRIFT")
        return model,saved["manifest"]
    if state["mastery"]["position"]!=0:
        raise ValueError("MASTERY_MIDPREFIX_REQUIRES_FROZEN_SOUP_SNAPSHOT")
    model,manifest=_build_grade_weighted_teacher(source,out,state,device)
    name=f"soup-stage-{state['soup_epoch']:04d}.pt"
    target=out/name
    if target.exists():
        raise ValueError("SPIRAL_SOUP_SNAPSHOT_ALREADY_EXISTS")
    temp=out/f".{name}.{uuid.uuid4().hex}.tmp"
    torch.save({"weights":{k:v.detach().cpu() for k,v in model.state_dict().items()},
                "manifest":manifest,"graph_sha256":state["graph_sha256"]},temp)
    os.replace(temp,target)
    saved={"epoch":state["soup_epoch"],"file":name,
           "sha256":engine._sha(target),"manifest":manifest}
    state["soup_snapshot"]=saved
    state["soup_history"].append(saved)
    engine._atomic_json(out/"state.json",state)
    return model,manifest


def _typed_loss(student, parent, soup, rows, graph, numbers, policy, device):
    """Supervised CE plus historically correct-only soup and parent KL."""
    kinds={name:[r for r in rows if r.get("answer_kind","evidence")==name]
           for name in ("evidence","numeric")}
    supervised=torch.zeros((),device=device)
    memory=torch.zeros((),device=device)
    consensus=torch.zeros((),device=device)
    trusted_rows=0
    for kind,items in kinds.items():
        if not items:continue
        ids,lengths=_input(items,graph,device)
        logits=contract.readout(student,ids,lengths,answer_kind=kind,number_ids=numbers)
        labels=_gold(items,kind,device)
        weight=len(items)/len(rows)
        supervised=supervised+weight*F.cross_entropy(logits,labels)
        with torch.no_grad():
            parent.eval();soup.eval()
            reference=contract.readout(parent,ids,lengths,answer_kind=kind,number_ids=numbers)
            senior=contract.readout(soup,ids,lengths,answer_kind=kind,number_ids=numbers)
            trusted=senior.argmax(-1)==labels
        memory_positions=[i for i,row in enumerate(items)
                          if row.get("course_meta",{}).get("retention")]
        if memory_positions:
            memory=memory+weight*F.kl_div(
                F.log_softmax(logits[memory_positions]/1.5,dim=-1),
                F.softmax(reference[memory_positions]/1.5,dim=-1),
                reduction="batchmean")*2.25
        if bool(trusted.any()):
            consensus=consensus+weight*F.kl_div(
                F.log_softmax(logits[trusted]/1.5,dim=-1),
                F.softmax(senior[trusted]/1.5,dim=-1),reduction="batchmean")*2.25
            trusted_rows+=int(trusted.sum().item())
    objective=supervised+policy["distill"]*memory+engine.CONSOLIDATION_WEIGHT*consensus
    return objective, {"supervised":float(supervised.detach().cpu()),
                       "parent_kl":float(memory.detach().cpu()),
                       "soup_kl":float(consensus.detach().cpu()),
                       "trusted_soup_rows":trusted_rows}


def train_step(student, optimizer, parent, soup, rows, graph, numbers, policy, device):
    numeric=[r for r in rows if r.get("answer_kind")=="numeric"]
    evidence=[r for r in rows if r.get("answer_kind")!="numeric"
              and r["input"].get("task") != bridge.VERSION]
    combined=[r for r in rows if r["input"].get("task")==bridge.VERSION]
    if numeric:mathcourse.validate_rows(numeric,graph)
    if evidence:lessons.valid_rows(evidence,graph)
    if combined:bridge.validate_rows(combined,graph,partition="train")
    optimizer.zero_grad(set_to_none=True)
    student.train()
    total,metrics=_typed_loss(student,parent,soup,rows,graph,numbers,policy,device)
    if not bool(torch.isfinite(total)):
        raise ValueError("SPIRAL_NONFINITE_TRAINING_LOSS")
    total.backward()
    torch.nn.utils.clip_grad_norm_(student.parameters(),1.0)
    optimizer.step()
    metrics["total_loss"]=float(total.detach().cpu())
    return metrics


def _numerical_retention(parent, candidate, *, recovery=False):
    if set(parent)!=set(candidate):
        raise ValueError("SPIRAL_NUMERIC_GRADE_SET_MISMATCH")
    if not parent:
        return True
    # During M01..M08 introduction use the tighter one-item local budget.
    # During G01..G22 recovery allow slightly more temporary interference;
    # the complete-pass numerical examination still controls persistence.
    local_budget=2 if recovery else 1
    total_budget=3 if recovery else 1
    if any(candidate[k]["correct"] < parent[k]["correct"]-local_budget
           for k in parent):
        return False
    return sum(v["correct"] for v in candidate.values()) >= sum(
        v["correct"] for v in parent.values())-total_budget


def _secondary_safety(before, after, *, numeric_phase=False):
    """Independent 22-grade sentinel uses the *current phase's* safety budget.

    This prevents a second, hidden pass-level gate from vetoing the numerical
    bending phase before G01..G22 have had a chance to restore old learning.
    """
    if set(before) != set(after) or len(before) != 22:
        raise ValueError("SPIRAL_SECONDARY_EXAM_INCOMPLETE")
    mean_budget = .05 if numeric_phase else .01
    grade_budget = 3 if numeric_phase else 2
    if sum(after.values()) < sum(before.values()) - mean_budget * 22 - 1e-9:
        return False
    return all(after[k] > before[k] - grade_budget * OLD_GRADE_ITEM + 1e-9
               for k in before)


def _teacher_grade_key(grade):
    """Preserve G23-G33 for Ithkuil, including teacher-policy statistics."""
    if grade in mathcourse.MAP:
        return 1000+int(grade[1:])
    if grade in CYCLE and grade.startswith("G"):
        return int(grade[1:])
    raise ValueError("SPIRAL_UNKNOWN_GRADE_TEACHER_KEY")


def _instruction_stats(teacher, grade):
    methods = teacher.setdefault("numeric_instruction_methods", {}).setdefault(
        grade, {key: {"trials": 0, "reward_sum": 0.0, "reward_ema": 0.0}
                for key in INSTRUCTIONAL_METHODS})
    if set(methods) != set(INSTRUCTIONAL_METHODS):
        raise ValueError("SPIRAL_TEACHER_INSTRUCTION_METHOD_ABI_CHANGED")
    return methods


def _choose_instruction(teacher, grade, rng, used=()):
    """Evidence-driven *lesson* choices alongside original parameter mutations."""
    methods = _instruction_stats(teacher, grade)
    candidates = [key for key in INSTRUCTIONAL_METHODS if key not in used]
    if not candidates:
        candidates = list(INSTRUCTIONAL_METHODS)
    total = sum(stats["trials"] for stats in methods.values()) + 1

    def utility(key):
        stats = methods[key]
        if not stats["trials"]:
            return 10.0 + rng.random()
        return (stats["reward_sum"] / stats["trials"] +
                .6 * math.sqrt(math.log(total + 2)/(1 + stats["trials"])))

    return max(candidates, key=utility)


def _observe_instruction(teacher, grade, mode, reward):
    if not math.isfinite(reward):
        raise ValueError("SPIRAL_NONFINITE_INSTRUCTION_REWARD")
    stats = _instruction_stats(teacher, grade)[mode]
    stats["trials"] += 1
    stats["reward_sum"] += reward
    stats["reward_ema"] = .7 * stats["reward_ema"] + .3 * reward
    teacher["numeric_instruction_events"] = teacher.get("numeric_instruction_events", 0) + 1


def pass_disposition(old_scores, champion_scores, numeric_scores,
                     champion_numeric_scores, *, regression_threshold=.01):
    """Full-cycle acceptance is *not* the candidate's +1-of-528 threshold.

    Preserve the original champion-anchored 1pp mean rollback. Also veto a
    two-item collapse on one historical grade or one already taught math grade.
    A smaller wobble remains the live accepted pass; strictly better old-22
    mean alone creates an old-school champion. Numerical gain cannot hide
    serious 22-grade regression by averaging two unrelated task families.
    """
    if (set(old_scores) != set(champion_scores) or len(old_scores) != 22 or
            set(numeric_scores) != set(champion_numeric_scores)):
        raise ValueError("SPIRAL_PASS_EXAM_PROFILE_INCOMPLETE")
    old_mean = sum(old_scores.values()) / 22
    prior_mean = sum(champion_scores.values()) / 22
    decline = old_mean - prior_mean
    if decline <= -regression_threshold + 1e-9:
        return "ROLLBACK", "CHAMPION_OLD_MEAN_REGRESSION"
    if any(old_scores[g] <= champion_scores[g] - 2 * OLD_GRADE_ITEM + 1e-9
           for g in old_scores):
        return "ROLLBACK", "CHAMPION_OLD_GRADE_REGRESSION"
    for grade, current in numeric_scores.items():
        previous = champion_numeric_scores[grade]
        if current["correct"] <= previous["correct"] - 2:
            return "ROLLBACK", "CHAMPION_NUMERIC_GRADE_REGRESSION"
    if old_mean > prior_mean + 1e-9:
        return "NEW_CHAMPION", "STRICT_NEW_HOLISTIC_CHAMPION"
    return "ACCEPTED", "BOUND_WITHIN_CHAMPION_TOLERANCE"


def _initialize(out, source, graph, model, config):
    if out.exists():
        raise ValueError("SPIRAL_RUN_DESTINATION_EXISTS")
    original=engine._read(source["state_path"])
    if not original.get("grade_champions") or len(original["grade_champions"])!=22:
        raise ValueError("SPIRAL_ORIGINAL_GRADE_CHAMPIONS_NOT_PRESENT")
    teacher=copy.deepcopy(original["teacher"])
    teacher_import={"source":"ORIGINAL_SCHOOL50_P43",
                    "events":teacher["events"],"mutations":teacher["mutations"]}
    if LEGACY_V4_TEACHER.is_file():
        # Negative teaching outcomes in failed v4 passes remain useful.
        # Import *teacher policy evidence only*: never v4's rolled-back
        # student weights, optimizer moments or incidental candidate state.
        imported=engine._read(LEGACY_V4_TEACHER)
        if (imported.get("version")=="bilqis.school50.numeric-spiral/v4" and
                imported.get("source_checkpoint_sha256")==pilot.CHAMPION_SHA256 and
                imported.get("source_state_sha256")==source["state_sha256"] and
                imported.get("teacher",{}).get("events",0)>=teacher["events"]):
            teacher=copy.deepcopy(imported["teacher"])
            teacher_import={"source":"V4_REJECTED_CANDIDATE_TEACHER_ONLY",
                            "state_sha256":engine._sha(LEGACY_V4_TEACHER),
                            "events":teacher["events"],
                            "mutations":teacher["mutations"]}
    if PREVIOUS_V5_TEACHER.is_file():
        # A stalled v5/v1 run still taught the independent teacher. V5/v2
        # starts a new, explicit training recipe; import only compatible
        # teacher evidence, never the stopped learner or optimizer.
        prior=engine._read(PREVIOUS_V5_TEACHER)
        if (prior.get("version")=="bilqis.school50.mastery-v5/v1" and
                prior.get("source_checkpoint_sha256")==pilot.CHAMPION_SHA256 and
                prior.get("source_state_sha256")==source["state_sha256"] and
                prior.get("mastery",{}).get("phase")=="STOPPED" and
                prior.get("teacher",{}).get("events",0)>teacher["events"]):
            teacher=copy.deepcopy(prior["teacher"])
            teacher_import={"source":"V5_V1_TEACHER_ONLY_AFTER_PREREQUISITE_STALL",
                            "state_sha256":engine._sha(PREVIOUS_V5_TEACHER),
                            "events":teacher["events"],
                            "mutations":teacher["mutations"]}
    completed_v2=_completed_v2_state()
    if completed_v2 is not None:
        # Import only stopped v2 evidence; no moving writer target.
        prior=completed_v2
        if (prior.get("version")=="bilqis.school50.mastery-v5/v2" and
                prior.get("source_checkpoint_sha256")==pilot.CHAMPION_SHA256 and
                prior.get("source_state_sha256")==source["state_sha256"] and
                prior.get("teacher",{}).get("events",0)>teacher["events"]):
            teacher=copy.deepcopy(prior["teacher"])
            teacher_import={"source":"V5_V2_COMPLETED_TEACHER_ONLY",
                            "state_sha256":engine._sha(PREVIOUS_V5_V2_TEACHER),
                            "events":teacher["events"],
                            "mutations":teacher["mutations"]}
    state={"version":VERSION, "config":config, "source_checkpoint_sha256":pilot.CHAMPION_SHA256,
           "source_state_sha256":source["state_sha256"],
           "source_optimizer_step":pilot.CHAMPION_STEP,
           "graph_sha256":digest(graph), "source_model_sha256":state_hash(model),
           "checkpoint":None, "checkpoint_sha256":None,
           "optimizer_step":pilot.CHAMPION_STEP,
           "cycle_index":0, "completed_passes":0,"grade_visits":0,
           "attempted_updates":0,"accepted_updates":0,
           "teacher":teacher,"teacher_import":teacher_import,
           "grade_ledger":[],"candidate_ledger":[],"pass_reports":[],
           "numeric_history":{},"last_run_status":"READY", "last_session":None,
           "grade_champions":{grade:{**entry,"location":"source"} for grade,entry
                              in original["grade_champions"].items()},
           "numeric_champions":{},
           "accepted_pass":None,"champion_pass":None,
           "expanded_champion":None,"research_champion":None,
           "soup_snapshot":None,"soup_history":[],
           "selected_candidate_updates":0,"rolled_back_updates":0,
           "stalled_passes":0,"best_numeric_pass_correct":None,"soup_epoch":0,
           "mastery":mastery.initialize(),"mastery_events":[],
           "primitive":{"stage_index":0,"qualified":{},"events":[]}}
    out.mkdir(parents=True,exist_ok=False)
    if completed_v2 is not None:
        old=completed_v2
        if (old.get("version")=="bilqis.school50.mastery-v5/v2" and
                old.get("source_checkpoint_sha256")==pilot.CHAMPION_SHA256 and
                old.get("source_state_sha256")==source["state_sha256"] and
                old.get("checkpoint") and old.get("checkpoint_sha256") and
                old.get("optimizer_step",0)>pilot.CHAMPION_STEP):
            parent=PREVIOUS_V5_V2_TEACHER.parent
            prior_checkpoint=parent/old["checkpoint"]
            if (Path(old["checkpoint"]).name!=old["checkpoint"] or
                    not prior_checkpoint.is_file() or
                    engine._sha(prior_checkpoint)!=old["checkpoint_sha256"]):
                raise ValueError("PRIMITIVE_V2_BOOTSTRAP_CHECKPOINT_DRIFT")
            original,prior_optimizer,payload=engine.load_checkpoint(prior_checkpoint)
            if (digest(payload["graph"])!=digest(graph) or
                    optimizer_receipt(prior_optimizer)["steps"]!=[old["optimizer_step"]]):
                raise ValueError("PRIMITIVE_V2_BOOTSTRAP_OPTIMIZER_OR_GRAPH_DRIFT")
            filename="incubation-v2-"+old["checkpoint"]
            shutil.copyfile(prior_checkpoint,out/filename)
            if engine._sha(out/filename)!=old["checkpoint_sha256"]:
                raise ValueError("PRIMITIVE_V2_BOOTSTRAP_COPY_DRIFT")
            state["checkpoint"]=filename
            state["checkpoint_sha256"]=old["checkpoint_sha256"]
            state["optimizer_step"]=old["optimizer_step"]
            state["bootstrap"]={"source":"V2_ACCEPTED_STUDENT_ADAMW_INCUBATION",
                "parent_state_sha256":engine._sha(PREVIOUS_V5_V2_TEACHER),
                "checkpoint_sha256":old["checkpoint_sha256"],
                "optimizer_step":old["optimizer_step"],
                "p43_historical_comparator_sha256":pilot.CHAMPION_SHA256}
    engine._atomic_json(out/"state.json",state)
    return state


def _validate_state(out, source, config):
    state=engine._read(out/"state.json")
    if (state["version"]!=VERSION or state["config"]!=config or
            state["source_checkpoint_sha256"]!=pilot.CHAMPION_SHA256 or
            state["source_state_sha256"]!=source["state_sha256"]):
        raise ValueError("SPIRAL_RESUME_RECIPE_OR_SOURCE_CHANGED")
    if not 0<=state["cycle_index"]<len(CYCLE):
        raise ValueError("SPIRAL_CYCLE_STATE_INVALID")
    if state["checkpoint"] is not None:
        name=state["checkpoint"]
        if (Path(name).name!=name or not (out/name).is_file() or
                engine._sha(out/name)!=state["checkpoint_sha256"]):
            raise ValueError("SPIRAL_LIVE_CHECKPOINT_INVALID")
    soup=state.get("soup_snapshot")
    if soup is not None and (Path(soup["file"]).name!=soup["file"] or
                             engine._sha(out/soup["file"])!=soup["sha256"]):
        raise ValueError("SPIRAL_LIVE_SOUP_SNAPSHOT_INVALID")
    return state


def _load_student(out, source, state, device):
    if state["checkpoint"] is None:
        model,optimizer,graph,numbers=pilot._load(source,device)
    else:
        model,optimizer,payload=engine.load_checkpoint(out/state["checkpoint"])
        engine._device(model,optimizer,device)
        graph=payload["graph"]
        numbers=contract.numeric_token_ids(graph)
        if state_hash(model)!=payload["state_sha256"]:
            raise ValueError("SPIRAL_CHECKPOINT_MODEL_READBACK_DRIFT")
    if (digest(graph)!=state["graph_sha256"] or
            optimizer_receipt(optimizer)["steps"] != [state["optimizer_step"]]):
        raise ValueError("SPIRAL_MODEL_OPTIMIZER_OR_GRAPH_DRIFT")
    return model,optimizer,graph,numbers


def _numeric_scores(model, graph, numbers, device, seed):
    return {grade:evaluate_numeric(model,_numeric_panel(
                grade,graph,split="development",seed=seed^0x57119),
                graph,numbers,device)
            for grade in mathcourse.MAP}


def _initialize_pass_champions(state, source_scores, original_model,
                               graph, numbers, device):
    if state["accepted_pass"] is not None:
        return
    numeric=_numeric_scores(original_model,graph,numbers,device,
                            state["config"]["seed"])
    initial={"pass":0,"checkpoint":None,"checkpoint_sha256":pilot.CHAMPION_SHA256,
             "optimizer_step":pilot.CHAMPION_STEP,
             "scores":dict(source_scores),"numeric_scores":numeric,
             "source":"ORIGINAL_FP32_WHOLE_SCHOOL_CHAMPION"}
    state["accepted_pass"]=copy.deepcopy(initial)
    state["champion_pass"]=copy.deepcopy(initial)
    state["source_numeric_scores"]=copy.deepcopy(numeric)
    state["best_numeric_pass_correct"]=sum(
        result["correct"] for result in numeric.values())


def _record_pass_progress(state, report):
    """Count genuine improvement, never an unchanged first pass as progress."""
    baseline=state["best_numeric_pass_correct"]
    if baseline is None:
        baseline=sum(r["correct"] for r in state["source_numeric_scores"].values())
    progressed=(report["decision"]=="NEW_CHAMPION" or
                (report["decision"]!="ROLLBACK" and
                 report["numeric_correct"]>baseline))
    state["stalled_passes"]=0 if progressed else state["stalled_passes"]+1
    if report["decision"]!="ROLLBACK":
        state["best_numeric_pass_correct"]=max(baseline,report["numeric_correct"])
    report["stalled_passes"]=state["stalled_passes"]
    return progressed


def _archive_grade_champion(state, grade, model, filename, sha, graph,
                            library, numbers, device):
    if grade in mathcourse.MAP:
        results=evaluate_numeric(model,_numeric_panel(
            grade,graph,split="development",seed=state["config"]["seed"]^0x57119),
            graph,numbers,device)
        score=results["correct"]
        ledger=state["numeric_champions"]
    else:
        score=engine._grade_champion_score(model,graph,library,int(grade[1:]),
                                            device=device)
        ledger=state["grade_champions"]
    old=ledger.get(grade)
    if old is None or score>old["score"]:
        ledger[grade]={"score":score,"checkpoint":filename,
                       "checkpoint_sha256":sha,"location":"research",
                       "optimizer_step":state["optimizer_step"],
                       "source_pass":state["completed_passes"]+1}
        return {"grade":grade,"new_champion":True,"score":score,
                "former_score":None if old is None else old["score"]}
    return {"grade":grade,"new_champion":False,"score":score,
            "former_score":old["score"]}


def _previous(grading_index, completed_passes=0):
    historical=tuple(f"G{i:02d}" for i in range(1,23))
    new=(tuple(mathcourse.MAP) if completed_passes else
         tuple(x for x in CYCLE[:grading_index] if x in mathcourse.MAP))
    return historical+new*3


def _batch_for(grade, library, graph, rng, policy, previous, instruction=None,
               primitive_stage=None):
    if grade in mathcourse.MAP:
        mode = instruction or "standard"
        if grade=="M01" and primitive_stage is not None:
            rows,tally=primitives.compile_batch(primitive_stage,library,graph,rng,
                                                 previous=previous,mode=mode)
        elif grade=="M01":
            # The final broad arithmetic worksheets must not reintroduce a
            # primitive development source under a new surface grammar.
            for _ in range(100):
                rows,tally=mathcourse.compile_batch(grade,library,graph,rng,
                                                    mode=mode,previous=previous)
                if all(primitives.admissible_rehearsal(row) for row in rows):
                    break
            else:
                raise ValueError("PRIMITIVE_FINAL_ADDITION_PARTITION_EXHAUSTED")
        else:
            rows,tally=mathcourse.compile_batch(grade,library,graph,rng,mode=mode,previous=previous)
        for row in rows:
            if row["course_meta"]["tranche"]=="random_old":
                row["course_meta"]["retention"]=True
        return rows,tally
    n=int(grade[1:])
    rows,counts=lessons.compose_batch(library,n,policy,graph,rng,
                                      admissible=primitives.admissible_rehearsal)
    start=counts["current"]
    stop=start+counts["old"]
    result=[dict(row,answer_kind="evidence",
                 course_meta={"retention":start<=i<stop,
                              "tranche":"random_old" if start<=i<stop else "novelty"})
            for i,row in enumerate(rows)]
    prior_math=tuple(dict.fromkeys(x for x in previous if x in mathcourse.MAP))
    if prior_math:
        choice=rng.choice(prior_math)
        family = (bridge.FAMILIES[(n-1) % 2] if n <= 10 else
                  "membership" if n % 2 else "subset")
        numeric=mathcourse.cross_domain_triplet(choice,graph,rng,family=family,
                                                tranche="random_old")
        for row in numeric:
            row["course_meta"].update({"tranche":"random_old",
                                       "retention":True,"source_grade":choice})
        result.extend(numeric)
        counts={**counts,"cross_domain_rehearsal":3}
    return result,counts


def _visit(out,source,state,old_champion,soup,library,device):
    grade=CYCLE[state["cycle_index"]]
    primitive_stage=(primitives.STAGES[state["primitive"]["stage_index"]]
          if grade=="M01" and state["primitive"]["stage_index"]<len(primitives.STAGES)-1
          else None)
    grade_key=_teacher_grade_key(grade)
    parent,_,graph,numbers=_load_student(out,source,state,device)
    old_before=engine._probe_all_grades(parent,graph,library,device=device)
    second_before={f"G{g:02d}":engine._scores(parent,library,graph,g,
        770013+g*7919,count=24,device=device) for g in engine.REPORT_GRADES}
    panel=(_primitive_panel(primitive_stage,graph,seed=state["config"]["seed"]^0x57119)
           if primitive_stage else
           _numeric_panel(grade,graph,split="development",
                         seed=state["config"]["seed"]^0x57119)
           if grade in mathcourse.MAP else None)
    evaluate_current=(evaluate_primitives if primitive_stage else evaluate_numeric)
    math_before=(evaluate_current(parent,panel,graph,numbers,device)
                 if panel is not None else None)
    primitive_confirm_panel=None;primitive_confirm_before=None
    if primitive_stage:
        used={r["course_meta"]["source_number"] for r in panel}
        primitive_confirm_panel=_primitive_panel(primitive_stage,graph,
            seed=state["config"]["seed"]^0x7F415,exclude=used)
        primitive_confirm_before=evaluate_primitives(parent,primitive_confirm_panel,
                                                       graph,numbers,device)
    target_bridge_grade=(grade if grade in mathcourse.MAP else
                         f"M{(int(grade[1:])-1)%8+1:02d}")
    bridge_panel=_bridge_for_stage(target_bridge_grade,primitive_stage,graph,
                                  seed=state["config"]["seed"]^0x21375)
    bridge_before=evaluate_bridge(parent,bridge_panel,graph,device)
    bridge_confirm_panel=None;bridge_confirm_before=None
    if primitive_stage:
        original_sources={r["course_meta"]["semantic_source_id"] for r in bridge_panel}
        bridge_confirm_panel=_bridge_for_stage("M01",primitive_stage,graph,
            seed=state["config"]["seed"]^0x64712,exclude=original_sources)
        bridge_confirm_before=evaluate_bridge(parent,bridge_confirm_panel,graph,device)
    visited_math={x for x in CYCLE[:state["cycle_index"]] if x in mathcourse.MAP}
    if state["completed_passes"]:
        visited_math=set(mathcourse.MAP)
    retention_panels={x:_numeric_panel(x,graph,split="development",
                                      seed=state["config"]["seed"]^0x57119)
                      for x in sorted(visited_math)}
    prior_numeric={x:evaluate_numeric(parent,p,graph,numbers,device)
                   for x,p in retention_panels.items()}
    used=set();attempts=[];winner=None;rank=None
    used_instructions=set()
    seed=state["config"]["seed"]+state["completed_passes"]*1000003
    seed+=state["grade_visits"]*71993+grade_key*9973
    with tempfile.TemporaryDirectory(prefix="bilqis-numeric-spiral-") as temporary:
        best_file=Path(temporary)/"best.pt"
        for attempt in range(1,state["config"]["attempts"]+1):
            rng=random.Random(seed+attempt*104729)
            key,policy=engine.pick(state["teacher"],grade_key,rng,exclude=used)
            used.add(key)
            method=(_choose_instruction(state["teacher"],grade,rng,used_instructions)
                    if grade in mathcourse.MAP else None)
            if method is not None:
                used_instructions.add(method)
            model,optimizer,other_graph,numbers=_load_student(out,source,state,device)
            if state_hash(model)!=state_hash(parent):
                raise ValueError("SPIRAL_CANDIDATE_NOT_SAME_PARENT")
            for group in optimizer.param_groups:group["lr"]=policy["lr"]
            anchor=copy.deepcopy(parent).eval()
            for p in anchor.parameters():p.requires_grad_(False)
            traces=[];exposures=[]
            for _ in range(state["config"]["block"]):
                rows,counts=_batch_for(grade,library,other_graph,rng,policy,
                                       _previous(state["cycle_index"],state["completed_passes"]),
                                       instruction=method,primitive_stage=primitive_stage)
                traces.append(train_step(model,optimizer,anchor,soup,rows,other_graph,
                                         numbers,policy,device))
                exposures.append(counts)
            candidate_step=optimizer_receipt(optimizer)["steps"]
            if candidate_step != [state["optimizer_step"]+state["config"]["block"]]:
                raise ValueError("SPIRAL_CANDIDATE_OPTIMIZER_STEP_DRIFT")
            old_after=engine._probe_all_grades(model,graph,library,device=device)
            second_after={f"G{g:02d}":engine._scores(model,library,graph,g,
                770013+g*7919,count=24,device=device) for g in engine.REPORT_GRADES}
            math_after=(evaluate_current(model,panel,graph,numbers,device)
                        if panel is not None else None)
            primitive_confirm_after=(evaluate_primitives(model,primitive_confirm_panel,
                graph,numbers,device) if primitive_confirm_panel is not None else None)
            bridge_after=evaluate_bridge(model,bridge_panel,graph,device)
            bridge_confirm_after=(evaluate_bridge(model,bridge_confirm_panel,graph,device)
                                  if bridge_confirm_panel is not None else None)
            after_numeric={x:evaluate_numeric(model,p,graph,numbers,device)
                           for x,p in retention_panels.items()}
            # Original legacy learner: local grade reward, independent whole-
            # school sentinel, then full-528 candidate consolidation. New
            # numerical subjects use their own typed local signal, keeping
            # the sentinel as an interference detector, not a binary-only
            # prerequisite for 101-class numerical acquisition.
            local_before=old_before.get(grade)
            local_after=old_after.get(grade)
            old_mean_delta=(sum(old_after.values())-sum(old_before.values()))/22
            if method is None:
                # Historical semantic phase is scored against the historical
                # logic champion. Numeric and bridge metrics remain observed
                # but are intentionally NOT a separate local promotion gate.
                reward=2*(local_after-local_before)+.6*old_mean_delta
                proposal=engine._candidate_gate_decision(reward)
                sentinel_before=sentinel_after=None
                if proposal["decision"]=="MEASURE":
                    sentinel_before=engine._sentinel_metrics(parent,library,graph,
                                                              device=device)
                    sentinel_after=engine._sentinel_metrics(model,library,graph,
                                                             device=device)
                    proposal=engine._candidate_gate_decision(
                        reward,sentinel_before,sentinel_after)
                if proposal["decision"]!="PROMOTE":
                    decision,reason="REJECT",proposal["reason"]
                else:
                    decision,reason=retention_gate(old_before,old_after,old_champion,
                                                   grade=grade)
            else:
                reward=(2*(math_after["accuracy"]-math_before["accuracy"])+
                        .15*(math_before["ce"]-math_after["ce"])+
                        .2*(bridge_after["accuracy"]-bridge_before["accuracy"])+
                        .6*old_mean_delta)
                sentinel_before=sentinel_after=None
                decision,reason=_numeric_candidate_decision(old_before,old_after,
                    old_champion,grade=grade,math_before=math_before,
                    math_after=math_after,bridge_before=bridge_before,
                    bridge_after=bridge_after,
                    bridge_confirm_before=bridge_confirm_before,
                    bridge_confirm_after=bridge_confirm_after,
                    primitive_stage=primitive_stage)
            if grade in mathcourse.MAP and decision=="ELIGIBLE" and not _numerical_retention(
                    prior_numeric,after_numeric,recovery=False):
                decision,reason="REJECT","PRIOR_NUMERIC_GRADE_RETENTION_VETO"
            if decision=="ELIGIBLE" and not _secondary_safety(
                    second_before,second_after,
                    numeric_phase=grade in mathcourse.MAP):
                decision,reason="REJECT","SECONDARY_FULL_SCHOOL_RETENTION_VETO"
            if (grade in mathcourse.MAP and decision=="ELIGIBLE" and
                    bridge_after["correct"] <= bridge_before["correct"]-2):
                decision,reason="REJECT","CROSS_DOMAIN_BRIDGE_RETENTION_VETO"
            gate={"decision":"PROMOTE" if decision=="ELIGIBLE" else "REJECT",
                  "reason":reason}
            teacher_credit=engine._candidate_teacher_credit(reward,gate)
            if decision=="REJECT" and ("REGRESSION" in reason or "VETO" in reason):
                teacher_credit=min(teacher_credit,-engine.CANDIDATE_CLEAR_REWARD)
            engine.observe(state["teacher"],grade_key,key,teacher_credit)
            if method is not None:
                _observe_instruction(state["teacher"],grade,method,teacher_credit)
            record={"grade":grade,"pass":state["completed_passes"]+1,
                    "attempt":attempt,"policy_id":key,"policy":policy,
                    "instruction_method":method,
                    "parent_step":state["optimizer_step"],"candidate_step":candidate_step[0],
                    "candidate_model_sha256":state_hash(model),
                    "old_before":old_before,"old_after":old_after,
                    "secondary_old_before":second_before,
                    "secondary_old_after":second_after,
                    "numeric_before":math_before,"numeric_after":math_after,
                    "primitive_confirm_before":primitive_confirm_before,
                    "primitive_confirm_after":primitive_confirm_after,
                    "bridge_grade":target_bridge_grade,
                    "bridge_before":bridge_before,"bridge_after":bridge_after,
                    "bridge_confirm_before":bridge_confirm_before,
                    "bridge_confirm_after":bridge_confirm_after,
                    "primitive_stage":primitive_stage,
                    "prior_numeric_before":prior_numeric,
                    "prior_numeric_after":after_numeric,
                    "allocation":exposures[0],"loss_first":traces[0],
                    "loss_last":traces[-1],"decision":decision,
                    "reason":reason,"reward":reward,"teacher_credit":teacher_credit,
                    "sentinel_before":sentinel_before,"sentinel_after":sentinel_after,
                    "selection":"REJECTED"}
            attempts.append(record)
            if decision=="ELIGIBLE":
                score=((math_after["correct"]-math_before["correct"],
                        (bridge_confirm_after["correct"]-bridge_confirm_before["correct"]
                         if bridge_confirm_after is not None else 0),
                        bridge_after["correct"]-bridge_before["correct"],
                        old_mean_delta,
                        math_before["ce"]-math_after["ce"],
                        min(old_after[g]-old_champion[g] for g in old_after),-attempt)
                       if method is not None else
                       (old_mean_delta,
                        min(old_after[g]-old_before[g] for g in old_after),
                        local_after-local_before,teacher_credit,-attempt))
                if winner is None or score>rank:
                    engine.save_checkpoint(best_file,model,optimizer,graph,{
                        "epoch":VERSION,"grade":grade,"candidate_attempt":attempt,
                        "no_external_promotion":True})
                    winner=record
                    rank=score
        if winner is None:
            return grade,attempts,parent,None,graph,None
        chosen,optimizer,payload=engine.load_checkpoint(best_file)
        engine._device(chosen,optimizer,device)
        if state_hash(chosen)!=winner["candidate_model_sha256"]:
            raise ValueError("SPIRAL_BEST_CANDIDATE_READBACK_DRIFT")
        winner["selection"]="SELECTED"
        for item in attempts:
            if item is not winner and item["decision"]=="ELIGIBLE":
                item["selection"]="ELIGIBLE_SUPERSEDED"
        return grade,attempts,chosen,optimizer,graph,winner


def _finish_spiral_pass(out, source, state, library, graph, numbers, device):
    """School50-style pass acceptance, champion promotion, or full rollback.

    The teacher and per-grade best archive are independent of any pass-level
    student rollback. A champion need only be *strictly* better, not +1pp;
    the 1pp bound is the separate negative-regression rollback threshold.
    """
    model,_,_,_=_load_student(out,source,state,device)
    current_old=engine._probe_all_grades(model,graph,library,device=device)
    current_numeric=_numeric_scores(model,graph,numbers,device,state["config"]["seed"])
    current_bridge=(_bridge_scores(model,graph,device,state["config"]["seed"])
                    if "source_bridge_scores" in state else {})
    champion=state["champion_pass"]
    prior=state["accepted_pass"]
    decision,reason=pass_disposition(
        current_old,champion["scores"],current_numeric,
        champion["numeric_scores"],regression_threshold=PASS_REGRESSION_THRESHOLD)
    # A subsequent pass cannot erase an already admitted numeric competence
    # simply because the historic original champion had no arithmetic head.
    if decision!="ROLLBACK" and any(
            current_numeric[grade]["correct"] <= prior["numeric_scores"][grade]["correct"]-2
            for grade in mathcourse.MAP):
        decision,reason="ROLLBACK","PREVIOUS_ACCEPTED_NUMERIC_GRADE_REGRESSION"
    previous_bridge=prior.get("bridge_scores",{})
    if decision!="ROLLBACK" and previous_bridge and any(
            current_bridge[g]["correct"]<=previous_bridge[g]["correct"]-2
            for g in mathcourse.MAP):
        decision,reason="ROLLBACK","PREVIOUS_ACCEPTED_BRIDGE_GRADE_REGRESSION"
    old_mean=sum(current_old.values())/22
    champion_mean=sum(champion["scores"].values())/22
    numeric_total=sum(r["correct"] for r in current_numeric.values())
    source_numeric=sum(r["correct"] for r in state["source_numeric_scores"].values())
    bridge_total=sum(r["correct"] for r in current_bridge.values())
    source_bridge_total=sum(r["correct"] for r in state.get("source_bridge_scores",{}).values())
    report={"pass":state["completed_passes"],"decision":decision,
            "reason":reason,"attempted_checkpoint":state["checkpoint"],
            "attempted_optimizer_step":state["optimizer_step"],
            "old_22_scores":current_old,"numeric_development":current_numeric,
            "bridge_development":current_bridge,
            "old_22_mean":old_mean,"champion_old_22_mean_before":champion_mean,
            "old_22_delta_pp":100*(old_mean-champion_mean),
            "old_22_worst_delta_pp":100*min(
                current_old[grade]-champion["scores"][grade] for grade in current_old),
            "numeric_correct":numeric_total,"numeric_source_correct":source_numeric,
            "numeric_net_gain":numeric_total-source_numeric,
            "bridge_correct":bridge_total,"bridge_source_correct":source_bridge_total,
            "bridge_net_gain":bridge_total-source_bridge_total,
            "teacher_events_preserved":state["teacher"]["events"],
            "teacher_mutations_preserved":state["teacher"]["mutations"],
            "numeric_instruction_events_preserved":state["teacher"].get(
                "numeric_instruction_events",0)}
    if decision=="ROLLBACK":
        discarded=max(0,state["optimizer_step"]-champion["optimizer_step"])
        state["rolled_back_updates"]+=discarded
        state["checkpoint"]=champion["checkpoint"]
        state["checkpoint_sha256"]=(None if champion["checkpoint"] is None
                                    else champion["checkpoint_sha256"])
        state["optimizer_step"]=champion["optimizer_step"]
        state["accepted_updates"]=state["optimizer_step"]-pilot.CHAMPION_STEP
        state["accepted_pass"]=copy.deepcopy(champion)
        report["restored_champion_pass"]=champion["pass"]
        report["restored_optimizer_step"]=champion["optimizer_step"]
    else:
        current={"pass":state["completed_passes"],
                 "checkpoint":state["checkpoint"],
                 "checkpoint_sha256":(state["checkpoint_sha256"]
                                      if state["checkpoint"] is not None
                                      else pilot.CHAMPION_SHA256),
                 "optimizer_step":state["optimizer_step"],
                 "scores":current_old,"numeric_scores":current_numeric,
                 "bridge_scores":current_bridge,
                 "source":"CUMULATIVE_SPIRAL_RESEARCH"}
        state["accepted_pass"]=current
        if decision=="NEW_CHAMPION":
            state["champion_pass"]=copy.deepcopy(current)
            report["patience_reset"]=True
            report["patience_reset_reason"]="NEW_HOLISTIC_CHAMPION"
        else:
            report["patience_reset"]=False
        # A distinct *expanded* experimental benchmark never displaces the
        # original old-22 champion or the user's FP32 source. Both metrics
        # must be defensible rather than one hiding the other's losses.
        incumbent=state.get("expanded_champion")
        before=-1 if incumbent is None else incumbent["numeric_correct"]
        if (old_mean >= state["source_scores_mean"]-1e-9 and
                numeric_total>source_numeric and numeric_total>before and
                bridge_total>source_bridge_total):
            state["expanded_champion"]={"pass":state["completed_passes"],
                "numeric_correct":numeric_total,"old_22_mean":old_mean,
                "bridge_correct":bridge_total,
                "checkpoint":state["checkpoint"],
                "checkpoint_sha256":state["checkpoint_sha256"],
                "optimizer_step":state["optimizer_step"],
                "research_only":True}
            state["research_champion"]=copy.deepcopy(state["expanded_champion"])
    state["pass_reports"].append(report)
    return report


def run(*, source_dir=pilot.SOURCE, run_dir=RUN, minutes=90,
        block=32, attempts=3, seed=20261012, device="mps",
        max_grade_visits=None, max_attempted_updates=100000, max_passes=None,
        max_stalled_passes=3, max_frontier_failures=36,
        stop_requested=lambda:False):
    if (not 0<minutes<=1440 or max_attempted_updates<1 or
            (max_grade_visits is not None and max_grade_visits<1) or
            (max_passes is not None and max_passes<1)):
        raise ValueError("SPIRAL_INVALID_SESSION_LIMIT")
    config=configuration(block,attempts,seed,device,max_stalled_passes,
                         max_frontier_failures)
    source=pilot._ancestor(source_dir)
    out=Path(run_dir).expanduser().resolve(strict=False)
    if (out==source["source_dir"] or out in source["source_dir"].parents or
            source["source_dir"] in out.parents):
        raise ValueError("SPIRAL_SOURCE_AND_RESEARCH_RUN_OVERLAP")
    out.parent.mkdir(parents=True,exist_ok=True)
    lock=out.with_name(out.name+".writer.lock")
    fd=os.open(lock,os.O_CREAT|os.O_RDWR|getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as err:
            raise RuntimeError("SPIRAL_RESEARCH_RUN_ALREADY_HAS_WRITER") from err
        if not out.exists():
            initial,_,graph,_=pilot._load(source,device)
            _initialize(out,source,graph,initial,config)
        state=_validate_state(out,source,config)
        student,_,graph,numbers=_load_student(out,source,state,device)
        library=lessons.TeacherLibrary()
        ancestor,_,_,_=pilot._load(source,device)
        source_scores=engine._probe_all_grades(ancestor,graph,library,device=device)
        source_secondary={f"G{g:02d}":engine._scores(
            ancestor,library,graph,g,770013+g*7919,count=24,device=device)
            for g in engine.REPORT_GRADES}
        if "source_scores" not in state:
            state["source_scores"]=source_scores
            state["source_secondary"]=source_secondary
            state["source_scores_mean"]=sum(source_scores.values())/22
        if state["source_scores"]!=source_scores or state["source_secondary"]!=source_secondary:
            raise ValueError("SPIRAL_ORIGINAL_EXAM_PROFILE_DRIFT")
        _initialize_pass_champions(state,source_scores,ancestor,graph,numbers,device)
        if "source_bridge_scores" not in state:
            state["source_bridge_scores"]=_bridge_scores(
                ancestor,graph,device,config["seed"])
            state["champion_pass"]["bridge_scores"]=copy.deepcopy(
                state["source_bridge_scores"])
            state["accepted_pass"]["bridge_scores"]=copy.deepcopy(
                state["source_bridge_scores"])
        soup,manifest=_consolidation_teacher(source,out,state,device)
        engine._atomic_json(out/"state.json",state)
        started=time.monotonic()
        visits=0
        attempted=0
        accepted=0
        target_pass=None

        def finish(reason):
            seconds=time.monotonic()-started
            state["last_run_status"]=reason
            state["last_session"]={"stop_reason":reason,
                "elapsed_seconds":round(seconds,2),"grade_visits":visits,
                "attempted_updates":attempted,"accepted_updates":accepted,
                "attempted_updates_per_second":round(attempted/max(seconds,1e-6),3)}
            if (pilot._sha(source["checkpoint"])!=pilot.CHAMPION_SHA256 or
                    pilot._sha(source["state_path"])!=source["state_sha256"]):
                raise ValueError("SPIRAL_ORIGINAL_CHECKPOINT_OR_HISTORY_MUTATED")
            engine._atomic_json(out/"state.json",state)
            return {"status":reason,"run_dir":str(out),
                    "next_grade":mastery.next_grade(state["mastery"]),
                    "optimizer_step":state["optimizer_step"],
                    "session":state["last_session"],
                    "last_grade":state["grade_ledger"][-1] if state["grade_ledger"] else None}
        while True:
            if stop_requested():return finish("GRACEFUL_OPERATOR_STOP")
            phase=state["mastery"]["phase"]
            if phase in ("NUMERIC_QUALIFICATION","LOGIC_QUALIFICATION"):
                current,_,_,_=_load_student(out,source,state,device)
                numbers=contract.numeric_token_ids(graph)
                if phase=="NUMERIC_QUALIFICATION":
                    scores=_numeric_scores(current,graph,numbers,device,config["seed"])
                    old_scores=engine._probe_all_grades(current,graph,library,device=device)
                    numerically_qualified=all(scores[g]["correct"] >=
                          state["source_numeric_scores"][g]["correct"]+1
                          for g in mastery.NUMERIC)
                    historically_safe=(sum(old_scores.values())/22 >=
                         state["source_scores_mean"]-.05 and
                         all(old_scores[g]>=state["source_scores"][g]-3/24-1e-9
                             for g in mastery.LOGIC))
                    okay=numerically_qualified and historically_safe
                    evidence={"numerical_scores":scores,"historical_scores":old_scores,
                              "numeric_pass":numerically_qualified,
                              "historical_interference_safe":historically_safe}
                else:
                    scores=engine._probe_all_grades(current,graph,library,device=device)
                    original=state["source_scores"]
                    okay=(sum(scores.values())/22 >= sum(original.values())/22-.01-1e-9 and
                          all(scores[g]>=original[g]-1/24-1e-9 for g in mastery.LOGIC))
                    evidence={"historical_scores":scores,"historical_pass":okay}
                marker={"checkpoint":state["checkpoint"],
                        "checkpoint_sha256":state["checkpoint_sha256"] or pilot.CHAMPION_SHA256,
                        "optimizer_step":state["optimizer_step"]}
                verdict=mastery.next_phase(state["mastery"],qualified=okay,
                                           checkpoint=marker if okay else None)
                state["mastery_events"].append({"phase":phase,"outcome":verdict,
                          "proof":evidence,"checkpoint":marker})
                engine._atomic_json(out/"state.json",state)
                print(f"[mastery-v5] {phase} {verdict} source={state['optimizer_step']}",flush=True)
                if phase=="NUMERIC_QUALIFICATION" and okay:
                    continue
                return finish("MASTERY_PHASE_BOUNDARY_"+state["mastery"]["phase"])
            if phase=="SOUP_QUALIFICATION":
                if set(state["numeric_champions"])!=set(mastery.NUMERIC):
                    state["mastery"]["phase"]="STOPPED"
                    state["mastery"]["halt_reason"]="NUMERIC_GRADE_ARCHIVE_INCOMPLETE"
                    return finish("NUMERIC_GRADE_ARCHIVE_INCOMPLETE")
                numeric_members=[state["numeric_champions"][g] for g in mastery.NUMERIC]
                logic_members=[state["grade_champions"][g] for g in mastery.LOGIC]
                numeric_soup,_,numeric_manifest=fusion.average(source,out,numeric_members,
                                                         [1]*len(numeric_members),device)
                logic_soup,_,logic_manifest=fusion.average(source,out,logic_members,
                                                     [1]*len(logic_members),device)
                numbers=contract.numeric_token_ids(graph)
                def qualification(model):
                    return (_numeric_scores(model,graph,numbers,device,config["seed"]),
                            engine._probe_all_grades(model,graph,library,device=device),
                            _bridge_scores(model,graph,device,config["seed"]))
                numeric_scores,numeric_old,numeric_bridge=qualification(numeric_soup)
                _,logic_scores,logic_bridge=qualification(logic_soup)
                numeric_floor=all(numeric_scores[g]["correct"] >=
                    state["source_numeric_scores"][g]["correct"]+1 for g in mastery.NUMERIC)
                logic_floor=(sum(logic_scores.values())/22 >=
                      state["source_scores_mean"]-.01-1e-9 and
                      all(logic_scores[g]>=state["source_scores"][g]-1/24-1e-9
                          for g in mastery.LOGIC))
                state["mastery_events"].append({"phase":phase,"numeric_floor":numeric_floor,
                    "logic_floor":logic_floor,"numeric_results":numeric_scores,
                    "logic_results":logic_scores})
                # Preserve the exact two independent soup artifacts whether
                # or not either earns the right to enter hybrid fusion.
                state["mastery"]["numeric_soup"]=fusion.save_frozen(
                    out,"numeric-soup",numeric_soup,graph,numeric_manifest)
                state["mastery"]["logic_soup"]=fusion.save_frozen(
                    out,"logic-soup",logic_soup,graph,logic_manifest)
                if not (numeric_floor and logic_floor):
                    state["mastery"]["phase"]="STOPPED"
                    state["mastery"]["halt_reason"]="DOMAIN_SOUP_QUALITY_FLOOR_FAILED"
                    return finish("DOMAIN_SOUP_QUALITY_FLOOR_FAILED")
                # Greedy bounded search: 0/100 and 100/0 are informative
                # baselines but cannot be called successful fusion.
                for numeric_vote in (.25,.5,.75):
                    hybrid,_,manifest=fusion.average(source,out,
                        numeric_members+logic_members,
                        [numeric_vote/len(numeric_members)]*len(numeric_members)+
                        [(1-numeric_vote)/len(logic_members)]*len(logic_members),device)
                    hybrid_numeric,hybrid_old,hybrid_bridge=qualification(hybrid)
                    has_numeric=all(hybrid_numeric[g]["correct"] >=
                         state["source_numeric_scores"][g]["correct"]+1 for g in mastery.NUMERIC)
                    has_logic=(sum(hybrid_old.values())/22 >=
                        state["source_scores_mean"]-.01-1e-9 and
                        all(hybrid_old[g]>=state["source_scores"][g]-1/24-1e-9
                            for g in mastery.LOGIC))
                    has_bridge=(sum(r["correct"] for r in hybrid_bridge.values()) >=
                        sum(r["correct"] for r in state["source_bridge_scores"].values())
                        and all(hybrid_bridge[g]["correct"] >=
                            state["source_bridge_scores"][g]["correct"]-1
                            for g in mastery.NUMERIC))
                    record={"numeric_vote":numeric_vote,"numeric_floor":has_numeric,
                        "logic_floor":has_logic,"bridge_floor":has_bridge,
                        "numeric_scores":hybrid_numeric,
                        "old_scores":hybrid_old,"bridge_scores":hybrid_bridge}
                    state["mastery_events"].append({"phase":"HYBRID_TRIAL",**record})
                    if has_numeric and has_logic and has_bridge:
                        state["mastery"]["hybrid_soup"]=fusion.save_frozen(
                            out,"hybrid-soup",hybrid,graph,manifest)
                        state["mastery"]["phase"]="OPERATOR_REVIEW"
                        return finish("HYBRID_QUALIFIED_OPERATOR_REVIEW")
                state["mastery"]["phase"]="STOPPED"
                state["mastery"]["halt_reason"]="NO_HYBRID_MEETS_BOTH_DOMAINS"
                return finish("NO_HYBRID_MEETS_BOTH_DOMAINS")
            if phase not in ("NUMERIC","LOGIC"):
                return finish("MASTERY_PHASE_BOUNDARY_"+phase)
            if time.monotonic()-started>=minutes*60:
                return finish("TIME_BUDGET_EXHAUSTED")
            if max_grade_visits is not None and visits>=max_grade_visits:
                return finish("EXPLICIT_GRADE_VISIT_CAP")
            if attempted+block*attempts>max_attempted_updates:
                return finish("ATTEMPTED_UPDATE_SAFETY_CAP")
            if shutil.disk_usage(out).free<1024**3:
                return finish("STORAGE_RESERVE_PAUSE")
            if state["soup_snapshot"]["epoch"]!=state["soup_epoch"]:
                soup,manifest=_consolidation_teacher(source,out,state,device)
            stage=state["mastery"]
            actual_grade=mastery.next_grade(stage)
            state["cycle_index"]=CYCLE.index(actual_grade)
            parent_step=state["optimizer_step"]
            parent_checkpoint=state["checkpoint"]
            parent_checkpoint_sha=state["checkpoint_sha256"]
            grade,history,model,optimizer,graph,winner=_visit(
                out,source,state,state["champion_pass"]["scores"],
                soup,library,device)
            visits+=1
            attempted+=block*len(history)
            state["attempted_updates"]+=block*len(history)
            state["candidate_ledger"].extend(history)
            selected=None
            grade_champion_result=None
            if winner is not None:
                steps=optimizer_receipt(optimizer)["steps"]
                if steps != [state["optimizer_step"]+block]:
                    raise ValueError("SPIRAL_ACCEPTED_STEPS_BROKEN")
                filename=f"student-{steps[0]}-{uuid.uuid4().hex[:12]}.pt"
                target=out/filename
                engine.save_checkpoint(target,model,optimizer,graph,{
                    "epoch":VERSION,"grade":grade,"attempt":winner["attempt"],
                    "source_champion_sha256":pilot.CHAMPION_SHA256,
                    "research_only_no_champion_promotion":True})
                check,check_opt,check_payload=engine.load_checkpoint(target)
                if (state_hash(check)!=state_hash(model) or
                        optimizer_receipt(check_opt)["steps"]!=steps or
                        digest(check_payload["graph"])!=state["graph_sha256"]):
                    raise ValueError("SPIRAL_CHECKPOINT_READBACK_FAILED")
                checksum=engine._sha(target)
                selected={"file":filename,"sha256":checksum,"step":steps[0]}
                state["checkpoint"]=filename
                state["checkpoint_sha256"]=checksum
                state["optimizer_step"]=steps[0]
                state["accepted_updates"]+=block
                state["selected_candidate_updates"]+=block
                accepted+=block
                grade_champion_result=_archive_grade_champion(
                    state,grade,model,filename,checksum,graph,library,
                    contract.numeric_token_ids(graph),device)
            record={"grade":grade,"pass":state["completed_passes"]+1,
                    "grade_visit":state["grade_visits"]+1,
                    "candidate_attempts":len(history),
                    "eligible":sum(item["decision"]=="ELIGIBLE" for item in history),
                    "rejected":sum(item["decision"]=="REJECT" for item in history),
                    "selected":selected,
                    "decisions":[item["reason"] for item in history],
                    "old_mean_after":(sum(winner["old_after"].values())/22
                                      if winner else None),
                    "numeric_after":winner["numeric_after"] if winner else None,
                    "personal_best":grade_champion_result,
                    "consolidation_teacher_digest":manifest["teacher_digest"],
                    "teacher_events":state["teacher"]["events"],
                    "teacher_mutations":state["teacher"]["mutations"]}
            state["grade_ledger"].append(record)
            state["grade_visits"]+=1
            # Candidate eligibility and grade graduation are NOT identical.
            # The last grade of each prefix must gain actual correct items;
            # lower CE alone cannot unlock later material.
            if stage["phase"]=="NUMERIC":
                before=history[0].get("numeric_before") if history else None
                after=winner.get("numeric_after") if winner else None
                improved=bool(before and after and after["correct"]>before["correct"])
            else:
                before=history[0].get("old_before",{}).get(grade) if history else None
                after=winner.get("old_after",{}).get(grade) if winner else None
                improved=bool(before is not None and after is not None and
                              after>before)
            # A one-item fluctuation on historical probes is tolerated; one
            # recorded domain grade may not fall two fixed probe items.
            prefix_safe=True
            if winner is not None and stage["phase"]=="NUMERIC":
                for previous_grade in mastery.NUMERIC[:stage["prefix"]-1]:
                    control=_numeric_panel(previous_grade,graph,split="development",
                        seed=config["seed"]^0x57119)
                    measurement=evaluate_numeric(model,control,graph,
                              contract.numeric_token_ids(graph),device)
                    floor=state["numeric_champions"].get(previous_grade)
                    if floor is None or measurement["correct"]<floor["score"]-1:
                        prefix_safe=False
                        break
                if grade=="M01":
                    # Protect previously earned *microconcepts* even when
                    # the broad M01 numeric exam still scores zero.
                    for prior_stage,receipt in state["primitive"]["qualified"].items():
                        earlier=_primitive_panel(prior_stage,graph,
                            seed=config["seed"]^0x57119)
                        result=evaluate_primitives(model,earlier,graph,
                                                     contract.numeric_token_ids(graph),device)
                        key="evidence_correct" if prior_stage=="order" else "numeric_correct"
                        if result[key]<receipt["correct"]-1:
                            prefix_safe=False
                            break
            if winner is not None and stage["phase"]=="LOGIC":
                for previous_grade in mastery.LOGIC[:stage["prefix"]]:
                    earlier=history[0]["old_before"][previous_grade]
                    later=winner["old_after"][previous_grade]
                    if later < earlier - 1/24 - 1e-9:
                        prefix_safe=False
                        break
            if not prefix_safe and winner is not None:
                # Reject candidate at the *prefix* boundary, but preserve the
                # independently adaptive teacher and any personal best archive.
                state["checkpoint"]=parent_checkpoint
                state["checkpoint_sha256"]=parent_checkpoint_sha
                state["optimizer_step"]=parent_step
                state["accepted_updates"]-=block
                state["rolled_back_updates"]+=block
                accepted-=block
                record["prefix_rollback"]={"from":selected,"to":parent_step}
            is_primitive=(grade=="M01" and
                          state["primitive"]["stage_index"]<len(primitives.STAGES)-1)
            if is_primitive:
                current=primitives.STAGES[state["primitive"]["stage_index"]]
                was=history[0]["numeric_before"] if history else None
                after=winner["numeric_after"] if winner else None
                confirm_before=history[0]["primitive_confirm_before"] if history else None
                confirm_after=winner["primitive_confirm_after"] if winner else None
                improved=bool(prefix_safe and was and after and
                    _primitive_progress(current,was,after,confirm_before,confirm_after))
            if is_primitive and improved:
                key="evidence_correct" if current=="order" else "numeric_correct"
                state["primitive"]["qualified"][current]={
                    "correct":after[key],"checkpoint":state["checkpoint"],
                    "checkpoint_sha256":state["checkpoint_sha256"],
                    "step":state["optimizer_step"],"confirm_correct":confirm_after[key]}
                state["primitive"]["stage_index"]+=1
                stage["frontier_failures"]=0
                outcome="PRIMITIVE_"+current.upper()+"_QUALIFIED"
            else:
                outcome=mastery.advance(stage,improved=improved,prefix_safe=prefix_safe,
                                        parent_step=parent_step,
                                        surviving_step=state["optimizer_step"],
                                        limits=mastery.Limits(
                                            max_attempts_per_frontier=config["max_frontier_failures"]))
                if (is_primitive and winner is not None and not improved and
                      winner["reason"]=="BRIDGE_TRANSFER_INCUBATION_WITH_RETENTION" and
                      stage["phase"]!="STOPPED"):
                    outcome="BRIDGE_INCUBATION_RETAINED"
            state["primitive"]["events"].append({"visit":state["grade_visits"],
                 "stage":(current if is_primitive else
                           "addition" if grade=="M01" else None),
                 "improved":improved,"outcome":outcome,
                 "step":state["optimizer_step"],"prefix_safe":prefix_safe})
            if outcome in ("PREFIX_EXPANDED","DOMAIN_PREFIX_COMPLETE"):
                # Rebuild the independently frozen consolidation teacher at
                # the next prefix entry, after new grade personal bests exist.
                state["soup_epoch"]+=1
            state["mastery_events"].append({"visit":state["grade_visits"],
                "grade":grade,"phase":stage["phase"],"prefix":stage["prefix"],
                "improved":improved,"prefix_safe":prefix_safe,"outcome":outcome,
                "optimizer_step":state["optimizer_step"]})
            state["cycle_index"]=(CYCLE.index(mastery.next_grade(stage))
                                   if mastery.next_grade(stage) else 0)
            state["last_run_status"]="DURABLE_GRADE_BOUNDARY"
            engine._atomic_json(out/"state.json",state)
            print(f"[school50-numeric-spiral] {grade} pass={record['pass']} "
                  f"attempts={len(history)} eligible={record['eligible']} "
                  f"accepted={winner is not None} step={state['optimizer_step']} "
                  f"primitive={state['primitive']['stage_index']}/5 "
                  f"mastery={outcome} next={mastery.next_grade(stage)} "
                  f"elapsed={time.monotonic()-started:.1f}s",flush=True)
    finally:
        os.close(fd)


def status(run_dir=RUN):
    path=Path(run_dir).expanduser()/"state.json"
    if not path.is_file():
        return {"status":"NOT_STARTED","run_dir":str(path.parent)}
    state=engine._read(path)
    stage=state["mastery"]
    return {"status":state["last_run_status"],
            "mastery":stage,"mastery_events":state["mastery_events"][-12:],
            "primitive":state["primitive"],
            "teacher_import":state.get("teacher_import"),
            "completed_passes":state["completed_passes"],
            "completed_grade_visits":state["grade_visits"],
            "next_grade":mastery.next_grade(stage),
            "original_source_step":state["source_optimizer_step"],
            "optimizer_step":state["optimizer_step"],
            "attempted_updates":state["attempted_updates"],
            "accepted_updates":state["accepted_updates"],
            "checkpoint":state["checkpoint"],
            "last_visit":state["grade_ledger"][-1] if state["grade_ledger"] else None,
            "last_session":state["last_session"],
            "stalled_passes":state["stalled_passes"],
            "champion_pass":state["champion_pass"],
            "expanded_champion":state["expanded_champion"]}


def summary(run_dir=RUN):
    """Short, read-only operator pulse without dumping champion score arrays."""
    path=Path(run_dir).expanduser()/"state.json"
    if not path.is_file():
        return {"status":"NOT_STARTED","run_dir":str(path.parent)}
    state=engine._read(path)
    latest=state["pass_reports"][-1] if state["pass_reports"] else None
    stage=state["mastery"]
    return {"status":state["last_run_status"],
            "phase":stage["phase"],"prefix":stage["prefix"],
            "primitive_stage":(primitives.STAGES[min(state["primitive"]["stage_index"],
                len(primitives.STAGES)-1)] if stage["phase"]=="NUMERIC" else None),
            "primitive_qualified":list(state["primitive"]["qualified"]),
            "prefix_position":stage["position"],
            "frontier_failures":stage["frontier_failures"],
            "mastery_halt_reason":stage["halt_reason"],
            "last_mastery_event":(state["mastery_events"][-1]
                                  if state["mastery_events"] else None),
            "teacher_import":state.get("teacher_import"),
            "completed_passes":state["completed_passes"],
            "next_grade":mastery.next_grade(stage),
            "optimizer_step":state["optimizer_step"],
            "original_optimizer_step":state["source_optimizer_step"],
            "grade_visits":state["grade_visits"],
            "attempted_updates":state["attempted_updates"],
            "accepted_updates":state["accepted_updates"],
            "teacher_events":state["teacher"]["events"],
            "teacher_mutations":state["teacher"]["mutations"],
            "stalled_passes":state["stalled_passes"],
            "last_grade":state["grade_ledger"][-1]["grade"] if state["grade_ledger"] else None,
            "last_pass":(None if latest is None else {
                "decision":latest["decision"],"reason":latest["reason"],
                "old_22_mean":latest["old_22_mean"],
                "old_22_delta_pp":latest["old_22_delta_pp"],
                "old_22_worst_delta_pp":latest["old_22_worst_delta_pp"],
                "numeric_correct":latest["numeric_correct"],
                "numeric_net_gain":latest["numeric_net_gain"],
                "bridge_correct":latest.get("bridge_correct"),
                "bridge_net_gain":latest.get("bridge_net_gain")})}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir",type=Path,default=pilot.SOURCE)
    parser.add_argument("--run-dir",type=Path,default=RUN)
    parser.add_argument("--device",choices=("mps","cpu"),default="mps")
    parser.add_argument("--minutes",type=float,default=90)
    parser.add_argument("--block",type=int,default=32)
    parser.add_argument("--attempts",type=int,default=3)
    parser.add_argument("--seed",type=int,default=20261012)
    parser.add_argument("--max-grade-visits",type=int)
    parser.add_argument("--max-passes",type=int,
                        help="obsolete v4 option; v5 limits by --max-grade-visits instead")
    parser.add_argument("--max-attempted-updates",type=int,default=100000)
    parser.add_argument("--max-stalled-passes",type=int,default=3)
    parser.add_argument("--max-frontier-failures",type=int,default=36,
                        help="recipe-frozen attempts at an unqualified prerequisite before stopping")
    parser.add_argument("--status",action="store_true")
    parser.add_argument("--summary",action="store_true",
                        help="display compact pass and learning status, without training")
    args=parser.parse_args()
    if args.status:
        print(json.dumps(status(args.run_dir),indent=2,sort_keys=True))
        return
    if args.summary:
        print(json.dumps(summary(args.run_dir),indent=2,sort_keys=True))
        return
    stopping={"requested":False}
    old=signal.getsignal(signal.SIGINT)
    def handle(_sig,_frame):
        if stopping["requested"]:
            raise KeyboardInterrupt("emergency interrupt, last grade boundary durable")
        stopping["requested"]=True
        print("[school50-numeric-spiral] graceful stop after current grade requested",
              flush=True)
    signal.signal(signal.SIGINT,handle)
    try:
        result=run(source_dir=args.source_dir,run_dir=args.run_dir,
                   minutes=args.minutes,block=args.block,attempts=args.attempts,
                   seed=args.seed,device=args.device,
                   max_grade_visits=args.max_grade_visits,
                   max_passes=args.max_passes,
                   max_attempted_updates=args.max_attempted_updates,
                   max_stalled_passes=args.max_stalled_passes,
                   max_frontier_failures=args.max_frontier_failures,
                   stop_requested=lambda:stopping["requested"])
    finally:
        signal.signal(signal.SIGINT,old)
    print(json.dumps(result,sort_keys=True,indent=2))


if __name__=="__main__":
    main()
