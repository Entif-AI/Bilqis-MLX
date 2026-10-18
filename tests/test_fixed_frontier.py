"""Fixed whole-school frontier is monotonic across candidate admission."""
import json
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.fixed_frontier import load_frontier, screen_frontier
from bilqis_mlx.generated_assessment import make_cohort


class FixedFrontierTests(unittest.TestCase):
    def test_saved_misses_reconstruct_parent_and_new_error_cannot_be_offset(self):
        rows = [
            {"id": "B.NOT:0", "capability": "B.NOT", "gold": "TRUE"},
            {"id": "B.NOT:1", "capability": "B.NOT", "gold": "FALSE"},
            {"id": "C.DIV:0", "capability": "C.DIV", "gold": "TRUE"},
            {"id": "C.DIV:1", "capability": "C.DIV", "gold": "FALSE"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "cohorts").mkdir()
            cohort = make_cohort(
                rows, generator_version="test-generator", seed=7,
                rubric_version="test-rubric")
            (run / "cohorts" / f"{cohort.digest}.json").write_text(json.dumps({
                "schema": "test-rubric",
                "generator_version": "test-generator",
                "seed": 7,
                "cohort_sha256": cohort.digest,
                "rows": rows,
            }))
            receipt = {"last_exam": {
                "student_sha256": "b" * 64,
                "optimizer_step": 123,
                "cohort_sha256": cohort.digest,
                "cohort_file": f"cohorts/{cohort.digest}.json",
                "scores": {
                    "B.NOT": {"correct": 1, "total": 2},
                    "C.DIV": {"correct": 2, "total": 2},
                },
                "misses_for_teacher": [{
                    "id": "B.NOT:1", "source_id": "B.NOT:1",
                    "capability": "B.NOT", "gold": "FALSE",
                    "predicted": "TRUE",
                }],
            }}
            fixed_rows, parent = load_frontier(
                run, receipt, parent_sha256="b" * 64,
                parent_optimizer_step=123)

        self.assertEqual(parent, {
            "B.NOT:0": "TRUE",
            "B.NOT:1": "TRUE",
            "C.DIV:0": "TRUE",
            "C.DIV:1": "FALSE",
        })
        candidate = dict(parent)
        candidate["B.NOT:1"] = "FALSE"  # repair the old miss
        candidate["C.DIV:0"] = "FALSE"  # but create a new error
        result = screen_frontier(
            fixed_rows, parent, candidate, cohort.digest)
        self.assertEqual(result["before_correct"], 3)
        self.assertEqual(result["after_correct"], 3)
        self.assertEqual(result["repaired"], [{
            "id": "B.NOT:1", "capability": "B.NOT"}])
        self.assertEqual(result["regressions"], [{
            "id": "C.DIV:0", "capability": "C.DIV"}])

    def test_frontier_grade_slice_is_available_independent_of_scheduler_grade(self):
        rows = [
            {"id": "B.IFF:0", "capability": "B.IFF", "gold": "TRUE"},
            {"id": "B.NOT:0", "capability": "B.NOT", "gold": "FALSE"},
            {"id": "C.DIV:0", "capability": "C.DIV", "gold": "TRUE"},
        ]
        parent = {row["id"]: row["gold"] for row in rows}
        candidate = dict(parent)
        candidate["B.NOT:0"] = "TRUE"
        result = screen_frontier(rows, parent, candidate, "a" * 64)
        self.assertEqual(result["grades"]["B"], {
            "before": 2, "after": 1, "total": 2, "net_correct_delta": -1})
        self.assertEqual(result["grades"]["C"], {
            "before": 1, "after": 1, "total": 1, "net_correct_delta": 0})

    def test_frontier_fails_closed_when_saved_exam_is_not_exact_parent(self):
        rows = [{"id": "B.NOT:0", "capability": "B.NOT", "gold": "TRUE"}]
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "cohorts").mkdir()
            cohort = make_cohort(
                rows, generator_version="test-generator", seed=7,
                rubric_version="test-rubric")
            (run / "cohorts" / f"{cohort.digest}.json").write_text(json.dumps({
                "schema": "test-rubric",
                "generator_version": "test-generator",
                "seed": 7,
                "cohort_sha256": cohort.digest,
                "rows": rows,
            }))
            receipt = {"last_exam": {
                "student_sha256": "a" * 64,
                "optimizer_step": 41,
                "cohort_sha256": cohort.digest,
                "cohort_file": f"cohorts/{cohort.digest}.json",
                "scores": {"B.NOT": {"correct": 1, "total": 1}},
                "misses_for_teacher": [],
            }}
            with self.assertRaisesRegex(
                    ValueError, "FIXED_FRONTIER_PARENT_IDENTITY_DRIFT"):
                load_frontier(
                    run, receipt, parent_sha256="b" * 64,
                    parent_optimizer_step=42)
