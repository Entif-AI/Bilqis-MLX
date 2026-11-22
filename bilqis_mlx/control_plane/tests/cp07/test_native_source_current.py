"""Depth-invariant CURRENT control-plane query behavior."""
import json
import os
import unittest
from unittest.mock import patch

from bilqis_mlx.control_plane import ControlPlaneService
from bilqis_mlx.control_plane.native_contracts import materialized_at, run_ref
from bilqis_mlx.control_plane.native_source import (
    authenticated_history, materialize_current_native_projection,
    materialize_native_projection, native_query_catalog, native_query_source, refresh_native_events,
)
from bilqis_mlx.control_plane.tests.support import start_service
from bilqis_mlx.mission_control import (
    CandidateDecision, CapabilitySnapshot, LearningEpisode,
    NeuralRuntimeSample, OperatorView, ResourceSample, TeacherSnapshot,
)
from bilqis_mlx.mission_control.contracts.dossier import CapabilityDossier
from bilqis_mlx.mission_control.electron_bridge import ElectronBridge
from bilqis_mlx.mission_control.projection import MissionControlProjection
from bilqis_mlx.mission_control.query_contracts import QueryFamily, QueryMode, QueryRequest
from bilqis_mlx.runtime.bamf_bundle import record_bamf_rejection
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import retention_decision
from ..observed import test_source as observed_support


from .native_source_support import NativeSourceFixture


class NativeBamfProjectionTests(NativeSourceFixture, unittest.TestCase):
    def test_event_refresh_skips_full_projection_when_mutable_sources_are_unchanged(self):
            self.parent()
            class FakeService:
                pass

            service = FakeService()
            service.run_dir = self.run
            service._cp07_native_event_ids = set()
            service._cp07_native_run_refs = tuple(
                run_ref(item) for item in authenticated_history(self.run))
            with patch(
                    "bilqis_mlx.control_plane.native_source.publish_native_events",
                    return_value=(None, ())) as publish:
                self.assertEqual(refresh_native_events(service), ())
                self.assertEqual(publish.call_count, 1)
                self.assertEqual(refresh_native_events(service), ())
                self.assertEqual(publish.call_count, 1)
                (self.run / "trainer-observed.json").write_text("{}")
                self.assertEqual(refresh_native_events(service), ())
                self.assertEqual(publish.call_count, 1)

    def test_query_source_reuses_catalog_until_mutable_source_changes(self):
            self.parent()
            self.publish_successor()
            with patch(
                    "bilqis_mlx.control_plane.native_source.authenticated_history",
                    wraps=authenticated_history) as authenticate:
                source = native_query_source(self.run)
                first = source()
                self.assertIs(source(), first)
                self.assertEqual(authenticate.call_count, 1)
                (self.run / "bamf-state.json").touch()
                second = source()
                self.assertIsNot(second, first)
                self.assertEqual(authenticate.call_count, 2)

    def test_query_source_observation_refresh_reuses_cumulative_accepted_history(self):
            self.parent()
            self.publish_successor()
            with patch(
                    "bilqis_mlx.control_plane.native_source.authenticated_history",
                    wraps=authenticated_history) as authenticate:
                source = native_query_source(self.run)
                source()
                self.assertEqual(authenticate.call_count, 1)
                (self.run / "trainer-observed.json").write_text("{}")
                source()
                self.assertEqual(authenticate.call_count, 1)

    def materialize(*args, **kwargs):
                nonlocal mutated
                material = real_materialize(*args, **kwargs)
                if not mutated:
                    (self.run / "trainer-observed.json").write_text(json.dumps({
                        "schema": "bilqis.bamf.trainer-observed/v7",
                        "visits": [],
                    }))
                    mutated = True
                return material

            with (
                    patch(
                        "bilqis_mlx.control_plane.native_source.authenticated_history",
                        wraps=authenticated_history) as authenticate,
                    patch(
                        "bilqis_mlx.control_plane.native_source._materialize_authenticated_history",
                        side_effect=materialize)):
                source = native_query_source(self.run)
                source()
                source()
                self.assertEqual(authenticate.call_count, 1)

    def test_query_source_event_ledger_refresh_reuses_authenticated_accepted_history(self):
            self.parent()
            self.publish_successor()
            with patch(
                    "bilqis_mlx.control_plane.native_source.authenticated_history",
                    wraps=authenticated_history) as authenticate:
                source = native_query_source(self.run)
                source()
                self.assertEqual(authenticate.call_count, 1)
                with (self.run / "events.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({"event": "IGNORED_TEST_EVENT"}) + "\n")
                source()
                self.assertEqual(authenticate.call_count, 1)

    def test_query_source_historical_request_uses_authenticated_history(self):
            self.parent()
            source_generation, _pointer = self.publish_successor()
            source = native_query_source(self.run)
            request = QueryRequest(
                QueryFamily.RUN, mode=QueryMode.HISTORICAL,
                run_id=source_generation.run_id, generation=0)
            with patch(
                    "bilqis_mlx.control_plane.native_source.authenticated_history",
                    wraps=authenticated_history) as authenticate:
                catalog = source(request)
            self.assertGreater(authenticate.call_count, 0)
            page = catalog.query(request)
            self.assertIn(page.state.value, {"PRESENT", "PARTIAL"})

    def test_query_source_observation_refresh_does_not_cold_load_accepted_student(self):
            self.parent()
            source_generation, _pointer = self.publish_successor()
            query_source = native_query_source(self.run)
            query_source()
            row = observed_support.visit(
                run_id=source_generation.run_id,
                parent_manifest_sha256=(self.run / "bamf-state.json").read_text(),
                outcome="COMPLETED",
            )
            pointer = json.loads((self.run / "bamf-state.json").read_text())
            row["parent_manifest_sha256"] = pointer["manifest_sha256"]
            (self.run / "trainer-observed.json").write_text(json.dumps({
                "schema": "bilqis.bamf.trainer-observed/v1",
                "visits": [row],
            }))
            with patch(
                    "bilqis_mlx.runtime.bamf_bundle.admission.load_accepted_generation",
                    side_effect=AssertionError("observation refresh cold-loaded accepted student")):
                page = query_source().query(QueryRequest(
                    QueryFamily.RUN, run_id=source_generation.run_id))
            self.assertIn(page.state.value, {"PRESENT", "PARTIAL"})

    def test_query_source_current_tip_projects_latest_accepted_capability_and_episode(self):
            self.parent()
            source_generation, _pointer = self.publish_successor()
            catalog = native_query_source(self.run)()
            capability = catalog.query(QueryRequest(
                QueryFamily.CAPABILITY, run_id=source_generation.run_id))
            episode = catalog.query(QueryRequest(
                QueryFamily.EPISODE, run_id=source_generation.run_id))
            self.assertTrue(any(
                isinstance(record, CapabilitySnapshot)
                and record.capability_id == "A.NATIVE"
                for record in capability.records))
            self.assertTrue(any(
                isinstance(record, LearningEpisode)
                and record.capability_id == "A.NATIVE"
                for record in episode.records))

    def test_query_source_current_context_keeps_prior_accepted_entities_and_chronology(self):
            self.parent()
            self.publish_successor()
            source_generation, _pointer = self.publish_next_successor("A.EDGE")

            catalog = native_query_source(self.run)()
            capability = catalog.query(QueryRequest(
                QueryFamily.CAPABILITY, run_id=source_generation.run_id))
            episode = catalog.query(QueryRequest(
                QueryFamily.EPISODE, run_id=source_generation.run_id))
            neural = catalog.query(QueryRequest(
                QueryFamily.NEURAL, run_id=source_generation.run_id))
            snapshots = {
                record.capability_id for record in capability.records
                if isinstance(record, CapabilitySnapshot)
            }
            dossiers = {
                record.capability_id for record in capability.records
                if isinstance(record, CapabilityDossier)
            }
            episodes = {
                record.capability_id for record in episode.records
                if isinstance(record, LearningEpisode)
            }
            self.assertEqual(snapshots, {"A.NATIVE", "A.EDGE"})
            self.assertEqual(dossiers, {"A.NATIVE", "A.EDGE"})
            self.assertEqual(episodes, {"A.NATIVE", "A.EDGE"})
            runtime = next(
                record for record in neural.records
                if isinstance(record, NeuralRuntimeSample))
            self.assertEqual(runtime.meta.run.generation, 2)
            self.assertEqual(runtime.optimizer_step, 2)
            self.assertEqual(runtime.step_duration_ms.value, 20_000.0)
            self.assertEqual(runtime.step_duration_ms.units, "ms")
            self.assertEqual(runtime.active_parameters.state.value, "MISSING")
            self.assertEqual(runtime.refinement_fraction.state.value, "MISSING")

    def test_electron_bridge_receives_cumulative_current_native_evidence(self):
            self.parent()
            self.publish_successor()
            source_generation, _pointer = self.publish_next_successor("A.EDGE")
            socket = self.run.parent / "cp07-native-electron.sock"
            service = ControlPlaneService(
                self.run, socket, query_source=native_query_source(self.run))
            thread = start_service(service)
            bridge = ElectronBridge()
            try:
                with patch.dict(
                        os.environ, {"BILQIS_CONTROL_PLANE_SOCKET": str(socket)}):
                    bridge.connect()
                capability = bridge.query(QueryRequest(
                    QueryFamily.CAPABILITY,
                    run_id=source_generation.run_id,
                ).to_record())
                episode = bridge.query(QueryRequest(
                    QueryFamily.EPISODE,
                    run_id=source_generation.run_id,
                ).to_record())
                self.assertEqual(
                    {
                        record["capability_id"] for record in capability["records"]
                        if record["schema_version"]
                        == "bilqis.bamf.mission-control.capability-snapshot/v1"
                    },
                    {"A.NATIVE", "A.EDGE"},
                )
                self.assertEqual(
                    {
                        record["capability_id"] for record in episode["records"]
                        if record["schema_version"]
                        == "bilqis.bamf.mission-control.learning-episode/v1"
                    },
                    {"A.NATIVE", "A.EDGE"},
                )
                self.assertNotIn("session", capability)
                self.assertNotIn("service", capability)
            finally:
                bridge.disconnect()
                service.shutdown()
                thread.join(2)

    def test_native_query_catalog_exposes_current_operator_view_without_cp06_database(self):
            self.parent()
            source, _pointer = self.publish_successor()
            page = native_query_catalog(self.run).query(QueryRequest(
                QueryFamily.RUN, run_id=source.run_id))
            view = next(record for record in page.records if isinstance(record, OperatorView))
            self.assertEqual(page.state.value, "PRESENT")
            self.assertEqual(view.meta.run.generation, 1)
            self.assertEqual(view.learner_state, "READY")

    def test_native_family_hydration_matrix_distinguishes_present_absent_and_contract_gap(self):
            self.parent()
            source, _pointer = self.publish_successor()
            catalog = native_query_catalog(self.run)

            for family in (
                    QueryFamily.CAPABILITY, QueryFamily.RESOURCE,
                    QueryFamily.TEACHER, QueryFamily.NEURAL):
                page = catalog.query(QueryRequest(family, run_id=source.run_id))
                self.assertEqual(page.state.value, "PARTIAL", family.value)
                self.assertGreater(len(page.records), 0, family.value)
                self.assertEqual(page.markers, (), family.value)

            semantic = catalog.query(QueryRequest(
                QueryFamily.SEMANTIC, run_id=source.run_id))
            self.assertEqual(semantic.state.value, "PARTIAL")
            self.assertGreater(len(semantic.records), 0)

            for family in (
                    QueryFamily.SCHOOL, QueryFamily.FRAME,
                    QueryFamily.MEMORY, QueryFamily.SALIENCE, QueryFamily.CORRECTION):
                page = catalog.query(QueryRequest(family, run_id=source.run_id))
                self.assertEqual(page.state.value, "EMPTY", family.value)
                self.assertEqual(page.coverage.value, "COMPLETE", family.value)
                self.assertEqual(page.records, (), family.value)
                self.assertEqual(page.markers, (), family.value)

            generation = catalog.query(QueryRequest(
                QueryFamily.GENERATION, run_id=source.run_id))
            self.assertEqual(generation.state.value, "UNKNOWN")
            self.assertEqual(generation.coverage.value, "UNKNOWN")
            self.assertEqual(generation.records, ())
            self.assertEqual(len(generation.markers), 1)
