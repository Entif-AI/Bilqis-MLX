#!/usr/bin/env python3
"""Validate BAMF-0.2 lane flow control and optional live PR inventory."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
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


def _require_exception(
    value: Any,
    required_fields: list[str],
    context: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FlowControlError(f"{context}: explicit exception is required")
    missing = [
        field
        for field in required_fields
        if not isinstance(value.get(field), str) or not value[field].strip()
    ]
    if missing:
        raise FlowControlError(
            f"{context}: exception missing {', '.join(missing)}"
        )
    return value


def _policy_contract(
    policy: dict[str, Any],
) -> tuple[dict[str, Any], int, list[str], dict[str, Any]]:
    if policy.get("schema") != "bilqis.bamf.flow-control-policy/v2":
        raise FlowControlError("policy schema must be bilqis.bamf.flow-control-policy/v2")

    states = policy.get("states")
    if not isinstance(states, dict) or not states:
        raise FlowControlError("policy.states must be a non-empty object")

    active_limit = policy.get("normal_active_limit_per_lane")
    if not isinstance(active_limit, int) or active_limit < 1:
        raise FlowControlError("normal_active_limit_per_lane must be a positive integer")

    rules = policy.get("rules")
    if not isinstance(rules, dict):
        raise FlowControlError("policy.rules must be an object")

    required = rules.get("over_limit_exception_required_fields", [])
    if not isinstance(required, list):
        raise FlowControlError("over-limit exception field list must be a list")

    inventory = policy.get("open_pr_inventory")
    if not isinstance(inventory, dict):
        raise FlowControlError("policy.open_pr_inventory must be an object")
    inventory_limit = inventory.get("normal_limit_total")
    if not isinstance(inventory_limit, int) or inventory_limit < 1:
        raise FlowControlError(
            "open_pr_inventory.normal_limit_total must be a positive integer"
        )
    unified_branch = inventory.get("unified_branch")
    if not isinstance(unified_branch, str) or not unified_branch.strip():
        raise FlowControlError("open_pr_inventory.unified_branch is required")

    grandfathered = inventory.get("grandfathered_prs", [])
    if (
        not isinstance(grandfathered, list)
        or any(not isinstance(number, int) or number <= 0 for number in grandfathered)
        or len(set(grandfathered)) != len(grandfathered)
    ):
        raise FlowControlError(
            "open_pr_inventory.grandfathered_prs must contain unique positive integers"
        )

    inventory_required = rules.get("inventory_exception_required_fields", [])
    if not isinstance(inventory_required, list):
        raise FlowControlError("inventory exception field list must be a list")

    for name in ("non_implementation_exceptions", "admission_exceptions"):
        exceptions = inventory.get(name, [])
        if not isinstance(exceptions, list):
            raise FlowControlError(f"open_pr_inventory.{name} must be a list")
        for index, exception in enumerate(exceptions):
            _require_exception(
                exception,
                inventory_required,
                f"open_pr_inventory.{name}[{index}]",
            )
            pr = exception.get("pr")
            head = exception.get("head_branch")
            if pr is None and not (isinstance(head, str) and head.strip()):
                raise FlowControlError(
                    f"open_pr_inventory.{name}[{index}]: pr or head_branch is required"
                )
            if pr is not None and (not isinstance(pr, int) or pr <= 0):
                raise FlowControlError(
                    f"open_pr_inventory.{name}[{index}].pr must be a positive integer"
                )

    return states, active_limit, required, inventory


def _validate_item(
    lane: str,
    index: int,
    item: Any,
    states: dict[str, Any],
    seen_prs: set[int],
    grandfathered_prs: set[int],
    open_pr_required_fields: list[str],
) -> bool:
    prefix = f"Lane {lane} item {index}"
    if not isinstance(item, dict):
        raise FlowControlError(f"{prefix}: item must be an object")

    issue = item.get("issue")
    if not isinstance(issue, int) or issue <= 0:
        raise FlowControlError(f"{prefix}: issue must be a positive integer")

    pr = item.get("pr")
    if pr is not None:
        if not isinstance(pr, int) or pr <= 0:
            raise FlowControlError(f"{prefix}: pr must be null or a positive integer")
        if pr in seen_prs:
            raise FlowControlError(f"{prefix}: duplicate PR #{pr}")
        seen_prs.add(pr)

    state = item.get("state")
    if state not in states:
        raise FlowControlError(f"{prefix}: unknown state {state!r}")
    state_policy = states[state]
    if not isinstance(state_policy, dict):
        raise FlowControlError(f"{prefix}: state policy must be an object")

    if state_policy.get("requires_resume_trigger") is True:
        trigger = item.get("resume_trigger")
        if not isinstance(trigger, str) or not trigger.strip():
            raise FlowControlError(
                f"{prefix}: {state} requires a non-empty resume_trigger"
            )

    if state != "ACTIVE" and state_policy.get("branch_mutation_allowed") is True:
        raise FlowControlError(f"{prefix}: only ACTIVE may permit branch mutation")

    if (
        state in {"WAITING", "BLOCKED"}
        and pr is not None
        and pr not in grandfathered_prs
    ):
        _require_exception(
            item.get("open_pr_exception"),
            open_pr_required_fields,
            f"{prefix}: non-grandfathered open {state} PR #{pr}",
        )

    return state_policy.get("counts_as_wip") is True


def _validate_lane(
    lane: str,
    data: dict[str, Any],
    states: dict[str, Any],
    seen_prs: set[int],
    grandfathered_prs: set[int],
    open_pr_required_fields: list[str],
) -> tuple[int, int]:
    if data.get("schema") != "bilqis.bamf.flow-control-lane/v1":
        raise FlowControlError(f"Lane {lane}: wrong lane schema")
    if data.get("lane") != lane:
        raise FlowControlError(f"Lane {lane}: lane field must equal {lane}")
    updated_at = data.get("updated_at")
    if not isinstance(updated_at, str) or not updated_at.strip():
        raise FlowControlError(f"Lane {lane}: updated_at is required")

    items = data.get("items")
    if not isinstance(items, list):
        raise FlowControlError(f"Lane {lane}: items must be a list")
    active = sum(
        _validate_item(
            lane,
            index,
            item,
            states,
            seen_prs,
            grandfathered_prs,
            open_pr_required_fields,
        )
        for index, item in enumerate(items)
    )
    return active, len(items)


def _validate_over_limit(
    lane: str,
    active: int,
    limit: int,
    exception: Any,
    required_fields: list[str],
) -> None:
    if active <= limit:
        return
    _require_exception(
        exception,
        required_fields,
        f"Lane {lane}: {active} ACTIVE items exceed normal limit {limit}",
    )


def _validated_state(
    base_dir: Path = DEFAULT_DIR,
) -> tuple[list[str], dict[str, Any], set[int]]:
    policy = _load(base_dir / "policy.json")
    states, limit, required_fields, inventory = _policy_contract(policy)
    rules = policy["rules"]
    open_pr_required_fields = rules.get("open_pr_exception_required_fields", [])
    if not isinstance(open_pr_required_fields, list):
        raise FlowControlError("open PR exception field list must be a list")
    grandfathered_prs = set(inventory.get("grandfathered_prs", []))

    summaries: list[str] = []
    seen_prs: set[int] = set()

    for lane in ("A", "B", "C"):
        data = _load(base_dir / f"lane-{lane.lower()}.json")
        active, tracked = _validate_lane(
            lane,
            data,
            states,
            seen_prs,
            grandfathered_prs,
            open_pr_required_fields,
        )
        _validate_over_limit(
            lane, active, limit, data.get("exception"), required_fields
        )
        summaries.append(f"Lane {lane}: ACTIVE {active}/{limit}; tracked {tracked}")

    return summaries, policy, seen_prs


def validate_flow_control(base_dir: Path = DEFAULT_DIR) -> list[str]:
    summaries, _, _ = _validated_state(base_dir)
    return summaries


def _exception_matches(pr: dict[str, Any], exception: dict[str, Any]) -> bool:
    number = pr.get("number")
    head = pr.get("head", {}).get("ref")
    return (
        exception.get("pr") == number
        or (
            isinstance(exception.get("head_branch"), str)
            and exception["head_branch"] == head
        )
    )


def _managed_prs(
    open_prs: list[dict[str, Any]],
    unified_branch: str,
) -> list[dict[str, Any]]:
    managed_numbers: set[int] = set()
    frontier = [
        pr for pr in open_prs if pr.get("base", {}).get("ref") == unified_branch
    ]

    while frontier:
        pr = frontier.pop()
        number = pr.get("number")
        if not isinstance(number, int) or number in managed_numbers:
            continue
        managed_numbers.add(number)
        head = pr.get("head", {}).get("ref")
        if not isinstance(head, str):
            continue
        frontier.extend(
            child
            for child in open_prs
            if child.get("base", {}).get("ref") == head
            and child.get("number") not in managed_numbers
        )

    return [pr for pr in open_prs if pr.get("number") in managed_numbers]


def validate_live_pr_inventory(
    open_prs: list[dict[str, Any]],
    base_dir: Path = DEFAULT_DIR,
) -> list[str]:
    summaries, policy, tracked_prs = _validated_state(base_dir)
    inventory = policy["open_pr_inventory"]
    limit = inventory["normal_limit_total"]
    grandfathered = set(inventory.get("grandfathered_prs", []))
    non_impl = inventory.get("non_implementation_exceptions", [])
    admission_exceptions = inventory.get("admission_exceptions", [])

    managed = _managed_prs(open_prs, inventory["unified_branch"])
    implementation = [
        pr
        for pr in managed
        if not any(_exception_matches(pr, exception) for exception in non_impl)
    ]

    open_numbers = {
        pr["number"] for pr in implementation if isinstance(pr.get("number"), int)
    }
    missing = sorted(open_numbers - tracked_prs)
    stale = sorted(tracked_prs - open_numbers)
    if missing:
        raise FlowControlError(
            "live open BAMF implementation PRs missing from flow-control ledger: "
            + ", ".join(f"#{number}" for number in missing)
        )
    if stale:
        raise FlowControlError(
            "flow-control ledger retains PRs that are not live BAMF implementation "
            "inventory: " + ", ".join(f"#{number}" for number in stale)
        )

    drain = len(open_numbers) > limit
    if drain:
        unadmitted = []
        for pr in implementation:
            number = pr["number"]
            if number in grandfathered:
                continue
            if any(_exception_matches(pr, exception) for exception in admission_exceptions):
                continue
            unadmitted.append(number)
        if unadmitted:
            raise FlowControlError(
                "DRAIN active: new implementation PR admission is not authorized: "
                + ", ".join(f"#{number}" for number in sorted(unadmitted))
            )

    mode = "DRAIN" if drain else "NORMAL"
    summaries.append(
        f"Integration inventory: OPEN {len(open_numbers)}/{limit}; mode {mode}"
    )
    return summaries


def _fetch_open_prs(repository: str, token: str | None) -> list[dict[str, Any]]:
    page = 1
    results: list[dict[str, Any]] = []
    while True:
        url = (
            f"https://api.github.com/repos/{repository}/pulls"
            f"?state=open&per_page=100&page={page}"
        )
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "bilqis-bamf-flow-control",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                batch = json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise FlowControlError(f"live GitHub PR read failed: {exc}") from exc
        if not isinstance(batch, list):
            raise FlowControlError("live GitHub PR response must be a list")
        results.extend(batch)
        if len(batch) < 100:
            return results
        page += 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live",
        action="store_true",
        help="reconcile the repository ledger against live GitHub open PR state",
    )
    parser.add_argument(
        "--repository",
        default=os.environ.get("GITHUB_REPOSITORY", "Entif-AI/Bilqis-MLX"),
    )
    parser.add_argument(
        "--live-json",
        type=Path,
        help="test-only path containing a GitHub open-PR JSON array",
    )
    args = parser.parse_args()

    try:
        if args.live_json is not None:
            open_prs = json.loads(args.live_json.read_text(encoding="utf-8"))
            if not isinstance(open_prs, list):
                raise FlowControlError("--live-json must contain a JSON array")
            summaries = validate_live_pr_inventory(open_prs)
        elif args.live:
            summaries = validate_live_pr_inventory(
                _fetch_open_prs(args.repository, os.environ.get("GITHUB_TOKEN"))
            )
        else:
            summaries = validate_flow_control()
    except (FlowControlError, OSError, json.JSONDecodeError) as exc:
        print(f"BAMF_FLOW_CONTROL_FAIL: {exc}", file=sys.stderr)
        return 1

    print("BAMF_FLOW_CONTROL_OK")
    for summary in summaries:
        print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
