from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_bamf_flow_control import (
    FlowControlError,
    validate_flow_control,
    validate_live_pr_inventory,
)


def policy(
    *,
    grandfathered_prs: list[int] | None = None,
    non_implementation_exceptions: list[dict] | None = None,
    admission_exceptions: list[dict] | None = None,
) -> dict:
    return {
        "schema": "bilqis.bamf.flow-control-policy/v2",
        "normal_active_limit_per_lane": 2,
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
            "normal_limit_total": 3,
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


def sha_for(pr_number: int) -> str:
    return f"{pr_number:040x}"[-40:]


def active(issue: int, pr: int) -> dict:
    return {
        "issue": issue,
        "pr": pr,
        "state": "ACTIVE",
        "head_sha": sha_for(pr),
        "resume_trigger": None,
    }


def waiting(
    issue: int,
    pr: int,
    *,
    open_pr_exception: dict | None = None,
) -> dict:
    item = {
        "issue": issue,
        "pr": pr,
        "state": "WAITING",
        "head_sha": sha_for(pr),
        "resume_trigger": "dependency accepted",
    }
    if open_pr_exception is not None:
        item["open_pr_exception"] = open_pr_exception
    return item


def pr(
    number: int,
    *,
    head: str,
    base: str,
) -> dict:
    return {
        "number": number,
        "head": {"ref": head, "sha": sha_for(number)},
        "base": {"ref": base},
    }


EXCEPTION = {
    "reason": "bounded transition",
    "authority": "owner instruction",
    "expires_when": "transition closes",
}


class BamfFlowControlTests(unittest.TestCase):
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

    def test_waiting_requires_resume_trigger(self) -> None:
        item = waiting(1, 10, open_pr_exception=EXCEPTION)
        item["resume_trigger"] = ""
        root = self.write_fixture(
            {"A": lane("A", [item]), "B": lane("B", []), "C": lane("C", [])}
        )
        with self.assertRaisesRegex(
            FlowControlError, "requires a non-empty resume_trigger"
        ):
            validate_flow_control(root)

    def test_non_grandfathered_waiting_open_pr_requires_exception(self) -> None:
        root = self.write_fixture(
            {
                "A": lane("A", [waiting(1, 10)]),
                "B": lane("B", []),
                "C": lane("C", []),
            }
        )
        with self.assertRaisesRegex(FlowControlError, "explicit exception is required"):
            validate_flow_control(root)

    def test_grandfathered_waiting_pr_needs_no_retention_exception(self) -> None:
        root = self.write_fixture(
            {
                "A": lane("A", [waiting(1, 10)]),
                "B": lane("B", []),
                "C": lane("C", []),
            },
            policy_value=policy(grandfathered_prs=[10]),
        )
        summaries = validate_flow_control(root)
        self.assertIn("Lane A: ACTIVE 0/2; tracked 1", summaries)

    def test_normal_limit_rejects_third_active_item(self) -> None:
        root = self.write_fixture(
            {
                "A": lane("A", [active(1, 11), active(2, 12), active(3, 13)]),
                "B": lane("B", []),
                "C": lane("C", []),
            }
        )
        with self.assertRaisesRegex(FlowControlError, "exceed normal limit"):
            validate_flow_control(root)

    def test_explicit_exception_allows_over_limit(self) -> None:
        root = self.write_fixture(
            {
                "A": lane(
                    "A",
                    [active(1, 11), active(2, 12), active(3, 13)],
                    EXCEPTION,
                ),
                "B": lane("B", []),
                "C": lane("C", []),
            }
        )
        summaries = validate_flow_control(root)
        self.assertIn("Lane A: ACTIVE 3/2; tracked 3", summaries)

    def test_live_reconciliation_rejects_untracked_open_pr(self) -> None:
        root = self.write_fixture(
            {"A": lane("A", []), "B": lane("B", []), "C": lane("C", [])}
        )
        with self.assertRaisesRegex(FlowControlError, "missing from flow-control ledger"):
            validate_live_pr_inventory(
                [pr(10, head="a", base="unified")],
                root,
            )

    def test_live_reconciliation_rejects_head_drift(self) -> None:
        root = self.write_fixture(
            {
                "A": lane("A", [active(1, 10)]),
                "B": lane("B", []),
                "C": lane("C", []),
            }
        )
        live = pr(10, head="a", base="unified")
        live["head"]["sha"] = "f" * 40
        with self.assertRaisesRegex(FlowControlError, "head_sha does not match"):
            validate_live_pr_inventory([live], root)

    def test_live_reconciliation_rejects_stale_tracked_pr(self) -> None:
        root = self.write_fixture(
            {
                "A": lane("A", [active(1, 10)]),
                "B": lane("B", []),
                "C": lane("C", []),
            }
        )
        with self.assertRaisesRegex(FlowControlError, "retains PRs"):
            validate_live_pr_inventory([], root)

    def test_drain_allows_only_grandfathered_existing_inventory(self) -> None:
        prs = [
            pr(10, head="a", base="unified"),
            pr(11, head="b", base="unified"),
            pr(12, head="c", base="unified"),
            pr(13, head="d", base="unified"),
        ]
        root = self.write_fixture(
            {
                "A": lane("A", [active(1, 10), active(2, 11)]),
                "B": lane("B", [active(3, 12), active(4, 13)]),
                "C": lane("C", []),
            },
            policy_value=policy(grandfathered_prs=[10, 11, 12, 13]),
        )
        summaries = validate_live_pr_inventory(prs, root)
        self.assertIn("Integration inventory: OPEN 4/3; mode DRAIN", summaries)

    def test_drain_rejects_new_implementation_pr(self) -> None:
        prs = [
            pr(10, head="a", base="unified"),
            pr(11, head="b", base="unified"),
            pr(12, head="c", base="unified"),
            pr(13, head="d", base="unified"),
        ]
        root = self.write_fixture(
            {
                "A": lane("A", [active(1, 10), active(2, 11)]),
                "B": lane("B", [active(3, 12), active(4, 13)]),
                "C": lane("C", []),
            },
            policy_value=policy(grandfathered_prs=[10, 11, 12]),
        )
        with self.assertRaisesRegex(FlowControlError, "DRAIN active"):
            validate_live_pr_inventory(prs, root)

    def test_stacked_pr_is_part_of_managed_inventory(self) -> None:
        prs = [
            pr(10, head="parent", base="unified"),
            pr(11, head="repair", base="parent"),
        ]
        root = self.write_fixture(
            {
                "A": lane("A", [active(1, 10), active(2, 11)]),
                "B": lane("B", []),
                "C": lane("C", []),
            },
            policy_value=policy(grandfathered_prs=[10, 11]),
        )
        summaries = validate_live_pr_inventory(prs, root)
        self.assertIn("Integration inventory: OPEN 2/3; mode NORMAL", summaries)

    def test_non_implementation_exception_is_excluded_from_inventory(self) -> None:
        exception = {
            **EXCEPTION,
            "head_branch": "governance/adr126",
        }
        prs = [
            pr(10, head="feature", base="unified"),
            pr(99, head="governance/adr126", base="unified"),
        ]
        root = self.write_fixture(
            {
                "A": lane("A", [active(1, 10)]),
                "B": lane("B", []),
                "C": lane("C", []),
            },
            policy_value=policy(non_implementation_exceptions=[exception]),
        )
        summaries = validate_live_pr_inventory(prs, root)
        self.assertIn("Integration inventory: OPEN 1/3; mode NORMAL", summaries)

    def test_repository_snapshot_is_valid(self) -> None:
        summaries = validate_flow_control()
        self.assertEqual(3, len(summaries))


if __name__ == "__main__":
    unittest.main()
