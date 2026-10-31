"""Preservation selection."""
import unittest

from bilqis_mlx.learning.tests.test_fragile_replay import (
    Counter, _direct_u7c_replay_rows, fragile_preservation_capabilities, select_preservation_rows,
    select_structural_preservation_rows, structural_signature,
)


class PreservationSelectionTests(unittest.TestCase):
    def test_common_fresh_selector_preserves_early_stop_fallback_and_leak_guard(self):
        from copy import deepcopy
        from unittest.mock import Mock, patch
        from bilqis_mlx.learning import fragile_replay
        fixed = _direct_u7c_replay_rows()
        fresh = tuple({**deepcopy(row), "id": "fresh:" + row["id"]} for row in fixed)
        draw = Mock(return_value=fresh)
        selected = fragile_replay.fresh_preservation_rows(
            fixed, capabilities=("B.OR",), draw_rows=draw,
            seed_for=lambda name, attempt: attempt, rotation=0, batch_size=1)
        self.assertEqual(len(selected), 4)
        draw.assert_called_once_with(capability="B.OR", seed=0, each=96)
        draw.reset_mock()
        with patch.object(fragile_replay, "select_structural_preservation_rows", return_value=()):
            fallback = fragile_replay.fresh_preservation_rows(
                fixed, capabilities=("B.OR",), draw_rows=draw,
                seed_for=lambda name, attempt: attempt, rotation=0, batch_size=1)
        self.assertEqual(fallback, selected)
        self.assertEqual(draw.call_count, 3)
        with patch.object(fragile_replay, "select_structural_preservation_rows", return_value=()), \
                patch.object(fragile_replay, "select_preservation_rows", side_effect=ValueError("SOURCE_DRIFT")):
            with self.assertRaisesRegex(ValueError, "^SOURCE_DRIFT$"):
                fragile_replay.fresh_preservation_rows(
                    fixed, capabilities=("B.OR",), draw_rows=draw,
                    seed_for=lambda name, attempt: attempt, rotation=0, batch_size=1)
        with patch.object(fragile_replay, "select_structural_preservation_rows", return_value=fixed[:4]):
            with self.assertRaisesRegex(ValueError, "^FRAGILE_PRESERVATION_EXAM_ROW_LEAK$"):
                fragile_replay.fresh_preservation_rows(
                    fixed, capabilities=("B.OR",), draw_rows=draw,
                    seed_for=lambda name, attempt: attempt, rotation=0, batch_size=1)

    def test_direct_u7c_preservation_uses_causal_quota_not_full_or_truth_table(self):
        rows = _direct_u7c_replay_rows()
        selected = select_preservation_rows(
            rows, capabilities=fragile_preservation_capabilities())

        self.assertEqual(len(selected), 8)
        or_patterns = [tuple(row["operand_truths"]) for row in selected
                       if row["capability"] == "B.OR"]
        xor_patterns = [tuple(row["operand_truths"]) for row in selected
                        if row["capability"] == "B.XOR"]
        self.assertEqual(or_patterns.count((False, False)), 2)
        self.assertEqual(or_patterns.count((True, False)), 1)
        self.assertEqual(or_patterns.count((False, True)), 1)
        self.assertNotIn((True, True), or_patterns)
        self.assertEqual(set(xor_patterns), {
            (False, False), (False, True), (True, False), (True, True)})

    def test_direct_u7c_structural_preservation_keeps_balanced_causal_quota(self):
        fixed = _direct_u7c_replay_rows()
        fresh = [
            {**row, "id": "fresh:" + row["id"],
             "source_id": "fresh:" + row["source_id"]}
            for row in fixed
        ]
        for capability in fragile_preservation_capabilities():
            selected = select_structural_preservation_rows(
                [row for row in fresh if row["capability"] == capability],
                [row for row in fixed if row["capability"] == capability],
                rotation=0, limit=4)
            patterns = Counter(tuple(row["operand_truths"]) for row in selected)
            if capability == "B.OR":
                self.assertEqual(patterns, Counter({
                    (False, False): 2,
                    (False, True): 1,
                    (True, False): 1,
                }))
            else:
                self.assertEqual(patterns, Counter({
                    (False, False): 1,
                    (False, True): 1,
                    (True, False): 1,
                    (True, True): 1,
                }))

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
