"""Four bounded graph-stage proofs (#90)."""
from __future__ import annotations
from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from lib.ithkuil.src.skos.falkor_import import Importer, connect
from lib.ithkuil.src.skos.falkor_smoke import SUITE_PATH
from lib.ithkuil.src.skos.conformance import write_evidence
from lib.ithkuil.src.skos.publication import json_bytes
from lib.ithkuil.tests.skos.falkor.test_skos_falkor_smoke import smoke_evidence
from lib.ithkuil.tests.skos.conformance.test_skos_shacl import A, BASE


HOST, PORT = "127.0.0.1", 16379
SUITE = SUITE_PATH
DATATYPE = BASE + "id/datatype/new-ithkuil"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _semantic_result(bundle: Path) -> dict:
    manifest = bundle / "manifest.json"
    conformance = json.loads((bundle / "conformance.json").read_text())
    coverage = json.loads((bundle / "coverage.json").read_text())
    canonical = bundle / "canonical.nt"
    digest = _sha(canonical)
    gate_artifacts = {
        gate["gate"]: {"path": str(bundle / f"gate-{gate['gate']}.json"),
                       "sha256": _sha(bundle / f"gate-{gate['gate']}.json")}
        for gate in conformance["gates"]
    }
    assert conformance["status"] == "complete"
    assert conformance["canonical_sha256"] == digest
    return {
        "schema": "bilqis.ithkuil.semantic-stage-result/v1",
        "run_identity": "fixture-semantic-run",
        "status": "SUCCEEDED",
        "validator": {"csv_preflight_passed": True, "frontier_passed": True},
        "graph_eligibility": {"eligible": True, "release_qualified": False},
        "artifacts": {
            "core_generation_bundle": {"bundle_id": "a" * 64,
                                        "canonical": {"sha256": "b" * 64}},
            "full_conformance_bundle": {
                "path": str(bundle),
                "bundle_id": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                "manifest": {"path": str(manifest),
                             "sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()},
                "status": conformance["status"],
                "coverage_status": conformance["coverage_status"],
                "canonical": {"path": str(canonical), "sha256": digest,
                              "triple_count": coverage["canonical_rdf"]["triple_count"]},
                "coverage": {"path": str(bundle / "coverage.json"),
                             "sha256": _sha(bundle / "coverage.json"),
                             "status": coverage["build_status"]},
                "conformance": {"path": str(bundle / "conformance.json"),
                                "sha256": _sha(bundle / "conformance.json"),
                                "status": conformance["status"], "failed_gates": []},
                "gate_artifacts": gate_artifacts,
                "gates": conformance["gates"],
            },
        },
    }


class IngestionGraphTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        fixture_bundle = smoke_evidence(self.root / "semantic-fixture")
        files = {path.name: path.read_bytes() for path in fixture_bundle.iterdir()
                 if path.is_file() and path.name != "manifest.json"}
        report = json.loads(files["conformance.json"])
        for gate in report["gates"]:
            files[f"gate-{gate['gate']}.json"] = json_bytes(gate)
        self.bundle = Path(write_evidence(files, self.root / "semantic")["path"])
        self.canonical = self.bundle / "canonical.nt"
        self.canonical_sha = _sha(self.canonical)
        self.semantic = _semantic_result(self.bundle)

    def _run(self, *, output: Path, graph: str, owner: str, **extra):
        from lib.ithkuil.src.ingestion_graph import run_graph

        return run_graph(
            REPO_ROOT, Path(__import__("sys").executable), self.semantic, output,
            enabled=True, graph=graph, owner=owner, host=HOST, port=PORT,
            suite=SUITE, notation="∅", datatype=DATATYPE, expected_iri=str(A), **extra,
        )

    def _target(self, label: str) -> tuple[str, str]:
        return "bilqis_skos_19_90_" + label + "_" + uuid.uuid4().hex[:10], "owner-90-" + uuid.uuid4().hex

    def test_disabled_needs_no_target_output_or_database(self):
        from lib.ithkuil.src.ingestion_graph import run_graph

        output = self.root / "not-created"
        result = run_graph(REPO_ROOT, "unused-python", self.semantic, output,
                           enabled=False)
        self.assertEqual(result["status"], "DISABLED")
        self.assertEqual(result["semantic_status"], "SUCCEEDED")
        self.assertEqual(result["commands"], [])
        self.assertFalse(output.exists())
        self.assertEqual(_sha(self.canonical), self.canonical_sha)

    def test_unavailable_optional_graph_does_not_downgrade_semantic_success(self):
        from lib.ithkuil.src.ingestion_graph import run_graph

        graph, owner = self._target("offline")
        output = self.root / "offline-run"
        result = run_graph(REPO_ROOT, Path(__import__("sys").executable),
                           self.semantic, output, enabled=True, graph=graph, owner=owner,
                           host="127.0.0.1", port=1, suite=SUITE, notation="∅",
                           datatype=DATATYPE, expected_iri=str(A), required=False)
        self.assertEqual(result["status"], "SKIPPED_UNAVAILABLE", result)
        self.assertEqual(result["semantic_status"], "SUCCEEDED")
        self.assertEqual(result["target"]["graph"], graph)
        self.assertEqual(result["commands"], [])
        self.assertTrue(Path(result["run_record"]).is_file())
        self.assertEqual(_sha(self.canonical), self.canonical_sha)

    def test_output_inside_immutable_bundle_is_refused_before_directory_creation(self):
        from lib.ithkuil.src.ingestion_graph import run_graph

        output = self.bundle / "graph-run-must-not-exist"
        before = {path.name: _sha(path) for path in self.bundle.iterdir() if path.is_file()}
        graph, owner = self._target("overlap")
        result = run_graph(REPO_ROOT, Path(__import__("sys").executable),
                           self.semantic, output, enabled=True, graph=graph, owner=owner,
                           host=HOST, port=PORT, suite=SUITE, notation="∅", datatype=DATATYPE,
                           expected_iri=str(A))
        after = {path.name: _sha(path) for path in self.bundle.iterdir() if path.is_file()}
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertIn("OVERLAP", result["error_code"])
        self.assertFalse(output.exists())
        self.assertEqual(before, after)

    @unittest.skipUnless(__import__("os").environ.get("BILQIS_FALKOR_LIVE") == "1",
                         "explicit isolated live graph proof only")
    def test_live_materialization_receipt_and_akasha_readback(self):
        graph, owner = self._target("live")
        result = self._run(output=self.root / "live-run", graph=graph, owner=owner)
        self.assertEqual(result["status"], "SUCCEEDED", result)
        self.assertEqual(result["semantic_status"], "SUCCEEDED")
        self.assertTrue(result["canonical_rdf_unchanged"])
        self.assertEqual(result["input"]["canonical_rdf_sha256"], self.canonical_sha)
        self.assertEqual(result["artifacts"]["materialization_receipt"]["receipt"]["status"], "complete")
        readback = result["artifacts"]["readback"]["result"]
        self.assertEqual(readback["concept_iri"], str(A))
        self.assertEqual(readback["notation"]["lexical"], "∅")
        self.assertEqual(readback["canonical_rdf_sha256"], self.canonical_sha)
        self.assertEqual(_sha(self.canonical), self.canonical_sha)
        self.assertEqual([command["stage"] for command in result["commands"]],
                         ["materialize_receipt", "akasha_readback"])
        print(json.dumps({"live_graph": graph, "owner": owner, "digest": self.canonical_sha,
                          "receipt_sha256": result["artifacts"]["materialization_receipt"]["sha256"]},
                         sort_keys=True), flush=True)

    @unittest.skipUnless(__import__("os").environ.get("BILQIS_FALKOR_LIVE") == "1",
                         "explicit isolated live graph proof only")
    def test_foreign_boundary_refuses_before_receipt_write(self):
        from lib.ithkuil.src.ingestion_graph import run_graph

        graph, owner = self._target("foreign")
        importer = Importer(connect(HOST, PORT), graph, owner)
        importer.materialize(self.bundle)
        importer.graph.query(
            "MATCH (n:RdfTerm) WHERE n.owner=$owner WITH n LIMIT 1 "
            "CREATE (f:RdfTerm {key:$key,iri:$iri,owner:'foreign-owner'}) "
            "CREATE (n)-[:RDF {key:$edge,predicate_iri:'urn:fixture:boundary',owner:$owner}]->(f) "
            "RETURN count(*)",
            {"owner": owner, "key": "foreign-90-" + uuid.uuid4().hex,
             "iri": "urn:fixture:foreign-" + uuid.uuid4().hex,
             "edge": "foreign-edge-90-" + uuid.uuid4().hex},
        )
        before = importer.graph.ro_query(
            "MATCH (n) RETURN count(n)", {}).result_set
        output = self.root / "foreign-run"
        result = run_graph(REPO_ROOT, Path(__import__("sys").executable),
                           self.semantic, output, enabled=True, graph=graph, owner=owner,
                           host=HOST, port=PORT, suite=SUITE, notation="∅", datatype=DATATYPE,
                           expected_iri=str(A))
        after = importer.graph.ro_query("MATCH (n) RETURN count(n)", {}).result_set
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertEqual(result["error_code"], "FOREIGN_BOUNDARY")
        self.assertEqual(result["commands"][-1]["stage"], "reset_plan")
        self.assertEqual(before, after)
        self.assertFalse((output / "materialization_receipt.json").exists())
        self.assertEqual(_sha(self.canonical), self.canonical_sha)


if __name__ == "__main__":
    unittest.main()
