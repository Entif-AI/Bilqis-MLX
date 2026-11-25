"""Source overlap and optional measured gradient/displacement diagnostics.

Source geometry is not learned representation geometry. A missing measurement
remains null, and a gradient dot product is a local prediction, not retention.
"""
import argparse
from collections import Counter
from itertools import combinations
import json
from pathlib import Path

from scripts.bamf.profiling.issue1645.reservation import CAPABILITIES, digest, prepare


def source_geometry(prepared):
    reservation = prepare(prepared)
    groups = {cap: [] for cap in CAPABILITIES}
    for entry in prepared["prospective"]["rows"]:
        row = entry["row"]
        groups[row["capability"]].append(row)
    worlds = {cap: {digest(row["record"]["world"]) for row in rows}
              for cap, rows in groups.items()}
    families = {cap: {row["source_family_id"] for row in rows}
                for cap, rows in groups.items()}
    pairs = []
    for left, right in combinations(CAPABILITIES, 2):
        pairs.append({"left": left, "right": right,
                      "exact_world_overlap": len(worlds[left] & worlds[right]),
                      "source_family_overlap": len(families[left] & families[right])})
    return {
        "reservation_sha256": reservation["reservation_sha256"],
        "source": {cap: {
            "rows": len(rows), "worlds": len(worlds[cap]),
            "families": len(families[cap]),
            "token_lengths": dict(Counter(len(row["tokens"]) for row in rows)),
            "universe_sizes": dict(Counter(row["universe_size"] for row in rows)),
        } for cap, rows in groups.items()},
        "pairs": pairs,
        "learned_representation_geometry": None,
        "architectural_attainability": None,
        "generalization": None,
    }


def interference(gradients, displacements):
    """Aligned, measured per-capability vectors on the same parameter basis."""
    import numpy as np

    result = {}
    for target in CAPABILITIES:
        for protected in CAPABILITIES:
            key = f"{target}->{protected}"
            if target not in displacements or protected not in gradients:
                result[key] = None
                continue
            step = np.asarray(displacements[target], dtype=np.float64)
            gradient = np.asarray(gradients[protected], dtype=np.float64)
            if (step.ndim != 1 or step.shape != gradient.shape or not step.size
                    or not np.all(np.isfinite(step)) or not np.all(np.isfinite(gradient))):
                raise ValueError("unmatched or nonfinite parameter basis")
            result[key] = float(np.dot(gradient, step))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    args = parser.parse_args()
    print(json.dumps(source_geometry(json.loads(args.prepared.read_text())), indent=2))


if __name__ == "__main__":
    main()
