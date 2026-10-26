"""Orchestrate canonical CSV compilation and semantic conformance (#89)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
from typing import Callable

from .ingestion import _bytes, _execute, _safe_environment, _write_atomic
from .skos.build import COMPILER_VERSION, PROFILE_VERSION, compiler_receipt, input_receipt
from .skos.conformance import GATES, GATE_VERSION
from .skos.errors import ProfileError
from .skos.preflight import preflight
from .skos.preflight_manifest import DEFAULT_MANIFEST_PATH, load_manifest
from .source_frontier import _json_bytes as frontier_json_bytes


RESULT_SCHEMA = "bilqis.ithkuil.semantic-stage-result/v1"
RUN_SCHEMA = "bilqis.ithkuil.semantic-run/v1"
CORE_MODULE = "lib.ithkuil.src.skos.build"
CONFORMANCE_MODULE = "lib.ithkuil.src.skos.conformance"
HEX64 = frozenset("0123456789abcdef")


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _file_sha(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError("INPUT_NOT_REGULAR_FILE:" + str(path))
    return _sha(path.read_bytes())


def _valid_sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= HEX64


def _result(*, run_identity: str, status: str, input_identity: dict | None = None,
            commands: list[dict] | None = None, artifacts: dict | None = None,
            validator: dict | None = None, graph_eligibility: dict | None = None,
            failed_stage: str | None = None, failed_gates: list[str] | None = None,
            error_code: str | None = None, run_record: Path | None = None) -> dict:
    return {
        "schema": RESULT_SCHEMA,
        "run_identity": run_identity,
        "status": status,
        "input_identity": input_identity or {},
        "commands": commands or [],
        "artifacts": artifacts or {},
        "validator": validator or {"csv_preflight_passed": False, "frontier_passed": False},
        "graph_eligibility": graph_eligibility or {"eligible": False, "reason": "NOT_CONFORMANCE_VERIFIED"},
        "failed_stage": failed_stage,
        "failed_gates": failed_gates or [],
        "error_code": error_code,
        "run_record": str(run_record) if run_record else None,
    }


def _load_contract(repo_root: Path) -> tuple[dict, str]:
    path = repo_root / "lib" / "ithkuil" / "ingestion_contract.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    if (contract.get("schema") != "bilqis.ithkuil.ingestion-contract/v1"
            or contract.get("governance", {}).get("authority_mode") != "public_only"
            or contract.get("llm_semantic_interpretation") is not False):
        raise ValueError("INGESTION_CONTRACT_AUTHORITY_INVALID")
    core = contract.get("stages", {}).get("core", {})
    conformance = contract.get("stages", {}).get("conformance", {})
    if core.get("modules") != [CORE_MODULE] or conformance.get("modules") != [CONFORMANCE_MODULE]:
        raise ValueError("INGESTION_CONTRACT_SEMANTIC_OWNER_DRIFT")
    if core.get("write_class") != "generated_artifact_write" or \
            conformance.get("write_class") != "generated_artifact_write":
        raise ValueError("INGESTION_CONTRACT_WRITE_CLASS_INVALID")
    return contract, _file_sha(path)


def _dependencies_match(repo_root: Path, *, contract_sha: str, compiler_sha: str,
                        orchestrator_sha: str) -> bool:
    try:
        _, current_contract_sha = _load_contract(repo_root)
        return (current_contract_sha == contract_sha
                and compiler_receipt()["sha256"] == compiler_sha
                and _file_sha(Path(__file__).resolve()) == orchestrator_sha)
    except (OSError, ValueError, KeyError, TypeError):
        return False


def _csv_paths(input_root: Path) -> tuple[str, ...]:
    manifest = load_manifest(DEFAULT_MANIFEST_PATH)
    paths = tuple(sorted({table.path for table in manifest.tables}))
    if not paths:
        raise ValueError("COMPILER_INPUT_MANIFEST_EMPTY")
    for value in paths:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("UNSAFE_COMPILER_INPUT_PATH:" + value)
        candidate = input_root.joinpath(*path.parts)
        if candidate.is_symlink() or not candidate.is_file():
            raise ValueError("CSV_INPUT_MISSING_OR_UNSAFE:" + value)
    return paths


def _all_csv_paths(input_root: Path) -> tuple[str, ...]:
    return tuple(sorted(path.relative_to(input_root).as_posix()
                        for path in input_root.rglob("*.csv")
                        if path.is_file() and not path.is_symlink()))


def _frontier(frontier_path: Path, input_root: Path, repo_root: Path) -> tuple[dict, str, str]:
    if frontier_path.is_symlink() or not frontier_path.is_file():
        raise ValueError("EXTRACTION_FRONTIER_MISSING_OR_UNSAFE")
    payload = frontier_path.read_bytes()
    frontier = json.loads(payload.decode("utf-8"))
    fixture = frontier.get("schema") == "bilqis.ithkuil.fixture-frontier/v1"
    if fixture and (frontier.get("scope") != "fixture_only" or frontier.get("claims") != {
            "production_admission": False, "full_new_ithkuil_coverage": False, "curriculum_admission": False}):
        raise ValueError("FIXTURE_FRONTIER_CLAIMS_INVALID")
    if not fixture and frontier.get("schema") != "bilqis.ithkuil.extraction-frontier/v1":
        raise ValueError("EXTRACTION_FRONTIER_SCHEMA_INVALID")
    claimed = frontier.get("receipt_sha256")
    without_digest = dict(frontier)
    without_digest.pop("receipt_sha256", None)
    if not _valid_sha(claimed) or _sha(frontier_json_bytes(without_digest)) != claimed:
        raise ValueError("EXTRACTION_FRONTIER_RECEIPT_DIGEST_MISMATCH")
    inputs = frontier.get("inputs")
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError("EXTRACTION_FRONTIER_INPUTS_MISSING")
    for name, expected in sorted(inputs.items()):
        if not isinstance(name, str) or not _valid_sha(expected):
            raise ValueError("EXTRACTION_FRONTIER_INPUT_RECEIPT_INVALID")
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("EXTRACTION_FRONTIER_INPUT_PATH_UNSAFE")
        if name.startswith("_raw/") or name.startswith("_data/pdf/"):
            continue
        if name == "lexicon_frontier_pins.json":
            candidate = repo_root / "lib" / "ithkuil" / "src" / name
        else:
            candidate = input_root.joinpath(*relative.parts)
        required = name.endswith(".csv") or name.startswith("sources/") or name == "lexicon_frontier_pins.json"
        if not candidate.exists():
            if required:
                raise ValueError("FRONTIER_CSV_IDENTITY_MISMATCH:" + name)
            continue
        if candidate.is_symlink() or not candidate.is_file() or _file_sha(candidate) != expected:
            raise ValueError("FRONTIER_CSV_IDENTITY_MISMATCH:" + name)
    return frontier, _sha(payload), claimed


def _load_source_result(source_result: dict | str | Path | None) -> tuple[dict | None, str | None]:
    if source_result is None:
        return None, None
    if isinstance(source_result, (str, Path)):
        path = Path(source_result).expanduser()
        if path.is_symlink() or not path.is_file():
            raise ValueError("STAGE_A_RESULT_MISSING_OR_UNSAFE")
        payload = path.read_bytes()
        value = json.loads(payload.decode("utf-8"))
        return value, _sha(payload)
    if isinstance(source_result, dict):
        return source_result, _sha(_bytes(source_result))
    raise ValueError("STAGE_A_RESULT_TYPE_INVALID")


def _validate_source_result(result: dict | None, result_sha: str | None,
                            csv_root: Path, frontier_path: Path, frontier_sha: str,
                            csv_hashes: dict[str, str]) -> dict:
    if result is None:
        return {"provided": False, "stage_a_success": False,
                "statement": "CSV preflight and current frontier closure validated; source bytes are not reverified."}
    if result.get("status") not in {"SUCCEEDED", "REUSED"}:
        raise ValueError("STAGE_A_RESULT_NOT_SUCCESSFUL")
    if result.get("validator", {}).get("passed") is not True:
        raise ValueError("STAGE_A_VALIDATOR_NOT_PASSED")
    if (not _valid_sha(result.get("source_manifest_sha256"))
            or result.get("source_manifest_sha256") != csv_hashes.get("sources/source_manifest.csv")):
        raise ValueError("STAGE_A_SOURCE_MANIFEST_IDENTITY_MISSING")
    artifacts = result.get("artifacts", {})
    canonical_root = artifacts.get("canonical_root")
    expected_root = (Path(canonical_root).expanduser().resolve() / "_data" / "csv") if canonical_root else None
    if expected_root != csv_root:
        raise ValueError("STAGE_A_CSV_ROOT_MISMATCH")
    published = artifacts.get("published_artifact_hashes")
    if not isinstance(published, dict):
        raise ValueError("STAGE_A_PUBLISHED_HASHES_MISSING")
    actual_csv_hashes = {name: digest for name, digest in published.items()
                         if name.startswith("_data/csv/") and name.endswith(".csv")}
    required_csv_hashes = {"_data/csv/" + name: digest for name, digest in csv_hashes.items()
                           if len(PurePosixPath(name).parts) == 1}
    if not required_csv_hashes.items() <= actual_csv_hashes.items():
        raise ValueError("STAGE_A_CSV_IDENTITY_MISMATCH")
    # Stage A publishes every top-level CSV, not just the compiler's 12-file
    # manifest closure. Verify every supplied CSV identity against this root.
    observed_top_level = {"_data/csv/" + path.name: _file_sha(path)
                          for path in csv_root.glob("*.csv") if path.is_file() and not path.is_symlink()}
    if actual_csv_hashes != observed_top_level:
        raise ValueError("STAGE_A_PUBLISHED_CSV_SET_MISMATCH")
    for name, expected in actual_csv_hashes.items():
        relative = PurePosixPath(name.removeprefix("_data/csv/"))
        if (relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 1
                or not _valid_sha(expected)):
            raise ValueError("STAGE_A_CSV_IDENTITY_INVALID")
        path = csv_root.joinpath(*relative.parts)
        if path.is_symlink() or not path.is_file() or _file_sha(path) != expected:
            raise ValueError("STAGE_A_CSV_IDENTITY_MISMATCH")
    expected_frontier = result.get("frontier", {})
    if (not isinstance(expected_frontier, dict)
            or Path(expected_frontier.get("path", "")).expanduser().resolve() != frontier_path
            or expected_frontier.get("sha256") != frontier_sha):
        raise ValueError("STAGE_A_FRONTIER_IDENTITY_MISMATCH")
    frontier_key = ("_data/csv/sources/fixture_frontier.json" if result.get("fixture_only") is True
                    else "_data/csv/sources/extraction_frontier.json")
    if published.get(frontier_key) != frontier_sha:
        raise ValueError("STAGE_A_FRONTIER_PUBLISHED_HASH_MISMATCH")
    return {"provided": True, "stage_a_success": True,
            "run_identity": result.get("run_identity"), "result_sha256": result_sha,
            "source_manifest_sha256": result["source_manifest_sha256"],
            "statement": "The successful Stage-A result binds this CSV root and frontier digest."}


def _input_snapshot(source: Path, target: Path, csv_paths: tuple[str, ...]) -> dict[str, str]:
    target.mkdir(parents=True, exist_ok=False)
    hashes: dict[str, str] = {}
    for name in csv_paths:
        relative = PurePosixPath(name)
        source_path = source.joinpath(*relative.parts)
        target_path = target.joinpath(*relative.parts)
        before = _file_sha(source_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        copied = _file_sha(target_path)
        after = _file_sha(source_path)
        if before != copied or before != after:
            raise ValueError("CSV_CHANGED_DURING_SNAPSHOT:" + name)
        hashes[name] = copied
    return hashes


def _input_hashes(root: Path, csv_paths: tuple[str, ...]) -> dict[str, str]:
    return {name: _file_sha(root.joinpath(*PurePosixPath(name).parts)) for name in csv_paths}


def _check_output_root(repo_root: Path, csv_root: Path, frontier_path: Path,
                       output_root: str | Path) -> Path:
    raw = Path(output_root).expanduser().absolute()
    if raw.is_symlink():
        raise ValueError("OUTPUT_ROOT_SYMLINK_FORBIDDEN")
    target = raw.resolve()
    if target == csv_root or target.is_relative_to(csv_root) or csv_root.is_relative_to(target):
        raise ValueError("OUTPUT_ROOT_OVERLAPS_CSV_INPUT")
    if target == frontier_path or target.is_relative_to(frontier_path) or frontier_path.is_relative_to(target):
        raise ValueError("OUTPUT_ROOT_OVERLAPS_FRONTIER")
    protected = [repo_root / ".git", repo_root / "runs", repo_root / "students",
                 repo_root / "lib" / "ithkuil" / "src", repo_root / "lib" / "ithkuil" / "_data"]
    if any(target == path.resolve() or target.is_relative_to(path.resolve())
           for path in protected if path.exists()):
        raise ValueError("OUTPUT_ROOT_PROTECTED_LOCATION")
    if raw.exists():
        raise ValueError("OUTPUT_ROOT_MUST_BE_NEW")
    return target


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _core_artifact(output_root: Path, summary: dict, expected_closure: str) -> dict:
    from .skos.publication import verify_publication

    receipt = verify_publication(output_root)
    generation = output_root / receipt["path"]
    metadata = receipt["metadata"]
    digest_path = generation / "digest.json"
    held_path = generation / "held.json"
    input_path = generation / "input.json"
    canonical_path = generation / "canonical.nt"
    digest = _read_json(digest_path)
    held = _read_json(held_path)
    input_doc = _read_json(input_path)
    canonical_sha = _file_sha(canonical_path)
    if (summary.get("bundle_id") != receipt["bundle_id"]
            or summary.get("canonical_sha256") != canonical_sha
            or digest.get("sha256") != canonical_sha
            or metadata.get("canonical_sha256") != canonical_sha
            or digest.get("input_closure_sha256") != expected_closure
            or input_doc.get("sha256") != expected_closure):
        raise ValueError("CORE_BUNDLE_IDENTITY_MISMATCH")
    return {
        "path": str(output_root), "bundle_id": receipt["bundle_id"],
        "status": metadata["status"], "release_ineligible": metadata["release_ineligible"],
        "triple_count": metadata["triple_count"], "resolved_resources": metadata["resolved_resources"],
        "emitted_resources": metadata["emitted_resources"],
        "manifest": {"path": str(generation / "manifest.json"), "sha256": receipt["bundle_id"]},
        "current": {"path": str(output_root / "CURRENT.json"), "sha256": _file_sha(output_root / "CURRENT.json")},
        "canonical": {"path": str(canonical_path), "sha256": canonical_sha,
                      "triple_count": digest["triple_count"]},
        "held": {"path": str(held_path), "sha256": _file_sha(held_path),
                 "blocking": held["blocking"], "counts": held["counts"]},
        "digest": {"path": str(digest_path), "sha256": _file_sha(digest_path),
                   "canonical_sha256": digest["sha256"], "profile_version": digest["profile_version"],
                   "profile_sha256": digest["profile_sha256"],
                   "input_closure_sha256": digest["input_closure_sha256"],
                   "compiler": digest["compiler"]},
        "input": {"path": str(input_path), "sha256": _file_sha(input_path),
                  "input_closure_sha256": input_doc["sha256"]},
    }


def _conformance_artifact(output_root: Path, report: dict) -> dict:
    evidence_ref = report.get("evidence", {})
    evidence = Path(evidence_ref.get("path", "")).resolve()
    root = output_root.resolve()
    if not evidence.is_relative_to(root) or evidence.is_symlink() or not evidence.is_dir():
        raise ValueError("CONFORMANCE_EVIDENCE_PATH_INVALID")
    manifest_path = evidence / "manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    bundle_id = evidence_ref.get("bundle_id")
    if not _valid_sha(bundle_id) or _sha(manifest_bytes) != bundle_id:
        raise ValueError("CONFORMANCE_MANIFEST_IDENTITY_MISMATCH")
    if set(path.name for path in evidence.iterdir()) != {*manifest.keys(), "manifest.json"}:
        raise ValueError("CONFORMANCE_EVIDENCE_FILE_SET_MISMATCH")
    files = {}
    for name, expected in sorted(manifest.items()):
        relative = PurePosixPath(name)
        path = evidence.joinpath(*relative.parts)
        if (relative.is_absolute() or ".." in relative.parts or not _valid_sha(expected)
                or path.is_symlink() or not path.is_file() or _file_sha(path) != expected):
            raise ValueError("CONFORMANCE_EVIDENCE_DIGEST_MISMATCH:" + name)
        files[name] = path
    required = {"canonical.nt", "comparison.nt", "coverage.json", "source-rows.json",
                "conformance.json", "admitted-mappings.nt", *(f"gate-{gate}.json" for gate in GATES)}
    if set(files) != required:
        raise ValueError("CONFORMANCE_EVIDENCE_ARTIFACT_SET_INVALID")
    canonical = files["canonical.nt"]
    coverage = _read_json(files["coverage.json"])
    conformance = _read_json(files["conformance.json"])
    if conformance.get("status") != report.get("status") or \
            conformance.get("canonical_sha256") != report.get("canonical_sha256") or \
            _file_sha(canonical) != report.get("canonical_sha256"):
        raise ValueError("CONFORMANCE_REPORT_ARTIFACT_MISMATCH")
    if coverage.get("canonical_rdf", {}).get("sha256") != report.get("canonical_sha256"):
        raise ValueError("CONFORMANCE_COVERAGE_CANONICAL_MISMATCH")
    gates = report.get("gates")
    if not isinstance(gates, list) or tuple(item.get("gate") for item in gates) != GATES:
        raise ValueError("CONFORMANCE_GATE_REGISTRY_MISMATCH")
    for gate in gates:
        if _read_json(files[f"gate-{gate['gate']}.json"]) != gate:
            raise ValueError("CONFORMANCE_GATE_EVIDENCE_MISMATCH:" + gate["gate"])
    return {
        "path": str(evidence), "bundle_id": bundle_id,
        "manifest": {"path": str(manifest_path), "sha256": bundle_id},
        "status": report.get("status"), "coverage_status": report.get("coverage_status"),
        "canonical": {"path": str(canonical), "sha256": report.get("canonical_sha256"),
                      "triple_count": coverage["canonical_rdf"]["triple_count"]},
        "comparison": {"path": str(files["comparison.nt"]), "sha256": _file_sha(files["comparison.nt"])},
        "coverage": {"path": str(files["coverage.json"]), "sha256": _file_sha(files["coverage.json"]),
                     "status": coverage.get("build_status")},
        "source_rows": {"path": str(files["source-rows.json"]), "sha256": _file_sha(files["source-rows.json"]),
                        "count": len(_read_json(files["source-rows.json"]))},
        "conformance": {"path": str(files["conformance.json"]),
                        "sha256": _file_sha(files["conformance.json"]),
                        "status": report.get("status"), "failed_gates": report.get("failed_gates", [])},
        "gates": gates,
        "gate_artifacts": {gate: {"path": str(files[f"gate-{gate}.json"]),
                                   "sha256": _file_sha(files[f"gate-{gate}.json"])} for gate in GATES},
    }


def _stdout_json(log_ref: str) -> dict | None:
    try:
        return json.loads(Path(log_ref).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None


def _update_record(record_path: Path, record: dict, **changes) -> None:
    record.update(changes)
    _write_atomic(record_path, _bytes(record))


def run_semantic(repo_root: str | Path, python_executable: str, input_root: str | Path,
                 frontier_ref: str | Path, output_root: str | Path, *,
                 source_result: dict | str | Path | None = None,
                 command_runner: Callable | None = None) -> dict:
    """Build the core bundle and full-domain conformance bundle from one CSV snapshot."""
    repo = Path(repo_root).expanduser().resolve()
    if repo != Path(__file__).resolve().parents[3]:
        return _result(run_identity="", status="BLOCKED", failed_stage="inspect",
                       error_code="REPOSITORY_MODULE_MISMATCH:invoke-the-selected-checkout-module")
    raw_csv_root = Path(input_root).expanduser().absolute()
    raw_frontier_path = Path(frontier_ref).expanduser().absolute()
    if raw_csv_root.is_symlink() or raw_frontier_path.is_symlink():
        return _result(run_identity="", status="BLOCKED", failed_stage="inspect",
                       error_code="INPUT_SYMLINK_FORBIDDEN")
    csv_root = raw_csv_root.resolve()
    frontier_path = raw_frontier_path.resolve()
    python = Path(python_executable).expanduser().absolute()
    if not python.is_file() or not os.access(python, os.X_OK):
        return _result(run_identity="", status="BLOCKED", failed_stage="inspect",
                       error_code="PYTHON_EXECUTABLE_INVALID")
    if not (repo / "lib" / "ithkuil" / "src").is_dir() or not csv_root.is_dir():
        return _result(run_identity="", status="BLOCKED", failed_stage="inspect",
                       error_code="REPOSITORY_OR_CSV_ROOT_INVALID")
    try:
        contract, contract_sha = _load_contract(repo)
        csv_paths = _csv_paths(csv_root)
        snapshot_paths = _all_csv_paths(csv_root)
        frontier, frontier_sha, frontier_receipt_sha = _frontier(frontier_path, csv_root, repo)
        frontier_csv_paths = {name for name in frontier.get("inputs", {}) if name.endswith(".csv")}
        frontier_unbound_csv_paths = sorted(set(snapshot_paths) - frontier_csv_paths)
        checked = preflight(csv_root)
        if not checked.ok or checked.closure is None:
            raise ValueError("CSV_PREFLIGHT_FAILED:" + ",".join(item.code for item in checked.findings))
        closure_sha = input_receipt(checked.closure)["sha256"]
        csv_hashes = _input_hashes(csv_root, csv_paths)
        snapshot_source_hashes = _input_hashes(csv_root, snapshot_paths)
        stage_a, stage_a_sha = _load_source_result(source_result)
        stage_a_identity = _validate_source_result(
            stage_a, stage_a_sha, csv_root, frontier_path, frontier_sha,
            {name: digest for name, digest in csv_hashes.items() if name in csv_paths},
        )
        compiler = compiler_receipt()
        compiler_identity = {
            "profile_version": PROFILE_VERSION, "compiler_version": COMPILER_VERSION,
            "compiler_sha256": compiler["sha256"], "contract_sha256": contract_sha,
            "conformance_gate_version": GATE_VERSION, "conformance_gates": list(GATES),
            "orchestrator_sha256": _file_sha(Path(__file__)),
        }
        input_identity = {
            "fixture_only": frontier.get("schema") == "bilqis.ithkuil.fixture-frontier/v1",
            "csv_root": str(csv_root), "csv_closure_sha256": closure_sha,
            "csv_file_sha256": csv_hashes,
            "csv_snapshot_file_sha256": snapshot_source_hashes,
            "frontier_unbound_csv_paths": frontier_unbound_csv_paths,
            "frontier_path": str(frontier_path), "frontier_file_sha256": frontier_sha,
            "frontier_receipt_sha256": frontier_receipt_sha,
            "source_stage": stage_a_identity,
            "source_bytes_reverified": False,
            "pinned_source_observation_receipt_sha256": frontier_receipt_sha,
        }
        identity = {"repo_root": str(repo), "python": str(python), "output_root": str(output_root),
                    "selection": "semantic", "input": input_identity, "compiler": compiler_identity}
        run_id = _sha(_bytes(identity))[:24]
        target = _check_output_root(repo, csv_root, frontier_path, output_root)
    except Exception as exc:
        return _result(run_identity="", status="BLOCKED", failed_stage="inspect", error_code=str(exc))

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.mkdir(mode=0o700, exist_ok=False)
    except FileExistsError:
        return _result(run_identity=run_id, status="BLOCKED", input_identity=input_identity,
                       failed_stage="inspect", error_code="OUTPUT_ROOT_MUST_BE_NEW")
    except Exception as exc:
        return _result(run_identity=run_id, status="BLOCKED", input_identity=input_identity,
                       failed_stage="inspect", error_code="OUTPUT_ROOT_CREATE_FAILED:" + type(exc).__name__)

    run_record = target / "run.json"
    commands: list[dict] = []
    artifacts: dict = {}
    record = {
        "schema": RUN_SCHEMA, "run_identity": run_id, "status": "READY", "attempt": 1,
        "input_identity": input_identity, "compiler_identity": compiler_identity,
        "output_root": str(target), "commands": commands,
    }
    _write_atomic(run_record, _bytes(record))
    validator = {"csv_preflight_passed": True, "frontier_passed": True,
                 "stage_a_result_passed": stage_a is not None,
                 "frontier_source_bytes_reverified": False}
    try:
        snapshot = target / "input_snapshot"
        snapshot_hashes = _input_snapshot(csv_root, snapshot, snapshot_paths)
        if (snapshot_hashes != snapshot_source_hashes
                or input_receipt(preflight(snapshot).require_valid())["sha256"] != closure_sha):
            raise ValueError("CSV_SNAPSHOT_CLOSURE_MISMATCH")
        record["input_snapshot"] = {"path": str(snapshot), "sha256": snapshot_hashes,
                                    "input_closure_sha256": closure_sha}
        _update_record(run_record, record, status="RUNNING", active_stage="core_build")
        env = _safe_environment()
        core_root = target / "core"
        conformance_root = target / "conformance"
        core_module = contract["stages"]["core"]["modules"][0]
        conformance_module = contract["stages"]["conformance"]["modules"][0]
        commands_to_run = [
            ("core_build", [str(python), "-B", "-m", core_module,
                            "--input-root", str(snapshot), "--output-root", str(core_root),
                            "--profile", PROFILE_VERSION]),
            ("full_conformance", [str(python), "-B", "-m", conformance_module,
                                  "--input-root", str(snapshot), "--output-root", str(conformance_root)]),
        ]
        for index, (stage, argv) in enumerate(commands_to_run, 1):
            if (_input_hashes(csv_root, csv_paths) != csv_hashes
                    or _input_hashes(csv_root, snapshot_paths) != snapshot_source_hashes
                    or _input_hashes(snapshot, snapshot_paths) != snapshot_hashes):
                raise ValueError("CSV_INPUT_IDENTITY_CHANGED_DURING_RUN")
            if _file_sha(frontier_path) != frontier_sha:
                raise ValueError("FRONTIER_IDENTITY_CHANGED_DURING_RUN")
            if not _dependencies_match(repo, contract_sha=contract_sha,
                                       compiler_sha=compiler_identity["compiler_sha256"],
                                       orchestrator_sha=compiler_identity["orchestrator_sha256"]):
                raise ValueError("SEMANTIC_DEPENDENCY_IDENTITY_CHANGED_DURING_RUN")
            _update_record(run_record, record, status="RUNNING", active_stage=stage,
                           commands=commands)
            command = _execute(argv, repo, env, target / "logs", index, command_runner)
            command["stage"] = stage
            commands.append(command)
            record["commands"] = commands
            _write_atomic(run_record, _bytes(record))
            stdout = _stdout_json(command["stdout_log_ref"])
            if stage == "core_build":
                if command["exit_code"] != 0 or stdout is None:
                    return _finish_failure(run_record, record, run_id, input_identity, commands, artifacts,
                                           validator, target, "core_build", "CORE_BUILD_FAILED", stdout)
                try:
                    artifacts["core_generation_bundle"] = _core_artifact(core_root, stdout, closure_sha)
                except Exception as exc:
                    return _finish_failure(run_record, record, run_id, input_identity, commands, artifacts,
                                           validator, target, "core_build", str(exc), stdout)
            else:
                if stdout is None:
                    failure = _stdout_json(command["stderr_log_ref"]) or {}
                    return _finish_failure(run_record, record, run_id, input_identity, commands, artifacts,
                                           validator, target, "full_conformance",
                                           str(failure.get("code", "CONFORMANCE_RESULT_MISSING")), failure)
                report = stdout
                if report.get("status") not in {"complete", "failed", "infrastructure-failed"}:
                    return _finish_failure(run_record, record, run_id, input_identity, commands, artifacts,
                                           validator, target, stage, "CONFORMANCE_RESULT_INVALID", report)
                try:
                    artifacts["full_conformance_bundle"] = _conformance_artifact(conformance_root, report)
                except Exception as exc:
                    return _finish_failure(run_record, record, run_id, input_identity, commands, artifacts,
                                           validator, target, stage, str(exc), report)
                expected_status = 0 if report["status"] == "complete" else (
                    3 if report["status"] == "infrastructure-failed" else 2)
                if command["exit_code"] != expected_status:
                    return _finish_failure(run_record, record, run_id, input_identity, commands, artifacts,
                                           validator, target, stage, "CONFORMANCE_EXIT_STATUS_MISMATCH", report)
                if report["status"] != "complete":
                    code = ("CONFORMANCE_INFRASTRUCTURE_FAILED" if report["status"] == "infrastructure-failed"
                            else "SEMANTIC_CONFORMANCE_FAILED")
                    return _finish_failure(run_record, record, run_id, input_identity, commands, artifacts,
                                           validator, target, stage, code, report,
                                           failed_gates=report.get("failed_gates", []))

        fresh_csv_hashes = _input_hashes(csv_root, csv_paths)
        if (fresh_csv_hashes != csv_hashes
                or _input_hashes(csv_root, snapshot_paths) != snapshot_source_hashes
                or _input_hashes(snapshot, snapshot_paths) != snapshot_hashes
                or _file_sha(frontier_path) != frontier_sha
                or not _dependencies_match(repo, contract_sha=contract_sha,
                                           compiler_sha=compiler_identity["compiler_sha256"],
                                           orchestrator_sha=compiler_identity["orchestrator_sha256"])):
            return _finish_failure(run_record, record, run_id, input_identity, commands, artifacts,
                                   validator, target, "postflight", "RUN_IDENTITY_CHANGED_DURING_RUN", None)
        full = artifacts["full_conformance_bundle"]
        all_gates_passed = all(gate["status"] == "passed" for gate in full["gates"])
        eligible = full["status"] == "complete" and all_gates_passed
        eligibility = {"eligible": eligible,
                       "reason": ("ALL_GATES_PASSED" if eligible else "CONFORMANCE_GATES_NOT_PASSED"),
                       "release_qualified": False,
                       "conformance_status": full["status"], "coverage_status": full["coverage_status"],
                       "coverage_complete": full["coverage_status"] == "complete",
                       "gate_statuses": {gate["gate"]: gate["status"] for gate in full["gates"]}}
        result = _result(run_identity=run_id, status="SUCCEEDED", input_identity=input_identity,
                         commands=commands, artifacts=artifacts, validator=validator,
                         graph_eligibility=eligibility, run_record=run_record)
        record.update({**result, "compiler_identity": compiler_identity, "output_root": str(target)})
        _write_atomic(run_record, _bytes(record))
        return result
    except Exception as exc:
        return _finish_failure(run_record, record, run_id, input_identity, commands, artifacts,
                               validator, target, record.get("active_stage", "source"),
                               str(exc), None)


def _finish_failure(run_record: Path, record: dict, run_id: str, input_identity: dict,
                    commands: list[dict], artifacts: dict, validator: dict, output_root: Path,
                    stage: str, error_code: str, diagnostics: dict | None,
                    failed_gates: list[str] | None = None) -> dict:
    graph_eligibility = {"eligible": False,
                         "reason": "CONFORMANCE_FAILED" if stage == "full_conformance" else "STAGE_FAILED"}
    record.update({"status": "FAILED", "active_stage": stage, "failed_stage": stage,
                   "error_code": error_code, "failed_gates": failed_gates or [],
                   "diagnostics": diagnostics, "commands": commands})
    _write_atomic(run_record, _bytes(record))
    return _result(run_identity=run_id, status="FAILED", input_identity=input_identity,
                   commands=commands, artifacts=artifacts, validator=validator,
                   graph_eligibility=graph_eligibility, failed_stage=stage,
                   failed_gates=failed_gates, error_code=error_code, run_record=run_record)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True, help="Repository root containing lib/ithkuil.")
    parser.add_argument("--python", required=True, help="Explicit Python executable for canonical owners.")
    parser.add_argument("--input-root", type=Path, required=True, help="Explicit canonical CSV root.")
    parser.add_argument("--frontier", type=Path, required=True, help="Extraction-frontier receipt reference.")
    parser.add_argument("--output-root", type=Path, required=True, help="New dedicated semantic artifact root.")
    parser.add_argument("--source-result", type=Path, help="Optional validated Stage-A result JSON.")
    args = parser.parse_args(argv)
    result = run_semantic(args.repo, args.python, args.input_root, args.frontier, args.output_root,
                          source_result=args.source_result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "SUCCEEDED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
