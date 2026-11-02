"""Static BAMF-0.2 flow-control policy and lane validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "docs" / "tasks" / "bamf-0.2" / "flow-control"


class FlowControlError(ValueError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FlowControlError(f"missing flow-control file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise FlowControlError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise FlowControlError(f"{path} must contain a JSON object")
    return value


def require_exception(
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
        raise FlowControlError(f"{context}: exception missing {', '.join(missing)}")
    return value


def policy_contract(
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
            require_exception(
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


def _valid_sha(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(char in "0123456789abcdef" for char in value.lower())
    )


def validate_item(
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
        if not _valid_sha(item.get("head_sha")):
            raise FlowControlError(
                f"{prefix}: open PR #{pr} requires an exact 40-character head_sha"
            )

    state = item.get("state")
    if state not in states:
        raise FlowControlError(f"{prefix}: unknown state {state!r}")
    state_policy = states[state]
    if state_policy.get("requires_resume_trigger") is True:
        trigger = item.get("resume_trigger")
        if not isinstance(trigger, str) or not trigger.strip():
            raise FlowControlError(
                f"{prefix}: {state} requires a non-empty resume_trigger"
            )
    if state != "ACTIVE" and state_policy.get("branch_mutation_allowed") is True:
        raise FlowControlError(f"{prefix}: only ACTIVE may permit branch mutation")

    if state in {"WAITING", "BLOCKED"} and pr not in (None, *grandfathered_prs):
        require_exception(
            item.get("open_pr_exception"),
            open_pr_required_fields,
            f"{prefix}: non-grandfathered open {state} PR #{pr}",
        )
    return state_policy.get("counts_as_wip") is True


def validated_state(
    base_dir: Path = DEFAULT_DIR,
) -> tuple[list[str], dict[str, Any], dict[int, str]]:
    policy = load_json(base_dir / "policy.json")
    states, limit, required_fields, inventory = policy_contract(policy)
    rules = policy["rules"]
    open_required = rules.get("open_pr_exception_required_fields", [])
    if not isinstance(open_required, list):
        raise FlowControlError("open PR exception field list must be a list")
    grandfathered = set(inventory.get("grandfathered_prs", []))

    summaries: list[str] = []
    seen_prs: set[int] = set()
    tracked_heads: dict[int, str] = {}
    for lane in ("A", "B", "C"):
        data = load_json(base_dir / f"lane-{lane.lower()}.json")
        if data.get("schema") != "bilqis.bamf.flow-control-lane/v1":
            raise FlowControlError(f"Lane {lane}: wrong lane schema")
        if data.get("lane") != lane:
            raise FlowControlError(f"Lane {lane}: lane field must equal {lane}")
        if not isinstance(data.get("updated_at"), str) or not data["updated_at"].strip():
            raise FlowControlError(f"Lane {lane}: updated_at is required")
        items = data.get("items")
        if not isinstance(items, list):
            raise FlowControlError(f"Lane {lane}: items must be a list")

        active = sum(
            validate_item(
                lane,
                index,
                item,
                states,
                seen_prs,
                grandfathered,
                open_required,
            )
            for index, item in enumerate(items)
        )
        if active > limit:
            require_exception(
                data.get("exception"),
                required_fields,
                f"Lane {lane}: {active} ACTIVE items exceed normal limit {limit}",
            )
        summaries.append(f"Lane {lane}: ACTIVE {active}/{limit}; tracked {len(items)}")
        for item in items:
            if item.get("pr") is not None:
                tracked_heads[item["pr"]] = item["head_sha"]
    return summaries, policy, tracked_heads


def validate_flow_control(base_dir: Path = DEFAULT_DIR) -> list[str]:
    summaries, _, _ = validated_state(base_dir)
    return summaries
