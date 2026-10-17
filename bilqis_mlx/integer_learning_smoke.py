"""Measured disposable neural acquisition for generated integer lessons.

This tool creates fresh synthetic weights/AdamW in RAM. It NEVER loads or
updates the human student's weights, run directory or teacher. It separately
reports source acquisition and development performance; --trial adds
simple/composed visits and one score-selected recovery round.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .integer_curriculum import generate_integer_curriculum
from .pedagogical_parity import build_plan
from .typed_answer_training import evaluate_rows, predict_rows, typed_objective, typed_step


LEGACY = Path(__file__).resolve().parents[2] / "bilqis-triplets-v16"


def _new_student(mx, optim, vocabulary):
    import numpy as np

    rng = np.random.default_rng(31)
    width = 12
    shapes = {"embedding.weight":(vocabulary,width),
              "position.weight":(96,width),"norm.weight":(width,),
              "blocks.0.n1.weight":(width,),"blocks.0.n2.weight":(width,),
              "blocks.0.qkv.weight":(3*width,width),
              "blocks.0.proj.weight":(width,width),
              "blocks.0.up.weight":(2*width,width),
              "blocks.0.down.weight":(width,2*width)}
    student = {name:mx.array(
        rng.normal(0,.025,shape).astype(np.float32) if len(shape) == 2
        else np.ones(shape,dtype=np.float32))
        for name,shape in shapes.items()}
    optimizer = optim.AdamW(learning_rate=.0015,bias_correction=True)
    config = {"heads":3,"layers":1}
    return student, optimizer, config


def run_smoke(parity: dict, legacy_root: Path, *, seed=100,
              count=20, steps=100, maximum=None) -> dict:
    import mlx.core as mx
    import mlx.optimizers as optim
    if type(steps) is not int or not 1 <= steps <= 1000:
        raise ValueError("INTEGER_SMOKE_STEPS_OUT_OF_BOUNDS")
    mx.set_default_device(mx.cpu)
    generated = generate_integer_curriculum(parity, legacy_root,
                  seed=seed, count=count, maximum=maximum)
    train = [row for group in generated["rows"] if group["partition"] == "train"
             for row in group["views"]][:12]
    development = [row for group in generated["rows"]
                   if group["partition"] == "development"
                   for row in group["views"]][:12]
    if len(train) < 6 or not development:
        raise ValueError("INTEGER_SMOKE_DISTINCT_TRAIN_DEVELOPMENT_REQUIRED")
    student, optimizer, config = _new_student(
        mx, optim, len(parity["heads"]["semantic_token"]["values"]))
    heads = generated["heads"]
    loss_before = float(typed_objective(mx,student,train,heads,config).item())
    before_train = evaluate_rows(mx,student,train,heads,config)
    before_development = evaluate_rows(mx,student,development,heads,config)
    for _ in range(steps):
        typed_step(mx,student,optimizer,train,heads,config)
    loss_after = float(typed_objective(mx,student,train,heads,config).item())
    after_train = evaluate_rows(mx,student,train,heads,config)
    after_development = evaluate_rows(mx,student,development,heads,config)
    return {"scope":"DISPOSABLE_SYNTHETIC_STUDENT_ONLY",
            "integer_max":generated["integer_max"],
            "seed":seed,"optimizer_steps":steps,
            "source_loss_before":round(loss_before,6),
            "source_loss_after":round(loss_after,6),
            "train_before":before_train,"train_after":after_train,
            "development_before":before_development,
            "development_after":after_development,
            "student_model_or_teacher_modified":False,
            "claim":"EXPOSED_ACQUISITION_NOT_SEALED_QUALIFICATION"}


def run_trial(parity: dict, legacy_root: Path, *, seed=100,
              count=80, steps=100, maximum=None, operation_names=None) -> dict:
    """Try simple → composed → weakest-group recovery on fresh toy weights.

    Every optimizer step samples fresh source-generated expressions. Scores
    use fixed generated probes so retention remains easy to read. Probe items
    are eligible for instruction; this is an exploratory learning trial.
    """
    import random
    from collections import Counter
    import mlx.core as mx
    import mlx.optimizers as optim

    if type(steps) is not int or not 1 <= steps <= 300:
        raise ValueError("INTEGER_TRIAL_STEPS_OUT_OF_BOUNDS")
    mx.set_default_device(mx.cpu)
    generated = generate_integer_curriculum(parity, legacy_root,
        seed=seed, count=count, maximum=maximum, operation_names=operation_names)
    heads = generated["heads"]
    student, optimizer, config = _new_student(
        mx, optim, len(heads["semantic_token"]["values"]))

    def family(group):
        expression = group["views"][0]["record"]["expression"]
        return ("composed" if any(arg["kind"] == "op"
                for arg in expression["args"]) else "simple")

    probes = {name: [row for group in generated["rows"] if family(group) == name
                     for row in group["views"]]
              for name in ("simple", "composed")}
    if any(not rows for rows in probes.values()):
        raise ValueError("INTEGER_TRIAL_BOTH_STAGES_REQUIRED")

    def scores():
        result = {}
        for name, rows in probes.items():
            measured = evaluate_rows(mx, student, rows, heads, config)
            native = measured["semantic_token"]
            assertions = measured["evidence"]
            direct = [row for row in rows if row["answer_kind"] == "numeric_active"]
            predictions = predict_rows(mx, student, direct, heads, config)
            result[name] = {"correct": native["correct"], "total": native["total"],
                "gold": dict(Counter(row["gold"] for row in direct)),
                "predictions": dict(Counter(predictions.values())),
                "assertions_correct": assertions["correct"],
                "assertions_total": assertions["total"]}
        return result

    before = scores()
    visits, taught = [], set()
    rng = random.Random(seed)
    focus = "simple"
    for visit in range(3):
        if visit == 1:
            focus = "composed"
        elif visit == 2:
            focus = min(observed, key=lambda name:
                        observed[name]["correct"] / observed[name]["total"])
        for step in range(steps):
            batch = generate_integer_curriculum(parity, legacy_root,
                seed=seed + 1 + visit * steps + step, count=20,
                maximum=generated["integer_max"], operation_names=operation_names)
            choices = [group for group in batch["rows"] if family(group) == focus]
            if not choices:
                raise ValueError("INTEGER_TRIAL_FRESH_STAGE_BATCH_EMPTY")
            selected = rng.sample(choices, min(4, len(choices)))
            taught.update(group["source_id"] for group in selected)
            rows = [row for group in selected for row in group["views"]]
            loss, _ = typed_step(mx, student, optimizer, rows, heads, config)
        observed = scores()
        visits.append({"focus": focus, "steps": steps,
                       "last_batch_loss": round(loss, 6), "scores": observed})
    return {"scope": "DISPOSABLE_SYNTHETIC_STUDENT_ONLY",
            "seed": seed, "integer_max": generated["integer_max"],
            "operations": [op["name"] for op in generated["operators"]
                           if op["output"] == "Number"],
            "optimizer_steps": int(optimizer.state["step"].item()),
            "distinct_taught_expressions": len(taught),
            "before": before, "visits": visits,
            "student_model_or_teacher_modified": False,
            "claim": "EXPLORATORY_EXPOSED_PROBES"}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed",type=int,default=100)
    parser.add_argument("--count",type=int)
    parser.add_argument("--trial",action="store_true",
                        help="Try simple, composed and score-selected recovery visits")
    parser.add_argument("--steps",type=int,default=100)
    parser.add_argument("--operation",action="append",
                        help="Select a source arithmetic operation for --trial")
    parser.add_argument("--legacy-root",type=Path,default=LEGACY)
    args=parser.parse_args(argv)
    if args.operation and not args.trial:
        parser.error("--operation requires --trial")
    parity=build_plan(args.legacy_root)
    runner = run_trial if args.trial else run_smoke
    count = args.count if args.count is not None else (80 if args.trial else 20)
    options = ({"operation_names": tuple(args.operation) if args.operation else None}
               if args.trial else {})
    print(json.dumps(runner(parity,args.legacy_root,seed=args.seed,
                           count=count,steps=args.steps,**options),indent=2))


if __name__ == "__main__":
    main()
