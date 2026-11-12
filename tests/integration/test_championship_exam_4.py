"""Focused championship exam behavior."""
from tests.integration.championship_exam_support import *  # noqa: F403,F405

class ChampionshipExamTests(TestCase):  # noqa: F405
    def test_legacy_earning_witness_preserves_compatible_historical_graph(self):
        old = {"tokens": ["PAD", "TRUE"], "nodes": [0, 1],
               "row_contract_sha256": {"PAD": "p", "TRUE": "t"}}
        current = {"tokens": old["tokens"] + ["NEW"], "nodes": [0, 1, 2],
                   "row_contract_sha256": {**old["row_contract_sha256"], "NEW": "n"}}
        rows = [{"id": "x0", "capability": "A.X", "gold": "TRUE", "tokens": [1]},
                {"id": "x1", "capability": "A.X", "gold": "FALSE", "tokens": [1]}]
        cohort = make_cohort(rows, generator_version="fixture", seed=1, rubric_version="fixture")
        pointer = {"filename": "bundles/old", "sha256": "a" * 64,
                   "optimizer_step": 10, "model_and_native_adamw": True}
        role = {"capability": "A.X", "cohort_sha256": cohort.digest,
                "rubric": "b" * 64, "correct": 1, "total": 2, "checkpoint": pointer}
        epoch = {"active_roles": {"A.X": role}}
        receipt = {"source_manifest_sha256": "c" * 64, "config": {}, "answer_ids": [1]}
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "cohorts").mkdir()
            (root / "cohorts" / (cohort.digest + ".json")).write_text(json.dumps({
                "cohort_sha256": cohort.digest, "rubric_sha256": "b" * 64,
                "source_manifest_sha256": "c" * 64, "schema": "fixture",
                "generator_version": "fixture", "seed": 1, "rows": rows}))
            bundle = root / pointer["filename"]
            bundle.mkdir(parents=True)
            (bundle / "model-and-own-adamw.safetensors").write_bytes(b"inert fixture")
            with (patch('bilqis_mlx.learning.lesson_guidance._cached_frozen_champion', return_value=({}, old)),
                  patch('bilqis_mlx.learning.student_ops._predictions', return_value={"x0": "TRUE", "x1": "WRONG"})):
                hydrated = trainer._hydrate_championship_witnesses(
                    None, root, receipt, epoch, current)
            proof = hydrated["active_roles"]["A.X"]["qualification_witnesses"][0]
            self.assertEqual(proof["source_graph_sha256"], trainer._fingerprint(old))
            self.assertEqual({q["id"] for q in proof["questions"]}, {"x0", "x1"})
            self.assertNotIn("qualification_witnesses", role)
            role = hydrated["active_roles"]["A.X"]
            battery = verified_battery(role)
            self.assertEqual({q["id"] for segment in battery for q in segment["questions"]},
                             {"x0", "x1"})
            with patch('bilqis_mlx.learning.student_ops._predictions', side_effect=[
                    {"x0": "TRUE", "x1": "FALSE"},
                    {"x0": "WRONG", "x1": "FALSE"}]) as infer:
                first = trainer._fresh_battery_results(None, root, receipt, role, {}, old)
                second = trainer._fresh_battery_results(None, root, receipt, role, {}, old)
            self.assertEqual(infer.call_count, 2)
            self.assertNotEqual(first, second)

    def test_fresh_battery_batches_verified_segments_into_one_model_inference(self):
        graph = {"tokens": ["PAD", "TRUE"], "nodes": [0, 1],
                 "row_contract_sha256": {}}
        receipt = {"source_manifest_sha256": "c" * 64,
                   "config": {}, "answer_ids": [1]}
        contexts = []
        cohorts = []
        for seed, prefix in ((1, "x"), (2, "y")):
            rows = [
                {"id": prefix + "0", "capability": "A.X",
                 "gold": "TRUE", "tokens": [1]},
                {"id": prefix + "1", "capability": "A.X",
                 "gold": "FALSE", "tokens": [1]},
            ]
            cohort = make_cohort(
                rows, generator_version="fixture", seed=seed,
                rubric_version="fixture")
            context = {
                "cohort_sha256": cohort.digest,
                "rubric_sha256": "d" * 64,
                "cohort_rubric_sha256": "d" * 64,
                "assessment_scope_sha256": "e" * 64,
                "source_graph_sha256": trainer._fingerprint(graph),
                "source_oracle_sha256": "c" * 64,
                "scores": {"A.X": {"correct": 2, "total": 2}},
                "questions": {"A.X": [
                    {"id": row["id"], "gold": row["gold"]} for row in rows]},
                "correct_questions": {"A.X": [
                    {"id": row["id"], "gold": row["gold"]} for row in rows]},
            }
            contexts.append(context)
            cohorts.append((cohort, rows))
        role = {
            "capability": "A.X",
            "surviving_battery": list(
                battery_from_exam(contexts[0], ("A.X",)) +
                battery_from_exam(contexts[1], ("A.X",))),
        }
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "cohorts").mkdir()
            for cohort, rows in cohorts:
                (root / "cohorts" / (cohort.digest + ".json")).write_text(
                    json.dumps({
                        "cohort_sha256": cohort.digest,
                        "rubric_sha256": "d" * 64,
                        "source_manifest_sha256": "c" * 64,
                        "schema": "fixture",
                        "generator_version": "fixture",
                        "seed": cohort.seed,
                        "rows": rows,
                    }))
            answers = {"x0": "TRUE", "x1": "FALSE",
                       "y0": "TRUE", "y1": "FALSE"}
            with patch('bilqis_mlx.learning.student_ops._predictions', return_value=answers) as infer:
                result = trainer._fresh_battery_results(
                    None, root, receipt, role, {}, graph)

        self.assertEqual(infer.call_count, 1)
        self.assertEqual(len(infer.call_args.args[2]), 4)
        self.assertEqual(set(result), {
            segment["sha256"] for segment in role["surviving_battery"]})
        self.assertTrue(all(len(correct) == 2 for correct in result.values()))

    def test_title_match_reinfers_both_models_for_current_panel_and_battery(self):
        graph = {"tokens": ["PAD", "TRUE"], "nodes": [0, 1],
                 "row_contract_sha256": {}}
        rows = [{"id": "x0", "capability": "A.X", "gold": "TRUE", "tokens": [1]},
                {"id": "x1", "capability": "A.X", "gold": "FALSE", "tokens": [1]}]
        cohort = make_cohort(rows, generator_version="fixture", seed=1,
                             rubric_version="d" * 64)
        incumbent = {"filename": "bundles/old", "sha256": "a" * 64,
                     "optimizer_step": 10, "model_and_native_adamw": True}
        challenger_pointer = {"filename": "bundles/new", "sha256": "b" * 64,
                              "optimizer_step": 11, "model_and_native_adamw": True}
        context = {
            "cohort_sha256": cohort.digest, "rubric_sha256": "d" * 64,
            "cohort_rubric_sha256": "d" * 64,
            "assessment_scope_sha256": "e" * 64,
            "source_graph_sha256": trainer._fingerprint(graph),
            "source_oracle_sha256": "c" * 64,
        }
        earning = {
            **context, "checkpoint": incumbent,
            "scores": {"A.X": {"correct": 2, "total": 2}},
            "questions": {"A.X": [{"id": r["id"], "gold": r["gold"]} for r in rows]},
            "correct_questions": {
                "A.X": [{"id": r["id"], "gold": r["gold"]} for r in rows]},
        }
        role = {
            "capability": "A.X", "checkpoint": incumbent,
            "surviving_battery": list(battery_from_exam(earning, ("A.X",))),
        }
        epoch = {"active_roles": {"A.X": role}}
        challenger = {
            **context, "checkpoint": challenger_pointer,
            "scores": {"A.X": {"correct": 2, "total": 2}},
            "questions": earning["questions"],
            "correct_questions": earning["correct_questions"],
        }
        receipt = {"source_manifest_sha256": "c" * 64,
                   "config": {}, "answer_ids": [1]}
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "cohorts").mkdir()
            (root / "cohorts" / (cohort.digest + ".json")).write_text(json.dumps({
                "cohort_sha256": cohort.digest, "rubric_sha256": "d" * 64,
                "source_manifest_sha256": "c" * 64, "schema": "d" * 64,
                "generator_version": "fixture", "seed": 1, "rows": rows}))
            predictions = [
                {"x0": "TRUE", "x1": "FALSE"},   # incumbent fresh current
                {"x0": "WRONG", "x1": "FALSE"},  # contender fresh current
                {"x0": "WRONG", "x1": "FALSE"},  # incumbent fresh battery
                {"x0": "TRUE", "x1": "FALSE"},   # contender fresh battery
            ]
            with (patch('bilqis_mlx.runtime.mlx_checkpoint.load_semantically_bound_bundle', return_value=(
                    {}, None, {"safetensors_sha256": "a" * 64,
                               "optimizer_step": 10}, graph)),
                  patch('bilqis_mlx.learning.student_ops._predictions', side_effect=predictions) as infer):
                match = trainer._fresh_title_match(
                    None, root, receipt, epoch, cohort, challenger, {}, graph, "A.X")
        self.assertEqual(infer.call_count, 4)
        self.assertEqual(match["incumbent_current_exam"]["scores"]["A.X"]["correct"], 2)
        self.assertEqual(match["challenger_current_exam"]["scores"]["A.X"]["correct"], 1)
        segment = role["surviving_battery"][0]["sha256"]
        self.assertEqual(len(match["battery_results"]["a" * 64][segment]), 1)
        self.assertEqual(len(match["battery_results"]["b" * 64][segment]), 2)
