"""Literal parent acceptance witnesses for B09 / #368."""
from dataclasses import asdict, replace
import json
from unittest import TestCase
from unittest.mock import patch

import mlx.core as mx
import numpy as np

from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.factory.executable_release import compile_executable_factory_release
from bilqis_mlx.factory.execution import CurriculumProfile
from bilqis_mlx.factory.tests.test_executable_release import _boolean_answers
from bilqis_mlx.learning.atlas_candidate import (
    begin_candidate, candidate_step, issue_promotion_transition_state,
    resolve_candidate,
)
from bilqis_mlx.learning.atlas_plasticity import (
    PlasticityPolicy, advance_candidate_policy, group_eligibility,
    next_update_mode,
)
from bilqis_mlx.learning._retention.tests.test_atlas_candidate import (
    CandidateTransactionTests,
)
from bilqis_mlx.learning._retention.tests.execution_fixtures import (
    execution_provenance,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, bamf_parameter_census,
)
from bilqis_mlx.runtime.tests.capability.factory.retention.test_plasticity_promotion_grade_neutrality import (
    PlasticityPromotionGradeNeutralityTests, _graph,
)


class B09ParentAcceptanceTests(TestCase):
    @staticmethod
    def _canonical_bytes(value):
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")

    def _retained_projection(self, retained, policy):
        for _ in range(3):
            self.assertEqual(
                next_update_mode(policy, teacher_requests_full=False), "FAST")
            policy = advance_candidate_policy(
                policy, teacher_requests_full=False, accepted=True,
                participating_rows=((0, 1),),
            )
        cold = PlasticityPolicy.from_record(
            json.loads(json.dumps(policy.to_record())))
        extents = GenerationExtents(
            1, 1, "a" * 64, retained.allocations.manifest.digest, "c" * 64)
        eligibility = group_eligibility(
            next_update_mode(cold, teacher_requests_full=False),
            bamf_parameter_census(ModelTopologySpecV2(), extents), cold.row_ages)
        clock = {
            "accepted_fast_since_full": cold.accepted_fast_since_full,
            "row_ages": [asdict(item) for item in cold.row_ages],
        }
        return (
            self._canonical_bytes(asdict(eligibility)),
            self._canonical_bytes(clock),
            self._canonical_bytes(cold.to_record()),
        )

    def test_actual_grade_id_relabel_cannot_change_b09_retained_state(self):
        fixture = PlasticityPromotionGradeNeutralityTests(methodName="runTest")
        fixture.setUp()
        baseline_release = fixture._runtime_release()

        relabel = {"A": "C", "B": "D"}
        relabeled_course = replace(
            fixture.course,
            grades=tuple(replace(grade, id=relabel[grade.id])
                         for grade in fixture.course.grades),
        )
        curriculum, bindings = from_legacy_course(relabeled_course)
        relabeled_release = compile_executable_factory_release(
            curriculum, bindings, CurriculumProfile.full(), fixture.registry,
            _boolean_answers(), source_root=None, graph=_graph(), verification_seed=97)

        baseline_grades = {
            item.capability_id: item.grade_id
            for item in baseline_release.execution_plan.capabilities
        }
        relabeled_grades = {
            item.capability_id: item.grade_id
            for item in relabeled_release.execution_plan.capabilities
        }
        self.assertEqual(set(baseline_grades), set(relabeled_grades))
        self.assertNotEqual(baseline_grades, relabeled_grades)
        self.assertNotEqual(
            baseline_release.release_sha256, relabeled_release.release_sha256)
        self.assertEqual(
            tuple(item.capability_id for item in baseline_release.execution_plan.capabilities),
            tuple(item.capability_id for item in relabeled_release.execution_plan.capabilities))

        receipt, _transition, _entry, _release = fixture._issue(
            baseline_release, grade_visit_order=("A", "B"))
        self.assertEqual(receipt.foundation_capability_ids, fixture.foundation)
        self.assertTrue(set(receipt.foundation_capability_ids).issubset(baseline_grades))
        self.assertTrue(set(receipt.foundation_capability_ids).issubset(relabeled_grades))

        baseline_policy = issue_promotion_transition_state(
            fixture.retained, receipt).policy
        relabeled_policy = issue_promotion_transition_state(
            fixture.retained, receipt).policy
        self.assertEqual(
            self._retained_projection(fixture.retained, baseline_policy),
            self._retained_projection(fixture.retained, relabeled_policy))

    def test_one_eight_step_candidate_ages_each_participant_once_or_zero_on_reject(self):
        fixture = CandidateTransactionTests(methodName="runTest")
        fixture.setUp()

        def bounded_step(candidate, rows):
            gradients = {
                fixture.name: mx.array(
                    [[.25, -.5], [.125, .25]], dtype=mx.float32),
            }
            with patch(
                    "bilqis_mlx.runtime.model_topology_v2.expected_bamf_shapes",
                    return_value=fixture.declared), patch(
                    "bilqis_mlx.runtime.topology_v2.validation.expected_bamf_shapes",
                    return_value=fixture.declared):
                return candidate_step(
                    candidate, gradients,
                    execution_provenance(
                        candidate.parent, rows=rows,
                        candidate_step=candidate.update_steps + 1),
                    fixture.hp, spec=fixture.spec, extents=fixture.extents,
                    loss_bearing=True, max_norm=1.)

        def eight_steps():
            candidate = begin_candidate(fixture.parent)
            for index in range(8):
                candidate = bounded_step(
                    candidate, (0,) if index % 2 == 0 else (1,))
            return candidate

        rejected_candidate = eight_steps()
        self.assertEqual(rejected_candidate.update_steps, 8)
        rejected = resolve_candidate(rejected_candidate, accepted=False)
        self.assertIs(rejected, fixture.parent)
        self.assertEqual(
            tuple(row.accepted_age for row in rejected.policy.row_ages), (7, 2))

        accepted_candidate = eight_steps()
        accepted = resolve_candidate(accepted_candidate, accepted=True)
        self.assertEqual(accepted.optimizer_step, fixture.parent.optimizer_step + 8)
        self.assertEqual(
            tuple(row.accepted_age for row in accepted.policy.row_ages), (8, 3))
        self.assertEqual(accepted.policy.accepted_fast_since_full, 8)
        np.testing.assert_array_equal(
            np.asarray(accepted.optimizer.update_counts[fixture.name]), [6, 7])
