from __future__ import annotations

import unittest

from scripts.check_bamf_flow_control import FlowControlError, validate_flow_control
from scripts.tests.bamf_flow_control_fixtures import (
    exception,
    FixtureMixin,
    active,
    lane,
    policy,
    waiting,
)


class BamfFlowControlTests(FixtureMixin):
    def test_waiting_requires_resume_trigger(self) -> None:
        item = waiting(1, 10, open_pr_exception=exception())
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
        self.assertIn("Lane A: ACTIVE 0/6; tracked 1", summaries)

    def test_normal_limit_rejects_seventh_active_item(self) -> None:
        root = self.write_fixture(
            {
                "A": lane("A", [active(i, i + 10) for i in range(1, 8)]),
                "B": lane("B", []),
                "C": lane("C", []),
            }
        )
        with self.assertRaisesRegex(FlowControlError, "exceed normal limit"):
            validate_flow_control(root)

    def test_explicit_exception_allows_over_limit(self) -> None:
        root = self.write_fixture(
            {
                "A": lane("A", [active(i, i + 10) for i in range(1, 8)], exception()),
                "B": lane("B", []),
                "C": lane("C", []),
            }
        )
        summaries = validate_flow_control(root)
        self.assertIn("Lane A: ACTIVE 7/6; tracked 7", summaries)

    def test_six_parallel_issue_branches_are_within_lane_limit(self) -> None:
        root = self.write_fixture(
            {
                "A": lane("A", [active(i, i + 10) for i in range(1, 7)]),
                "B": lane("B", []),
                "C": lane("C", []),
            }
        )
        self.assertIn("Lane A: ACTIVE 6/6; tracked 6", validate_flow_control(root))

    def test_repository_snapshot_is_valid(self) -> None:
        summaries = validate_flow_control()
        self.assertEqual(3, len(summaries))


if __name__ == "__main__":
    unittest.main()
