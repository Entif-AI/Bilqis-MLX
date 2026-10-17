"""Can the original School50 FP32 model learn *any* exact numerical answers?

This is a capacity / target-interface diagnosis, NOT a curriculum run.

Two isolated clones of the same pass-43 FP32 champion see exactly 16 fixed,
source-oracle-verified mathematical expressions with both TRUE and FALSE EQ
wrappers (32 identical input questions). Both learn the exact left-hand value.

One clone uses the existing input-number embedding rows as a tied output head.
The other starts from *identical* logits but unties a copied output projection.
This is a separate, explicit readout-factor ablation. No teacher mutations,
other-grade rehearsal, altered math syntax, or automatic promotion is allowed.

Stop early only after independently measured near-perfect memorization, or at
an explicit wall-clock / update ceiling. Heldout transfer is measured once
after training, not used for early stopping or model selection. The original
checkpoint is verified before AND after the experiment.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
import time

import torch
from torch import nn
from torch.nn import functional as F

from bilqis_logic.kernel import digest
from bilqis_ref.model import state_hash
from . import arithmetic, engine, numeric_answer_contract as contract
from . import numeric_answer_pilot as pilot

VERSION = "bilqis.school50.numeric-capacity/v1"
ARMS = ("tied", "untied")

# The sixteen gold numbers are distinct. Equality candidates are *not* the
# answer on the negative half. Operations span ADD/SUB/MUL/MOD as in School50.
# This is deliberately tiny and fixed, so the question is memorization first.
EXAMPLES = (
    ("ADD", 1, 2), ("ADD", 5, 7), ("ADD", 7, 9), ("ADD", 4, 14),
    ("SUB", 15, 14), ("SUB", 16, 14), ("SUB", 19, 10), ("SUB", 23, 12),
    ("MUL", 2, 2), ("MUL", 2, 3), ("MUL", 2, 4), ("MUL", 3, 5),
    ("MOD", 12, 7), ("MOD", 17, 10), ("MOD", 25, 15), ("MOD", 32, 19),
)


def fixtures():
    pairs = []
    values = set()
    for op, a, b in EXAMPLES:
        term = arithmetic.operation(op, arithmetic.atom(a), arithmetic.atom(b))
        arithmetic.verify(term)
        value = arithmetic.evaluate(term)
        if not isinstance(value, int) or isinstance(value, bool) or value in values:
            raise ValueError("CAPACITY_GOLD_NOT_DISTINCT_NUMBER")
        values.add(value)
        false_value = (value + 1) if value < 100 else (value - 1)
        true = arithmetic.row(arithmetic.operation("EQ", copy.deepcopy(term), arithmetic.atom(value)), 20)
        false = arithmetic.row(arithmetic.operation("EQ", copy.deepcopy(term), arithmetic.atom(false_value)), 20)
        if (contract.answer_gold(true), contract.answer_gold(false)) != (value, value):
            raise ValueError("CAPACITY_UNSOUND_PAIR")
        pairs.append({"grade": 20, "expression_id": digest(term),
                      "numeric_gold": value, "true": true, "false": false})
    if len(values) != 16 or len({p["expression_id"] for p in pairs}) != 16:
        raise ValueError("CAPACITY_DUPLICATE_EXPRESSION")
    return pairs


def numeric_logits(model, ids, lengths, numbers, head=None):
    if head is None:
        return contract.readout(model, ids, lengths,
                                answer_kind="numeric", number_ids=numbers)
    # Same native hidden representation and initial number-token output
    # geometry as the tied path, with a separately trainable readout matrix.
    positions = torch.arange(ids.shape[1], device=ids.device)
    x = model.embedding(ids) + model.position(positions)[None]
    for layer in model.blocks:
        x = layer(x)
    hidden = model.norm(x)[torch.arange(ids.shape[0], device=ids.device), lengths - 1]
    return head(hidden)


def _batch(pairs, graph, device):
    rows = contract.flatten(pairs)
    ids, lengths = contract.encode_questions(rows, graph, device)
    gold = torch.tensor([contract.answer_gold(row) for row in rows],
                        dtype=torch.long, device=device)
    return rows, ids, lengths, gold


@torch.no_grad()
def evaluate(model, head, pairs, graph, numbers, device):
    model.eval()
    if head is not None:
        head.eval()
    _, ids, lengths, gold = _batch(pairs, graph, device)
    logits = numeric_logits(model, ids, lengths, numbers, head)
    picks = logits.argmax(-1)
    right = (picks == gold).detach().cpu().tolist()
    predictions = picks.detach().cpu().tolist()
    target = gold.detach().cpu().tolist()
    exact_pairs = sum(right[i] and right[i + 1] for i in range(0, len(right), 2))
    return {"pair_correct": exact_pairs, "pairs": len(pairs),
            "pair_accuracy": exact_pairs / len(pairs),
            "question_accuracy": sum(right) / len(right),
            "ce": float(F.cross_entropy(logits, gold).detach().cpu()),
            "distinct_predicted_numbers": len(set(predictions)),
            "mean_pair_invariance": sum(predictions[i] == predictions[i + 1]
                                         for i in range(0, len(right), 2)) / len(pairs),
            "prediction_counts": {str(num): predictions.count(num) for num in sorted(set(predictions))},
            "gold_numbers": sorted(set(target))}


def run(*, output, source=pilot.SOURCE, device="mps", max_steps=1024,
        check_every=32, min_steps=64, max_minutes=20,
        target_pair_accuracy=1.0, seed=20261012):
    if (device not in ("cpu", "mps") or not 32 <= max_steps <= 4096 or
            check_every not in (16, 32, 64, 128) or not 0 <= min_steps <= max_steps or
            not 0 < max_minutes <= 60 or not .875 <= target_pair_accuracy <= 1):
        raise ValueError("CAPACITY_BUDGET_INVALID")
    destination = Path(output).expanduser().resolve(strict=False)
    parent = pilot._ancestor(source)
    if (destination.exists() or destination == parent["source_dir"] or
            parent["source_dir"] in destination.parents or
            destination in parent["source_dir"].parents):
        raise ValueError("CAPACITY_DESTINATION_MUST_BE_NEW_AND_ISOLATED")

    train = fixtures()
    # Held out by expression identity. The seed and generator are frozen and
    # never inspected by a teacher or intervention chooser during training.
    transfer = contract.panel("sealed", expressions_per_grade=24, seed=seed ^ 0x4AB19,
                              exclude_expression_ids={p["expression_id"] for p in train})
    if set(p["expression_id"] for p in train) & set(p["expression_id"] for p in transfer):
        raise ValueError("CAPACITY_TRANSFER_CONTAMINATION")
    baseline, _, graph, numbers = pilot._load(parent, device)
    initial_hash = state_hash(baseline)
    baseline_train = evaluate(baseline, None, train, graph, numbers, device)
    baseline_transfer = evaluate(baseline, None, transfer, graph, numbers, device)
    rows, ids, lengths, gold = _batch(train, graph, device)
    receipts = {"version": VERSION, "status": "IN_PROGRESS_NO_PROMOTION",
                "source_checkpoint_sha256": pilot.CHAMPION_SHA256,
                "source_state_sha256": parent["state_sha256"],
                "source_optimizer_step": pilot.CHAMPION_STEP,
                "source_model_sha256": initial_hash,
                "train_expression_count": len(train),
                "training_gold_classes": baseline_train["gold_numbers"],
                "training_input_manifest_sha256": digest([r["id"] for r in rows]),
                "transfer_expression_manifest_sha256": digest([p["expression_id"] for p in transfer]),
                "starting_train": baseline_train, "starting_transfer": baseline_transfer,
                "max_steps": max_steps, "min_steps": min_steps,
                "check_every": check_every, "max_minutes": max_minutes,
                "target_pair_accuracy": target_pair_accuracy,
                "seed": seed, "device": device,
                "experiment_policy": "zero-rehearsal, 100% direct-numeric CE; no automatic promotion",
                "arms": {}}
    destination.mkdir(parents=True, exist_ok=False)
    torch.manual_seed(seed)
    total_started = time.monotonic()

    for arm in ARMS:
        model, optimizer, student_graph, student_numbers = pilot._load(parent, device)
        if state_hash(model) != initial_hash or digest(student_graph) != digest(graph):
            raise ValueError("CAPACITY_STUDENTS_NOT_IDENTICAL_INITIALIZATION")
        head = None
        if arm == "untied":
            head = nn.Linear(model.config.width, len(numbers), bias=False, device=device)
            with torch.no_grad():
                head.weight.copy_(model.embedding.weight[list(numbers)].detach())
            optimizer.add_param_group({"params": head.parameters(),
                                       "lr": optimizer.param_groups[0]["lr"]})
        model.eval()
        with torch.no_grad():
            before = numeric_logits(model, ids, lengths, numbers, head)
            native = contract.readout(model, ids, lengths,
                                      answer_kind="numeric", number_ids=numbers)
            if not torch.allclose(before, native, atol=1e-5, rtol=1e-6):
                raise ValueError("CAPACITY_HEAD_INITIAL_LOGITS_NOT_EQUAL")
        track = []
        status = "MAX_STEPS_EXHAUSTED"
        arm_start = time.monotonic()
        for step in range(1, max_steps + 1):
            model.train()
            if head is not None:
                head.train()
            optimizer.zero_grad(set_to_none=True)
            logits = numeric_logits(model, ids, lengths, numbers, head)
            loss = F.cross_entropy(logits, gold)
            if not bool(torch.isfinite(loss)):
                raise ValueError("CAPACITY_NONFINITE_LOSS")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                list(model.parameters()) + (list(head.parameters()) if head is not None else []), 1.0)
            optimizer.step()
            if step % check_every == 0 or step == max_steps:
                progress = evaluate(model, head, train, graph, numbers, device)
                progress.update({"step": step, "elapsed_seconds": round(time.monotonic() - arm_start, 2)})
                track.append(progress)
                print(f"[capacity:{arm}] {step}/{max_steps} train={progress['pair_correct']}/16 "
                      f"unique_answers={progress['distinct_predicted_numbers']} "
                      f"ce={progress['ce']:.3f} elapsed={progress['elapsed_seconds']:.1f}s", flush=True)
                if (step >= min_steps and progress["pair_accuracy"] >= target_pair_accuracy and
                        progress["distinct_predicted_numbers"] >= 14):
                    status = "MEMORIZATION_PROVEN"
                    break
                if time.monotonic() - total_started >= max_minutes * 60:
                    status = "TIME_CEILING_REACHED"
                    break
        end_train = evaluate(model, head, train, graph, numbers, device)
        # The transfer panel is a single post-training observation, never used
        # to choose the early stop point or alter the next arm's loss/recipe.
        end_transfer = evaluate(model, head, transfer, graph, numbers, device)
        receipts["arms"][arm] = {"status": status, "steps": step,
                                 "elapsed_seconds": round(time.monotonic() - arm_start, 2),
                                 "new_parameters": 0 if head is None else sum(p.numel() for p in head.parameters()),
                                 "training": end_train, "heldout_transfer": end_transfer,
                                 "trace": track,
                                 "final_model_sha256": state_hash(model),
                                 "never_promoted": True}
        if time.monotonic() - total_started >= max_minutes * 60:
            break
    receipts["elapsed_seconds"] = round(time.monotonic() - total_started, 2)
    receipts["status"] = "COMPLETED_CAPACITY_DIAGNOSTIC_NO_PROMOTION"
    receipts["qualification"] = {
        arm: data["status"] == "MEMORIZATION_PROVEN" for arm, data in receipts["arms"].items()}
    if (pilot._sha(parent["checkpoint"]) != pilot.CHAMPION_SHA256 or
            pilot._sha(parent["state_path"]) != parent["state_sha256"]):
        raise ValueError("CAPACITY_PARENT_CHECKPOINT_CHANGED")
    engine._atomic_json(destination / "report.json", receipts)
    if engine._read(destination / "report.json") != json.loads(json.dumps(receipts)):
        raise ValueError("CAPACITY_REPORT_READBACK_FAILED")
    return receipts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=pilot.SOURCE)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] /
                        "runs/school50-numeric-capacity-20261012")
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    parser.add_argument("--max-steps", type=int, default=1024)
    parser.add_argument("--check-every", type=int, default=32)
    parser.add_argument("--min-steps", type=int, default=64)
    parser.add_argument("--max-minutes", type=float, default=20)
    parser.add_argument("--target-pair-accuracy", type=float, default=1.0)
    args = parser.parse_args()
    result = run(output=args.output, source=args.source, device=args.device,
                 max_steps=args.max_steps, check_every=args.check_every,
                 min_steps=args.min_steps, max_minutes=args.max_minutes,
                 target_pair_accuracy=args.target_pair_accuracy)
    print(json.dumps({"status": result["status"], "qualification": result["qualification"],
                      "arms": {name: {"status": data["status"], "steps": data["steps"],
                                      "train_pairs": data["training"]["pair_correct"],
                                      "transfer_pairs": data["heldout_transfer"]["pair_correct"],
                                      "elapsed_seconds": data["elapsed_seconds"]}
                               for name, data in result["arms"].items()},
                      "report": str(args.output / "report.json")}, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
