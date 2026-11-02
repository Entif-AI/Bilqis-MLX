#!/usr/bin/env python3
"""Validate BAMF-0.2 lane flow-control state.

This checker enforces repository-visible flow-control invariants. It cannot observe
an agent merely reading a branch or a remote PR changing outside the checked files,
so AGENTS.md still requires operators to update lane state before mutation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "docs" / "tasks" / "bamf-0.2" / "flow-control"


class FlowControlError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FlowControlError(f"missing flow-control file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise FlowControlError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise FlowControlError(f"{path} must contain a JSON object")
    return value


def validate_flow_control(base_dir: Path = DEFAULT_DIR) -> list[str]:
    policy = _load(base_dir / "policy.json")
    if policy.get("schema") != "bilqis.bamf.flow-control-policy/v1":
        raise FlowControlError("policy schema must be bilqis.bamf.flow-control-policy/v1")

    states = policy.get("states")
    if not isinstance(states, dict) or not states:
        raise FlowControlError("policy.states must be a non-empty object")
    limit = policy.get("normal_active_limit_per_lane")
    if not isinstance(limit, int) or limit < 1:
        raise FlowControlError("normal_active_limit_per_lane must be a positive integer")

    required_exception_fields = (
        policy.get("rules", {}).get("over_limit_exception_required_fields", [])
    )
    summaries: list[str] = []
    seen_prs: set[int] = set()

    for lane in ("A", "B", "C"):
        data = _load(base_dir / f"lane-{lane.lower()}.json")
        if data.get("schema") != "bilqis.bamf.flow-control-lane/v1":
            raise FlowControlError(f"Lane {lane}: wrong lane schema")
        if data.get("lane") != lane:
            raise FlowControlError(f"Lane {lane}: lane field must equal {lane}")
        if not isinstance(data.get("updated_at"), str) or not data["updated_at"].strip():
            raise FlowControlError(f"Lane {lane}: updated_at is required")

        items = data.get("items")
        if not isinstance(items, list):
            raise FlowControlError(f"Lane {lane}: items must be a list")

        active = 0
        for index, item in enumerate(items):
            prefix = f"Lane {lane} item {index}"
            if not isinstance(item, dict):
                raise FlowControlError(f"{prefix}: item must be an object")
            issue = item.get("issue")
            pr = item.get("pr")
            state = item.get("state")
            trigger = item.get("resume_trigger")

            if not isinstance(issue, int) or issue <= 0:
                raise FlowControlError(f"{prefix}: issue must be a positive integer")
            if pr is not None:
                if not isinstance(pr, int) or pr <= 0:
                    raise FlowControlError(f"{prefix}: pr must be null or a positive integer")
                if pr in seen_prs:
                    raise FlowControlError(f"{prefix}: duplicate PR #{pr}")
                seen_prs.add(pr)
            if state not in states:
                raise FlowControlError(f"{prefix}: unknown state {state!r}")

            state_policy = states[state]
            if state_policy.get("counts_as_wip") is True:
                active += 1
            if state_policy.get("requires_resume_trigger") is True:
                if not isinstance(trigger, str) or not trigger.strip():
                    raise FlowControlError(
                        f"{prefix}: {state} requires a non-empty resume_trigger"
                    )
            if state != "ACTIVE" and state_policy.get("branch_mutation_allowed") is True:
                raise FlowControlError(
                    f"{prefix}: only ACTIVE may permit branch mutation"
                )

        exception = data.get("exception")
        if active > limit:
            if not isinstance(exception, dict):
                raise FlowControlError(
                    f"Lane {lane}: {active} ACTIVE items exceed normal limit {limit} "
                    "without an explicit exception"
                )
            missing = [
                field
                for field in required_exception_fields
                if not isinstance(exception.get(field), str)
                or not exception[field].strip()
            ]
            if missing:
                raise FlowControlError(
                    f"Lane {lane}: over-limit exception missing {', '.join(missing)}"
                )
        summaries.append(f"Lane {lane}: ACTIVE {active}/{limit}; tracked {len(items)}")

    return summaries


def main() -> int:
    try:
        summaries = validate_flow_control()
    except FlowControlError as exc:
        print(f"BAMF_FLOW_CONTROL_FAIL: {exc}", file=sys.stderr)
        return 1
    print("BAMF_FLOW_CONTROL_OK")
    for summary in summaries:
        print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
