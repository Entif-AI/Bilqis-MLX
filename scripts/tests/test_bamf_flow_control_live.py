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
        prs.extend(pr(i, head=f"lane-{i}", base="unified") for i in range(14, 23))
        root = self.write_fixture(
            {
                "A": lane("A", [active(i, i + 9) for i in range(1, 7)]),
                "B": lane("B", [active(i, i + 15) for i in range(1, 7)]),
                "C": lane("C", [active(13, 22)]),
            },
            policy_value=policy(grandfathered_prs=list(range(10, 23))),
        )
        summaries = validate_live_pr_inventory(prs, root)
        self.assertIn("Integration inventory: OPEN 13/12; mode DRAIN", summaries)

    def test_drain_rejects_new_implementation_pr(self) -> None:
        prs = [
            pr(10, head="a", base="unified"),
            pr(11, head="b", base="unified"),
            pr(12, head="c", base="unified"),
            pr(13, head="d", base="unified"),
        ]
        prs.extend(pr(i, head=f"lane-{i}", base="unified") for i in range(14, 23))
        root = self.write_fixture(
            {
                "A": lane("A", [active(i, i + 9) for i in range(1, 7)]),
                "B": lane("B", [active(i, i + 15) for i in range(1, 7)]),
                "C": lane("C", [active(13, 22)]),
            },
            policy_value=policy(grandfathered_prs=list(range(10, 22))),
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
        self.assertIn("Integration inventory: OPEN 2/12; mode NORMAL", summaries)

    def test_tracked_stacked_pr_counts_when_parent_pr_is_closed(self) -> None:
        prs = [pr(11, head="repair", base="closed-parent")]
        root = self.write_fixture(
            {
                "A": lane("A", []),
                "B": lane("B", [active(2, 11)]),
                "C": lane("C", []),
            }
        )
        summaries = validate_live_pr_inventory(prs, root)
        self.assertIn("Integration inventory: OPEN 1/12; mode NORMAL", summaries)

    def test_non_implementation_exception_is_excluded_from_inventory(self) -> None:
        control_plane_exception = {**exception(), "head_branch": "governance/adr126"}
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
            policy_value=policy(non_implementation_exceptions=[control_plane_exception]),
        )
        summaries = validate_live_pr_inventory(prs, root)
        self.assertIn("Integration inventory: OPEN 1/12; mode NORMAL", summaries)

    def test_twelve_open_prs_in_one_lane_are_within_inventory_limit(self) -> None:
        prs = [pr(i, head=f"a-{i}", base="unified") for i in range(10, 22)]
        root = self.write_fixture(
            {
                "A": lane("A", [active(i, i + 9) for i in range(1, 7)] + [
                    {"issue": i, "pr": i + 9, "state": "TURNED_IN", "resume_trigger": None}
                    for i in range(7, 13)
                ]),
                "B": lane("B", []),
                "C": lane("C", []),
            }
        )
        self.assertIn("Integration inventory: OPEN 12/12; mode NORMAL", validate_live_pr_inventory(prs, root))


if __name__ == "__main__":
    unittest.main()
