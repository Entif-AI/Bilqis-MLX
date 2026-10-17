"""Resumable, time-first, single-writer School50 numeric-target experiment.

This runtime is purpose-built for an answer-type ablation. It never writes
School50 or the experimental v2/v3 directories. The single variable between
arms remains the arithmetic target/readout: Boolean evidence vs exact integer.
Every grade round advances BOTH students by precisely one AdamW update before
either can be checkpointed. At each durable block, BOTH complete model/AdamW
snapshots are verified, then ONE atomic state file advances their shared step.

The historical whole-school champion is read-only. No research descendant is
declared a new champion. A stopped or crashed call resumes from the *last fully
paired block*. A changed recipe/target/comparison scope starts a new lineage.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import time
import uuid

import torch
from torch.nn import functional as F

from bilqis_logic.kernel import digest
from bilqis_micro.run import optimizer_receipt
from bilqis_ref.model import state_hash
from . import engine, lessons, numeric_answer_contract as contract
from . import numeric_answer_pilot as pilot

VERSION = "bilqis.school50.numeric-answer-series/v3"
# Safety guard, *not* a default duration. 250k steps is well beyond a normal
# 90-minute MPS session: session time and observed transfer govern the run.
MAX_UPDATES = 250000
DEFAULT_RUN = Path(__file__).resolve().parents[1] / "runs/school50-numeric-answer-time-v3"
DEFAULT_QUALIFICATION = Path(__file__).resolve().parents[1] / "runs/numeric-capacity-qualification-4096/report.json"


def _qualified(report, parent):
    """Do not spend long-run compute until the existing tied readout can learn."""
    path = Path(report).expanduser().resolve(strict=True)
    result = engine._read(path)
    tied = result.get("arms", {}).get("tied", {})
    if (result.get("version") != "bilqis.school50.numeric-capacity/v1" or
            result.get("source_checkpoint_sha256") != pilot.CHAMPION_SHA256 or
            result.get("source_state_sha256") != parent["state_sha256"] or
            not result.get("qualification", {}).get("tied") or
            tied.get("status") != "MEMORIZATION_PROVEN" or
            tied.get("training", {}).get("pair_correct", 0) < 14 or
            tied.get("training", {}).get("distinct_predicted_numbers", 0) < 14):
        raise ValueError("NUMERIC_CAMPAIGN_CAPACITY_NOT_QUALIFIED")
    return pilot._sha(path)


def _planned_block(library, graph, *, first, after, seed):
    """Validate every upcoming question BEFORE applying any update in a block.

    An invalid source-generated world must never spend optimizer updates that
    cannot safely reach the next paired checkpoint. Both arms receive the
    same immutable exposure plan; its only mutation is training itself.
    """
    planned = []
    for step in range(first, after):
        pairs = contract.panel("train", expressions_per_grade=pilot.MATH_PAIRS_PER_GRADE,
                               seed=seed + step * 1301)
        earlier = contract.rehearsal(library, graph, step=step, seed=seed)
        math_rows = contract.flatten(pairs)
        lessons.valid_rows(math_rows, graph)
        for row in math_rows:
            contract.answer_gold(row)
        if len(earlier) != pilot.REHEARSAL_PER_UPDATE or len(math_rows) != 16:
            raise ValueError("NUMERIC_PRECOMPILED_BLOCK_EXPOSURE_DRIFT")
        planned.append((step, pairs, earlier))
    if len(planned) != after - first:
        raise ValueError("NUMERIC_INCOMPLETE_BLOCK_PREFLIGHT")
    return planned


def _recipe_shas():
    files = (Path(__file__), Path(contract.__file__), Path(pilot.__file__),
             Path(engine.__file__), Path(lessons.__file__))
    return {p.name: pilot._sha(p) for p in files}


def _configuration(*, target_updates, checkpoint_every, seed, device,
                   qualification_sha256=None, observe_every=512):
    if (not isinstance(target_updates, int) or not 1 <= target_updates <= MAX_UPDATES or
            not isinstance(checkpoint_every, int) or
            not 1 <= checkpoint_every <= min(512, target_updates) or
            not isinstance(observe_every, int) or observe_every < checkpoint_every or
            observe_every % checkpoint_every != 0 or
            device not in ("cpu", "mps")):
        raise ValueError("NUMERIC_SERIES_UNSUPPORTED_BUDGET_OR_DEVICE")
    return {"target_updates": target_updates, "checkpoint_every": checkpoint_every,
            "seed": seed, "device": device, "recipe_sha256": _recipe_shas(),
            "qualification_sha256": qualification_sha256,
            "observe_every": observe_every,
            "source_checkpoint_sha256": pilot.CHAMPION_SHA256,
            "version": VERSION, "arms": list(contract.ARMS),
            "math_pairs_per_grade": pilot.MATH_PAIRS_PER_GRADE,
            "rehearsal_questions": pilot.REHEARSAL_PER_UPDATE,
            "retention_distillation_weight": pilot.DISTILLATION_WEIGHT}


@contextmanager
def _guard(destination):
    destination = Path(destination).expanduser().resolve(strict=False)
    destination.parent.mkdir(parents=True, exist_ok=True)
    path = destination.with_name(destination.name + ".numeric-answer.writer.lock")
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("NUMERIC_SERIES_ALREADY_HAS_WRITER") from exc
        yield destination
    finally:
        os.close(fd)


def _verified_state(out, parent, config):
    saved = engine._read(out / "state.json")
    if (saved.get("version") != VERSION or saved.get("config") != config or
            saved.get("source_state_sha256") != parent["state_sha256"] or
            saved.get("source_checkpoint_sha256") != pilot.CHAMPION_SHA256):
        raise ValueError("NUMERIC_SERIES_CANNOT_RESUME_DIFFERENT_RECIPE_OR_SOURCE")
    if (not isinstance(saved.get("completed_updates"), int) or
            not 0 <= saved["completed_updates"] <= config["target_updates"] or
            set(saved["arms"]) != set(contract.ARMS)):
        raise ValueError("NUMERIC_SERIES_STATE_INVALID")
    for name, data in saved["arms"].items():
        record = data.get("checkpoint")
        if saved["completed_updates"] == 0:
            if record is not None:
                raise ValueError("NUMERIC_SERIES_NEW_RUN_HAS_STUDENT_CHECKPOINT")
            continue
        if (not isinstance(record, dict) or not isinstance(record.get("file"), str) or
                Path(record["file"]).name != record["file"]):
            raise ValueError("NUMERIC_SERIES_UNSAFE_CHECKPOINT_POINTER")
        if pilot._sha(out / record["file"]) != record["sha256"]:
            raise ValueError("NUMERIC_SERIES_STUDENT_CHECKPOINT_HASH_MISMATCH")
    return saved


def _students(out, state, parent, device):
    result = {}
    source_graph = None
    for arm in contract.ARMS:
        pointer = state["arms"][arm]["checkpoint"]
        if pointer is None:
            model, optimizer, graph, numbers = pilot._load(parent, device)
        else:
            model, optimizer, payload = engine.load_checkpoint(out / pointer["file"])
            engine._device(model, optimizer, device)
            graph = payload["graph"]
            numbers = contract.numeric_token_ids(graph)
            if state_hash(model) != pointer["model_sha256"]:
                raise ValueError("NUMERIC_SERIES_STUDENT_MODEL_HASH_MISMATCH")
        if optimizer_receipt(optimizer)["steps"] != [pilot.CHAMPION_STEP + state["completed_updates"]]:
            raise ValueError("NUMERIC_SERIES_STUDENT_OPTIMIZER_STEP_MISMATCH")
        if source_graph is None:
            source_graph = graph
        elif digest(graph) != digest(source_graph):
            raise ValueError("NUMERIC_SERIES_ARMS_HAVE_DIFFERENT_TOKEN_ABI")
        result[arm] = {"model": model, "optimizer": optimizer, "graph": graph,
                       "numbers": numbers}
    return result, source_graph


def _persist_block(out, state, models, graph, after, traces):
    """Save both candidates; move shared pointer only after both readbacks."""
    pending = {}
    for arm in contract.ARMS:
        file = f"student-{pilot.CHAMPION_STEP + after}-{arm}-{uuid.uuid4().hex[:10]}.pt"
        path = out / file
        model, optim = models[arm]["model"], models[arm]["optimizer"]
        engine.save_checkpoint(path, model, optim, graph, {
            "epoch": VERSION, "answer_arm": arm,
            "source_champion_sha256": pilot.CHAMPION_SHA256,
            "optimizer_step": pilot.CHAMPION_STEP + after,
            "no_champion_promotion": True})
        check_model, check_optimizer, check_payload = engine.load_checkpoint(path)
        if (state_hash(check_model) != state_hash(model) or
                digest(check_payload["graph"]) != digest(graph) or
                optimizer_receipt(check_optimizer)["steps"] != [pilot.CHAMPION_STEP + after]):
            raise ValueError("NUMERIC_SERIES_SAVED_ARM_READBACK_INCORRECT")
        pending[arm] = {"file": file, "sha256": pilot._sha(path),
                        "model_sha256": state_hash(model),
                        "optimizer_step": pilot.CHAMPION_STEP + after}
    changed = dict(state)
    changed["arms"] = {name: {"checkpoint": pending[name]} for name in contract.ARMS}
    changed["completed_updates"] = after
    changed["last_run_status"] = "DURABLE_PAIRED_BLOCK"
    changed["training_trace"] = state["training_trace"] + traces
    old_keep = dict(state.get("recent_snapshots", {}))
    changed["recent_snapshots"] = {"previous": old_keep.get("latest"),
                                   "latest": {arm: pending[arm]["file"] for arm in contract.ARMS}}
    engine._atomic_json(out / "state.json", changed)
    if engine._read(out / "state.json") != json.loads(json.dumps(changed)):
        raise ValueError("NUMERIC_SERIES_STATE_READBACK_MISMATCH")
    # Prune only this isolated run's *older* experiment snapshots AFTER a
    # verified state points at the new paired generation. Never prune parent.
    old = old_keep.get("previous")
    if old:
        protected = set(pending[a]["file"] for a in contract.ARMS)
        protected.update(old_keep.get("latest", {}).values())
        for path in old.values():
            if path not in protected and (out / path).is_file():
                (out / path).unlink()
    return changed


def _finish(out, state, models, graph, parent, library):
    seed = state["config"]["seed"]
    device = state["config"]["device"]
    source_model, _, _, numbers = pilot._load(parent, device)
    develop = contract.panel("development", expressions_per_grade=24, seed=seed ^ 0x437BA)
    heldout = contract.panel("sealed", expressions_per_grade=40, seed=seed ^ 0xA92C)
    # Collision proof is structural: expression hash buckets cannot belong to
    # two split classes, rather than guessing from step-level manifest hashes.
    for pair in develop:
        if contract.split_of(pair["expression_id"]) != "development":
            raise ValueError("NUMERIC_SERIES_DEVELOPMENT_SPLIT_CHANGED")
    for pair in heldout:
        if contract.split_of(pair["expression_id"]) != "sealed":
            raise ValueError("NUMERIC_SERIES_HELDOUT_SPLIT_CHANGED")
    old_scores = engine._probe_all_grades(source_model, graph, library, device=device)
    report = {"version": VERSION, "status": "COMPLETED_RESEARCH_NO_PROMOTION",
              "source_checkpoint_sha256": pilot.CHAMPION_SHA256,
              "source_state_sha256": parent["state_sha256"],
              "config": state["config"],
              "completed_updates_per_arm": state["completed_updates"],
              "training_trace_sha256": digest(state["training_trace"]),
              "development_manifest_sha256": digest([p["expression_id"] for p in develop]),
              "heldout_manifest_sha256": digest([p["expression_id"] for p in heldout]),
              "baseline_old_scores": old_scores,
              "baseline_development": pilot.evaluate(source_model, develop, graph, numbers, device),
              "baseline_heldout": pilot.evaluate(source_model, heldout, graph, numbers, device),
              "outcomes": {}}
    for arm in contract.ARMS:
        model = models[arm]["model"]
        scores = engine._probe_all_grades(model, graph, library, device=device)
        report["outcomes"][arm] = {
            "checkpoint": state["arms"][arm]["checkpoint"],
            "development": pilot.evaluate(model, develop, graph, numbers, device),
            "heldout": pilot.evaluate(model, heldout, graph, numbers, device),
            "legacy_22_scores": scores,
            "legacy_mean_delta": (sum(scores.values()) - sum(old_scores.values())) / 22,
            "legacy_worst_grade_delta": min(scores[k] - old_scores[k] for k in old_scores),
            "automatic_promotion": False}
    if pilot._sha(parent["checkpoint"]) != pilot.CHAMPION_SHA256 or pilot._sha(
            parent["state_path"]) != parent["state_sha256"]:
        raise ValueError("NUMERIC_SERIES_PARENT_MUTATED_DURING_EXPERIMENT")
    engine._atomic_json(out / "report.json", report)
    if engine._read(out / "report.json") != json.loads(json.dumps(report)):
        raise ValueError("NUMERIC_SERIES_FINAL_REPORT_READBACK_FAILED")
    state["last_run_status"] = "COMPLETE_RESEARCH_NO_PROMOTION"
    engine._atomic_json(out / "state.json", state)
    return report


def _observe(models, graph, library, teacher, device, seed, completed_updates,
             elapsed_seconds):
    """Selection-visible development panel only; *never* examine sealed final."""
    develop = contract.panel("development", expressions_per_grade=24, seed=seed ^ 0x437BA)
    baseline = engine._probe_all_grades(teacher, graph, library, device=device)
    result = {"completed_updates": completed_updates,
              "session_elapsed_seconds": round(elapsed_seconds, 2), "by_arm": {}}
    for arm in contract.ARMS:
        member = models[arm]
        model, numbers = member["model"], member["numbers"]
        metric = pilot.evaluate(model, develop, graph, numbers, device)
        # Continuous cross-entropy complements exact accuracy, which has a
        # discontinuous threshold and may stay flat while learning advances.
        with torch.no_grad():
            _, ids, lengths, targets, _ = pilot._math_batch(develop, graph, device)
            logits = contract.readout(model.eval(), ids, lengths,
                                      answer_kind="numeric", number_ids=numbers)
            numeric_ce = float(F.cross_entropy(logits, targets).detach().cpu())
        old = engine._probe_all_grades(model, graph, library, device=device)
        result["by_arm"][arm] = {
            "numeric_development_ce": numeric_ce,
            "numeric_development_pair_accuracy": metric["numeric_exact_pair_accuracy"],
            "numeric_predicted_numbers": metric["numeric_predictions_unique"],
            "binary_development_pair_accuracy": metric["native_binary_both_answers_correct"],
            "original_22_mean_delta": (sum(old.values()) - sum(baseline.values())) / 22,
            "original_22_worst_grade_delta": min(old[g] - baseline[g] for g in baseline)}
    return result


def run(*, source=pilot.SOURCE, run_dir=DEFAULT_RUN, target_updates=200000,
        checkpoint_every=128, observe_every=512, seed=20261012,
        device="mps", minutes=90.0, qualification_report=DEFAULT_QUALIFICATION,
        max_blocks=None, stop_requested=lambda: False):
    if not 0 < minutes <= 1440 or (max_blocks is not None and not 1 <= max_blocks <= 256):
        raise ValueError("NUMERIC_SERIES_INVALID_SESSION_BUDGET")
    parent = pilot._ancestor(source)
    qualification_sha = _qualified(qualification_report, parent)
    config = _configuration(target_updates=target_updates,
                            checkpoint_every=checkpoint_every, seed=seed, device=device,
                            qualification_sha256=qualification_sha,
                            observe_every=observe_every)
    with _guard(run_dir) as out:
        if out == parent["source_dir"] or out in parent["source_dir"].parents or parent[
                "source_dir"] in out.parents:
            raise ValueError("NUMERIC_SERIES_OVERLAPS_ORIGINAL_SCHOOL50")
        if not out.exists():
            # The runner owns this independent namespace only.
            out.mkdir(parents=True, exist_ok=False)
            state = {"version": VERSION, "config": config,
                     "source_checkpoint_sha256": pilot.CHAMPION_SHA256,
                     "source_state_sha256": parent["state_sha256"],
                     "completed_updates": 0,
                     "arms": {name: {"checkpoint": None} for name in contract.ARMS},
                     "training_trace": [], "recent_snapshots": {},
                     "observations": [], "last_session": None,
                     "last_run_status": "READY_NO_UPDATES"}
            engine._atomic_json(out / "state.json", state)
        state = _verified_state(out, parent, config)
        if (state["last_run_status"] == "COMPLETE_RESEARCH_NO_PROMOTION" and
                (out / "report.json").exists()):
            result = engine._read(out / "report.json")
            if result["status"] != "COMPLETED_RESEARCH_NO_PROMOTION":
                raise ValueError("NUMERIC_SERIES_EXISTING_REPORT_INVALID")
            return result
        models, graph = _students(out, state, parent, device)
        library = lessons.TeacherLibrary()
        teacher, _, _, _ = pilot._load(parent, device)
        teacher.eval()
        for parameter in teacher.parameters():
            parameter.requires_grad_(False)
        start = time.monotonic()
        blocks = 0
        start_updates = state["completed_updates"]

        def pause(reason):
            elapsed = time.monotonic() - start
            taken = state["completed_updates"] - start_updates
            state["last_run_status"] = reason
            state["last_session"] = {"reason": reason, "seconds": round(elapsed, 2),
                                     "updates": taken,
                                     "paired_updates_per_second": round(taken / max(elapsed, 1e-6), 3)}
            if (pilot._sha(parent["checkpoint"]) != pilot.CHAMPION_SHA256 or
                    pilot._sha(parent["state_path"]) != parent["state_sha256"]):
                raise ValueError("NUMERIC_SERIES_SOURCE_DRIFT_AT_SESSION_STOP")
            engine._atomic_json(out / "state.json", state)
            print(f"[numeric-answer-series] STOP reason={reason} "
                  f"completed={state['completed_updates']} "
                  f"session_elapsed={elapsed:.1f}s paired_updates={taken} "
                  f"rate={taken / max(elapsed, 1e-6):.2f}/s", flush=True)
            return {"status": reason, "completed_updates": state["completed_updates"],
                    "target_updates": target_updates, "run_dir": str(out),
                    "session": state["last_session"],
                    "latest_observation": (state.get("observations") or [None])[-1]}

        while state["completed_updates"] < target_updates:
            if stop_requested():
                return pause("STOPPED_BY_GRACEFUL_INTERRUPT")
            if time.monotonic() - start >= minutes * 60:
                return pause("TIME_BUDGET_EXHAUSTED")
            if max_blocks is not None and blocks >= max_blocks:
                return pause("EXPLICIT_BLOCK_CAP_REACHED")
            if shutil.disk_usage(out).free < 1024 ** 3:
                return pause("PAUSED_FOR_STORAGE_RESERVE")
            before = state["completed_updates"]
            after = min(before + checkpoint_every, target_updates)
            traces = []
            planned = _planned_block(library, graph, first=before, after=after, seed=seed)
            for step, pairs, earlier in planned:
                receipts = {}
                for arm in contract.ARMS:
                    st = models[arm]
                    receipt = pilot._train(st["model"], st["optimizer"], teacher,
                                           arm=arm, graph=graph, numbers=st["numbers"],
                                           math_pairs=pairs, older=earlier, device=device)
                    receipts[arm] = receipt
                for key in ("math_input_sha256", "old_rehearsal_sha256",
                            "math_questions", "older_questions"):
                    if receipts["binary"][key] != receipts["numeric"][key]:
                        raise ValueError("NUMERIC_SERIES_EXPOSURE_IMBALANCE")
                traces.append({"update": step + 1,
                               "math_input_sha256": receipts["binary"]["math_input_sha256"],
                               "old_rehearsal_sha256": receipts["binary"]["old_rehearsal_sha256"],
                               "math_loss_by_arm": {arm: r["math_loss"] for arm, r in receipts.items()},
                               "old_loss_by_arm": {arm: r["rehearsal_loss"] for arm, r in receipts.items()}})
            state = _persist_block(out, state, models, graph, after, traces)
            blocks += 1
            elapsed = time.monotonic() - start
            print(f"[numeric-answer-series] paired step {after}/{target_updates} "
                  f"source={pilot.CHAMPION_STEP} checkpointed "
                  f"elapsed={elapsed:.1f}s rate={(after-start_updates)/max(elapsed, 1e-6):.2f}/s; "
                  f"binary_math_ce={traces[-1]['math_loss_by_arm']['binary']:.3f} "
                  f"numeric_math_ce={traces[-1]['math_loss_by_arm']['numeric']:.3f}",
                  flush=True)
            if after % observe_every == 0 or after == target_updates:
                observation = _observe(models, graph, library, teacher, device, seed,
                                       after, elapsed)
                state["observations"] = state.get("observations", []) + [observation]
                engine._atomic_json(out / "state.json", state)
                numerical = observation["by_arm"]["numeric"]
                print(f"[numeric-answer-series] development step={after} "
                      f"numeric_pairs={numerical['numeric_development_pair_accuracy']:.3f} "
                      f"numeric_ce={numerical['numeric_development_ce']:.3f} "
                      f"distinct_numbers={numerical['numeric_predicted_numbers']} "
                      f"old22_delta={numerical['original_22_mean_delta']:+.3f}", flush=True)
                if (numerical["original_22_mean_delta"] < -0.05 or
                        numerical["original_22_worst_grade_delta"] < -0.25):
                    return pause("RETENTION_GUARD_PAUSE")
                # Only stop for a demonstrable long-term plateau AFTER a
                # substantial minimum dose. A four-window flat exact score
                # alone is not a plateau if cross-entropy still improves.
                recent = state["observations"][-5:]
                if (len(recent) == 5 and after >= 8192 and elapsed >= 20 * 60):
                    first = recent[0]["by_arm"]["numeric"]
                    if (max(r["by_arm"]["numeric"]["numeric_development_pair_accuracy"]
                            for r in recent[1:]) <= first["numeric_development_pair_accuracy"] and
                            min(r["by_arm"]["numeric"]["numeric_development_ce"]
                                for r in recent[1:]) > first["numeric_development_ce"] - 0.02):
                        return pause("LEARNING_PLATEAU_PAUSE")
        state["last_session"] = {"reason": "SAFETY_UPDATE_CAP_REACHED",
                                 "seconds": round(time.monotonic() - start, 2),
                                 "updates": state["completed_updates"] - start_updates}
        return _finish(out, state, models, graph, parent, library)


def finalize_run(*, source=pilot.SOURCE, run_dir=DEFAULT_RUN,
                 target_updates=200000, checkpoint_every=128,
                 observe_every=512, seed=20261012, device="mps",
                 qualification_report=DEFAULT_QUALIFICATION):
    """Human-invoked frozen endpoint. Sealed exam is never used during training."""
    parent = pilot._ancestor(source)
    qualifying_sha = _qualified(qualification_report, parent)
    config = _configuration(target_updates=target_updates,
                            checkpoint_every=checkpoint_every, observe_every=observe_every,
                            seed=seed, device=device, qualification_sha256=qualifying_sha)
    with _guard(run_dir) as out:
        state = _verified_state(out, parent, config)
        if state["last_run_status"] == "COMPLETE_RESEARCH_NO_PROMOTION":
            return engine._read(out / "report.json")
        if state["completed_updates"] < checkpoint_every:
            raise ValueError("NUMERIC_SERIES_NOT_ENOUGH_PAIRED_TRAINING_TO_FINALIZE")
        models, graph = _students(out, state, parent, device)
        return _finish(out, state, models, graph, parent, lessons.TeacherLibrary())


def status(run_dir=DEFAULT_RUN):
    state_file = Path(run_dir).expanduser() / "state.json"
    if not state_file.is_file():
        return {"status": "NOT_STARTED", "run_dir": str(state_file.parent)}
    state = engine._read(state_file)
    return {k: state.get(k) for k in
            ("version", "completed_updates", "last_run_status", "arms", "config",
             "last_session") } | {"latest_observation": (state.get("observations") or [None])[-1],
                                    "final_report_available": (state_file.parent / "report.json").is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--source", type=Path, default=pilot.SOURCE)
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    parser.add_argument("--updates", type=int, default=200000,
                        help="High safety cap only; wall-clock budget is primary")
    parser.add_argument("--checkpoint-every", type=int, default=128)
    parser.add_argument("--observe-every", type=int, default=512)
    parser.add_argument("--qualification-report", type=Path, default=DEFAULT_QUALIFICATION)
    parser.add_argument("--seed", type=int, default=20261012)
    parser.add_argument("--minutes", type=float, default=90)
    parser.add_argument("--max-blocks", type=int, default=None,
                        help="Explicit limited blocks for smoke tests; never defaulted")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--finalize", action="store_true",
                        help="Freeze a paused lineage and evaluate untouched heldout once")
    args = parser.parse_args()
    if args.status:
        print(json.dumps(status(args.run_dir), sort_keys=True, indent=2))
        return
    if args.finalize:
        report = finalize_run(source=args.source, run_dir=args.run_dir,
                              target_updates=args.updates,
                              checkpoint_every=args.checkpoint_every,
                              observe_every=args.observe_every,
                              qualification_report=args.qualification_report,
                              seed=args.seed, device=args.device)
        print(json.dumps({"status": report["status"],
                          "completed_updates": report["completed_updates_per_arm"],
                          "source_sha256": report["source_checkpoint_sha256"],
                          "outcomes": {name: {
                              "numeric_exact": r["heldout"]["numeric_exact_pair_accuracy"],
                              "binary_pair": r["heldout"]["native_binary_both_answers_correct"],
                              "retention_mean_delta": r["legacy_mean_delta"]}
                              for name, r in report["outcomes"].items()}},
                         sort_keys=True, indent=2))
        return
    stopping = {"requested": False}
    previous = signal.getsignal(signal.SIGINT)
    def graceful(_signal, _frame):
        if stopping["requested"]:
            raise KeyboardInterrupt("second Ctrl+C is emergency stop")
        stopping["requested"] = True
        print("[numeric-answer-series] graceful pause after paired block requested",
              flush=True)
    signal.signal(signal.SIGINT, graceful)
    try:
        result = run(source=args.source, run_dir=args.run_dir,
                     target_updates=args.updates, checkpoint_every=args.checkpoint_every,
                     observe_every=args.observe_every,
                     qualification_report=args.qualification_report,
                     seed=args.seed, device=args.device, minutes=args.minutes,
                     max_blocks=args.max_blocks,
                     stop_requested=lambda: stopping["requested"])
    finally:
        signal.signal(signal.SIGINT, previous)
    summary = {"status": result["status"]}
    if "outcomes" in result:
        summary["baseline_numeric_exact"] = result["baseline_heldout"]["numeric_exact_pair_accuracy"]
        summary["outcomes"] = {name: {
            "numeric_exact": outcome["heldout"]["numeric_exact_pair_accuracy"],
            "binary_pair": outcome["heldout"]["native_binary_both_answers_correct"],
            "retention_mean_delta": outcome["legacy_mean_delta"]}
            for name, outcome in result["outcomes"].items()}
    else:
        summary.update(result)
    print(json.dumps(summary, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
