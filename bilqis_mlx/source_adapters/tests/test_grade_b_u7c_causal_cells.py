"""U7C-style causal Boolean cells over every admitted Grade-B connective.

The historical U7C grammar balanced labels, limited one-arm shortcuts, and
proved operand influence with same-world counterfactual siblings.  This test
replays that discipline against the current Grade-B source constructor without
changing the admitted lesson or assessment generator.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import json
import unittest

from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.grade_b_oracle import (
    CONNECTIVES,
    evaluate as independent_oracle,
    operand_truth,
)
from bilqis_mlx.live_grade_a import live_course as live_a_course
from bilqis_mlx.live_grade_b import independent_truth, live_course
from bilqis_mlx.source_adapters.school import draw_b


ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "vendor" / "legacy-v16"
MANIFEST = ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json"

# U7C kept only causally useful cells while balancing TRUE/FALSE per gate.
# Repeated patterns are deliberate weights, not duplicate source records.
U7C_PATTERN_QUOTAS = {
    "NOT": {(False,): 1, (True,): 1},
    "AND": {(True, True): 2, (True, False): 1, (False, True): 1},
    "OR": {(False, False): 2, (True, False): 1, (False, True): 1},
    "XOR": {
        (False, False): 1,
        (False, True): 1,
        (True, False): 1,
        (True, True): 1,
    },
    "IMPLIES": {(True, True): 1, (True, False): 2, (False, False): 1},
    "IFF": {
        (False, False): 1,
        (False, True): 1,
        (True, False): 1,
        (True, True): 1,
    },
}

FULLY_CAUSAL_PATTERNS = {
    "NOT": {(False,), (True,)},
    "AND": {(True, True)},
    "OR": {(False, False)},
    "XOR": {(False, False), (False, True), (True, False), (True, True)},
    "IMPLIES": {(True, False)},
    "IFF": {(False, False), (False, True), (True, False), (True, True)},
}


def _u7c_cells(rows: tuple[dict, ...], operation: str) -> tuple[dict, ...]:
    by_pattern = defaultdict(list)
    for row in rows:
        by_pattern[tuple(row["operand_truths"])].append(row)
    selected = []
    for pattern, count in U7C_PATTERN_QUOTAS[operation].items():
        if len(by_pattern[pattern]) < count:
            raise AssertionError(
                f"{operation} lacks U7C pattern {pattern}: "
                f"{len(by_pattern[pattern])}/{count}"
            )
        selected.extend(by_pattern[pattern][:count])
    return tuple(selected)


def _identity_operand(micro, world: dict, truth: bool) -> dict:
    """Return an already-admitted A.IDENTITY proposition with requested truth."""
    first, second = world["entities"][:2]
    return micro.compare(
        "EQ",
        micro.entity(first),
        micro.entity(first if truth else second),
    )


def _single_arm_baseline(rows: tuple[dict, ...], slot: int) -> tuple[int, int]:
    groups = defaultdict(Counter)
    for row in rows:
        groups[row["operand_truths"][slot]][row["gold"]] += 1
    return sum(max(counts.values()) for counts in groups.values()), len(rows)


class GradeBU7CCausalCellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.micro, _, cls.graph, _, _ = read_sources(SOURCE_ROOT)
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        grade_a = live_a_course(accepted_grade_a(manifest))
        cls.course = live_course(grade_a, SOURCE_ROOT)

    def test_every_grade_b_connective_has_u7c_balanced_causal_cells(self):
        self.assertEqual(
            set(CONNECTIVES),
            {"NOT", "AND", "OR", "XOR", "IMPLIES", "IFF"},
        )
        self.assertEqual(set(U7C_PATTERN_QUOTAS), set(CONNECTIVES))

        all_selected = []
        for operation in CONNECTIVES:
            source_rows = draw_b(
                source_root=SOURCE_ROOT,
                graph=self.graph,
                course=self.course,
                seed=2026102301,
                each=12,
                capability="B." + operation,
            )
            self.assertEqual(
                {row["runtime_sampler"] for row in source_rows},
                {"bilqis.mlx.grade-b-runtime-sampler/v2"},
            )
            selected = _u7c_cells(source_rows, operation)
            all_selected.extend(selected)

            # U7C's gate-only shortcut is exactly chance because each gate's
            # selected cells contain equal TRUE and FALSE labels.
            labels = Counter(row["gold"] for row in selected)
            self.assertEqual(labels["TRUE"], labels["FALSE"], operation)

            influence = [False] * (1 if operation == "NOT" else 2)
            fully_causal = set()
            for row in selected:
                record = row["record"]
                world = record["world"]
                query = record["query"]
                pattern = tuple(row["operand_truths"])
                self.assertEqual(
                    pattern,
                    tuple(operand_truth(world, operand) for operand in query["args"]),
                )
                self.assertEqual(
                    row["gold"] == "TRUE",
                    independent_truth(operation, pattern),
                )

                changed_slots = []
                for slot in range(len(pattern)):
                    toggled = list(pattern)
                    toggled[slot] = not toggled[slot]
                    operands = list(query["args"])
                    operands[slot] = _identity_operand(
                        self.micro, world, toggled[slot]
                    )
                    sibling = self.micro.record(
                        world,
                        self.micro.logic(operation, *operands),
                    )

                    # The world and outer connective stay fixed.  Only one
                    # operand's truth is intervened through mastered A.IDENTITY.
                    self.assertEqual(sibling["world"], world)
                    self.assertEqual(sibling["query"]["operator"], operation)
                    self.assertEqual(
                        tuple(operand_truth(world, operand)
                              for operand in sibling["query"]["args"]),
                        tuple(toggled),
                    )
                    sibling_gold = self.micro.evaluate(sibling)
                    self.assertEqual(
                        sibling_gold,
                        self.micro.independent_evaluate(sibling),
                    )
                    self.assertEqual(
                        sibling_gold,
                        independent_oracle(sibling, "B." + operation),
                    )
                    self.assertEqual(
                        sibling_gold == "TRUE",
                        independent_truth(operation, tuple(toggled)),
                    )

                    changed = sibling_gold != row["gold"]
                    self.assertEqual(
                        changed,
                        independent_truth(operation, pattern)
                        != independent_truth(operation, tuple(toggled)),
                    )
                    influence[slot] |= changed
                    changed_slots.append(changed)

                if all(changed_slots):
                    fully_causal.add(pattern)

            # Every operand position must control the answer somewhere in the
            # selected cohort, and the strongest both-arm anchors must match the
            # connective's actual truth function.
            self.assertTrue(all(influence), operation)
            self.assertEqual(fully_causal, FULLY_CAUSAL_PATTERNS[operation])

            # U7C also prevented a learner from solving a binary gate by
            # looking at only one arm.  The generalized six-gate matrix keeps
            # either single-arm majority baseline at or below 75%.
            if operation != "NOT":
                for slot in (0, 1):
                    correct, total = _single_arm_baseline(selected, slot)
                    self.assertLessEqual(correct * 4, total * 3,
                                         (operation, slot, correct, total))

        combined = Counter(row["gold"] for row in all_selected)
        self.assertEqual(combined["TRUE"], combined["FALSE"])


if __name__ == "__main__":
    unittest.main()
