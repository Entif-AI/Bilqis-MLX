"""Championship evidence stays separate from ordinary local C05 retention evidence."""
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from bilqis_mlx.runtime.capability_retention import EvidenceStage
from bilqis_mlx.runtime.tests.capability.capability_retention_helpers import _cases, _solver
import bilqis_mlx.runtime.retention.championship_evidence as championship_evidence


class ChampionshipEvidenceTests(unittest.TestCase):
    def test_stable_panel_enables_generation_independent_compiled_cohort_reuse(self):
        rows = ({"id": "row-1", "capability": "future:first", "tokens": [1]},)
        projection = NS(source="1" * 64, assessment="2" * 64)
        verification = NS(digest=lambda: "3" * 64)
        release = NS(
            release_sha256="4" * 64, semantic_catalog_sha256="5" * 64)
        source_context = NS(
            release=release,
            execution_for=lambda capability: NS(grade_id="future"),
            assessment_projection_for=lambda capability: projection,
            verification_for=lambda capability: verification,
            draw_rows=lambda **kwargs: rows,
        )
        raw = NS(rows=rows)

        with patch.object(
                championship_evidence, "make_cohort", return_value=raw), patch.object(
                championship_evidence, "_instruments",
                return_value=("instrument",)) as instruments:
            actual, _contract = championship_evidence.capability_championship_instruments(
                source_context, object(), "artifact", NS(run_id="run"),
                "future:first")

        self.assertEqual(actual, ("instrument",))
        self.assertNotIn("each", instruments.call_args.kwargs)
        self.assertTrue(instruments.call_args.kwargs["release_prevalidated"])

    def test_measurement_is_complete_for_target_without_peer_school_scope(self):
        cases, contexts = _cases("future:first", "future", 2, "first")
        solver = _solver(contexts, {case.case_id for case in cases})
        instruments = tuple(NS(case=case) for case in cases)
        contract = NS(
            rubric_sha256="1" * 64, source_sha256="2" * 64,
            factory_release_sha256="3" * 64,
            semantic_catalog_sha256="4" * 64)
        source_context = NS(
            execution_for=lambda capability: NS(grade_id="future")
            if capability == "future:first" else None)
        observed = []

        with patch.object(
                championship_evidence, "capability_championship_instruments",
                return_value=(instruments, contract)), patch.object(
                championship_evidence, "factory_complete_solver",
                return_value=(solver, "4" * 64)):
            cohort, assessment = championship_evidence.capability_championship_evidence(
                source_context, object(), "artifact", object(), "future:first",
                ((), ()), EvidenceStage.FOUNDATION_ACQUISITION,
                observer=observed.append)

        self.assertEqual(cohort.capability_groups, (("future:first", "future"),))
        self.assertEqual({case.capability_id for case in cohort.cases}, {"future:first"})
        self.assertEqual(assessment.score("future:first"), (2, 2))
        profile = {}
        for event in observed:
            profile.update(event)
        for field in (
                "retention_championship_prepare_wall_seconds",
                "retention_championship_solver_wall_seconds",
                "retention_championship_candidate_wall_seconds"):
            self.assertIsInstance(profile[field], float)
            self.assertGreaterEqual(profile[field], 0.0)


if __name__ == "__main__":
    unittest.main()
