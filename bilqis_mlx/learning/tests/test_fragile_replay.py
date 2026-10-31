"""Bounded source-cohort Boolean replay, without neural training."""
import json
from pathlib import Path
import tempfile
import unittest
from collections import Counter

from bilqis_mlx.learning.fragile_replay import (
    load_replay_rows, screen_replay, select_preservation_rows,
    select_structural_preservation_rows, structural_signature,
)
from bilqis_mlx.generated_assessment import make_cohort, EXECUTABLE_COHORT_SCHEMA
from bilqis_mlx.profiles.retention import fragile_preservation_capabilities


def _v2_replay_rows():
    rows = []
    for capability in ("B.OR", "B.XOR"):
        for repetition in range(3):
            for pattern_index, bits in enumerate((
                    (False, False), (False, True), (True, False), (True, True))):
                args = [
                    {"kind": "relation", "name": relation,
                     "args": [{"kind": "entity", "name": "A"},
                              {"kind": "entity", "name": "B"}]}
                    for relation in ("PARENT", "LINK")
                ]
                gold = ("TRUE" if (any(bits) if capability == "B.OR"
                                   else bits[0] != bits[1]) else "FALSE")
                rows.append({
                    "id": f"{capability}:{repetition}:{pattern_index}",
                    "capability": capability,
                    "gold": gold,
                    "operand_truths": list(bits),
                    "tokens": [17, 24, 5],
                    "record": {"task": "micro", "world": {
                        "entities": ["A", "B"],
                        "facts": [[relation, "A", "B"] for relation, truth in
                                  zip(("PARENT", "LINK"), bits) if truth]},
                        "query": {"kind": "apply", "operator": capability[2:],
                                  "args": args}},
                })
    return rows


def _direct_u7c_replay_rows():
    rows = []
    patterns = {
        "B.OR": ((False, False),) * 6 + ((True, False),) * 3 + ((False, True),) * 3,
        "B.XOR": ((False, False),) * 3 + ((False, True),) * 3 +
                 ((True, False),) * 3 + ((True, True),) * 3,
    }
    for capability in ("B.OR", "B.XOR"):
        operator = capability[2:]
        for index, bits in enumerate(patterns[capability]):
            args = [
                {"kind": "literal", "value": bits[0]},
                {"kind": "literal", "value": bits[1]},
            ]
            gold = ("TRUE" if (any(bits) if capability == "B.OR"
                               else bits[0] != bits[1]) else "FALSE")
            expression = {"kind": "apply", "operator": operator, "args": args}
            rows.append({
                "id": f"direct:{capability}:{index}",
                "source_id": f"source:{capability}:{index}",
                "capability": capability,
                "gold": gold,
                "operand_truths": list(bits),
                "runtime_sampler": "bilqis.mlx.grade-b-u7c-runtime-sampler/v3",
                "tokens": [17, 24, 5],
                "record": {
                    "task": "evaluate",
                    "assignments": {},
                    "expression": expression,
                    "query": expression,
                },
            })
    return rows
