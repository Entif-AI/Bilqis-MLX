"""Live GitHub reconciliation for BAMF-0.2 PR inventory."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

if __package__:
    from scripts.bamf_flow_control_core import (
        DEFAULT_DIR,
        FlowControlError,
        validated_state,
    )
else:
    from bamf_flow_control_core import DEFAULT_DIR, FlowControlError, validated_state


def exception_matches(pr: dict[str, Any], exception: dict[str, Any]) -> bool:
    number = pr.get("number")
    head = pr.get("head", {}).get("ref")
    return exception.get("pr") == number or exception.get("head_branch") == head


def managed_prs(
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
    summaries, policy, tracked_prs = validated_state(base_dir)
    inventory = policy["open_pr_inventory"]
    limit = inventory["normal_limit_total"]
    grandfathered = set(inventory.get("grandfathered_prs", []))
    non_impl = inventory.get("non_implementation_exceptions", [])
    admission_exceptions = inventory.get("admission_exceptions", [])

    managed = managed_prs(open_prs, inventory["unified_branch"])
    implementation = [
        pr
        for pr in managed
        if not any(exception_matches(pr, exception) for exception in non_impl)
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
        unadmitted = [
            pr["number"]
            for pr in implementation
            if pr["number"] not in grandfathered
            and not any(
                exception_matches(pr, exception)
                for exception in admission_exceptions
            )
        ]
        if unadmitted:
            raise FlowControlError(
                "DRAIN active: new implementation PR admission is not authorized: "
                + ", ".join(f"#{number}" for number in sorted(unadmitted))
            )

    summaries.append(
        f"Integration inventory: OPEN {len(open_numbers)}/{limit}; "
        f"mode {'DRAIN' if drain else 'NORMAL'}"
    )
    return summaries


def fetch_open_prs(repository: str, token: str | None = None) -> list[dict[str, Any]]:
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


def validate_live_from_environment(
    repository: str | None = None,
    base_dir: Path = DEFAULT_DIR,
) -> list[str]:
    target = repository or os.environ.get("GITHUB_REPOSITORY", "Entif-AI/Bilqis-MLX")
    return validate_live_pr_inventory(
        fetch_open_prs(target, os.environ.get("GITHUB_TOKEN")),
        base_dir,
    )
