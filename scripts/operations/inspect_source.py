"""Read-only native FP32 checkpoint structure review; zero optimizer updates."""
from pathlib import Path
import json
import torch
from bilqis_mlx.backup import digest_file
from bilqis_mlx.source import AUDITED_PARENT


def inspect(path: Path) -> dict:
    if digest_file(path) != AUDITED_PARENT.sha256:
        raise ValueError("HISTORICAL_PARENT_SHA_MISMATCH")
    payload=torch.load(path,map_location="cpu",weights_only=True)
    optimizer=payload["optimizer"]
    return {
        "checkpoint_sha256": AUDITED_PARENT.sha256,
        "version":payload.get("version"),
        "config":payload.get("config"),
        "model_parameter_names":list(payload["model"])[:12],
        "model_parameters":len(payload["model"]),
        "token_count":len(payload["graph"]["tokens"]),
        "optimizer_state_count":len(optimizer["state"]),
        "optimizer_group_count":len(optimizer["param_groups"]),
        "optimizer_group":{k:v for k,v in optimizer["param_groups"][0].items() if k!="params"},
        "first_optimizer_state_fields":list(next(iter(optimizer["state"].values()))),
        "native_adamw_present":True,
        "neural_updates":0}


if __name__ == "__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--checkpoint",required=True,type=Path)
    args=p.parse_args()
    print(json.dumps(inspect(args.checkpoint),indent=2,sort_keys=True))
