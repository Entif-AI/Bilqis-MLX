from __future__ import annotations

import unittest

from scripts.check_bamf_flow_control import (
    FlowControlError,
    validate_live_pr_inventory,
)
from scripts.tests.bamf_flow_control_fixtures import (
    exception,
    FixtureMixin,
    active,
    lane,
    policy,
    pr,
)


class BamfFlowControlLiveTests(FixtureMixin):
    def test_live_reconciliation_rejects_untracked_open_pr(self) -> None:
        root = self.write_fixture(
            {"A": lane("A", []), "B": lane("B", []), "C": lane("C", [])}
        )
        with self.assertRaisesRegex(FlowControlError, "missing from flow-control ledger"):
            validate_live_pr_inventory([pr(10, head="a", base="unified")], root)

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
        exception = {**exception(), "head_branch": "governance/adr126"}
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


if __name__ == "__main__":
    unittest.main()
