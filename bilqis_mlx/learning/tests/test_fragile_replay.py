"""Bounded source-cohort Boolean replay, without neural training."""
import json
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.learning.fragile_replay import (
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

    def test_materialized_unbalanced_runtime_cohort_is_valid_when_truth_table_is_complete(self):
        rows = []
        patterns = {
            "B.OR": (
                ([False, False],) * 4 +
                ([False, True],) * 3 +
                ([True, False],) * 3 +
                ([True, True],) * 2
            ),
            "B.XOR": (
                ([False, False],) * 4 +
                ([True, True],) * 4 +
                ([False, True],) * 2 +
                ([True, False],) * 2
            ),
        }
        for name, cases in patterns.items():
            for i, bits in enumerate(cases):
                args = [{"kind": "relation", "name": relation,
                         "args": [{"kind": "entity", "name": "A"},
                                  {"kind": "entity", "name": "B"}]}
                        for relation in ("PARENT", "LINK")]
                gold = ("TRUE" if (any(bits) if name == "B.OR"
                                   else bits[0] != bits[1]) else "FALSE")
                rows.append({
                    "id": f"{name}:{i}", "capability": name, "gold": gold,
                    "operand_truths": list(bits), "tokens": [17, 24, 5],
                    "runtime_sampler": "bilqis.mlx.grade-b-runtime-sampler/v2",
                    "record": {"task": "micro", "world": {
                        "entities": ["A", "B"],
                        "facts": [[rel, "A", "B"] for rel, bit in
                                  zip(("PARENT", "LINK"), bits) if bit]},
                        "query": {"kind": "apply", "operator": name[2:],
                                  "args": args}},
                })
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cohorts"
            path.mkdir()
            cohort = make_cohort(rows, generator_version="test-oracle", seed=29,
                                 rubric_version="test-grade-b")
            digest = cohort.digest
            (path / f"{digest}.json").write_text(json.dumps({
                "cohort_sha256": digest, "rows": rows, "seed": 29,
                "generator_version": "test-oracle", "schema": "test-grade-b"}))
            receipt = {"last_exam": {"cohort_sha256": digest,
                                     "cohort_file": f"cohorts/{digest}.json",
                                     "scores": {"B.OR": {"correct": 9, "total": 12},
                                                "B.XOR": {"correct": 8, "total": 12}}}}
            replay = load_replay_rows(Path(tmp), receipt)
        self.assertEqual(len(replay), 24)
        self.assertEqual(sum(row["gold"] == "TRUE" for row in replay
                             if row["capability"] == "B.OR"), 8)
        self.assertEqual(sum(row["gold"] == "TRUE" for row in replay
                             if row["capability"] == "B.XOR"), 4)

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

    def test_structural_preservation_matches_operand_kinds_and_universe_size(self):
        def operand(kind, left="A", right="B"):
            if kind == "EQ":
                return {"kind": "compare", "operator": "EQ", "args": [
                    {"kind": "entity", "name": left},
                    {"kind": "entity", "name": right}]}
            return {"kind": "relation", "name": kind, "args": [
                {"kind": "entity", "name": left},
                {"kind": "entity", "name": right}]}

        def row(identity, *, capability, bits, kinds, universe):
            gold = ("TRUE" if (any(bits) if capability == "B.OR"
                               else bits[0] != bits[1]) else "FALSE")
            return {
                "id": identity, "capability": capability, "gold": gold,
                "operand_truths": list(bits), "universe_size": universe,
                "tokens": [1, 2, 3], "record": {"query": {
                    "kind": "apply", "operator": capability[2:],
                    "args": [operand(kind) for kind in kinds]}},
            }

        fixed = [
            row("exam:xor", capability="B.XOR", bits=(True, False),
                kinds=("LINK", "EQ"), universe=4),
            row("exam:or", capability="B.OR", bits=(False, False),
                kinds=("PARENT", "PARENT"), universe=4),
        ]
        fresh = [
            # Same truth cells, but structurally wrong.
            row("fresh:xor-wrong", capability="B.XOR", bits=(True, False),
                kinds=("EQ", "LINK"), universe=4),
            row("fresh:or-wrong", capability="B.OR", bits=(False, False),
                kinds=("PARENT", "PARENT"), universe=3),
            # Exact structural siblings.
            row("fresh:xor", capability="B.XOR", bits=(True, False),
                kinds=("LINK", "EQ"), universe=4),
            row("fresh:or", capability="B.OR", bits=(False, False),
                kinds=("PARENT", "PARENT"), universe=4),
        ]
        selected = select_structural_preservation_rows(
            fresh, fixed, excluded_ids={row["id"] for row in fixed},
            rotation=0, limit=2)
        self.assertEqual([row["id"] for row in selected],
                         ["fresh:or", "fresh:xor"])
        self.assertEqual(
            {structural_signature(row) for row in selected},
            {structural_signature(row) for row in fixed})

    def test_structural_preservation_falls_back_without_becoming_a_gate(self):
        def operand(kind):
            if kind == "EQ":
                return {"kind": "compare", "operator": "EQ", "args": [
                    {"kind": "entity", "name": "A"},
                    {"kind": "entity", "name": "B"}]}
            return {"kind": "relation", "name": kind, "args": [
                {"kind": "entity", "name": "A"},
                {"kind": "entity", "name": "B"}]}

        def row(identity, kinds, universe):
            return {
                "id": identity, "capability": "B.XOR", "gold": "TRUE",
                "operand_truths": [True, False], "universe_size": universe,
                "tokens": [1, 2, 3], "record": {"query": {
                    "kind": "apply", "operator": "XOR",
                    "args": [operand(kind) for kind in kinds]}},
            }

        fixed = [row("exam", ("LINK", "EQ"), 4)]
        same_kinds_other_universe = row("fresh:kinds", ("LINK", "EQ"), 3)
        same_truth_other_shape = row("fresh:truth", ("EQ", "LINK"), 5)
        selected = select_structural_preservation_rows(
            [same_truth_other_shape, same_kinds_other_universe], fixed,
            excluded_ids={"exam"}, rotation=0, limit=1)
        self.assertEqual([row["id"] for row in selected], ["fresh:kinds"])

        selected = select_structural_preservation_rows(
            [same_truth_other_shape], fixed, excluded_ids={"exam"},
            rotation=0, limit=1)
        self.assertEqual([row["id"] for row in selected], ["fresh:truth"])

