from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from scripts.check_factory_workstack import WorkstackError, ready_specs, validate_manifest


def leaf(
    spec_id: str,
    *,
    depends_on: list[str] | None = None,
    issue_number: int | None = 1,
    spec_sha256: str = "0" * 64,
) -> dict[str, object]:
    number = spec_id.removeprefix("SPEC-")
    return {
        "spec_id": spec_id,
        "path": f"docs/specifications/{number}_TEST.md",
        "spec_sha256": spec_sha256,
        "title": spec_id,
        "track": "control",
        "depends_on": depends_on or [],
        "wave": "test",
        "verification_tier": "tier0",
        "issue_number": issue_number,
        "issue_sha256": "1" * 64 if issue_number is not None else None,
    }


def manifest(*leaves: dict[str, object]) -> dict[str, object]:
    return {"schema": "bilqis.factory-workstack/v1", "parent_issue": 150, "leaves": list(leaves)}


class FactoryWorkstackTest(unittest.TestCase):
    def test_valid_dag_and_ready_set(self) -> None:
        payload = manifest(
            leaf("SPEC-0006", issue_number=6),
            leaf("SPEC-0007", depends_on=["SPEC-0006"], issue_number=7),
            leaf("SPEC-0008", issue_number=8),
        )
        self.assertEqual(validate_manifest(payload), ("SPEC-0006", "SPEC-0008", "SPEC-0007"))
        self.assertEqual(ready_specs(payload), ("SPEC-0006", "SPEC-0008"))
        self.assertEqual(ready_specs(payload, done=["SPEC-0006"]), ("SPEC-0007", "SPEC-0008"))

    def test_cycle_fails(self) -> None:
        payload = manifest(
            leaf("SPEC-0006", depends_on=["SPEC-0007"], issue_number=6),
            leaf("SPEC-0007", depends_on=["SPEC-0006"], issue_number=7),
        )
        with self.assertRaisesRegex(WorkstackError, "FACTORY_WORKSTACK_CYCLE"):
            validate_manifest(payload)

    def test_missing_dependency_fails(self) -> None:
        payload = manifest(leaf("SPEC-0006", depends_on=["SPEC-9999"], issue_number=6))
        with self.assertRaisesRegex(WorkstackError, "FACTORY_WORKSTACK_MISSING_DEPENDENCY"):
            validate_manifest(payload)

    def test_duplicate_spec_fails(self) -> None:
        payload = manifest(leaf("SPEC-0006", issue_number=6), leaf("SPEC-0006", issue_number=7))
        with self.assertRaisesRegex(WorkstackError, "FACTORY_WORKSTACK_DUPLICATE_SPEC"):
            validate_manifest(payload)

    def test_blocked_dependency_keeps_descendant_unready(self) -> None:
        payload = manifest(
            leaf("SPEC-0006", issue_number=6),
            leaf("SPEC-0007", depends_on=["SPEC-0006"], issue_number=7),
            leaf("SPEC-0008", issue_number=8),
        )
        self.assertEqual(ready_specs(payload, blocked=["SPEC-0006"]), ("SPEC-0008",))

    def test_execution_ready_requires_issue(self) -> None:
        payload = manifest(leaf("SPEC-0006", issue_number=None))
        with self.assertRaisesRegex(WorkstackError, "FACTORY_WORKSTACK_ISSUE_MISSING"):
            validate_manifest(payload, execution_ready=True)

    def test_spec_file_identity_is_checked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "docs/specifications/0006_TEST.md"
            path.parent.mkdir(parents=True)
            content = b"# SPEC-0006: Test\n"
            path.write_bytes(content)
            payload = manifest(
                leaf(
                    "SPEC-0006",
                    issue_number=6,
                    spec_sha256=hashlib.sha256(content).hexdigest(),
                )
            )
            self.assertEqual(validate_manifest(payload, root=root), ("SPEC-0006",))
            path.write_text("# SPEC-0007: Wrong\n", encoding="utf-8")
            with self.assertRaisesRegex(WorkstackError, "FACTORY_WORKSTACK_SPEC_HASH_MISMATCH"):
                validate_manifest(payload, root=root)

    def test_execution_ready_requires_issue_hash(self) -> None:
        entry = leaf("SPEC-0006", issue_number=6)
        entry["issue_sha256"] = None
        payload = manifest(entry)
        with self.assertRaisesRegex(WorkstackError, "FACTORY_WORKSTACK_ISSUE_HASH_INVALID"):
            validate_manifest(payload, execution_ready=True)


if __name__ == "__main__":
    unittest.main()
