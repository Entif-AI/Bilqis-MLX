"""Authenticated BAMF history is the CP07 production-source acceptance witness."""
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.teacher_visit_identity import TeacherVisitIdentity
from bilqis_mlx.control_plane import ControlPlaneClient, ControlPlaneService, EventFamily
from bilqis_mlx.control_plane.native_source import (
    authenticated_history, materialize_native_projection, refresh_native_events,
)
from bilqis_mlx.mission_control import CandidateDecision, CapabilitySnapshot, LearningEpisode
from bilqis_mlx.mission_control.projection import MissionControlProjection
from bilqis_mlx.mission_control.query_contracts import QueryFamily, QueryMode, QueryRequest
from bilqis_mlx.runtime.tests.custody.bamf_bundle.contracts.acceptance._generation_acceptance_support import (
    GenerationAcceptanceFixture,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import shape_patch
from bilqis_mlx.runtime.bamf_bundle import record_bamf_rejection

from ..support import start_service


class NativeBamfProjectionTests(GenerationAcceptanceFixture, unittest.TestCase):
    def _successor(self):
        parent = self.parent()
        source = self.source()
        step = source.retained_state.optimizer_step
        visit = TeacherVisitIdentity(
            parent.run_identity.digest, parent.run_identity.run_seed,
            parent.generation, self._parent_pointer["manifest_sha256"],
            parent.teacher_state["teacher_identity"],
            parent.teacher_state["teacher_epoch"],
            candidate_identity_digest(parent.retained_state),
            parent.teacher_state["next_seed"], parent.teacher_state["cursor"],
            "A.NATIVE", "policy:native",
        )
        return replace(
            source,
            teacher_state={**source.teacher_state, "last_visit": visit.to_record()},
            outbox=({
                "event": "BAMF_C16_3_ACCEPTED",
                "optimizer_step": step,
                "capability": "A.NATIVE",
            },),
        )

    def _publish_successor(self):
        source = self._successor()
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            pointer = self.publish(source, acceptance=self.binding(source))
        return source, pointer

    def test_authenticated_history_materializes_native_cp02_and_rebuilds_cp06(self):
        self.parent()
        source, pointer = self._publish_successor()
        before = (self.run / "bamf-state.json").read_bytes()

        history = authenticated_history(self.run)
        self.assertEqual([item.manifest["generation"] for item in history], [0, 1])
        self.assertEqual(history[-1].manifest_sha256, pointer["manifest_sha256"])

        material = materialize_native_projection(self.run)
        episodes = [record for record in material.records if isinstance(record, LearningEpisode)]
        candidates = [record for record in material.records if isinstance(record, CandidateDecision)]
        capabilities = [record for record in material.records if isinstance(record, CapabilitySnapshot)]
        self.assertEqual(len(episodes), 1)
        self.assertEqual(episodes[0].capability_id, "A.NATIVE")
        self.assertEqual(episodes[0].meta.coverage.value, "PARTIAL")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].outcome.value, "ACCEPTED")
        self.assertEqual(len(capabilities), 1)
        self.assertEqual(capabilities[0].score_correct.state.value, "MISSING")

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
        resource_gap = projection.catalog().query(QueryRequest(
            QueryFamily.RESOURCE, mode=QueryMode.HISTORICAL,
            run_id=source.run_id, generation=1,
        ))
        self.assertEqual(generation_gap.state.value, "UNKNOWN")
        self.assertEqual(resource_gap.state.value, "UNKNOWN")
        projected_episode = next(
            record for record in historical.records if isinstance(record, LearningEpisode))
        self.assertEqual(projected_episode.episode_id, episodes[0].episode_id)

        index.unlink()
        rebuilt = MissionControlProjection.rebuild_from_bamf(index, self.run)
        self.assertEqual(rebuilt.catalog().query(QueryRequest(
            QueryFamily.CAPABILITY, run_id=source.run_id,
        )), current)
        self.assertEqual((self.run / "bamf-state.json").read_bytes(), before)

    def test_historical_acceptance_tamper_fails_closed(self):
        self.parent()
        source, _pointer = self._publish_successor()
        index = self.root / "tampered.sqlite3"
        projection = MissionControlProjection.rebuild_from_bamf(index, self.run)
        before = projection.catalog().query(QueryRequest(
            QueryFamily.CAPABILITY, run_id=source.run_id))
        history = authenticated_history(self.run)
        parent = history[0]
        acceptance = self.run / "bamf-acceptance" / f"{parent.manifest_sha256}.json"
        raw = acceptance.read_text(encoding="utf-8")
        acceptance.write_text(raw.replace('"generation":0', '"generation":9'), encoding="utf-8")
        with self.assertRaises(BilqisError) as caught:
            MissionControlProjection.rebuild_from_bamf(index, self.run)
        self.assertEqual(
            caught.exception.context.get("reason"),
            "CONTROL_PLANE_NATIVE_HISTORY_ACCEPTANCE_DRIFT",
        )
        self.assertEqual(
            MissionControlProjection(index).catalog().query(QueryRequest(
                QueryFamily.CAPABILITY, run_id=source.run_id)),
            before,
        )

    def test_subscription_automatically_publishes_new_authenticated_native_events(self):
        self.parent()
        socket = self.root / "native.sock"
        service = ControlPlaneService(
            self.run, socket, event_heartbeat_seconds=0.01,
            event_retention_limit=16, event_queue_limit=16,
        )
        thread = start_service(service)
        try:
            with ControlPlaneClient(socket) as client:
                subscription = client.subscribe_events()
                self._publish_successor()
                observed = []
                while len(observed) < 5:
                    event = next(subscription)
                    if event.schema_version.endswith("event-envelope/v1"):
                        observed.append(event)
                    if len(observed) == 4:
                        break
                families = {event.event_family for event in observed}
                self.assertTrue({
                    EventFamily.RUN_STATE_CHANGED.value,
                    EventFamily.LESSON_VISIT_COMPLETED.value,
                    EventFamily.CANDIDATE_RETAINED.value,
                    EventFamily.CAPABILITY_CHANGED.value,
                } <= families)
                ids = [event.event_id for event in observed]
                self.assertEqual(len(ids), len(set(ids)))
                self.assertEqual(refresh_native_events(service), ())
        finally:
            service.shutdown()
            thread.join(2)

    def test_authenticated_rejection_is_projected_without_advancing_learner(self):
        parent = self.parent()
        before = (self.run / "bamf-state.json").read_bytes()
        receipt = record_bamf_rejection(self.run, parent, {
            "schema": "bilqis.bamf.c16.3-rejection/v2",
            "visit_id": "visit:native-rejection",
            "selected_option_id": "option:native",
            "selected_policy_key": "policy:native",
            "candidate_optimizer_step": parent.retained_state.optimizer_step + 1,
            "retained_optimizer_step": parent.retained_state.optimizer_step,
            "retention_reason": "NATIVE_REJECTED",
            "capability": "A.REJECT",
            "decision": {"decision": "REJECT"},
        })
        material = materialize_native_projection(self.run)
        rejected = [
            record for record in material.records
            if isinstance(record, CandidateDecision) and record.outcome.value == "REJECTED"
        ]
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0].capability_id, "A.REJECT")
        self.assertEqual(rejected[0].reason_code, "NATIVE_REJECTED")
        self.assertIn(f"bamf-rejection:{receipt}", rejected[0].meta.receipt_refs)
        self.assertEqual((self.run / "bamf-state.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
