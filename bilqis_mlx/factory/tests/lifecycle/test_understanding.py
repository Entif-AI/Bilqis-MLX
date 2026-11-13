import unittest

from bilqis_mlx.factory.autonomy import EvidenceKind
from bilqis_mlx.factory.development import (
    UnderstandingProjection, post_boolean_staircase,
)
from bilqis_mlx.factory.understanding import (
    PROJECTION_SPECS,
    ProofAxis,
    autonomy_projection_inputs,
    contract_for_target,
    plan_understanding_evidence,
)


class UnderstandingProjectionTests(unittest.TestCase):
    def setUp(self):
        self.staircase = post_boolean_staircase()

    def test_each_projection_has_a_distinct_observable_proof_axis(self):
        axes = {
            projection: spec.proof_axes
            for projection, spec in PROJECTION_SPECS.items()
        }
        self.assertEqual(
            axes[UnderstandingProjection.DISCRIMINATE],
            (ProofAxis.NEAREST_NEIGHBOR_CONTRAST,),
        )
        self.assertEqual(
            axes[UnderstandingProjection.TRANSFER],
            (ProofAxis.NONCE_SYMBOL_RENAMING,),
        )
        self.assertEqual(
            axes[UnderstandingProjection.COMPOSE],
            (ProofAxis.HELD_OUT_RECOMBINATION,),
        )
        self.assertEqual(
            axes[UnderstandingProjection.INVERT],
            (ProofAxis.REVERSE_MAPPING,),
        )
        self.assertEqual(
            axes[UnderstandingProjection.COUNTERFACTUAL],
            (ProofAxis.SINGLE_FACTOR_PERTURBATION,),
        )
        self.assertEqual(
            axes[UnderstandingProjection.EXPLAIN],
            (ProofAxis.STRUCTURED_CAUSAL_TRACE,),
        )

    def test_target_contract_requests_only_projections_relevant_to_that_step(self):
        law = contract_for_target(
            self.staircase.target_map["DEV.LAW_SCHEMA"])
        requested = tuple(item.projection for item in law.projections)
        self.assertIn(UnderstandingProjection.TRANSFER, requested)
        self.assertIn(UnderstandingProjection.INVERT, requested)
        self.assertNotIn(UnderstandingProjection.EXPLAIN, requested)

    def test_unsupported_projection_becomes_coverage_debt_not_fake_evidence(self):
        target = self.staircase.target_map["DEV.ALLOMORPHY"]
        contract = contract_for_target(target)
        plan = plan_understanding_evidence(
            contract,
            generation_axes=("source-valid", "fresh-seed"),
            supported_projections=(UnderstandingProjection.EXECUTE,),
        )
        self.assertEqual(len(plan.obligations), 1)
        self.assertEqual(
            plan.obligations[0].key,
            UnderstandingProjection.EXECUTE.value,
        )
        self.assertFalse(plan.source_supported)
        self.assertIn(
            "DEV.ALLOMORPHY:INVERT:SOURCE_PROJECTION_UNSUPPORTED",
            plan.coverage_debt,
        )

    def test_fully_supported_contract_mints_projection_obligations(self):
        target = self.staircase.target_map["DEV.FEATURE_BUNDLE"]
        contract = contract_for_target(target)
        supported = tuple(item.projection for item in contract.projections)
        plan = plan_understanding_evidence(
            contract,
            generation_axes=("source-valid", "fresh-seed"),
            supported_projections=supported,
        )
        self.assertTrue(plan.source_supported)
        self.assertEqual(
            tuple(item.kind for item in plan.obligations),
            (EvidenceKind.PROJECTION,) * len(contract.projections),
        )
        compose = next(
            item for item in plan.obligations
            if item.key == UnderstandingProjection.COMPOSE.value)
        self.assertEqual(
            compose.proof_axes,
            (ProofAxis.HELD_OUT_RECOMBINATION.value,),
        )
        self.assertEqual(compose.minimum_specimens, 2)

    def test_explanation_is_structured_trace_not_free_form_language_requirement(self):
        target = self.staircase.target_map["DEV.COUNTERFACTUAL_EXPLANATION"]
        contract = contract_for_target(target)
        explain = next(
            item for item in contract.projections
            if item.projection is UnderstandingProjection.EXPLAIN)
        self.assertEqual(
            explain.proof_axes,
            (ProofAxis.STRUCTURED_CAUSAL_TRACE,),
        )
        self.assertIn("rule, bindings, and result", explain.failure_signature)

    def test_adapter_cannot_claim_projection_outside_target_contract(self):
        target = self.staircase.target_map["DEV.FEATURE_DIMENSION"]
        contract = contract_for_target(target)
        with self.assertRaisesRegex(ValueError, "SUPPORT_OUTSIDE_CONTRACT"):
            plan_understanding_evidence(
                contract,
                generation_axes=("source-valid",),
                supported_projections=(
                    *tuple(item.projection for item in contract.projections),
                    UnderstandingProjection.EXPLAIN,
                ),
            )

    def test_source_evidence_plan_projects_into_autonomy_inputs_without_reinterpretation(self):
        target = self.staircase.target_map["DEV.LAW_SCHEMA"]
        contract = contract_for_target(target)
        plan = plan_understanding_evidence(
            contract,
            generation_axes=("source-valid", "fresh-seed"),
            supported_projections=(
                UnderstandingProjection.TRANSFER,
                UnderstandingProjection.INVERT,
            ),
        )
        specs, debt = autonomy_projection_inputs((plan,))
        self.assertEqual(
            tuple(item.projection_id for item in specs),
            ("TRANSFER", "INVERT"),
        )
        self.assertEqual(
            tuple(item.proof_axes for item in specs),
            (("nonce-symbol-renaming",), ("reverse-mapping",)),
        )
        self.assertIn(
            "DEV.LAW_SCHEMA:COUNTERFACTUAL:SOURCE_PROJECTION_UNSUPPORTED",
            debt,
        )


if __name__ == "__main__":
    unittest.main()
