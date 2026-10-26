"""Exercise canonical failure isolation using the selected clean-room fixture."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

from lib.ithkuil.src.ingestion_fixture import run_fixture
from lib.ithkuil.src.ingestion_graph import run_graph
from lib.ithkuil.src.ingestion_semantic import run_semantic
from lib.ithkuil.tests.ingestion_cleanroom import hashes
from lib.ithkuil.tests.ingestion_failure_injection import fail_no_omission


def prove_failures(proof: Path, python: str) -> dict:
    workspace = proof / "one"
    repo = workspace / "runtime"
    good = json.loads((workspace / "stdout.json").read_text())
    before = hashes(workspace / "output")
    failures = proof / "failures"
    failures.mkdir()
    fixture = failures / "source-fixture"
    shutil.copytree(workspace / "fixture", fixture)
    excerpt = fixture / "source.html"
    excerpt.write_bytes(excerpt.read_bytes() + b" ")
    source_failed = run_fixture(repo, python, fixture / "descriptor.json", failures / "source")
    if (source_failed["status"] != "BLOCKED" or source_failed["failed_stage"] != "source_fixture"
            or source_failed["semantic_result"] is not None or source_failed["graph_result"] is not None):
        raise AssertionError("SOURCE_FAILURE_ISOLATION_NOT_PROVEN")

    source = good["source_result"]
    data = Path(source["artifacts"]["canonical_root"]) / "_data/csv"
    semantic_failed = run_semantic(repo, python, data, source["frontier"]["path"],
                                   failures / "semantic", source_result=source,
                                   command_runner=fail_no_omission)
    if (semantic_failed["status"] != "FAILED" or semantic_failed["failed_gates"] != ["no-omission"]
            or semantic_failed["graph_eligibility"]["eligible"]):
        raise AssertionError("SEMANTIC_FAILURE_ISOLATION_NOT_PROVEN:" + json.dumps(semantic_failed))
    semantic_retry = run_semantic(repo, python, data, source["frontier"]["path"],
                                  failures / "semantic-retry", source_result=source)
    expected = good["semantic_result"]["artifacts"]["full_conformance_bundle"]["bundle_id"]
    if (semantic_retry["status"] != "SUCCEEDED"
            or semantic_retry["artifacts"]["full_conformance_bundle"]["bundle_id"] != expected):
        raise AssertionError("SEMANTIC_RETRY_CHANGED_IDENTITY")

    graph_failed = run_graph(repo, python, good["semantic_result"], failures / "graph", enabled=True,
                             required=True, graph="bilqis_skos_92_unreachable_fixture", owner="issue92",
                             host="127.0.0.1", port=1, suite=workspace / "fixture/smoke.json",
                             notation="MFF", datatype="https://github.com/Entif-AI/Bilqis-MLX/id/datatype/grammar-code",
                             expected_iri="https://github.com/Entif-AI/Bilqis-MLX/id/grammar/CONFIGURATION/MFF")
    if graph_failed["status"] != "FAILED" or graph_failed["failed_stage"] != "runtime_preflight":
        raise AssertionError("GRAPH_FAILURE_ISOLATION_NOT_PROVEN")
    if hashes(workspace / "output") != before:
        raise AssertionError("FAILURE_MUTATED_PRIOR_AUTHORITATIVE_ARTIFACTS")
    result = {"schema": "bilqis.ithkuil.fixture-failure-proof/v1", "fixture_only": True,
              "status": "passed", "source": source_failed["status"],
              "source_error": source_failed["error_code"],
              "semantic_failed_gates": semantic_failed["failed_gates"],
              "semantic_retry": semantic_retry["status"], "required_graph": graph_failed["status"],
              "required_graph_failed_stage": graph_failed["failed_stage"],
              "prior_authoritative_artifacts_unchanged": True}
    for name, value in (("source", source_failed), ("semantic", semantic_failed),
                        ("semantic-retry", semantic_retry), ("graph", graph_failed)):
        (failures / (name + "-result.json")).write_text(json.dumps(value, indent=2) + "\n")
    (proof / "failure-proof.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    return result


if __name__ == "__main__":
    import argparse
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prove_failures(args.proof.resolve(), sys.executable), sort_keys=True))
