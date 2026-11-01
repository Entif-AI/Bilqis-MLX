"""Replay custody."""
import unittest

from bilqis_mlx.learning.tests.test_fragile_replay import (
    EXECUTABLE_COHORT_SCHEMA, Path, _direct_u7c_replay_rows, _v2_replay_rows,
    fragile_preservation_capabilities, json, load_replay_rows, make_cohort,
    screen_replay, tempfile,
)


class ReplayCustody1Tests(unittest.TestCase):
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
