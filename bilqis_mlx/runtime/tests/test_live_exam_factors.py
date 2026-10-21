"""Cohort coverage follows the admitted provider's declared variation axes."""
from types import SimpleNamespace
import unittest

from bilqis_mlx.curriculum import AnswerFamily
from bilqis_mlx.trainer import _live_exam_factors_complete


def _exam(*, families, axes, rows):
    cap = SimpleNamespace(answer_families=families, variation_axes=axes)
    release = SimpleNamespace(execution_plan=SimpleNamespace(
        capability_map={"X.CAP": cap}))
    cohort = SimpleNamespace(rows=rows)
    return release, cohort


class LiveExamFactorsTests(unittest.TestCase):
    def test_numeric_domain_does_not_require_every_possible_answer_per_exam(self):
        families = (AnswerFamily("numeric_active", ("0", "1", "2", "3", "4")),)
        rows = [
            {"capability": "X.CAP", "answer_kind": "numeric_active", "gold": value}
            for value in ("0", "2", "4")]
        release, cohort = _exam(
            families=families,
            axes=("source-valid", "typed-answer", "numeric-scope", "construction-shape"),
            rows=rows)
        self.assertTrue(_live_exam_factors_complete(release, cohort, {"X.CAP": 3}))

    def test_balanced_provider_requires_full_admitted_target_domain(self):
        families = (AnswerFamily("boolean_operator", ("AND", "IFF")),)
        rows = [
            {"capability": "X.CAP", "answer_kind": "boolean_operator", "gold": "AND"}
            for _ in range(3)]
        release, cohort = _exam(
            families=families,
            axes=("source-valid", "balanced-operator-targets"), rows=rows)
        self.assertFalse(_live_exam_factors_complete(release, cohort, {"X.CAP": 3}))

    def test_missing_modality_is_not_accepted_as_coverage(self):
        families = (AnswerFamily("binary", ("FALSE", "TRUE")),
                    AnswerFamily("numeric_active", ("0", "1", "2")))
        rows = [{"capability": "X.CAP", "answer_kind": "binary", "gold": "FALSE"}]
        release, cohort = _exam(
            families=families, axes=("source-valid", "typed-answer"), rows=rows)
        self.assertFalse(_live_exam_factors_complete(release, cohort, {"X.CAP": 1}))


if __name__ == "__main__":
    unittest.main()
