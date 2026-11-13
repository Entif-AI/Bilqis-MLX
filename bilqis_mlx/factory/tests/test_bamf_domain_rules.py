"""C14.3 recursive grade-neutral domain-rule and succession contract."""
import unittest

from bilqis_mlx.factory.curriculum.developmental_program import load_bamf_developmental_program
from bilqis_mlx.factory.curriculum.developmental_rules import (
    CROSS_DOMAIN_BLOCKING, GRADE_INTRODUCTION,
    load_developmental_rule_manifest, resolve_domain_succession,
)
from bilqis_mlx.factory.curriculum.developmental_stage import (
    DevelopmentalLearnerState, DevelopmentalSourceCoverage,
)
from bilqis_mlx.factory.tests.test_bamf_training_program import BamfTrainingStageTests


class BamfDomainRulesTests(unittest.TestCase):
    def test_same_policy_covers_boolean_numeric_and_future_world_semantics(self):
        rules = load_developmental_rule_manifest()

        self.assertIn("boolean_composition", rules.family_ids)
        self.assertIn("numeric_composition", rules.family_ids)
        self.assertIn("qualified_world_model", rules.family_ids)
        self.assertEqual(rules.grade_introduction, GRADE_INTRODUCTION)
        self.assertEqual(rules.cross_domain_blocking, CROSS_DOMAIN_BLOCKING)
        self.assertFalse(rules.named_grade_priority)
        self.assertFalse(rules.named_grade_debt_exception)
        self.assertEqual(rules.shared_contracts, (
            "SOURCE_QUALIFIED_PREREQUISITES",
            "CURRENT_EVIDENCE_REQUIRED",
            "FAMILY_OWNED_TEACHING_ASSESSMENT",
            "GRADE_NEUTRAL_PROMOTION_DEBT",
            "FACTORY_RELEASE_ADMISSION",
        ))

    def test_grade_label_permutation_changes_metadata_not_recursive_selection(self):
        program = load_bamf_developmental_program()
        rules = load_developmental_rule_manifest()
        release_a, snapshot_a, closure_a = BamfTrainingStageTests._coverage_fixture(("A", "B"))
        release_b, snapshot_b, closure_b = BamfTrainingStageTests._coverage_fixture(("Q", "R"))

        first = resolve_domain_succession(
            program, DevelopmentalSourceCoverage(snapshot_a, closure_a),
            DevelopmentalLearnerState(release_a), rules)
        second = resolve_domain_succession(
            program, DevelopmentalSourceCoverage(snapshot_b, closure_b),
            DevelopmentalLearnerState(release_b), rules)

        self.assertEqual(first.stage.selected_semantic_id, second.stage.selected_semantic_id)
        self.assertEqual(first.selected_rule_family_ids, second.selected_rule_family_ids)
        self.assertEqual(first.stage.status, second.stage.status)
        self.assertEqual(first.stage.active_grade_ids, second.stage.active_grade_ids)
        self.assertFalse(first.stage.authorizes_learning)
        self.assertFalse(second.stage.authorizes_learning)

    def test_typed_cross_domain_prerequisite_blocks_without_named_grade_exception(self):
        program = load_bamf_developmental_program()
        rules = load_developmental_rule_manifest()
        release, snapshot, closure = BamfTrainingStageTests._coverage_fixture(("A", "B"))

        intent = resolve_domain_succession(
            program, DevelopmentalSourceCoverage(snapshot, closure),
            DevelopmentalLearnerState(release), rules)

        self.assertEqual(intent.stage.selected_semantic_id, "z.op.2")
        self.assertTrue(any(
            item.code == "PREREQUISITE_WAITING_FOR_EVIDENCE"
            and item.dependency_id == "z.op.2"
            for item in intent.stage.remediation))
        self.assertFalse(intent.named_grade_priority)
        self.assertFalse(intent.named_grade_debt_exception)


if __name__ == "__main__":
    unittest.main()
