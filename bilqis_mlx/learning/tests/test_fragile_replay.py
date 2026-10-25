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


class FragileReplayTests(unittest.TestCase):
    def test_retention_profile_owns_immutable_fragile_source_policy(self):
        from dataclasses import FrozenInstanceError
        from bilqis_mlx.profiles.retention import FragilePreservationPolicy, fragile_preservation_policy
        policy = fragile_preservation_policy()
        self.assertIsInstance(policy, FragilePreservationPolicy)
        self.assertEqual(policy.capabilities, ("B.OR", "B.XOR"))
        self.assertIs(fragile_preservation_capabilities(), policy.capabilities)
        self.assertEqual(policy.per_capability_target, 4)
        self.assertEqual(policy.source_selector, "bilqis.mlx.grade-b-u7c-runtime-sampler/v3")
        with self.assertRaises(FrozenInstanceError):
            policy.per_capability_target = 8
        for capabilities, target, selector in ((["B.OR"], 4, "source"),
                (("B.OR", "B.OR"), 4, "source"), (("",), 4, "source"),
                (("B.OR",), True, "source"), (("B.OR",), 0, "source"),
                (("B.OR",), 4, "")):
            with self.subTest(capabilities=capabilities, target=target, selector=selector), \
                    self.assertRaises(ValueError):
                FragilePreservationPolicy(capabilities, target, selector)

    def test_generic_selection_uses_source_callbacks_for_non_boolean_shapes(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from bilqis_mlx.learning import fragile_replay
        policy = SimpleNamespace(
            is_exact=lambda row: False,
            pattern_counts=lambda *args, **kwargs: {("alpha",): 1},
            row_pattern=lambda row: (row["shape"],), eligible=lambda row: True,
            answer_values=("OK", "BAD"), signature=lambda row: (row["capability"], row["shape"]),
            matching_keys=lambda signature: (signature,))
        row = {"id": "synthetic", "capability": "X", "gold": "OK", "tokens": [1], "shape": "alpha"}
        with patch.object(fragile_replay, "_source_policy", return_value=policy):
            self.assertEqual(select_preservation_rows([row]), (row,))
            self.assertEqual(select_structural_preservation_rows(
                [row], [row], rotation=0, limit=1), (row,))
            self.assertEqual(screen_replay((row,), {"synthetic": "OK"},
                {"synthetic": "BAD"}, "c" * 64)["regressions"],
                [{"id": "synthetic", "capability": "X"}])

    def test_source_policy_owns_fragile_truth_and_structure_callbacks(self):
        from bilqis_mlx.source_adapters.school import fragile_source_policy
        from bilqis_mlx.profiles.retention import fragile_preservation_policy
        policy = fragile_source_policy(fragile_preservation_policy().source_selector)
        direct = _direct_u7c_replay_rows()[0]
        historical = _v2_replay_rows()[0]
        self.assertTrue(policy.is_exact(direct))
        self.assertFalse(policy.is_exact(historical))
        self.assertEqual(policy.signature(direct), structural_signature(direct))
        self.assertTrue(policy.verify_row(direct, direct["capability"]))
        self.assertTrue(policy.verify_row(historical, historical["capability"]))
        self.assertFalse(policy.verify_row({**direct, "gold": "wrong"}, direct["capability"]))
        self.assertEqual(policy.pattern_counts("B.OR", _direct_u7c_replay_rows(), each=4),
                         {(False, False): 2, (False, True): 1, (True, False): 1})
        with self.assertRaisesRegex(ValueError, "FRAGILE_PRESERVATION_SOURCE_POLICY_UNKNOWN"):
            fragile_source_policy("unadmitted.source")

    def test_saved_direct_u7c_cohort_replay_does_not_require_world(self):
        rows = _direct_u7c_replay_rows()
        rubric = "b" * 64
        release = "c" * 64
        cohort = make_cohort(
            rows, generator_version="test-direct-u7c", seed=37,
            rubric_version=rubric)
        digest = cohort.digest
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cohorts"
            path.mkdir()
            (path / f"{digest}.json").write_text(json.dumps({
                "schema": "bilqis.mlx.generated-cohort/v2",
                "factory_release_sha256": release,
                "rubric_sha256": rubric,
                "cohort_sha256": digest,
                "rows": rows,
                "seed": 37,
                "generator_version": "test-direct-u7c",
            }))
            receipt = {"last_exam": {
                "cohort_sha256": digest,
                "cohort_file": f"cohorts/{digest}.json",
                "rubric_sha256": rubric,
                "factory_release_sha256": release,
                "scores": {
                    "B.OR": {"correct": 12, "total": 12},
                    "B.XOR": {"correct": 12, "total": 12},
                },
            }}

            replay = load_replay_rows(
                Path(tmp), receipt,
                capabilities=fragile_preservation_capabilities())

        self.assertEqual(len(replay), 24)
        self.assertTrue(all("world" not in row["record"] for row in replay))

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

    def test_saved_v2_cohort_replay_uses_rubric_digest_and_release_binding(self):
        rows = _v2_replay_rows()
        rubric = "b" * 64
        release = "c" * 64
        cohort = make_cohort(
            rows, generator_version="test-v2-oracle", seed=31,
            rubric_version=rubric)
        digest = cohort.digest
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cohorts"
            path.mkdir()
            payload = {
                "schema": "bilqis.mlx.generated-cohort/v2",
                "factory_release_sha256": release,
                "rubric_sha256": rubric,
                "cohort_sha256": digest,
                "rows": rows,
                "seed": 31,
                "generator_version": "test-v2-oracle",
            }
            cohort_path = path / f"{digest}.json"
            cohort_path.write_text(json.dumps(payload))
            receipt = {"last_exam": {
                "cohort_sha256": digest,
                "cohort_file": f"cohorts/{digest}.json",
                "rubric_sha256": rubric,
                "factory_release_sha256": release,
                "scores": {
                    "B.OR": {"correct": 12, "total": 12},
                    "B.XOR": {"correct": 12, "total": 12},
                },
            }}

            replay = load_replay_rows(
                Path(tmp), receipt,
                capabilities=fragile_preservation_capabilities())
            self.assertEqual(len(replay), 24)

            payload["factory_release_sha256"] = "d" * 64
            cohort_path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "IDENTITY|METADATA|RELEASE"):
                load_replay_rows(
                    Path(tmp), receipt,
                    capabilities=fragile_preservation_capabilities())

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
                                 rubric_version="b" * 64)
            digest = cohort.digest
            receipt = {"last_exam": {"cohort_sha256": digest,
                                     "cohort_file": f"cohorts/{digest}.json",
                                     "scores": {"B.OR": {"correct": 12, "total": 12},
                                                "B.XOR": {"correct": 12, "total": 12}}}}
            file = path / f"{digest}.json"
            for schema in ("b" * 64, EXECUTABLE_COHORT_SCHEMA):
                payload = dict(cohort_sha256=digest, rows=rows, seed=23,
                               generator_version="test-oracle", schema=schema,
                               rubric_sha256="b" * 64, factory_release_sha256="c" * 64)
                file.write_text(json.dumps(payload))
                with self.subTest(schema=schema):
                    replay = load_replay_rows(Path(tmp), receipt,
                        capabilities=fragile_preservation_capabilities())
                    self.assertEqual(len(replay), 24)
            payload["rubric_sha256"] = "d" * 64
            file.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "CONTENT_DRIFT"):
                load_replay_rows(Path(tmp), receipt,
                    capabilities=fragile_preservation_capabilities())
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
            replay = load_replay_rows(
                Path(tmp), receipt,
                capabilities=fragile_preservation_capabilities())
        self.assertEqual(len(replay), 24)
        self.assertEqual(sum(row["gold"] == "TRUE" for row in replay
                             if row["capability"] == "B.OR"), 8)
        self.assertEqual(sum(row["gold"] == "TRUE" for row in replay
                             if row["capability"] == "B.XOR"), 4)

    def test_no_grade_b_exam_means_no_replay(self):
        self.assertEqual(load_replay_rows(
            Path("unused"), {"last_exam": {
                "scores": {"A.LINK": {"correct": 12, "total": 12}}}},
            capabilities=fragile_preservation_capabilities()), ())

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

