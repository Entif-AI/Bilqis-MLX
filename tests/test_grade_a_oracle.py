"""Literal source-record witnesses and label-leakage regression tests."""
import random
from pathlib import Path
import unittest

from bilqis_mlx.grade_a_oracle import evaluate
from bilqis_mlx.grade_a_probe import FAMILIES, make_record, read_sources, _draw

ROOT = Path(__file__).resolve().parents[1] / "vendor" / "legacy-v16"


class IndependentOracleTests(unittest.TestCase):
    def test_independently_interpreted_literal_worlds(self):
        cases = (
            ("A.IDENTITY", {"task": "micro", "world": {},
                "query": {"kind": "compare", "operator": "EQ",
                          "args": [{"kind": "entity", "name": "A"},
                                   {"kind": "entity", "name": "B"}]}}, "FALSE"),
            ("A.PARENT", {"task": "micro", "world": {"facts": [["CHILD", "B", "A"]]},
                "query": {"kind": "relation", "name": "PARENT",
                          "args": [{"kind": "entity", "name": "A"},
                                   {"kind": "entity", "name": "B"}]}}, "TRUE"),
            ("A.LINK", {"task": "micro", "world": {"facts": [["LINK", "B", "A"]]},
                "query": {"kind": "relation", "name": "LINK",
                          "args": [{"kind": "entity", "name": "A"},
                                   {"kind": "entity", "name": "B"}]}}, "TRUE"),
            ("A.MEMBER", {"task": "development", "world": {"sets": {"K0": ["B", "C"]}},
                "query": {"kind": "op", "op": "MEMBER", "args": [
                    {"kind": "const", "type": "Entity", "name": "A"},
                    {"kind": "const", "type": "Set", "name": "K0"}]}}, "FALSE"),
            ("A.EDGE", {"task": "development", "world": {"edges": [["B", "A"]]},
                "query": {"kind": "op", "op": "EDGE", "args": [
                    {"kind": "const", "type": "Entity", "name": "A"},
                    {"kind": "const", "type": "Entity", "name": "B"}]}}, "FALSE"),
            ("A.MAPS", {"task": "development", "world": {
                "functions": {"F0": [["A", "C"]]}},
                "query": {"kind": "op", "op": "MAPS", "args": [
                    {"kind": "const", "type": "Function", "name": "F0"},
                    {"kind": "const", "type": "Entity", "name": "A"},
                    {"kind": "const", "type": "Entity", "name": "C"}]}}, "TRUE"),
        )
        for capability, record, expected in cases:
            with self.subTest(capability=capability):
                self.assertEqual(evaluate(record, capability), expected)
        with self.assertRaisesRegex(ValueError, "WRONG_QUERY"):
            evaluate(cases[-2][1], "A.MAPS")

    @unittest.skipUnless(ROOT.joinpath("bilqis_micro/kernel.py").is_file(),
                         "Original source archive not mounted")
    def test_member_labels_cannot_be_read_from_set_cardinality(self):
        micro, dev, graph, _, _ = read_sources(ROOT)
        both = []
        for split in ("train", "exam"):
            rows = _draw("A.MEMBER", split, count=24, micro=micro,
                         development=dev, graph=graph, past_ids=set())
            for r in rows:
                members = r["record"]["world"]["sets"]["K0"]
                both.append((r["gold"], len(members)))
                self.assertEqual(len(members), 2)
                self.assertEqual(evaluate(r["record"], "A.MEMBER"), r["gold"])
        self.assertEqual({k for k, _ in both}, {"TRUE", "FALSE"})
        self.assertEqual({length for _, length in both}, {2})

    @unittest.skipUnless(ROOT.joinpath("bilqis_micro/kernel.py").is_file(),
                         "Original source archive not mounted")
    def test_all_six_new_gold_checks_are_separate_from_source_evaluators(self):
        micro, dev, _, _, _ = read_sources(ROOT)
        for cap, _, _, _ in FAMILIES:
            for positive in (False, True):
                record, lib = make_record(cap, random.Random(1234), positive,
                                          split="train", micro=micro, development=dev)
                literal_oracle = evaluate(record, cap)
                self.assertEqual(literal_oracle, "TRUE" if positive else "FALSE")
                self.assertEqual(literal_oracle, lib.evaluate(record))
                self.assertEqual(literal_oracle, lib.independent_evaluate(record))


if __name__ == "__main__":
    unittest.main()
