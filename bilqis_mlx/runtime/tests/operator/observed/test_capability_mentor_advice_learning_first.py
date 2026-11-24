"""Ordinary-mode frozen championship adviser reuse."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import tempfile
from unittest.mock import patch

from bilqis_mlx.runtime.championship_advisers import (
    championship_mentor_supervision, prepare_championship_adviser_pool,
)
from bilqis_mlx.runtime.tests.operator.observed.capability_championship_support import (
    CAPABILITY, NativeChampionshipCase, capability_cohort, measurement,
)
from bilqis_mlx.runtime.tests.operator.observed.test_capability_mentor_advice_operator_path import (
    _accepted_ancestor_fixture, _answer, _runtime_context,
)


class LearningFirstChampionshipAdviceTests(NativeChampionshipCase):
    def test_ordinary_session_reuses_frozen_pool_and_identical_lesson_inference(self):
        from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
        from bilqis_mlx.runtime.championship_advisers import championship_adviser_session
        group = "Z"
        self.context = _runtime_context(self, group=group)
        cohort, contexts = capability_cohort(CAPABILITY, group)
        self.cohort, self.contexts = cohort, contexts
        first = self.successor()
        assessment, binding = measurement(first, cohort, contexts, 19, "8" * 64)
        titled = self.bind(self.parent, first, assessment, binding)
        cache = SimpleNamespace(accepted_manifest_sha256="a" * 64)
        gold = _answer(True)
        instrument = SimpleNamespace(case=SimpleNamespace(goal="g", gold=gold, capability_id=CAPABILITY))
        solver = SimpleNamespace(evaluate_cases=lambda goals, generation: ((SimpleNamespace(answer=gold), ()),),
                                 telemetry_for=lambda: {"shared_backbone_launches": 1})
        with tempfile.TemporaryDirectory() as temp, evidence_mode(strict=False), championship_adviser_session(), patch(
                "bilqis_mlx.runtime.championship_advisers._accepted_ancestor",
                return_value=(_accepted_ancestor_fixture(titled), "f" * 64)), patch(
                "bilqis_mlx.runtime.championship_advisers.factory_evaluation_instruments", return_value=(instrument,)), patch(
                "bilqis_mlx.runtime.championship_advisers.factory_complete_solver", return_value=(solver, "g")):
            pool = prepare_championship_adviser_pool(Path(temp), titled, self.context, "atlas", cache, reserve_gib=0)
            rows = ({"id": "row:one", "capability": CAPABILITY},)
            first_advice = championship_mentor_supervision(pool, rows, source_seed=1, teacher_strategy={"distill": 1.0})
            second_pool = prepare_championship_adviser_pool(Path(temp), titled, self.context, "atlas", cache, reserve_gib=0)
            second_advice = championship_mentor_supervision(second_pool, rows, source_seed=1, teacher_strategy={"distill": 0.25})
            third = championship_mentor_supervision(second_pool, ({"id": "row:two", "capability": CAPABILITY},),
                                                   source_seed=2, teacher_strategy={"distill": 1.0})
            advanced = replace(titled, generation=titled.generation + 1,
                               parent_manifest_sha256=cache.accepted_manifest_sha256)
            next_cache = SimpleNamespace(accepted_manifest_sha256="b" * 64)
            with patch("bilqis_mlx.runtime.championship_advisers._accepted_ancestor",
                       side_effect=AssertionError("unchanged roster must not reload tensors")):
                advanced_pool = prepare_championship_adviser_pool(Path(temp), advanced, self.context, "atlas", next_cache, reserve_gib=0)
                next_advice = championship_mentor_supervision(advanced_pool, rows, source_seed=1, teacher_strategy={"distill": 1.0})
        self.assertEqual(next_advice.accepted_manifest_sha256, "b" * 64)
        self.assertEqual(next_advice.physical_inference_launches, 1)
        self.assertEqual(first_advice.physical_inference_launches, 1)
        self.assertEqual(second_advice.physical_inference_launches, 0)
        self.assertEqual(third.physical_inference_launches, 1)
        self.assertEqual(first_advice.rows[0].direct_votes, 1)
        self.assertEqual(first_advice.rows[0].soup_votes, 1.0)
        self.assertEqual(second_advice.rows[0].influence, first_advice.rows[0].influence * 0.5)
        self.assertEqual(third.rows[0].row_id, "row:two")
