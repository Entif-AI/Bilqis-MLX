"""Behavior contracts for source-grounded sampling, independent of MLX and files."""
import unittest

from bilqis_mlx.semantic_sampling import (
    AuditPolicy,
    BinaryBalancePolicy,
    InvalidSamplingPolicy,
    SamplingRule,
    audit_budget_violations,
    balanced_answer_targets,
    missing_coverage_cases,
    sample_count_violations,
)
from bilqis_mlx.errors import BilqisError, SEMANTIC_COVERAGE
from bilqis_mlx.semantic_coverage import (
    audit_pinned_micro_generator, affected_typed_dependency_closure,
)
from bilqis_mlx.live_grade_b import draw_connectives


class SamplingPolicyTests(unittest.TestCase):
    def test_invalid_policy_configuration_cannot_be_constructed(self):
        with self.assertRaises(InvalidSamplingPolicy):
            BinaryBalancePolicy(minimum_per_outcome=-1)
        with self.assertRaises(InvalidSamplingPolicy):
            BinaryBalancePolicy(minimum_per_outcome=True)
        with self.assertRaises(InvalidSamplingPolicy):
            BinaryBalancePolicy(outcomes=(True, True))
        with self.assertRaises(InvalidSamplingPolicy):
            AuditPolicy(minimum_rounds=5, max_rounds=2)

    def test_minimum_sample_size_follows_outcome_count_and_per_outcome_policy(self):
        policy = BinaryBalancePolicy(minimum_per_outcome=2)
        self.assertEqual(policy.minimum_total, 4)
        self.assertEqual(
            sample_count_violations(2, policy=policy)[0].rule,
            SamplingRule.INSUFFICIENT_PER_OUTCOME,
        )
        self.assertEqual(sample_count_violations(4, policy=policy), ())
        self.assertEqual(sample_count_violations(6, policy=policy), ())

    def test_even_requirement_is_a_class_balance_rule_not_an_opaque_modulo(self):
        issues = sample_count_violations(5)
        self.assertEqual([issue.rule for issue in issues],
                         [SamplingRule.NONUNIFORM_OUTCOME_ALLOCATION])
        self.assertEqual(balanced_answer_targets(6),
                         (True, False, True, False, True, False))
        self.assertEqual(sum(balanced_answer_targets(6)), 3)

    def test_type_errors_cannot_sneak_in_as_integer_budgets(self):
        self.assertEqual(sample_count_violations(True)[0].rule,
                         SamplingRule.INTEGER_REQUIRED)
        self.assertEqual(sample_count_violations(4.0)[0].rule,
                         SamplingRule.INTEGER_REQUIRED)
        self.assertEqual(audit_budget_violations(True, 4)[0].rule,
                         SamplingRule.INTEGER_REQUIRED)

    def test_round_ceiling_is_an_explicit_audit_policy_not_a_semantic_fact(self):
        policy = AuditPolicy(max_rounds=32)
        self.assertEqual(audit_budget_violations(1, 4, policy=policy), ())
        self.assertEqual(audit_budget_violations(32, 4, policy=policy), ())
        self.assertEqual(audit_budget_violations(33, 4, policy=policy)[0].rule,
                         SamplingRule.ROUND_BUDGET_OUT_OF_RANGE)
        self.assertEqual(audit_budget_violations(0, 4, policy=policy)[0].rule,
                         SamplingRule.ROUND_BUDGET_OUT_OF_RANGE)

    def test_balanced_answers_do_not_imply_complete_operand_patterns(self):
        required = ((False, False), (False, True), (True, False), (True, True))
        observed = ((False, False), (True, False), (True, True), (True, True))
        self.assertEqual(len(observed), 4)
        self.assertEqual(missing_coverage_cases(required, observed),
                         ((False, True),))

    def test_coverage_audit_reports_the_actual_invalid_field_without_source_io(self):
        with self.assertRaises(BilqisError) as captured:
            audit_pinned_micro_generator({}, "/does/not/exist", max_rounds=0, each=3)
        error = captured.exception
        self.assertIs(error.spec, SEMANTIC_COVERAGE.AUDIT.INVALID_BUDGET)
        self.assertEqual([item.field for item in error.context["violations"]],
                         ["max_rounds", "each", "each"])

    def test_pinned_grade_b_generator_matches_policy_without_source_rewrite(self):
        # A refactor of live_grade_b.py changes its constructor digest. Keep
        # the pinned implementation untouched until release-governed migration.
        with self.assertRaisesRegex(ValueError,
                                    "GRADE_B_BALANCED_EVEN_SAMPLE_REQUIRED"):
            draw_connectives("/does/not/exist", {}, seed=1, each=5)
        self.assertEqual(sample_count_violations(5)[0].rule,
                         SamplingRule.NONUNIFORM_OUTCOME_ALLOCATION)

    def test_coverage_plan_schema_guard_is_one_typed_diagnostic(self):
        with self.assertRaises(BilqisError) as captured:
            affected_typed_dependency_closure({"schema": "old"}, ())
        self.assertIs(captured.exception.spec,
                      SEMANTIC_COVERAGE.PLAN.VERSION_MISMATCH)
        self.assertIn("expected_schema", captured.exception.context)


if __name__ == "__main__":
    unittest.main()
