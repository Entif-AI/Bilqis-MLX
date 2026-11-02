from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_bamf_flow_control import FlowControlError, validate_flow_control


def policy() -> dict:\n    return {
    "schema": "bilqis.bamf.flow-control-policy/v1",
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
    "rules": {
        "over_limit_exception_required_fields": ["reason", "authority", "expires_when"]
    },
    }\n\n\ndef lane(name: str, items: list[dict], exception=None) -> dict:
    return {
        "schema": "bilqis.bamf.flow-control-lane/v1",
        "lane": name,
        "updated_at": "2026-11-02T05:10:00Z",
        "exception": exception,
        "items": items,
    }


class BamfFlowControlTests(unittest.TestCase):
    def write_fixture(self, lanes: dict[str, dict]) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / "policy.json").write_text(json.dumps(policy()), encoding="utf-8")
        for name in ("A", "B", "C"):
            (root / f"lane-{name.lower()}.json").write_text(
                json.dumps(lanes[name]), encoding="utf-8"
            )
        return root

    def test_waiting_requires_resume_trigger(self) -> None:
        root = self.write_fixture(
            {
                "A": lane("A", [{"issue": 1, "pr": 10, "state": "WAITING", "resume_trigger": ""}]),
                "B": lane("B", []),
                "C": lane("C", []),
            }
        )
        with self.assertRaisesRegex(FlowControlError, "requires a non-empty resume_trigger"):
            validate_flow_control(root)

    def test_normal_limit_rejects_third_active_item(self) -> None:
        root = self.write_fixture(
            {
                "A": lane(
                    "A",
                    [
                        {"issue": 1, "pr": 11, "state": "ACTIVE", "resume_trigger": None},
                        {"issue": 2, "pr": 12, "state": "ACTIVE", "resume_trigger": None},
                        {"issue": 3, "pr": 13, "state": "ACTIVE", "resume_trigger": None},
                    ],
                ),
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
                    [
                        {"issue": 1, "pr": 11, "state": "ACTIVE", "resume_trigger": None},
                        {"issue": 2, "pr": 12, "state": "ACTIVE", "resume_trigger": None},
                        {"issue": 3, "pr": 13, "state": "ACTIVE", "resume_trigger": None},
                    ],
                    {
                        "reason": "bounded emergency repair",
                        "authority": "owner instruction",
                        "expires_when": "repair merges",
                    },
                ),
                "B": lane("B", []),
                "C": lane("C", []),
            }
        )
        summaries = validate_flow_control(root)
        self.assertIn("Lane A: ACTIVE 3/2; tracked 3", summaries)

    def test_repository_snapshot_is_valid(self) -> None:
        summaries = validate_flow_control()
        self.assertEqual(3, len(summaries))


if __name__ == "__main__":
    unittest.main()
