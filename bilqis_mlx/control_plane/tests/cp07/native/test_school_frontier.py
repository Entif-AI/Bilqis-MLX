"""Issued School observations do not become accepted history."""
import json
import time
from unittest.mock import patch

from bilqis_mlx.control_plane.native_source import (
    authenticated_history, native_query_source,
)
from bilqis_mlx.control_plane.native_contracts import run_ref
from bilqis_mlx.control_plane.projection.school import read_admitted_release
from bilqis_mlx.mission_control.contracts.dossier import CapabilityDossier
from bilqis_mlx.mission_control.contracts.snapshots import CurriculumFrontier
from bilqis_mlx.mission_control.query_contracts import QueryFamily, QueryMode, QueryRequest
from bilqis_mlx.runtime.bamf_operator.evidence_parts.school import SCHEMA
from bilqis_mlx.control_plane.projection.school import _bounded_names
from bilqis_mlx.runtime.bamf_operator.evidence_parts.salience import issued_salience_observations

from ..native_source_support import NativeSourceFixture
from ...observed.test_source import visit
import unittest


class SchoolFrontierTests(NativeSourceFixture, unittest.TestCase):
    def test_live_frontier_and_source_offer_are_current_only(self):
        self.parent()
        self.publish_successor()
        generation = authenticated_history(self.run)[-1]
        run = run_ref(generation)
        release = read_admitted_release(self.run, generation)
        ready, held = tuple(item.capability_id for item in
                            release.execution_plan.capabilities)[:2]
        issued = dict(schema=SCHEMA, run_id=run.run_id, generation=run.generation,
                      manifest_sha256=run.generation_manifest_sha256,
                      release_sha256=run.factory_release_sha256,
                      frontier_sha256="a"*64, active_grade_sha256="b"*64,
                      ready=[ready], held=[held],
                      source_offer=dict(capability_id=ready, family_id="family:issued",
                                        content_sha256="c"*64))
        request = QueryRequest(QueryFamily.SCHOOL, run_id=run.run_id)
        source = native_query_source(self.run)

        def frontier(query=request):
            return next(row for row in source().query(query).records
                        if isinstance(row, CurriculumFrontier))

        def write(payload):
            row = visit(run_id=run.run_id,
                        parent_manifest_sha256=run.generation_manifest_sha256,
                        observed_at=int(time.time()*1000),
                        school_frontier=payload)
            (self.run / "trainer-observed.json").write_text(json.dumps({
                "schema": "bilqis.bamf.trainer-observed/v1", "visits": [row]}))

        self.assertEqual(frontier().meta.coverage.value, "PARTIAL")
        with patch("bilqis_mlx.control_plane.observed.source.process_exists",
                   return_value=True):
            write(issued)
            result = frontier()
            self.assertEqual(result.meta.authority.value, "MEASURED")
            self.assertEqual(result.ready_capability_ids, (ready,))
            self.assertEqual(result.held_capability_ids, (held,))
            self.assertEqual(result.meta.coverage.value, "COMPLETE")
            dossier = next(row for row in source().query(QueryRequest(
                QueryFamily.CAPABILITY, run_id=run.run_id,
                schema_version=CapabilityDossier.SCHEMA, limit=32)).records
                if row.capability_id == ready)
            self.assertIn("family:issued", [entry.related_id for entry in dossier.entries])
            historical = frontier(QueryRequest(
                QueryFamily.SCHOOL, mode=QueryMode.HISTORICAL,
                run_id=run.run_id, generation=run.generation))
            self.assertEqual(historical.meta.coverage.value, "PARTIAL")
            with patch("bilqis_mlx.control_plane.native_cache.source.time.time",
                       return_value=time.time() + 20):
                self.assertEqual(frontier().meta.coverage.value, "PARTIAL")
            write({**issued, "release_sha256": "d"*64})
            self.assertEqual(frontier().meta.coverage.value, "PARTIAL")
            write({**issued, "ready": [held]})
            self.assertEqual(frontier().meta.coverage.value, "PARTIAL")

    def test_admission_summary_budget(self):
        names = tuple("a" * 400 + str(i) for i in range(200))
        bounded = _bounded_names(names)
        self.assertTrue(bounded)
        self.assertLess(len(bounded), len(names))
        self.assertLess(len(json.dumps(bounded).encode()), 12_000)
        self.assertEqual(bounded, names[:len(bounded)])

    def test_signed_salience_fixture_projects_original_event_and_unknown_axis(self):
        from bilqis_mlx.learning._salience.tests.test_salience_history import (
            _policy, _event, _window_policy, _append, SalienceHistory,
        )
        policy = _policy()
        event = _event(0, policy)
        history = _append(SalienceHistory(_window_policy(policy), ()), event)
        self.assertEqual(issued_salience_observations(history), ({
            "event_id": event.event_id, "event_sha256": event.digest(),
            "receipt_sha256": event.source_receipt_sha256,
            "capability_id": "capability:one", "kind": "OBSERVATION",
            "impact": "LOW", "exigency": "LOW", "novelty": "UNKNOWN",
        },))
