"""C14 developmental-program data contract."""
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.curriculum.developmental_program import (
    DevelopmentalLevel,
    load_bamf_developmental_program,
)


class BamfTrainingProgramTests(unittest.TestCase):
    def test_declares_constructive_l0_and_released_l1_l2_programs(self):
        program = load_bamf_developmental_program()

        self.assertEqual(
            tuple(item.level.value for item in program.levels),
            ("L0", "L1", "L2", "L3", "L4"),
        )
        self.assertEqual(
            program.require_level("L0").domains,
            ("positive-identity", "boolean", "numeric"),
        )
        self.assertEqual(
            program.require_level("L0").constructive_steps,
            ("POSITIVE_IDENTITY", "DIRECT_CONSTITUENTS", "LAWFUL_COMPOSITION"),
        )
        self.assertEqual(
            program.require_level("L1").domains,
            ("skos-roles", "skos-senses", "skos-morphology",
             "bravo-category-frames", "bravo-time-frames"),
        )
        self.assertEqual(
            program.require_level("L2").domains,
            ("new-concepts", "ambiguity", "relations", "cross-family-composition"),
        )
        self.assertIn("ADMITTED_RELEASE", program.require_level("L1").source_requirements)
        self.assertIn("ADMITTED_RELEASE", program.require_level("L2").source_requirements)

    def test_l3_is_optional_and_l4_packages_bounded_capabilities(self):
        program = load_bamf_developmental_program()

        self.assertTrue(program.require_level(DevelopmentalLevel.L3).optional)
        self.assertFalse(program.require_level("L3").packages_bounded_capabilities)
        self.assertTrue(program.require_level("L4").packages_bounded_capabilities)
        self.assertIn("RESOURCE_AUTHORITY", program.require_level("L3").source_requirements)
        self.assertIn("RIGHTS_AUTHORITY", program.require_level("L4").source_requirements)

    def test_program_and_levels_are_immutable_and_digest_is_stable(self):
        first = load_bamf_developmental_program()
        second = load_bamf_developmental_program()

        self.assertEqual(first.digest(), second.digest())
        with self.assertRaises(FrozenInstanceError):
            first.program_id = "other"
        with self.assertRaises(FrozenInstanceError):
            first.levels[0].purpose = "other"


    def test_public_constructors_reject_mutable_collections(self):
        from bilqis_mlx.factory.curriculum.developmental_program import (
            BamfDevelopmentalProgram, DevelopmentalDomainProgram, SCHEMA)

        with self.assertRaises(BilqisError):
            DevelopmentalDomainProgram(
                DevelopmentalLevel.L0, "bad", ["numeric"],
                ("POSITIVE_IDENTITY",), ("ADMITTED_RELEASE",))
        level = load_bamf_developmental_program().levels[0]
        with self.assertRaises(BilqisError):
            BamfDevelopmentalProgram(SCHEMA, "bad", "v1", [level])

    def test_default_manifest_is_packaged_and_operator_path_is_same_data(self):
        from importlib import resources
        from bilqis_mlx.factory.curriculum import developmental_program as owner

        packaged = resources.files(owner.__package__).joinpath(
            owner.DEFAULT_PROGRAM_RESOURCE).read_bytes()
        operator_path = (Path(__file__).resolve().parents[3] / "configs" /
                         "curricula" / "bamf-developmental-v1.json")
        self.assertEqual(operator_path.read_bytes(), packaged)
        self.assertIn(b'"numeric"', packaged)

    def test_malformed_json_collection_shape_fails_typed_boundary(self):
        path = Path(__file__).resolve().parents[3] / "configs" / "curricula" / "bamf-developmental-v1.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["levels"][0]["domains"] = "numeric"
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "program.json"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(BilqisError):
                load_bamf_developmental_program(candidate)

    def test_invalid_utf8_fails_through_typed_error_bus(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "program.json"
            candidate.write_bytes(b"\xff\xfe\xfd")
            with self.assertRaises(BilqisError) as caught:
                load_bamf_developmental_program(candidate)
        self.assertIn("FACTORY.DEVELOPMENTAL_PROGRAM.INVALID", str(caught.exception))

    def test_invalid_level_order_fails_through_typed_error_bus(self):
        path = Path(__file__).resolve().parents[3] / "configs" / "curricula" / "bamf-developmental-v1.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["levels"][0], payload["levels"][1] = payload["levels"][1], payload["levels"][0]
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "program.json"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(BilqisError) as caught:
                load_bamf_developmental_program(candidate)
        self.assertIn("FACTORY.DEVELOPMENTAL_PROGRAM.INVALID", str(caught.exception))


class BamfTrainingStageTests(unittest.TestCase):
    @staticmethod
    def _coverage_fixture(grade_labels=()):
        from bilqis_mlx.factory.atlas_frontier_closure import ClosureReason, ClosureStatus
        from bilqis_mlx.factory.atlas_frontier_contracts import PrerequisiteEdge
        from bilqis_mlx.factory.tests.curriculum.frontier.atlas_frontier_closure_fixtures import rehash
        from bilqis_mlx.factory.tests.curriculum.frontier.test_atlas_frontier_selection import (
            _candidate, _closure, _release, _snapshot,
        )

        release = _release()
        snapshot = _snapshot(release, prerequisite_edges=(
            PrerequisiteEdge("z.op.1", "z.op.2", "a" * 64),
        ))
        if grade_labels:
            snapshot = rehash(snapshot, grade_labels=grade_labels)
        waiting = ClosureReason(
            "PREREQUISITE_WAITING_FOR_EVIDENCE", "factory:prerequisite", "z.op.2")
        closure = _closure(snapshot, (
            _candidate(snapshot, "z.op.0"),
            _candidate(snapshot, "z.op.1", status=ClosureStatus.WAITING_FOR_EVIDENCE,
                       prerequisites=("z.op.2",), reasons=(waiting,)),
            _candidate(snapshot, "z.op.2"),
        ))
        return release, snapshot, closure

    def test_resolves_prerequisite_ranked_interleaved_intent_without_authorizing_learning(self):
        from bilqis_mlx.factory.curriculum.developmental_stage import (
            DevelopmentalLearnerState, DevelopmentalSourceCoverage,
        )

        release, snapshot, closure = self._coverage_fixture()
        program = load_bamf_developmental_program()
        intent = program.resolve_training_stage(
            DevelopmentalSourceCoverage(snapshot, closure),
            DevelopmentalLearnerState(release),
        )

        self.assertEqual(intent.selected_semantic_id, "z.op.2")
        self.assertEqual(intent.selected_family_ids, ("positive_identity",))
        self.assertEqual(intent.active_grade_ids, tuple(
            grade.grade_id for grade in release.execution_plan.grades))
        self.assertEqual(intent.active_capability_ids, tuple(
            capability.capability_id for capability in release.execution_plan.capabilities))
        self.assertEqual(intent.source_eligible_concept_ids, snapshot.source_eligible_concept_ids)
        self.assertEqual(intent.covered_semantic_ids, snapshot.source_eligible_concept_ids)
        self.assertEqual(intent.retained_mastery_debt, snapshot.retained_mastery_debt)
        self.assertEqual(intent.teacher_epoch, snapshot.teacher_epoch)
        self.assertIn("SOURCE_QUALIFIED_PREREQUISITES",
                      intent.blocking_source_requirements)
        self.assertNotIn("RESOURCE_AUTHORITY", intent.blocking_source_requirements)
        self.assertNotIn("RIGHTS_AUTHORITY", intent.blocking_source_requirements)
        self.assertEqual(intent.nonblocking_levels, ("L3", "L4"))
        self.assertFalse(intent.authorizes_learning)
        self.assertTrue(any(
            item.owner == "factory:prerequisite" and item.dependency_id == "z.op.2"
            for item in intent.remediation))
        self.assertTrue(any(
            item.code == "RIGHTS_MISSING" and item.owner == "source:owner"
            and item.dependency_id == "synthetic/held/row1"
            for item in intent.remediation))

    def test_grade_label_renaming_does_not_change_stage_selection(self):
        from bilqis_mlx.factory.curriculum.developmental_stage import (
            DevelopmentalLearnerState, DevelopmentalSourceCoverage,
        )

        program = load_bamf_developmental_program()
        release_a, snapshot_a, closure_a = self._coverage_fixture(("A", "B"))
        release_b, snapshot_b, closure_b = self._coverage_fixture(("Q", "R"))
        first = program.resolve_training_stage(
            DevelopmentalSourceCoverage(snapshot_a, closure_a),
            DevelopmentalLearnerState(release_a),
        )
        second = program.resolve_training_stage(
            DevelopmentalSourceCoverage(snapshot_b, closure_b),
            DevelopmentalLearnerState(release_b),
        )
        self.assertEqual(first.selected_semantic_id, second.selected_semantic_id)
        self.assertEqual(first.selected_family_ids, second.selected_family_ids)
        self.assertEqual(first.status, second.status)

    def test_l3_l4_requirements_cannot_block_earlier_stage_selection(self):
        from bilqis_mlx.factory.curriculum.developmental_program import BamfDevelopmentalProgram
        from bilqis_mlx.factory.curriculum.developmental_stage import (
            DevelopmentalLearnerState, DevelopmentalSourceCoverage,
        )

        release, snapshot, closure = self._coverage_fixture()
        ordinary = load_bamf_developmental_program()
        late_changed = tuple(
            replace(item, source_requirements=("UNAVAILABLE_LATE_RESOURCE",))
            if item.level in {DevelopmentalLevel.L3, DevelopmentalLevel.L4} else item
            for item in ordinary.levels)
        candidate = BamfDevelopmentalProgram(
            ordinary.schema, ordinary.program_id, ordinary.policy_version, late_changed)

        first = ordinary.resolve_training_stage(
            DevelopmentalSourceCoverage(snapshot, closure),
            DevelopmentalLearnerState(release))
        second = candidate.resolve_training_stage(
            DevelopmentalSourceCoverage(snapshot, closure),
            DevelopmentalLearnerState(release))

        self.assertEqual(first.selected_semantic_id, second.selected_semantic_id)
        self.assertEqual(first.selected_family_ids, second.selected_family_ids)
        self.assertEqual(first.status, second.status)
        self.assertNotIn("UNAVAILABLE_LATE_RESOURCE",
                         second.blocking_source_requirements)

    def test_protected_debt_is_visible_but_does_not_create_named_grade_priority(self):
        from bilqis_mlx.factory.curriculum.developmental_stage import (
            DevelopmentalLearnerState, DevelopmentalSourceCoverage,
        )
        from bilqis_mlx.factory.tests.curriculum.frontier.atlas_frontier_closure_fixtures import rehash

        program = load_bamf_developmental_program()
        release, base, _ = self._coverage_fixture()
        first_snapshot = rehash(
            base, grade_labels=("A", "B"), retained_mastery_debt=("A.DEBT",),
            retained_debt_source_sha256="d" * 64)
        second_snapshot = rehash(
            base, grade_labels=("Q", "R"), retained_mastery_debt=("R.DEBT",),
            retained_debt_source_sha256="e" * 64)
        _, _, first_closure = self._coverage_fixture(("A", "B"))
        _, _, second_closure = self._coverage_fixture(("Q", "R"))
        first_closure = replace(
            first_closure, snapshot_sha256=first_snapshot.snapshot_sha256,
            closure_sha256="0" * 64)
        first_closure = replace(
            first_closure, closure_sha256=first_closure.expected_digest())
        second_closure = replace(
            second_closure, snapshot_sha256=second_snapshot.snapshot_sha256,
            closure_sha256="0" * 64)
        second_closure = replace(
            second_closure, closure_sha256=second_closure.expected_digest())

        first = program.resolve_training_stage(
            DevelopmentalSourceCoverage(first_snapshot, first_closure),
            DevelopmentalLearnerState(release))
        second = program.resolve_training_stage(
            DevelopmentalSourceCoverage(second_snapshot, second_closure),
            DevelopmentalLearnerState(release))
        self.assertEqual(first.selected_semantic_id, second.selected_semantic_id)
        self.assertEqual(first.status, second.status)
        self.assertEqual(first.retained_mastery_debt, ("A.DEBT",))
        self.assertEqual(second.retained_mastery_debt, ("R.DEBT",))

    def test_numeric_scope_is_projected_from_admitted_release_parameters(self):
        from types import SimpleNamespace
        from bilqis_mlx.factory.curriculum.developmental_stage import (
            _numeric_maximum_from_capabilities,
        )

        capabilities = (
            SimpleNamespace(provider_parameters=(("numbers", ("0", "1", "2", "3", "4")),)),
            SimpleNamespace(provider_parameters=()),
        )
        self.assertEqual(_numeric_maximum_from_capabilities(capabilities), 4)
        with self.assertRaises(BilqisError):
            _numeric_maximum_from_capabilities((
                SimpleNamespace(provider_parameters=(("numbers", ("0", "2")),)),
            ))

if __name__ == "__main__":
    unittest.main()
