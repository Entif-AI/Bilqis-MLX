"""Read-only receipt/observer analysis. Unknown timing is never estimated."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
from statistics import median

from bilqis_mlx.control_plane.native_custody import authenticated_history
from bilqis_mlx.control_plane.native_rejections import _verified_rejection


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def summarize(values):
    values = sorted(values)
    return {"count": len(values), "p50": median(values) if values else None,
            "p95": values[math.ceil(len(values)*.95)-1] if values else None}


def stop_suffix(root):
    ledger_hash = hashlib.sha256()
    pending, last = [], None
    with (root / "events.jsonl").open("rb") as f:
        for line in f:
            ledger_hash.update(line)
            row = json.loads(line)
            kind = row.get("event")
            if kind == "BAMF_CANDIDATE_REJECTED":
                pending.append(row)
            elif kind == "BAMF_RUN_STOPPED":
                last = (row, pending)
                pending = []
    return last, ledger_hash.hexdigest()


def verified_suffix(last, by_digest):
    stop_event, preceding = last
    stop = stop_event["run_stop_receipt"]
    assert stop["receipt_sha256"] == stop_event["receipt_sha256"]
    from bilqis_mlx.runtime.bamf_operator.session_parts.stop_receipt import _canonical
    assert sha(_canonical({k:v for k,v in stop.items() if k != "receipt_sha256"}).encode()) == stop["receipt_sha256"]
    # Stop receipt count is a terminal suffix, not a start boundary.
    n = stop["rejected_visits"]
    rows = preceding[-n:] if n else []
    assert len(rows) == n
    verified = []
    for row in rows:
        v = _verified_rejection(row, by_digest[row["student_manifest_sha256"]])
        assert v is not None and v[-1]
        verified.append(v[3])
    visits = {e["visit_id"]: e for e in verified}
    assert len({r["event_id"] for r in rows}) == n
    duplicate_visit_ids = n-len(visits)
    steps = sum(e["candidate_optimizer_step"] - e["retained_optimizer_step"] for e in verified)
    return stop, preceding, rows, verified, visits, duplicate_visit_ids, steps


def analyze(root):
    pointer = (root / "bamf-state.json").read_bytes()
    generations = authenticated_history(root)
    by_digest = {g.manifest_sha256: g for g in generations}
    last, ledger_digest = stop_suffix(root)
    stop, preceding, rows, verified, visits, duplicate_visit_ids, steps = verified_suffix(last, by_digest)
    n = len(rows)
    raw = (root/"trainer-observed.json").read_bytes()
    observed = json.loads(raw)["visits"]
    matched = [v for v in observed if v.get("visit_id") in visits and v["outcome"] == "REJECTED"]
    for v in matched:
        e = visits[v["visit_id"]]
        assert v["candidate_step"] == e["candidate_optimizer_step"]-e["retained_optimizer_step"]
    assessment = [v["retention_wall_seconds"] for v in matched if v.get("retention_wall_seconds") is not None]
    elapsed = stop["elapsed_seconds"]
    result = {"source_pointer_sha256": sha(pointer), "ledger_sha256": ledger_digest,
              "observer_sha256": sha(raw), "stop": stop, "earlier_unassigned_rejections": len(preceding)-n,
              "suffix_binding": "portable authenticated rejections; terminal count match, explicit start absent",
              "attempted_steps": steps, "attempted_steps_per_minute": 60*steps/elapsed,
              "retained_steps_per_minute": 0 if stop["accepted_visits"] == 0 else None,
              "authenticated_rejections": n, "duplicate_visit_ids": duplicate_visit_ids, "horizons": dict(Counter(e["candidate_optimizer_step"]-e["retained_optimizer_step"] for e in verified)),
              "matched_observer_rows": len(matched), "visit_seconds": summarize([v["elapsed_ms"]/1000 for v in matched]),
              "assessment_seconds": summarize(assessment),
              "candidate_evaluations_per_minute": None,
              "independent_retained_competence_per_minute": None,
              "peak_rss_bytes": max((v["peak_rss_bytes"] for v in matched if v.get("peak_rss_bytes") is not None), default=None),
              "swap_bytes": None, "accepted_generation_implementation_sha256": generations[-1].manifest.get("implementation_sha256"),
              "actual_training_executable_identity": None,
              "receipt_sha256": stop.get("receipt_sha256"),
              "event_ids": [r["event_id"] for r in rows]}
    assert pointer == (root/"bamf-state.json").read_bytes()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze(args.run), indent=2))
