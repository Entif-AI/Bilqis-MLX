"""A diagnostic is an immutable domain value, not ad hoc exception prose."""
import unittest

from bilqis_mlx.runtime.diagnostic_bus import (
    DiagnosticError,
    ErrorBus,
    SemanticCoverageCode,
    GradeBCode,
    lookup_definition,
)
from bilqis_mlx.runtime.operator_recovery import recovery_advice
from bilqis_mlx.semantic_sampling import SamplingRule, SamplingViolation


class DiagnosticBusTests(unittest.TestCase):
    def test_broker_preserves_structured_context_and_stable_machine_identity(self):
        with self.assertRaises(DiagnosticError) as captured:
            ErrorBus.Raise(SemanticCoverageCode.PLAN_VERSION_MISMATCH,
                           actual="previous", expected="current")
        error = captured.exception
        self.assertEqual(error.code, SemanticCoverageCode.PLAN_VERSION_MISMATCH)
        self.assertEqual(error.context["actual"], "previous")
        self.assertEqual(error.context["expected"], "current")
        self.assertIn(error.code.value, str(error))
        self.assertIn("plan.version_mismatch", lookup_definition(error.code).message_key)
        with self.assertRaises(TypeError):
            error.context["actual"] = "tampered"
        self.assertEqual(recovery_advice(error).code,
                         SemanticCoverageCode.PLAN_VERSION_MISMATCH.value)

    def test_legacy_external_code_is_symbolic_and_operator_action_is_catalog_owned(self):
        definition = lookup_definition(GradeBCode.BALANCED_SAMPLE_REQUIRED)
        self.assertEqual(definition.code.value,
                         "GRADE_B_BALANCED_EVEN_SAMPLE_REQUIRED")
        with self.assertRaises(DiagnosticError) as captured:
            ErrorBus.Raise(GradeBCode.BALANCED_SAMPLE_REQUIRED,
                           violations=(SamplingViolation(
                               "each", SamplingRule.INTEGER_REQUIRED, True, "int"),))
        advice = recovery_advice(captured.exception)
        self.assertEqual(advice.disposition, "CORRECT_INPUT_OR_STATE")
        self.assertIn("balanced", advice.next_action.lower())


if __name__ == "__main__":
    unittest.main()
