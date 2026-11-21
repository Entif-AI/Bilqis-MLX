"""Authenticated BAMF history production-source acceptance witness."""
import json
import unittest
from unittest.mock import patch

from bilqis_mlx.control_plane.native_contracts import materialized_at, run_ref
from bilqis_mlx.control_plane.native_source import (
    authenticated_history, materialize_current_native_projection,
    materialize_native_projection, native_query_catalog, native_query_source, refresh_native_events,
)
from bilqis_mlx.mission_control import (
    CandidateDecision, CapabilitySnapshot, LearningEpisode, OperatorView, ResourceSample, TeacherSnapshot,
)
from bilqis_mlx.mission_control.projection import MissionControlProjection
from bilqis_mlx.mission_control.query_contracts import QueryFamily, QueryMode, QueryRequest
from bilqis_mlx.runtime.bamf_bundle import record_bamf_rejection
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import retention_decision
from ..observed import test_source as observed_support


from .native_source_support import NativeSourceFixture


class NativeBamfProjectionTests(NativeSourceFixture, unittest.TestCase):
    def test_authenticated_history_materializes_native_cp02_and_rebuilds_cp06(self):
            self.parent()
            source, pointer = self.publish_successor()
            before = (self.run / "bamf-state.json").read_bytes()

            history = authenticated_history(self.run)
            self.assertEqual([item.manifest["generation"] for item in history], [0, 1])
            self.assertEqual(history[-1].manifest_sha256, pointer["manifest_sha256"])

            material = materialize_native_projection(self.run)
            episodes = [record for record in material.records if isinstance(record, LearningEpisode)]
            candidates = [record for record in material.records if isinstance(record, CandidateDecision)]
            capabilities = [record for record in material.records if isinstance(record, CapabilitySnapshot)]
            resources = [record for record in material.records if isinstance(record, ResourceSample)]
            teachers = [record for record in material.records if isinstance(record, TeacherSnapshot)]
            operator_views = [record for record in material.records if isinstance(record, OperatorView)]
            self.assertEqual(len(operator_views), 2)
            self.assertEqual(operator_views[-1].learner_state, "READY")
            self.assertEqual(operator_views[-1].meta.run.generation, 1)
            self.assertEqual(len(episodes), 1)
            self.assertEqual(episodes[0].capability_id, "A.NATIVE")
            self.assertEqual(episodes[0].meta.coverage.value, "PARTIAL")
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0].outcome.value, "ACCEPTED")
            self.assertEqual(len(capabilities), 1)
            self.assertEqual(capabilities[0].grade_id, "UNKNOWN")
            self.assertEqual(capabilities[0].score_correct.state.value, "MISSING")
            self.assertEqual(capabilities[0].score_total.state.value, "MISSING")
            self.assertEqual(capabilities[0].debt.state.value, "MISSING")
            self.assertEqual(len(resources), 1)
            self.assertEqual(resources[0].memory_used_bytes.state.value, "UNKNOWN")
            self.assertEqual(resources[0].memory_budget_bytes.value, 64 * 1024 ** 3)
            self.assertGreater(resources[0].disk_used_bytes.value, 0)
            self.assertEqual(resources[0].step_rate_per_minute.value, 2.0)
            self.assertEqual(len(teachers), 1)
            self.assertEqual(teachers[0].teacher_identity, history[-1].teacher_state["teacher_identity"])
            self.assertEqual(teachers[0].teacher_epoch, history[-1].teacher_state["teacher_epoch"])
            self.assertEqual(
                teachers[0].strategy_id,
                history[-1].teacher_state["last_visit"]["policy_key"],
            )
            self.assertEqual(teachers[0].attempts.state.value, "MISSING")
            self.assertEqual(teachers[0].accepted.state.value, "MISSING")
            self.assertEqual(teachers[0].rejected.state.value, "MISSING")

            index = self.root / "native-projection.sqlite3"
            projection = MissionControlProjection.rebuild_from_bamf(index, self.run)
            current = projection.catalog().query(QueryRequest(
                QueryFamily.CAPABILITY, run_id=source.run_id,
            ))
            historical = projection.catalog().query(QueryRequest(
                QueryFamily.EPISODE, mode=QueryMode.HISTORICAL,
                run_id=source.run_id, generation=1,
            ))
            self.assertEqual(current.records[0].capability_id, "A.NATIVE")
            generation_gap = projection.catalog().query(QueryRequest(
                QueryFamily.GENERATION, mode=QueryMode.HISTORICAL,
                run_id=source.run_id, generation=1,
            ))
            resource_page = projection.catalog().query(QueryRequest(
                QueryFamily.RESOURCE, mode=QueryMode.HISTORICAL,
                run_id=source.run_id, generation=1,
            ))
            current_resource_page = projection.catalog().query(QueryRequest(
                QueryFamily.RESOURCE, run_id=source.run_id,
            ))
            self.assertEqual(generation_gap.state.value, "UNKNOWN")
            self.assertEqual(resource_page.state.value, "PARTIAL")
            self.assertIsInstance(resource_page.records[0], ResourceSample)
            self.assertEqual(current_resource_page.state.value, "PARTIAL")
            self.assertEqual(current_resource_page.markers, ())
            self.assertIsInstance(current_resource_page.records[0], ResourceSample)
            projected_episode = next(
                record for record in historical.records if isinstance(record, LearningEpisode))
            self.assertEqual(projected_episode.episode_id, episodes[0].episode_id)

            index.unlink()
            rebuilt = MissionControlProjection.rebuild_from_bamf(index, self.run)
            self.assertEqual(rebuilt.catalog().query(QueryRequest(
                QueryFamily.CAPABILITY, run_id=source.run_id,
            )), current)
            self.assertEqual((self.run / "bamf-state.json").read_bytes(), before)

    def test_generation_coordinate_is_never_reinterpreted_as_unix_materialization_time(self):
            self.assertEqual(materialized_at({}, 7), 0)
            self.assertEqual(materialized_at({"recorded_at": 1_800_000_000}, 7), 1_800_000_000)

    def test_authenticated_rejection_is_projected_without_advancing_learner(self):
            parent = self.parent()
            before = (self.run / "bamf-state.json").read_bytes()
            visit = self.native_visit(parent)
            decision = retention_decision(
                accepted=False, parent=parent.retained_state, retained=parent.retained_state)
            receipt = record_bamf_rejection(self.run, parent, {
                "schema": "bilqis.bamf.c16.3-rejection/v2",
                "visit_id": visit.visit_id,
                "teacher_visit": visit.to_record(),
                "selected_option_id": "option:native",
                "selected_policy_key": visit.policy_key,
                "candidate_optimizer_step": parent.retained_state.optimizer_step + 1,
                "retained_optimizer_step": parent.retained_state.optimizer_step,
                "retention_reason": decision.reason,
                "capability": "A.REJECT",
                "decision": decision.to_record(),
            })
            material = materialize_native_projection(
                self.run, include_live_rejections=True)
            rejected = [
                record for record in material.records
                if isinstance(record, CandidateDecision) and record.outcome.value == "REJECTED"
            ]
            self.assertEqual(len(rejected), 1)
            self.assertEqual(rejected[0].capability_id, "A.REJECT")
            self.assertEqual(rejected[0].reason_code, decision.reason)
            self.assertEqual(rejected[0].candidate_id, decision.candidate_generation)
            self.assertIn(f"bamf-rejection:{receipt}", rejected[0].meta.receipt_refs)
            self.assertEqual((self.run / "bamf-state.json").read_bytes(), before)

            with patch(
                    "bilqis_mlx.data_plane.data_plane",
                    side_effect=AssertionError("CP06 reconstruction accessed shared data plane")):
                portable = materialize_native_projection(self.run)
            self.assertFalse(any(
                isinstance(record, CandidateDecision) and record.outcome.value == "REJECTED"
                for record in portable.records))
