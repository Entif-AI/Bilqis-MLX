"""Whole-school fixed-frontier admission invariants, without neural training."""
import json
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.fixed_frontier import load_frontier, screen_frontier
from bilqis_mlx.generated_assessment import make_cohort


class FixedFrontierTests(unittest.TestCase):
    def test_saved_misses_reconstruct_parent_and_item_trade_is_visible(self):
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
            fixed_rows, parent = load_frontier(run, receipt)

        candidate = dict(parent)
        candidate["B.NOT:1"] = "FALSE"
        candidate["C.DIV:0"] = "FALSE"
        result = screen_frontier(
            fixed_rows, parent, candidate, cohort.digest)
        self.assertEqual(result["before_correct"], 3)
        self.assertEqual(result["after_correct"], 3)
        self.assertEqual(result["repaired"], [{
            "id": "B.NOT:1", "capability": "B.NOT"}])
        self.assertEqual(result["regressions"], [{
            "id": "C.DIV:0", "capability": "C.DIV"}])

    def test_grade_slices_report_cross_grade_repairs_without_requiring_origin_gain(self):
        rows = [
            {"id": "B.IFF:0", "capability": "B.IFF", "gold": "TRUE"},
            {"id": "B.NOT:0", "capability": "B.NOT", "gold": "FALSE"},
            {"id": "C.DIV:0", "capability": "C.DIV", "gold": "TRUE"},
        ]
        parent = {
            "B.IFF:0": "TRUE", "B.NOT:0": "FALSE", "C.DIV:0": "FALSE"}
        candidate = dict(parent)
        candidate["C.DIV:0"] = "TRUE"
        result = screen_frontier(rows, parent, candidate, "a" * 64)
        self.assertEqual(result["regressions"], [])
        self.assertEqual(result["grades"]["B"], {
            "before": 2, "after": 2, "total": 2, "net_correct_delta": 0})
        self.assertEqual(result["grades"]["C"], {
            "before": 0, "after": 1, "total": 1, "net_correct_delta": 1})
