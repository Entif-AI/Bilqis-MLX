"""Reproduce an explicitly unratified historical sensitivity experiment.

Reads immutable exam receipts only. No student tensors or teacher policy are
loaded. Thresholds below are experimental comparisons, not runtime defaults.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bilqis_mlx.diagnostics.health_shadow import (
    ShadowContext, ShadowPhase, ShadowPolicy, replay_health_shadow,
)
from bilqis_mlx.diagnostics.observations import load_archived_exam_history


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--exam-grade", required=True)
    parser.add_argument("--active-grade", required=True)
    parser.add_argument("--phase", choices=[phase.value for phase in ShadowPhase], required=True)
    args = parser.parse_args(argv)
    history = load_archived_exam_history(args.run_dir, grade=args.exam_grade)
    if not history:
        parser.error("No committed examinations match the requested grade")
    required = tuple(cap.capability for cap in history[-1].capabilities)
    reports = []
    for drop, hysteresis in ((1, 2), (2, 2), (3, 3)):
        policy = ShadowPolicy("historical-replay-sensitivity", "source-only-v1",
                              max(3, hysteresis + 1), hysteresis, drop, 0, 1)
        result = replay_health_shadow(history, required_capabilities=required, policy=policy,
            context=ShadowContext(args.active_grade, ShadowPhase(args.phase)))
        reports.append({"score_drop": drop, "hysteresis": hysteresis,
            "policy_sha256": result.policy_digest, "lineage_sha256": result.lineage_sha256,
            "states": dict(Counter(item.state.value for item in result.by_capability.values())),
            "proposed_quarantine": result.proposed_quarantine,
            "required_capability_debt": result.required_capability_debt,
            "lineage_gap": result.lineage_gap,
            "alert_evidence_sha256": [alert.evidence_sha256 for alert in result.end_of_run_alerts]})
    def fingerprint(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    output = {"status": "READ_ONLY_HISTORICAL_SHADOW_EXPERIMENT", "observations": len(history),
        "first_optimizer_step": history[0].optimizer_step,
        "last_optimizer_step": history[-1].optimizer_step,
        "latest_student_sha256": history[-1].student_sha256,
        "event_ledger_sha256": fingerprint(args.run_dir / "events.jsonl"),
        "implementation_sha256": fingerprint(ROOT / "bilqis_mlx/diagnostics/health_shadow.py"),
        "procedure_sha256": fingerprint(Path(__file__)), "reports": reports,
        "thresholds": "EXPLORATORY_SENSITIVITY_ONLY_NOT_CALIBRATED_OR_RATIFIED",
        "causal_benefit": "NOT_MEASURED", "false_alerts_and_missed_failures": "NOT_MEASURED",
        "actual_neural_updates": 0, "actual_vetoes": 0, "actual_teacher_updates": 0}
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
