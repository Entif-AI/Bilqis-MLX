"""Measured disposable neural acquisition for generated integer lessons.

This tool creates fresh synthetic weights/AdamW in RAM. It NEVER loads or
updates the human student's weights, run directory or teacher. It separately
reports source acquisition and untouched development probe performance.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .integer_curriculum import generate_integer_curriculum
from .pedagogical_parity import build_plan
from .typed_answer_training import evaluate_rows, typed_objective, typed_step


LEGACY = Path(__file__).resolve().parents[2] / "bilqis-triplets-v16"


def run_smoke(parity: dict, legacy_root: Path, *, seed=100,
              count=20, steps=100, maximum=None) -> dict:
    import mlx.core as mx
    import mlx.optimizers as optim
    import numpy as np

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
    rng = np.random.default_rng(31)
    width = 12
    vocabulary = len(parity["heads"]["semantic_token"]["values"])
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


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed",type=int,default=100)
    parser.add_argument("--count",type=int,default=20)
    parser.add_argument("--steps",type=int,default=100)
    parser.add_argument("--legacy-root",type=Path,default=LEGACY)
    args=parser.parse_args(argv)
    parity=build_plan(args.legacy_root)
    print(json.dumps(run_smoke(parity,args.legacy_root,seed=args.seed,
                               count=args.count,steps=args.steps),indent=2))


if __name__ == "__main__":
    main()
