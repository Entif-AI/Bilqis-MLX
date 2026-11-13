"""C14.3 recursive grade-neutral domain-rule and succession contract."""
from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.curriculum.developmental_program import load_bamf_developmental_program
from bilqis_mlx.factory.curriculum.developmental_rules import (
    CROSS_DOMAIN_BLOCKING, GRADE_INTRODUCTION, SHARED_CONTRACTS,
    DevelopmentalRuleManifest, load_developmental_rule_manifest,
    resolve_domain_succession,
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
        self.assertEqual(rules.shared_contracts, SHARED_CONTRACTS)

    def test_shared_contracts_are_runtime_policy_not_freeform_manifest_text(self):
        rules = load_developmental_rule_manifest()

        with self.assertRaises(BilqisError):
            DevelopmentalRuleManifest(
                rules.schema, rules.policy_version, rules.family_ids,
                ("DECORATIVE_POLICY_LABEL",), rules.grade_introduction,
                rules.cross_domain_blocking, False, False)

        release, snapshot, closure = BamfTrainingStageTests._coverage_fixture()
        intent = resolve_domain_succession(
            load_bamf_developmental_program(),
            DevelopmentalSourceCoverage(snapshot, closure),
            DevelopmentalLearnerState(release), rules)
        self.assertEqual(intent.shared_contracts, SHARED_CONTRACTS)

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
        from bilqis_mlx.factory.atlas_frontier_closure import ClosureReason, ClosureStatus
        from bilqis_mlx.factory.atlas_frontier_contracts import PrerequisiteEdge
        from bilqis_mlx.factory.tests.curriculum.frontier.atlas_frontier_closure_fixtures import (
            rehash, row,
        )
        from bilqis_mlx.factory.tests.curriculum.frontier.test_atlas_frontier_selection import (
            _candidate, _closure, _release, _snapshot,
        )

        program = load_bamf_developmental_program()
        rules = load_developmental_rule_manifest()
        release = _release()
        snapshot = _snapshot(release, prerequisite_edges=(
            PrerequisiteEdge("z.op.1", "z.op.0", "a" * 64),
        ))
        snapshot = rehash(
            snapshot,
            coverage_rows=tuple(sorted((
                row("z.op.0", "boolean_composition", implemented=False),
                row("z.op.1", "numeric_composition"),
                row("z.op.2", "positive_identity"),
            ), key=lambda item: (item.semantic_id, item.family_id))),
            required_source_family_ids=(
                "boolean_composition", "numeric_composition", "positive_identity"),
        )
        uncovered = ClosureReason(
            "FAMILY_IMPLEMENTATION_UNCOVERED", "family:boolean_composition")
        waiting = ClosureReason(
            "PREREQUISITE_IMPLEMENTATION_UNCOVERED",
            "factory:prerequisite", "z.op.0")
        closure = _closure(snapshot, (
            _candidate(snapshot, "z.op.0", family_id="boolean_composition",
                       status=ClosureStatus.IMPLEMENTATION_UNCOVERED,
                       reasons=(uncovered,)),
            _candidate(snapshot, "z.op.1", family_id="numeric_composition",
                       prerequisites=("z.op.0",),
                       status=ClosureStatus.IMPLEMENTATION_UNCOVERED,
                       reasons=(waiting,)),
            _candidate(snapshot, "z.op.2", family_id="positive_identity"),
        ))

        intent = resolve_domain_succession(
            program, DevelopmentalSourceCoverage(snapshot, closure),
            DevelopmentalLearnerState(release), rules)

        self.assertEqual(intent.stage.selected_semantic_id, "z.op.2")
        self.assertEqual(intent.selected_rule_family_ids, ("positive_identity",))
        self.assertEqual(
            next(row.family_id for row in snapshot.coverage_rows
                 if row.semantic_id == "z.op.0"),
            "boolean_composition")
        self.assertEqual(
            next(row.family_id for row in snapshot.coverage_rows
                 if row.semantic_id == "z.op.1"),
            "numeric_composition")
        self.assertTrue(any(
            item.code == "PREREQUISITE_IMPLEMENTATION_UNCOVERED"
            and item.semantic_id == "z.op.1"
            and item.family_id == "numeric_composition"
            and item.dependency_id == "z.op.0"
            for item in intent.stage.remediation))
        self.assertFalse(intent.named_grade_priority)
        self.assertFalse(intent.named_grade_debt_exception)


if __name__ == "__main__":
    unittest.main()
