"""Optional live #91 proof over two isolated runtimes and owned graphs."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import uuid

from lib.ithkuil.src.skos.falkor_import import Importer, connect
from lib.ithkuil.tests.ingestion_cleanroom import hashes

BASE = "https://github.com/Entif-AI/Bilqis-MLX/"


def graph_command(workspace, python, semantic, name, output, host, port, suite):
    repo = workspace / "runtime"
    semantic_path = workspace / "semantic-result.json"
    semantic_path.write_text(json.dumps(semantic))
    argv = [python, "-B", "-m", "lib.ithkuil.src.ingestion_graph", "--repo", str(repo),
            "--python", python, "--semantic-result", str(semantic_path),
            "--output-root", str(output), "--enable-graph", "--required",
            "--graph", name, "--owner", "codex_ingestion_91", "--host", host, "--port", str(port),
            "--suite", str(suite), "--notation", "MFF", "--datatype", BASE + "id/datatype/grammar-code",
            "--expected-iri", BASE + "id/grammar/CONFIGURATION/MFF"]
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("PYTHON", "BILQIS"))}
    process = subprocess.run(argv, cwd=repo, env=environment, capture_output=True, text=True,
                             timeout=180, check=False)
    result = json.loads(process.stdout)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix(".result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def prove_graphs(proof, python, host="127.0.0.1", port=16379):
    receipts = []
    targets = []
    for name in ("one", "two"):
        workspace = proof / name
        semantic = json.loads((workspace / "stdout.json").read_text())["semantic_result"]
        before = hashes(workspace / "output")
        graph = "bilqis_skos_91_" + uuid.uuid4().hex[:12]
        targets.append(graph)
        suite = workspace / "fixture/smoke.json"
        good = graph_command(workspace, python, semantic, graph, workspace / "graph-good", host, port, suite)
        if good["status"] != "SUCCEEDED":
            raise AssertionError("GRAPH_PROOF_FAILED:" + str(good.get("error_code")))
        receipt = json.loads(Path(good["artifacts"]["materialization_receipt"]["path"]).read_text())
        receipts.append({key: value for key, value in receipt.items() if key not in {"timestamp", "graph"}})
        # Preserve all prior good graph evidence before refusal and retry.
        evidence_before = hashes(workspace / "graph-good")
        wrong = json.loads(suite.read_text())
        wrong["queries"][0]["expected"] = [[BASE + "id/deliberate-smoke-failure"]]
        broken_suite = workspace / "broken-smoke.json"
        broken_suite.write_text(json.dumps(wrong))
        failed = graph_command(workspace, python, semantic, graph, workspace / "graph-failed", host, port, broken_suite)
        if failed["status"] != "FAILED" or failed["failed_stage"] != "materialize_receipt":
            raise AssertionError("GRAPH_FAILURE_BOUNDARY_NOT_PROVEN")
        if any(c.get("stage") == "akasha_readback" for c in failed["commands"]):
            raise AssertionError("GRAPH_DOWNSTREAM_NOT_SUPPRESSED")
        retry = graph_command(workspace, python, semantic, graph, workspace / "graph-retry", host, port, suite)
        if retry["status"] != "SUCCEEDED":
            raise AssertionError("GRAPH_RETRY_FAILED")
        if hashes(workspace / "output") != before or hashes(workspace / "graph-good") != evidence_before:
            raise AssertionError("GRAPH_MUTATED_PRIOR_EVIDENCE")
        # An ownership refusal must not fall back or alter even the target graph.
        importer = Importer(connect(host, port), graph, "codex_ingestion_91")
        importer.graph.query("MATCH (n:RdfTerm) WHERE n.owner=$owner WITH n LIMIT 1 "
                             "CREATE (n)-[:FixtureBoundary]->(:FixtureForeignBoundary {fixture: 'issue91'})",
                             {"owner": "codex_ingestion_91"})
        census = importer.graph.ro_query("MATCH(n) RETURN count(n)").result_set
        refused = graph_command(workspace, python, semantic, graph, workspace / "graph-refused", host, port, suite)
        if refused["status"] != "BLOCKED" or refused["failed_stage"] != "reset_plan":
            raise AssertionError("FOREIGN_BOUNDARY_NOT_REFUSED")
        if importer.graph.ro_query("MATCH(n) RETURN count(n)").result_set != census:
            raise AssertionError("FOREIGN_BOUNDARY_MUTATED")
    if receipts[0] != receipts[1]:
        raise AssertionError("GRAPH_RECEIPTS_DIFFER")
    result = {"schema": "bilqis.ithkuil.fixture-graph-proof/v1", "fixture_only": True,
              "status": "passed", "graphs": targets, "compared_receipt": receipts[0],
              "excluded_fields": ["timestamp", "graph"], "differences": [],
              "failure_injection": "wrong smoke expectation fails at materialize_receipt; Akasha skipped; good-suite retry succeeds",
              "foreign_boundary": "blocked at reset_plan; node census unchanged",
              "prior_authoritative_artifacts_unchanged": True}
    (proof / "graph-proof.json").write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    return result
