"""Accepted BAMF custody projects only proven Factory cockpit facts."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from bilqis_mlx.control_plane import ControlPlaneClient, ControlPlaneService
from bilqis_mlx.control_plane.tests.support import start_service
from bilqis_mlx.mission_control import MissionControlQueryCatalog, QueryRequest, QueryFamily, QueryMode
from bilqis_mlx.mission_control.contracts.observability import GenerationManifestV2
from bilqis_mlx.mission_control.contracts.model import CoverageState
from bilqis_mlx.control_plane.native_contracts import record_meta, run_ref

from bilqis_mlx.control_plane.native_contracts import AuthenticatedGeneration
from bilqis_mlx.control_plane.native_factory import accepted_factory_records
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2


def digest(char):
    return char * 64


def generation(number, release, semantic, *, adoption=False):
    outbox = ()
    if adoption:
        outbox = ({
            "event": "BAMF_FACTORY_RELEASE_ADOPTION_COMMITTED",
            "factory_release_sha256": release,
            "transition_sha256": digest("5"),
            "selection_receipt_sha256": digest("6"),
        },)
    return AuthenticatedGeneration(
        f"{number + 1:064x}", f"{number + 2:064x}",
        {
            "run_id": "run-factory", "generation": number,
            "optimizer": {"step": number},
            "provenance": {"release_digest": semantic},
            "topology": ModelTopologySpecV2().to_record(),
            "transition": {},
        },
        {"candidate_identity_sha256": digest("8"), "factory_release_sha256": release},
        {
            "run_identity_sha256": digest("9"),
            "initial_candidate_identity_sha256": digest("8"),
            "factory_release_sha256": release,
        },
        correction_frontier={}, teacher_state={}, outbox=outbox,
    )


class NativeFactoryProjectionTests(unittest.TestCase):
    def test_accepted_history_keeps_prior_release_stale_and_current_release_exact(self):
        old_release, current_release = digest("a"), digest("c")
        rows = accepted_factory_records((
            generation(0, old_release, digest("b")),
            generation(1, current_release, digest("d"), adoption=True),
        ))
        self.assertEqual([item.currency_state.value for item in rows], ["STALE", "CURRENT"])
        self.assertEqual(rows[0].meta.coverage.value, "PARTIAL")
        self.assertEqual(rows[1].lifecycle_state.value, "ADMITTED")
        self.assertEqual(rows[1].delivery_status.value, "NOT_EVIDENCED")
        self.assertEqual(rows[1].lineage[0].generation, 1)
        self.assertEqual(rows[1].lineage[0].topology.knowledge.value, "EXACT")
        self.assertEqual(rows[1].lineage[0].topology.layers, 12)
        self.assertEqual(rows[1].admission_receipt_sha256, f"{3:064x}")
        self.assertEqual(rows[1].capability_ids, ())


    def test_large_release_summary_and_complete_lineage_paginate_over_cp01(self):
        release = digest("c")
        history = tuple(
            generation(n, release, digest("d"), adoption=n == 1)
            for n in range(301))
        summary, = accepted_factory_records(history)
        self.assertEqual([row.generation for row in summary.lineage], [0, 1, 300])
        self.assertEqual(summary.admission_receipt_sha256, history[1].acceptance_sha256)
        self.assertEqual(len(summary.meta.source_refs), 3)
        self.assertLessEqual(len(summary.receipt_refs), 6)
        records = [summary]
        for item in history:
            run = run_ref(item)
            records.append(GenerationManifestV2(
                record_meta(f"generation:{run.generation}", run, item,
                            coverage=CoverageState.PARTIAL,
                            receipt_refs=(item.acceptance_sha256,)),
                digest("e"), None, None, None, "ACCEPTED"))
        # A different release in the same run must not leak into this history.
        other = generation(301, digest("a"), digest("b"))
        run = run_ref(other)
        records.append(GenerationManifestV2(
            record_meta("generation:301", run, other, coverage=CoverageState.PARTIAL),
            digest("e"), None, None, None, "ACCEPTED"))
        catalog = MissionControlQueryCatalog(records)
        with TemporaryDirectory() as temp:
            root = Path(temp)
            service = ControlPlaneService(root / "run", root / "cp.sock",
                                          query_source=lambda: catalog)
            thread = start_service(service)
            try:
                with ControlPlaneClient(root / "cp.sock") as client:
                    page = client.query(QueryRequest(QueryFamily.FACTORY))
                    self.assertTrue(page["accepted"], page)
                    self.assertLess(len(json.dumps(page).encode()), 64 * 1024)
                    self.assertEqual(page["records"][0]["lineage"][-1]["generation"], 300)
                    query = QueryRequest(
                        QueryFamily.GENERATION, run_id="run-factory",
                        reference=f"factory-release:{release}",
                        schema_version=GenerationManifestV2.SCHEMA, limit=32)
                    recovered = []
                    first_cursor = None
                    while True:
                        page = client.query(query)
                        self.assertTrue(page["accepted"], page)
                        self.assertEqual(page["total_matches"], 301)
                        self.assertLess(len(json.dumps(page, separators=(",", ":")).encode()), 64 * 1024)
                        recovered.extend(row["meta"]["run"]["generation"] for row in page["records"])
                        if page["next_cursor"] is None:
                            break
                        if first_cursor is None:
                            first_cursor = page["next_cursor"]
                        query = replace(query, cursor=page["next_cursor"])
                    self.assertEqual(recovered, list(range(301)))
                    wrong_release = client.query(replace(
                        query, reference=f"factory-release:{digest('a')}", cursor=first_cursor))
                    self.assertFalse(wrong_release["accepted"])
                    self.assertEqual(wrong_release["reason"], "CONTROL_PLANE_QUERY_INVALID")
                    wrong_run = client.query(replace(
                        query, run_id="different-run", cursor=None))
                    self.assertTrue(wrong_run["accepted"])
                    self.assertEqual(wrong_run["records"], [])
                    ordinary = client.query(QueryRequest(QueryFamily.GENERATION))
                    self.assertEqual([r["meta"]["run"]["generation"] for r in ordinary["records"]], [301])
                    historical = client.query(QueryRequest(
                        QueryFamily.GENERATION, QueryMode.HISTORICAL,
                        run_id="run-factory", generation=17))
                    self.assertEqual(historical["records"][0]["meta"]["run"]["generation_manifest_sha256"],
                                     history[17].manifest_sha256)
            finally:
                service.shutdown()
                thread.join(2)


if __name__ == "__main__":
    unittest.main()
