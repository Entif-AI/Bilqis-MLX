"""Focused tests for BAMF grooming contract decomposition."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "bamf"))

import bamf02_groom_contracts as contracts


class GroomContractTests(unittest.TestCase):
    def sample_body(self, prescription: str) -> str:
        return f"""# A01

## Outcome
Outcome text.

## Direct dependencies and existing owners
A00.

## Source and allowed edit surface
src/a.py

## Interface to implement
`call()`

## Implementation prescription
{prescription}

## Relevant shared contracts
### Alpha contract
Alpha detail about output handling.

### Beta contract
Beta detail about source validation.

## Acceptance and bounded proof
Acceptance text.

## EGM and faithful execution
Review text.
"""

    def test_split_contract_preserves_named_sections(self):
        result = contracts.split_contract(self.sample_body("First clause. Second clause."))
        self.assertEqual(result["outcome"], "Outcome text.")
        self.assertEqual(result["interface"], "`call()`")
        self.assertEqual(result["acceptance"], "Acceptance text.")

    def test_prescription_sentences_keeps_order(self):
        self.assertEqual(
            contracts.prescription_sentences("First clause. Second clause? Third clause!"),
            ["First clause.", "Second clause?", "Third clause!"],
        )

    def test_plan_for_rejects_slice_that_does_not_cover_source(self):
        old = contracts.SLICES.get("ZZZ")
        contracts.SLICES["ZZZ"] = (("Only", 1),)
        try:
            with self.assertRaisesRegex(ValueError, "expected final sentence index"):
                contracts.plan_for("ZZZ", self.sample_body("One. Two."), 1, [])
        finally:
            if old is None:
                del contracts.SLICES["ZZZ"]
            else:
                contracts.SLICES["ZZZ"] = old

    def test_child_body_marks_group_as_non_implementing(self):
        body = self.sample_body("One clause.")
        group = {"key": "A01.1", "parent": "A01", "group": True,
                 "title": "Group", "deps": [], "clauses": [], "owned": []}
        rendered = contracts.child_body("A01", group, {}, body, 341)
        self.assertIn("a non-implementing group", rendered)
        self.assertIn("This is **not a coding assignment**", rendered)


if __name__ == "__main__":
    unittest.main()
