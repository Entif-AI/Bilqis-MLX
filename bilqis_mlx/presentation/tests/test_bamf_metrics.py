"""BAMF cockpit separates source coverage, activity, retention and measured gain."""
import copy
import io
import unittest

from bilqis_mlx.presentation.dashboard import ingest
from bilqis_mlx.presentation.school_telemetry import LETTER_TABLES, SchoolTelemetry
from bilqis_mlx.presentation.spiral_dashboard import Dashboard
from bilqis_mlx.presentation.tests.school50.fixtures import exam


def receipt():
    return {
        "schema": "bilqis.bamf.operator-status/v1",
        "source_release_sha256": "a" * 64, "model_sha256": "b" * 64,
        "evaluator_sha256": "c" * 64, "rights_sha256": "d" * 64,
        "coverage_census_sha256": "e" * 64,
        "coverage": {"source_eligible": 8, "source_held": 3,
                     "implementation_uncovered": 2, "ready": 2, "staged": 1,
                     "admitted": 1, "exposed": 1, "qualified": 1},
        "observations": {"active_concepts": 4, "active_banks": 1,
                         "atoms_per_frame": 2.5, "fallback_fraction": 0.25,
                         "expansion_fraction": 0.5, "motif_hit_fraction": 0.0,
                         "plasticity_mode": "FAST", "memory_used_bytes": 1024,
                         "memory_budget_bytes": 4096},
    }


def board():
    result = Dashboard(stream=io.StringIO(), clock=lambda: 0,
                       tables=LETTER_TABLES, compact_header=True, show_all_panels=True)
    result.school_telemetry = SchoolTelemetry(result, active_grades=("A", "Z"))
    return result


class BamfMetricsTests(unittest.TestCase):
    def test_compact_panel_keeps_source_denominator_and_staging_distinct(self):
        value = receipt()
        saved = copy.deepcopy(value)
        view = board()
        ingest(view, {"event": "BAMF_OPERATOR_STATUS_OBSERVED", "receipt": value})
        rendered = view.render(width=320, height=40)
        self.assertIn("eligible 8 | source-held 3 | uncovered 2", rendered)
        self.assertIn("ready 2 | staged 1", rendered)
        self.assertIn("active 4 | banks 1", rendered)
        self.assertIn("transfer NOT MEASURED", rendered)
        self.assertEqual(value, saved)
        self.assertFalse(view.rows["GRADES & MASTERY"])

    def test_expansion_exposes_observations_and_exact_source_bindings(self):
        view = board()
        ingest(view, {"event": "BAMF_OPERATOR_STATUS_OBSERVED", "receipt": receipt()})
        view.atlas_expanded = True
        rendered = view.render(width=320, height=40)
        self.assertIn("atoms/frame 2.5", rendered)
        self.assertIn("fallback 25.0%", rendered)
        self.assertIn("motif hits 0.0%", rendered)
        self.assertIn("plasticity FAST", rendered)
        self.assertIn("memory 1024/4096 bytes", rendered)
        self.assertIn("census " + "e" * 64, rendered)
        self.assertIn("rubric " + "c" * 64, rendered)

    def test_ten_retentions_do_not_claim_growth_or_perfect_mastery(self):
        view = board()
        ingest(view, exam("A", 1, "rubric", {"A.IDENTITY": (5, 10)}, step=0))
        for generation in range(2, 12):
            ingest(view, {"event": "SCHOOL_VISIT_COMMITTED", "grade": "A",
                          "generation": generation, "capability": "A.IDENTITY",
                          "optimizer_step": generation, "attempted_optimizer_updates": 1,
                          "retained_optimizer_updates": 1})
        ingest(view, {"event": "BAMF_OPERATOR_STATUS_OBSERVED", "receipt": receipt()})
        flat = view.render(width=320, height=40)
        self.assertIn("GREW +0 | retained steps 10", flat)
        self.assertIn("perfect mastery NOT MEASURED", flat)
        ingest(view, exam("A", 12, "rubric", {"A.IDENTITY": (6, 10)}, step=12))
        self.assertIn("GREW +10 | retained steps 10", view.render(width=320, height=40))

    def test_relabeling_grade_preserves_coverage_and_policy(self):
        panels = []
        for grade in ("A", "Z"):
            view = board()
            ingest(view, exam(grade, 1, "same-rubric", {grade + ".TARGET": (5, 10)}, step=0))
            ingest(view, {"event": "BAMF_OPERATOR_STATUS_OBSERVED", "receipt": receipt()})
            panels.append([line for line in view.render(width=320, height=40).splitlines()
                           if line.startswith(("ATLAS", "LEARNING"))])
        self.assertEqual(panels[0], panels[1])
        self.assertIn("grade-neutral", panels[0][0])

    def test_missing_observations_remain_unmeasured(self):
        value = receipt()
        value.pop("observations")
        view = board()
        ingest(view, {"event": "BAMF_OPERATOR_STATUS_OBSERVED", "receipt": value})
        view.atlas_expanded = True
        rendered = view.render(width=320, height=40)
        self.assertIn("active NOT MEASURED | banks NOT MEASURED", rendered)
        self.assertIn("memory NOT MEASURED", rendered)
        self.assertNotIn("NaN", rendered)
        self.assertNotIn("nan", rendered)

    def test_malformed_receipt_preserves_previous_view(self):
        from bilqis_mlx.errors import BilqisError
        view = board()
        ingest(view, {"event": "BAMF_OPERATOR_STATUS_OBSERVED", "receipt": receipt()})
        original = view.bamf_operator_view
        for mutate in (lambda r: r["coverage"].update(ready=99),
                       lambda r: r["observations"].update(fallback_fraction=float("nan")),
                       lambda r: r.update(model_sha256="missing"),
                       lambda r: r["coverage"].update(source_eligible=True)):
            value = receipt()
            mutate(value)
            with self.subTest(receipt=value), self.assertRaises(BilqisError):
                ingest(view, {"event": "BAMF_OPERATOR_STATUS_OBSERVED", "receipt": value})
            self.assertIs(view.bamf_operator_view, original)
