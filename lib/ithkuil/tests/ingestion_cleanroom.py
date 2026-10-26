"""Fresh runtime isolation and artifact comparison for the #91 workflow proof."""
from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def hashes(root: Path) -> dict:
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*")) if path.is_file()}


def isolated_run(repo: Path, fixture: Path, target: Path, python: str) -> dict:
    """Copy only code, normative profiles, negative fixtures, and declared inputs."""
    runtime = target / "runtime"
    library = runtime / "lib/ithkuil"
    library.mkdir(parents=True)
    shutil.copytree(repo / "lib/ithkuil/src", library / "src",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("ingestion_contract.json", "SKOS_PROFILE.md", "SKOS_COMPILER.md", "requirements-semantic.txt", "requirements-falkor.txt"):
        shutil.copyfile(repo / "lib/ithkuil" / name, library / name)
    negatives = library / "tests/fixtures"
    negatives.mkdir(parents=True)
    for name in ("skos_root_sense_negative.ttl", "skos_composition_negative.ttl"):
        shutil.copyfile(repo / "lib/ithkuil/tests/fixtures" / name, negatives / name)
    shutil.copytree(fixture, target / "fixture")
    # No _raw, _data, runs, checkpoints, Git checkout or user Python path exists.
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("PYTHON", "BILQIS"))}
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    before = hashes(runtime)
    command = [python, "-B", "-m", "lib.ithkuil.src.ingestion_fixture", "--repo", str(runtime),
               "--python", python, "--descriptor", str(target / "fixture/descriptor.json"),
               "--output-root", str(target / "output")]
    completed = subprocess.run(command, cwd=runtime, env=environment, capture_output=True,
                               text=True, timeout=120, check=False)
    (target / "stdout.json").write_text(completed.stdout)
    (target / "stderr.log").write_text(completed.stderr)
    if completed.returncode:
        raise AssertionError("CLEANROOM_COMMAND_FAILED:" + completed.stdout[-800:] + completed.stderr[-800:])
    result = json.loads(completed.stdout)
    if result["status"] != "SUCCEEDED" or hashes(runtime) != before:
        raise AssertionError("CLEANROOM_RESULT_OR_RUNTIME_MUTATION")
    return result


def comparable(result: dict) -> dict:
    source, semantic = result["source_result"], result["semantic_result"]
    core = semantic["artifacts"]["core_generation_bundle"]
    full = semantic["artifacts"]["full_conformance_bundle"]
    return {"source_input": source["source_input_identity"],
            "csv_and_fixture_receipt": source["artifacts"]["published_artifact_hashes"],
            "fixture_frontier_sha256": semantic["input_identity"]["frontier_receipt_sha256"],
            "csv_closure_sha256": semantic["input_identity"]["csv_closure_sha256"],
            "core_manifest": core["manifest"]["sha256"],
            "core_rdf": core["canonical"]["sha256"], "held_ledger": core["held"]["sha256"],
            "full_bundle": full["bundle_id"], "full_rdf": full["canonical"]["sha256"],
            "coverage": full["coverage"]["sha256"], "conformance": full["conformance"]["sha256"],
            "gates": full["gates"]}


def prove(repo: Path, fixture: Path, output: Path, python: str) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    first = isolated_run(repo, fixture, output / "one", python)
    second = isolated_run(repo, fixture, output / "two", python)
    left, right = comparable(first), comparable(second)
    if left != right:
        raise AssertionError("CLEANROOM_ARTIFACT_MISMATCH")
    receipt = {"schema": "bilqis.ithkuil.cleanroom-proof/v1", "fixture_only": True,
               "status": "passed", "independent_runtime_workspaces": 2,
               "shared_generated_cache": False, "differences": [], "compared": left,
               "dependencies": {name: version(name) for name in ("lxml", "rdflib", "pyshacl")},
               "python_version": sys.version,
               "excluded_operational_fields": ["repo_root", "python", "output_root", "csv_root",
                   "frontier_path", "artifact paths", "run_identity", "source_stage.result_sha256",
                   "command argv and log paths"],
               "exclusion_reason": "Locations and their derived orchestration identities vary; every semantic artifact byte and manifest is compared."}
    (output / "proof.json").write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    receipt = prove(args.repo.resolve(), args.fixture.resolve(), args.output_root.resolve(), sys.executable)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
