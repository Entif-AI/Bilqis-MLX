"""Independent School50 answer-type A/B pilot, starting at *pass-43 champion*.

No v2/v3 imports, no curriculum redesign, no optimizer/architecture change,
no new token or learnable head, no public write and NO champion promotion.

For *identical* School50 `EQ(expression, candidate)` input questions:
  binary arm learns the original five-class evidence classification;
  numeric arm learns the original integer result of `expression` using a
  101-class projection onto ALREADY-TRAINED number-token embeddings.

Both arms share the original model+AdamW source, 16 math/16 pre-G19 rehearsal
questions per update, source LR, parent preservation loss and budget. Original
School50 G01-G22 fixed probes and independently sampled heldout questions are
reported separately. All new artifact paths are independent and immutable.

No scientifically sealed custodian examination exists for this pilot: the
deterministic heldout panels are exploratory research until independently
preregistered, externally protected and replicated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch
from torch.nn import functional as F

from bilqis_logic.kernel import digest
from bilqis_micro.graph import STATES
from bilqis_micro.run import optimizer_receipt
from bilqis_ref.model import batch, state_hash
from . import engine, lessons, numeric_answer_contract as contract

VERSION = "bilqis.school50.answer-paradigm-pilot/v1"
CHAMPION = "student-67800-2cf61275e081.pt"
CHAMPION_SHA256 = "82a16a1d5865547bde1fb9dc974e7cfcb254e5331d719b6b29fe5e09c8021726"
CHAMPION_STEP = 67800
SOURCE = Path.home() / "Code/bilqis-auto-curriculum50/runs/school50-continuous-v1"
REHEARSAL_PER_UPDATE = 16
MATH_PAIRS_PER_GRADE = 4
DISTILLATION_WEIGHT = 0.35


def _sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _ancestor(source):
    directory = Path(source).expanduser().resolve(strict=True)
    state_path = directory / "state.json"
    data = state_path.read_bytes()
    state = json.loads(data)
    champion = state["champion_pass"]
    if (champion.get("checkpoint") != CHAMPION or
            champion.get("checkpoint_sha256") != CHAMPION_SHA256 or
            champion.get("optimizer_step") != CHAMPION_STEP):
        raise ValueError("NUMERIC_NOT_ORIGINAL_SCHOOL50_P43_CHAMPION")
    checkpoint = directory / CHAMPION
    if _sha(checkpoint) != CHAMPION_SHA256:
        raise ValueError("NUMERIC_SOURCE_CHECKPOINT_SHA_MISMATCH")
    return {"source_dir": directory, "checkpoint": checkpoint,
            "state_path": state_path,
            "state_sha256": hashlib.sha256(data).hexdigest(),
            "checkpoint_sha256": CHAMPION_SHA256}


def _load(parent, device):
    if _sha(parent["checkpoint"]) != CHAMPION_SHA256:
        raise ValueError("NUMERIC_SOURCE_CHECKPOINT_CHANGED_BEFORE_LOAD")
    model, optimizer, payload = engine.load_checkpoint(parent["checkpoint"])
    if (model.config.precision != "fp32" or
            optimizer_receipt(optimizer)["steps"] != [CHAMPION_STEP]):
        raise ValueError("NUMERIC_SOURCE_MODEL_OR_ADAMW_NOT_FP32_CHAMPION")
    engine._device(model, optimizer, device)
    graph = payload["graph"]
    if model.config.vocab_size != len(graph["tokens"]):
        raise ValueError("NUMERIC_SOURCE_GRAPH_ABI_DRIFT")
    ids = contract.numeric_token_ids(graph)
    return model, optimizer, graph, ids


def _math_batch(pairs, graph, device):
    rows = contract.flatten(pairs)
    ids, lengths = contract.encode_questions(rows, graph, device)
    targets = torch.tensor([contract.answer_gold(row) for row in rows],
                           dtype=torch.long, device=device)
    gold = torch.tensor([STATES.index(row["gold"]) for row in rows],
                        dtype=torch.long, device=device)
    return rows, ids, lengths, targets, gold


@torch.no_grad()
def evaluate(model, pairs, graph, numbers, device):
    """Exact numeric, original Boolean, paired discrimination, answer bias."""
    model.eval()
    predicted_booleans = []
    predicted_numbers = []
    expected = []
    rows_seen = []
    for begin in range(0, len(pairs), 24):
        rows, ids, lengths, targets, gold = _math_batch(
            pairs[begin:begin + 24], graph, device)
        native = contract.readout(model, ids, lengths,
                                  answer_kind="evidence", number_ids=numbers)
        direct = contract.readout(model, ids, lengths,
                                  answer_kind="numeric", number_ids=numbers)
        booleans = native.argmax(-1).detach().cpu().tolist()
        values = direct.argmax(-1).detach().cpu().tolist()
        predicted_booleans.extend(booleans)
        predicted_numbers.extend(values)
        expected.extend(targets.detach().cpu().tolist())
        rows_seen.extend(rows)
    total = len(rows_seen)
    pair_total = len(pairs)
    if total != 2 * pair_total:
        raise ValueError("NUMERIC_EXAM_INCOMPLETE")
    gold_bool = [STATES.index(row["gold"]) for row in rows_seen]
    correct_bool = [p == g for p, g in zip(predicted_booleans, gold_bool)]
    exact_num = [p == g for p, g in zip(predicted_numbers, expected)]
    # The derived EQ answer is an EXTERNAL deterministic comparison and is not
    # the model's native evidence head. Report it distinctly.
    derived = []
    for value, row in zip(predicted_numbers, rows_seen):
        candidate = row["input"]["expression"]["args"][1]["value"]
        derived.append("TRUE" if value == candidate else "FALSE")
    derived_correct = [a == r["gold"] for a, r in zip(derived, rows_seen)]
    value_flip_pairs = 0
    same_numeric_across_distractor = 0
    for i in range(0, total, 2):
        value_flip_pairs += predicted_numbers[i] != predicted_numbers[i + 1]
        same_numeric_across_distractor += predicted_numbers[i] == predicted_numbers[i + 1]
    by_grade = {}
    for grade in contract.GRADES:
        positions = [i for i, row in enumerate(rows_seen) if row["stage"] == grade - 1]
        by_grade[f"G{grade:02d}"] = {
            "questions": len(positions),
            "numeric_exact_question_accuracy": sum(exact_num[i] for i in positions) / len(positions),
            "native_binary_question_accuracy": sum(correct_bool[i] for i in positions) / len(positions)}
    return {"questions": total, "expression_pairs": pair_total,
            "numeric_exact_question_accuracy": sum(exact_num) / total,
            "numeric_exact_pair_accuracy": sum(all(exact_num[i:i + 2])
                                              for i in range(0, total, 2)) / pair_total,
            "native_binary_question_accuracy": sum(correct_bool) / total,
            "native_binary_both_answers_correct": sum(all(correct_bool[i:i + 2])
                                                      for i in range(0, total, 2)) / pair_total,
            "derived_from_numeric_boolean_accuracy": sum(derived_correct) / total,
            "derived_from_numeric_both_answers_correct": sum(all(derived_correct[i:i + 2])
                                                             for i in range(0, total, 2)) / pair_total,
            "numeric_distractor_invariance": same_numeric_across_distractor / pair_total,
            "numeric_distractor_sensitive_pairs": value_flip_pairs,
            "numeric_predictions_unique": len(set(predicted_numbers)),
            "numeric_prediction_mode": max(set(predicted_numbers),
                                           key=lambda n: (predicted_numbers.count(n), -n)),
            "native_evidence_prediction_counts": {
                label: predicted_booleans.count(i)
                for i, label in enumerate(STATES) if i in predicted_booleans},
            "native_true_recall": sum(correct_bool[i] for i, row in enumerate(rows_seen)
                                      if row["gold"] == "TRUE") / pair_total,
            "native_false_recall": sum(correct_bool[i] for i, row in enumerate(rows_seen)
                                       if row["gold"] == "FALSE") / pair_total,
            "by_grade": by_grade,
            "number_class_majority_accuracy": max(expected.count(value)
                                                   for value in set(expected)) / total,
            "semantic_expression_manifest_sha256": digest([p["expression_id"] for p in pairs]),
            "question_ids_sha256": digest([r["id"] for r in rows_seen])}


def _train(model, optimizer, parent_model, *, arm, graph, numbers, math_pairs,
           older, device):
    math_rows, ids, lengths, target_number, target_binary = _math_batch(
        math_pairs, graph, device)
    old_ids, old_lengths = batch([lessons.encode(row, graph) for row in older], device=device)
    old_target = torch.tensor([STATES.index(row["gold"]) for row in older],
                              dtype=torch.long, device=device)
    optimizer.zero_grad(set_to_none=True)
    model.train()
    new_logits = contract.readout(model, ids, lengths,
                                 answer_kind="numeric" if arm == "numeric" else "evidence",
                                 number_ids=numbers)
    supervised = F.cross_entropy(new_logits, target_number if arm == "numeric" else target_binary)
    old_logits = contract.readout(model, old_ids, old_lengths,
                                  answer_kind="evidence", number_ids=numbers)
    old_loss = F.cross_entropy(old_logits, old_target)
    with torch.no_grad():
        parent_model.eval()
        reference = parent_model(old_ids, old_lengths)
    keep = F.kl_div(F.log_softmax(old_logits / 1.5, dim=-1),
                    F.softmax(reference / 1.5, dim=-1),
                    reduction="batchmean") * (1.5 ** 2)
    loss = 0.5 * supervised + 0.5 * old_loss + DISTILLATION_WEIGHT * keep
    if not bool(torch.isfinite(loss)):
        raise ValueError("NUMERIC_NONFINITE_OPTIMIZER_OBJECTIVE")
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
    optimizer.step()
    return {"combined_loss": float(loss.detach().cpu()),
            "math_loss": float(supervised.detach().cpu()),
            "rehearsal_loss": float(old_loss.detach().cpu()),
            "distillation_loss": float(keep.detach().cpu()),
            "math_input_sha256": digest([row["id"] for row in math_rows]),
            "old_rehearsal_sha256": digest([row["id"] for row in older]),
            "math_questions": len(math_rows), "older_questions": len(older)}


def run(*, source=SOURCE, output=None, updates=4, seed=20261012,
        device="cpu", execute=False):
    if not isinstance(updates, int) or not 1 <= updates <= 8 or device not in ("cpu", "mps"):
        raise ValueError("NUMERIC_EXPERIMENT_BUDGET_OUT_OF_BOUNDS")
    parent = _ancestor(source)
    model, optimizer, graph, numbers = _load(parent, device)
    library = lessons.TeacherLibrary()
    if state_hash(model) != engine.load_checkpoint(parent["checkpoint"])[2]["state_sha256"]:
        raise ValueError("NUMERIC_SOURCE_MODEL_HASH_INCONSISTENT")
    baseline_model_hash = state_hash(model)
    original_optimizer = optimizer_receipt(optimizer)
    original_head_size = int(model.answer_ids.numel())
    warmup = contract.panel("train", expressions_per_grade=MATH_PAIRS_PER_GRADE,
                            seed=seed)
    initial_rows, inputs, lengths, _, _ = _math_batch(warmup, graph, device)
    with torch.no_grad():
        model.eval()
        original_logits = model(inputs, lengths)
        same_readout = contract.readout(model, inputs, lengths, answer_kind="evidence",
                                        number_ids=numbers)
    if not bool(torch.allclose(original_logits, same_readout, atol=1e-5, rtol=1e-6)):
        raise ValueError("NUMERIC_READOUT_CHANGED_ORIGINAL_MODEL_BEHAVIOR")
    receipt = {"version": VERSION, "status": "PREFLIGHT_NO_TRAINING",
               "source_checkpoint": CHAMPION, "source_checkpoint_sha256": CHAMPION_SHA256,
               "source_optimizer_step": CHAMPION_STEP,
               "source_state_sha256": parent["state_sha256"],
               "source_model_sha256": baseline_model_hash,
               "graph_sha256": digest(graph),
               "initial_optimizer_receipt": original_optimizer,
               "precision": model.config.precision,
               "initial_model_parameters": sum(p.numel() for p in model.parameters()),
               "original_evidence_classes": original_head_size,
               "existing_numeric_answer_classes": len(numbers),
               "new_parameters_per_arm": 0,
               "math_supervision_is_the_only_arm_difference": True,
               "math_inputs_identical_across_arms": True,
               "training_updates_per_arm": updates,
               "batch_size_per_arm": 2 * MATH_PAIRS_PER_GRADE * len(contract.GRADES) +
                                     REHEARSAL_PER_UPDATE,
               "rehearsal_count_per_update": REHEARSAL_PER_UPDATE,
               "parent_distillation_weight": DISTILLATION_WEIGHT,
               "source_learning_rate": float(optimizer.param_groups[0]["lr"]),
               "split_buckets": {k: sorted(v) for k, v in contract.SPLIT_BUCKETS.items()},
               "first_math_batch_ids_sha256": digest([r["id"] for r in initial_rows]),
               "cohort": contract.GRADES,
               "limitations": [
                   "Direct numeric target is the value of EQ's left-hand arithmetic expression; identical Boolean question inputs in both arms.",
                   "The output-paradigm change necessarily changes the number of target classes and supervised loss landscape.",
                   "This small experiment is not a full reconstruction of historical School50 teacher mutation or 10/2/4 curriculum.",
                   "Held-out hash partitions are exploratory, not independently custodian-sealed certification.",
                   "No model promotion or public publication is authorized."]}
    if not execute:
        return receipt
    if output is None:
        raise ValueError("NUMERIC_EXPERIMENT_REQUIRES_NEW_OUTPUT_DIRECTORY")
    destination = Path(output).expanduser().resolve(strict=False)
    if destination.exists() or (parent["source_dir"] in destination.parents or
                                destination in parent["source_dir"].parents):
        raise ValueError("NUMERIC_EXPERIMENT_DESTINATION_NOT_ISOLATED_AND_NEW")
    results = {}
    seen_train = set()
    signatures = {}
    for arm in contract.ARMS:
        student, optim, student_graph, number_ids = _load(parent, device)
        if state_hash(student) != baseline_model_hash or digest(student_graph) != digest(graph):
            raise ValueError("NUMERIC_ARMS_DO_NOT_SHARE_THE_EXACT_ANCESTOR")
        teacher, _, _, _ = _load(parent, device)
        teacher.eval()
        for p in teacher.parameters():
            p.requires_grad_(False)
        traces = []
        for step in range(updates):
            pairs = contract.panel("train", expressions_per_grade=MATH_PAIRS_PER_GRADE,
                                   seed=seed + step * 1301)
            old = contract.rehearsal(library, graph, step=step, seed=seed)
            seen_train.update(pair["expression_id"] for pair in pairs)
            train_receipt = _train(student, optim, teacher, arm=arm, graph=graph,
                                   numbers=number_ids, math_pairs=pairs, older=old,
                                   device=device)
            train_receipt["step"] = step + 1
            signatures.setdefault(step, (train_receipt["math_input_sha256"],
                                         train_receipt["old_rehearsal_sha256"]))
            if signatures[step] != (train_receipt["math_input_sha256"],
                                    train_receipt["old_rehearsal_sha256"]):
                raise ValueError("NUMERIC_EXPERIMENT_ARMS_RECEIVED_DIFFERENT_QUESTIONS")
            traces.append(train_receipt)
        expected_optimizer_step = CHAMPION_STEP + updates
        if optimizer_receipt(optim)["steps"] != [expected_optimizer_step]:
            raise ValueError("NUMERIC_EXPERIMENT_OPTIMIZER_STEP_MISMATCH")
        results[arm] = {"arm": arm, "optimizer_step": expected_optimizer_step,
                        "updates_attempted": updates, "updates_promoted": 0,
                        "training_traces": traces,
                        "source_start_model_sha256": baseline_model_hash,
                        "trained_model_sha256": state_hash(student),
                        "promotion": "RESEARCH_ONLY_NOT_ELIGIBLE"}
        results[arm]["_student"] = student
        del optim, teacher
    # Neither the developmental nor held-out final panel influences training
    # choices; there are no adaptive candidates or early stopping decisions.
    dev = contract.panel("development", expressions_per_grade=24, seed=seed ^ 0x437BA)
    sealed = contract.panel("sealed", expressions_per_grade=40, seed=seed ^ 0xA92C)
    train_ids = seen_train
    dev_ids = {pair["expression_id"] for pair in dev}
    sealed_ids = {pair["expression_id"] for pair in sealed}
    if train_ids & dev_ids or train_ids & sealed_ids or dev_ids & sealed_ids:
        raise ValueError("NUMERIC_TRAIN_DEV_SEALED_EXPRESSION_LEAK")
    initial_old_scores = engine._probe_all_grades(model, graph, library, device=device)
    baseline_development = evaluate(model, dev, graph, numbers, device)
    baseline_final = evaluate(model, sealed, graph, numbers, device)
    receipt.update(status="COMPLETED_NO_PROMOTION", actual_training_manifest_sha256=digest(signatures),
                   train_expression_ids_count=len(train_ids),
                   original_22_grade_scores=initial_old_scores,
                   baseline_development=baseline_development,
                   baseline_heldout=baseline_final,
                   outcomes={})
    for arm, outcome in results.items():
        student = outcome.pop("_student")
        scores = engine._probe_all_grades(student, graph, library, device=device)
        outcome["original_22_grade_scores"] = scores
        outcome["original_22_mean_delta"] = (
            sum(scores.values()) - sum(initial_old_scores.values())) / len(scores)
        outcome["original_22_worst_grade_delta"] = min(
            scores[g] - initial_old_scores[g] for g in scores)
        outcome["development"] = evaluate(student, dev, graph, numbers, device)
        outcome["heldout"] = evaluate(student, sealed, graph, numbers, device)
        receipt["outcomes"][arm] = outcome
        del student
    if _sha(parent["checkpoint"]) != CHAMPION_SHA256 or _sha(parent["state_path"]) != parent["state_sha256"]:
        raise ValueError("NUMERIC_EXPERIMENT_SOURCE_CHANGED_DURING_RUN")
    destination.mkdir(parents=True, exist_ok=False)
    engine._atomic_json(destination / "report.json", receipt)
    if engine._read(destination / "report.json") != json.loads(json.dumps(receipt)):
        raise ValueError("NUMERIC_EXPERIMENT_REPORT_READBACK_FAILED")
    return receipt


def verify_report(path, *, source=SOURCE):
    p = Path(path).expanduser().resolve(strict=True)
    source_identity = _ancestor(source)
    report = engine._read(p)
    if (report["version"] != VERSION or report["status"] != "COMPLETED_NO_PROMOTION" or
            report["source_checkpoint_sha256"] != source_identity["checkpoint_sha256"] or
            report["source_state_sha256"] != source_identity["state_sha256"] or
            set(report["outcomes"]) != set(contract.ARMS)):
        raise ValueError("NUMERIC_REPORT_IDENTITY_MISMATCH")
    for outcome in report["outcomes"].values():
        if (outcome["optimizer_step"] != CHAMPION_STEP + report["training_updates_per_arm"] or
                outcome["updates_promoted"] != 0 or
                outcome["source_start_model_sha256"] != report["source_model_sha256"] or
                outcome["heldout"]["questions"] != report["baseline_heldout"]["questions"]):
            raise ValueError("NUMERIC_REPORT_OUTCOME_INCONSISTENT")
    return {"status": "VERIFIED_RESEARCH_ONLY_NO_PROMOTION",
            "report_sha256": _sha(p), "source_checkpoint_sha256": CHAMPION_SHA256,
            "heldout": {name: {
                "numeric_exact": outcome["heldout"]["numeric_exact_pair_accuracy"],
                "binary_pair_accuracy": outcome["heldout"]["native_binary_both_answers_correct"],
                "legacy_mean_delta": outcome["original_22_mean_delta"]}
                for name, outcome in report["outcomes"].items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] /
                        "runs/school50-answer-type-pilot")
    parser.add_argument("--device", choices=("cpu", "mps"), default="cpu")
    parser.add_argument("--updates", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20261012)
    parser.add_argument("--execute", action="store_true",
                        help="Bounded, two-arm optimizer pilot; never promotes candidates")
    parser.add_argument("--verify-report", type=Path,
                        help="Verify an existing report without rerunning training")
    args = parser.parse_args()
    if args.verify_report:
        print(json.dumps(verify_report(args.verify_report, source=args.source),
                         indent=2, sort_keys=True))
        return
    report = run(source=args.source, output=args.output, updates=args.updates,
                 seed=args.seed, device=args.device, execute=args.execute)
    if args.execute:
        report = {"status": report["status"], "source_checkpoint_sha256": CHAMPION_SHA256,
                  "baseline": report["baseline_heldout"],
                  "outcomes": {name: {"heldout": outcome["heldout"],
                                      "original_22_mean_delta": outcome["original_22_mean_delta"]}
                               for name, outcome in report["outcomes"].items()}}
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
