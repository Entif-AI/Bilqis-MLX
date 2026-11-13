"""Replay custody."""
import unittest

from bilqis_mlx.learning.tests.test_fragile_replay import (
    Path, fragile_preservation_capabilities, json, load_replay_rows,
    make_cohort, tempfile,
)


class ReplayCustody2Tests(unittest.TestCase):
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
