"""Read-only replay of the historical B false-mastery governing failure.

This script requires the local forensic run bundle; it never writes model state
or calls an optimizer. Portable CI uses the compact replay receipt fixture.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import mlx.core as mx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bilqis_mlx.trainer import _predictions
from bilqis_mlx.mlx_checkpoint import load_semantically_bound_bundle


PROMOTION = "1888c7d27ddfe7f7a8679d84328fc7b0a180e7b942963998e9c6c42784403da7"
FRESH = "e2550b8b950f57b7ff60d08e897e1506119571dd5018cc052075ec53aa2dbeae"
CHECKPOINT = "e65d62174b7c9681991d27e3e2a424358f38dceeb50c90544803bc94d7546585"


def replay(run: Path) -> dict:
    state = json.loads((run / "states/0006824.json").read_text())
    parameters, _, manifest, _ = load_semantically_bound_bundle(run / state["model_bundle"])
    if manifest["safetensors_sha256"] != CHECKPOINT:
        raise ValueError("HISTORICAL_B_CHECKPOINT_DRIFT")
    result = {"checkpoint_sha256": CHECKPOINT,
              "optimizer_step": manifest["optimizer_step"], "cohorts": {}}
    for digest in (PROMOTION, FRESH):
        stored = json.loads((run / "cohorts" / (digest + ".json")).read_text())
        rows = [row for row in stored["rows"]
                if row["capability"].startswith(("A.", "B."))]
        guesses = _predictions(mx, parameters, rows, state["config"], state["answer_ids"])
        scores = {}
        for grade in ("A", "B"):
            selected = [row for row in rows if row["capability"].startswith(grade + ".")]
            scores[grade] = {
                "correct": sum(guesses[row["id"]] == row["gold"] for row in selected),
                "total": len(selected),
            }
        result["cohorts"][digest] = scores
    return result


if __name__ == "__main__":
    root = Path("runs/issue-340-mentor-epoch-trial")
    observed = replay(root)
    familiar = observed["cohorts"][PROMOTION]
    fresh = observed["cohorts"][FRESH]
    if familiar != {"A": {"correct": 72, "total": 72},
                    "B": {"correct": 72, "total": 72}}:
        raise SystemExit("HISTORICAL_B_FAMILIAR_REPLAY_DRIFT")
    if fresh != {"A": {"correct": 71, "total": 72},
                 "B": {"correct": 47, "total": 72}}:
        raise SystemExit("HISTORICAL_B_FRESH_REPLAY_DRIFT")
    print(json.dumps(observed, sort_keys=True))
