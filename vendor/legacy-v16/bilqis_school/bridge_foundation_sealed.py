"""One-time sealed bridge examination, outside the frozen training recipe.

The operator calls this only after deciding to stop a research lineage.
It never updates student, optimizer or teacher, and a later call returns the
same persisted receipt without re-examining the model. The supported
launcher refuses further training after the sealed result is exposed.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path

from bilqis_logic.kernel import digest
from bilqis_micro.run import optimizer_receipt
from . import bridge_foundation_lessons as course
from . import bridge_foundation_runner as runner
from . import engine,numeric_answer_pilot as pilot


def evaluate_once(*,run_dir=runner.RUN,source_dir=pilot.SOURCE,device="mps"):
    out=Path(run_dir).expanduser().resolve(strict=True)
    receipt=out/"sealed-evaluation.json"
    lock=out.with_name(out.name+".writer.lock")
    fd=os.open(lock,os.O_CREAT|os.O_RDWR|getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("BRIDGE_SEALED_EXAM_TRAINER_STILL_ACTIVE") from exc
        if receipt.is_file():return engine._read(receipt)
        state=engine._read(out/"state.json")
        if state.get("last_run_status") in ("READY","DURABLE_BRIDGE_BOUNDARY"):
            raise ValueError("BRIDGE_SEALED_EXAM_REQUIRES_STOPPED_RUN")
        if (state["version"]!=runner.VERSION or
                state["config"]["recipe"]!=runner.recipe()):
            raise ValueError("BRIDGE_SEALED_EXAM_RECIPE_HASH_CHANGED")
        source=pilot._ancestor(source_dir)
        config=state["config"]
        model,_,graph,_=runner._load(out,source,state,config,device)
        parents=list(out.glob("bridge-parent-*.pt"))
        if len(parents)!=1 or engine._sha(parents[0])!=state["bootstrap"]["checkpoint_sha256"]:
            raise ValueError("BRIDGE_SEALED_BASELINE_PROVENANCE_INVALID")
        baseline,prior_optimizer,payload=engine.load_checkpoint(parents[0])
        engine._device(baseline,prior_optimizer,device)
        if (digest(payload["graph"])!=digest(graph) or
            optimizer_receipt(prior_optimizer)["steps"]!=[
                state["bootstrap"]["optimizer_step"]]):
            raise ValueError("BRIDGE_SEALED_BASELINE_OPTIMIZER_DRIFT")
        data={}
        for fold in ("primary","confirm"):
            rows=course.panel(graph,split="sealed",fold=fold,seed=config["seed"])
            data[fold]={"imported_parent":runner.evaluate_panel(baseline,rows,graph,device),
                        "current_student":runner.evaluate_panel(model,rows,graph,device)}
        result={"version":"bilqis.school50.bridge-sealed-receipt/v1",
            "run_version":runner.VERSION,"checkpoint_sha256":state["checkpoint_sha256"],
            "optimizer_step":state["optimizer_step"],
            "baseline_sha256":state["bootstrap"]["checkpoint_sha256"],
            "protected_p43_sha256":pilot.CHAMPION_SHA256,
            "recipe":config["recipe"],"panels":data,
            "disposition":"ONE_TIME_SEALED_EXAM_FROZEN_NO_FURTHER_TRAINING"}
        handle=os.open(receipt,os.O_CREAT|os.O_EXCL|os.O_WRONLY|
                       getattr(os,"O_NOFOLLOW",0),0o600)
        with os.fdopen(handle,"w",encoding="utf-8") as stream:
            json.dump(result,stream,sort_keys=True,indent=2)
            stream.write("\n")
            stream.flush();os.fsync(stream.fileno())
        if engine._read(receipt)!=result:
            raise ValueError("BRIDGE_SEALED_RECEIPT_READBACK_FAILED")
        return result
    finally:os.close(fd)


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--run-dir",type=Path,default=runner.RUN)
    cli.add_argument("--source-dir",type=Path,default=pilot.SOURCE)
    cli.add_argument("--device",choices=("cpu","mps"),default="mps")
    args=cli.parse_args()
    print(json.dumps(evaluate_once(run_dir=args.run_dir,
          source_dir=args.source_dir,device=args.device),sort_keys=True,indent=2))


if __name__=="__main__":main()
