from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


def exception() -> dict[str, str]:
    return {
        "reason": "bounded transition",
        "authority": "owner instruction",
        "expires_when": "transition closes",
    }


def policy(
    *,
    grandfathered_prs: list[int] | None = None,
    non_implementation_exceptions: list[dict] | None = None,
    admission_exceptions: list[dict] | None = None,
) -> dict:
    return {
        "schema": "bilqis.bamf.flow-control-policy/v2",
        "normal_active_limit_per_lane": 6,
        "states": {
            "ACTIVE": {
                "counts_as_wip": True,
                "branch_mutation_allowed": True,
                "requires_resume_trigger": False,
            },
            "READY": {
                "counts_as_wip": False,
                "branch_mutation_allowed": False,
                "requires_resume_trigger": False,
            },
            "WAITING": {
                "counts_as_wip": False,
                "branch_mutation_allowed": False,
                "requires_resume_trigger": True,
            },
            "BLOCKED": {
                "counts_as_wip": False,
                "branch_mutation_allowed": False,
                "requires_resume_trigger": True,
            },
            "TURNED_IN": {
                "counts_as_wip": False,
                "branch_mutation_allowed": False,
                "requires_resume_trigger": False,
            },
        },
        "open_pr_inventory": {
            "normal_limit_total": 12,
            "unified_branch": "unified",
            "grandfathered_prs": grandfathered_prs or [],
            "non_implementation_exceptions": non_implementation_exceptions or [],
            "admission_exceptions": admission_exceptions or [],
        },
        "rules": {
            "over_limit_exception_required_fields": [
                "reason",
                "authority",
                "expires_when",
            ],
            "open_pr_exception_required_fields": [
                "reason",
                "authority",
                "expires_when",
            ],
            "inventory_exception_required_fields": [
                "reason",
                "authority",
                "expires_when",
            ],
        },
    }


def lane(name: str, items: list[dict], exception=None) -> dict:
    return {
        "schema": "bilqis.bamf.flow-control-lane/v1",
        "lane": name,
        "updated_at": "2026-11-02T05:10:00Z",
        "exception": exception,
        "items": items,
    }


def active(issue: int, pr_number: int) -> dict:
    return {
        "issue": issue,
        "pr": pr_number,
        "state": "ACTIVE",
        "resume_trigger": None,
    }


def waiting(
    issue: int,
    pr_number: int,
    *,
    open_pr_exception: dict | None = None,
) -> dict:
    item = {
        "issue": issue,
        "pr": pr_number,
        "state": "WAITING",
        "resume_trigger": "dependency accepted",
    }
    if open_pr_exception is not None:
        item["open_pr_exception"] = open_pr_exception
    return item


def pr(number: int, *, head: str, base: str) -> dict:
    return {
        "number": number,
        "head": {"ref": head},
        "base": {"ref": base},
    }


class FixtureMixin(unittest.TestCase):
    def write_fixture(
        self,
        lanes: dict[str, dict],
        *,
        policy_value: dict | None = None,
    ) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / "policy.json").write_text(
            json.dumps(policy_value or policy()), encoding="utf-8"
        )
        for name in ("A", "B", "C"):
            (root / f"lane-{name.lower()}.json").write_text(
                json.dumps(lanes[name]), encoding="utf-8"
            )
        return root
