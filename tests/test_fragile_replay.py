"""Bounded source-cohort Boolean replay, without neural training."""
import json
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.fragile_replay import (
    load_replay_rows, screen_replay, select_preservation_rows,
    select_structural_preservation_rows, structural_signature,
)
from bilqis_mlx.generated_assessment import make_cohort


class FragileReplayTests(unittest.TestCase):
    def test_materialized_balanced_or_xor_only_and_per_item_loss(self):
        rows = []
        for name in ("B.OR", "B.XOR"):
            for i in range(12):
                positive = i % 2 == 0
                index = i // 2
                bits = (([False, True], [True, False], [True, True])[index % 3]
                        if name == "B.OR" and positive else
                        ([False, True], [True, False])[index % 2]
                        if positive else
                        ([False, False], [True, True])[index % 2]
                        if name == "B.XOR" else [False, False])
                args = [{"kind": "relation", "name": relation,
                         "args": [{"kind": "entity", "name": "A"},
                                  {"kind": "entity", "name": "B"}]}
                        for relation in ("PARENT", "LINK")]
                rows.append({"id": f"{name}:{i}", "capability": name,
                             "gold": "TRUE" if positive else "FALSE",
                             "operand_truths": bits, "tokens": [17, 24, 5],
                             "record": {"task": "micro", "world": {
                                 "entities": ["A", "B"],
                                 "facts": [([rel, "A", "B"]) for rel, bit in
                                           zip(("PARENT", "LINK"), bits) if bit]},
                                 "query": {"kind": "apply", "operator": name[2:],
                                           "args": args}}})
        rows.append({"id": "A.LINK:0", "capability": "A.LINK", "gold": "TRUE"})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cohorts"
            path.mkdir()
            cohort = make_cohort(rows, generator_version="test-oracle", seed=23,
                                 rubric_version="test-grade-b")
            digest = cohort.digest
            (path / f"{digest}.json").write_text(json.dumps({
                "cohort_sha256": digest, "rows": rows, "seed": 23,
                "generator_version": "test-oracle", "schema": "test-grade-b"}))
            receipt = {"last_exam": {"cohort_sha256": digest,
                                     "cohort_file": f"cohorts/{digest}.json",
                                     "scores": {"B.OR": {"correct": 12, "total": 12},
                                                "B.XOR": {"correct": 12, "total": 12}}}}
            replay = load_replay_rows(Path(tmp), receipt)
        self.assertEqual(len(replay), 24)
        self.assertEqual({r["capability"] for r in replay}, {"B.OR", "B.XOR"})
        before = {r["id"]: r["gold"] for r in replay}
        before["B.XOR:1"] = "TRUE"
        after = dict(before)
        after["B.XOR:0"] = "FALSE"
        after["B.XOR:1"] = "FALSE"
        result = screen_replay(replay, before, after, digest)
        self.assertEqual(result["rows"], 24)
        self.assertEqual(result["regressions"], [{"id": "B.XOR:0", "capability": "B.XOR"}])
        self.assertEqual(result["repaired"], 1)

    def test_no_grade_b_exam_means_no_replay(self):
        self.assertEqual(load_replay_rows(Path("unused"), {"last_exam": {
            "scores": {"A.LINK": {"correct": 12, "total": 12}}}}), ())

    def test_preservation_rows_cover_each_truth_pattern_without_exam_leakage(self):
        rows = []
        for capability in ("B.OR", "B.XOR"):
            for index, bits in enumerate((
                    (False, False), (False, True), (True, False), (True, True))):
                gold = ("TRUE" if (any(bits) if capability == "B.OR"
                                   else bits[0] != bits[1]) else "FALSE")
                rows.extend([
                    {"id": f"{capability}:{index}:exam", "capability": capability,
                     "gold": gold, "operand_truths": list(bits), "tokens": [1, 2, 3]},
                    {"id": f"{capability}:{index}:fresh", "capability": capability,
                     "gold": gold, "operand_truths": list(bits), "tokens": [4, 5, 6]},
                ])
        excluded = {row["id"] for row in rows if row["id"].endswith(":exam")}
        selected = select_preservation_rows(rows, excluded_ids=excluded)
        self.assertEqual(len(selected), 8)
        self.assertFalse({row["id"] for row in selected} & excluded)
        self.assertEqual(
            {(row["capability"], tuple(row["operand_truths"])) for row in selected},
            {(capability, bits)
             for capability in ("B.OR", "B.XOR")
             for bits in ((False, False), (False, True), (True, False), (True, True))},
        )

    def test_structural_preservation_matches_endpoint_topology_not_only_truth_bits(self):
        def operand(kind, left, right):
            if kind == "EQ":
                return {"kind": "compare", "operator": "EQ", "args": [
                    {"kind": "entity", "name": left},
                    {"kind": "entity", "name": right}]}
            return {"kind": "relation", "name": kind, "args": [
                {"kind": "entity", "name": left},
                {"kind": "entity", "name": right}]}

        def row(identity, args, *, universe=4):
            return {
                "id": identity, "capability": "B.XOR", "gold": "TRUE",
                "operand_truths": [True, False], "universe_size": universe,
                "tokens": [1, 2, 3], "record": {"query": {
                    "kind": "apply", "operator": "XOR", "args": args}},
            }

        fixed = [row("exam", [
            operand("LINK", "D", "E"), operand("EQ", "D", "E")])]
        fresh = [
            row("wrong-order", [
                operand("EQ", "D", "E"), operand("LINK", "D", "E")]),
            row("wrong-topology", [
                operand("LINK", "D", "E"), operand("EQ", "E", "D")]),
            row("match", [
                operand("LINK", "A", "B"), operand("EQ", "A", "B")]),
        ]
        selected = select_structural_preservation_rows(
            fresh, fixed, excluded_ids={"exam"}, rotation=0, limit=1)
        self.assertEqual([item["id"] for item in selected], ["match"])
        self.assertEqual(structural_signature(selected[0]),
                         structural_signature(fixed[0]))

