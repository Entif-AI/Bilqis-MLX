"""Opt-in, owned Falkor materialization and bounded Akasha readback (#90)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import uuid
from typing import Callable

from .ingestion import _bytes, _execute, _file_sha, _safe_environment, _write_atomic


RESULT_SCHEMA = "bilqis.ithkuil.graph-stage-result/v1"
GRAPH_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,127}$")
OWNER_NAME = re.compile(r"^[A-Za-z0-9_-]{3,128}$")
HEX64 = re.compile(r"^[a-f0-9]{64}$")
MODULES = {
    "reset_plan": "lib.ithkuil.src.skos.falkor_reset",
    "materialize_receipt": "lib.ithkuil.src.skos.falkor_receipt",
    "akasha_readback": "lib.ithkuil.src.skos.akasha_skos",
}
FINGERPRINTS = (
    "lib/ithkuil/ingestion_contract.json",
    "lib/ithkuil/src/ingestion_graph.py",
    "lib/ithkuil/src/ingestion.py",
    "lib/ithkuil/src/skos/falkor_reset.py",
    "lib/ithkuil/src/skos/falkor_receipt.py",
    "lib/ithkuil/src/skos/falkor_import.py",
    "lib/ithkuil/src/skos/falkor_projection.py",
    "lib/ithkuil/src/skos/falkor_lookup.py",
    "lib/ithkuil/src/skos/falkor_smoke.py",
    "lib/ithkuil/src/skos/akasha_skos.py",
    "lib/ithkuil/src/skos/materialization_receipt.schema.json",
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("INPUT_NOT_REGULAR_FILE:" + str(path))
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON_OBJECT_REQUIRED:" + str(path))
    return value


def _semantic_input(value: dict | str | Path) -> tuple[dict, str, Path | None]:
    if isinstance(value, dict):
        return value, _sha(_bytes(value)), None
    path = Path(value).expanduser().absolute()
    if path.is_symlink() or not path.is_file():
        raise ValueError("SEMANTIC_RESULT_MISSING_OR_UNSAFE")
    payload = path.read_bytes()
    result = json.loads(payload.decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError("SEMANTIC_RESULT_OBJECT_REQUIRED")
    return result, _sha(payload), path.resolve()


def _bundle_identity(full: dict) -> tuple[Path, dict, dict]:
    root_value = full.get("path")
    if not isinstance(root_value, str) or not root_value:
        raise ValueError("FULL_CONFORMANCE_BUNDLE_PATH_MISSING")
    raw_root = Path(root_value).expanduser().absolute()
    if raw_root.is_symlink():
        raise ValueError("FULL_CONFORMANCE_BUNDLE_UNSAFE")
    root = raw_root.resolve()
    if not root.is_dir():
        raise ValueError("FULL_CONFORMANCE_BUNDLE_UNSAFE")
    manifest_path = root / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("FULL_CONFORMANCE_MANIFEST_UNSAFE")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    if not isinstance(manifest, dict) or not HEX64.fullmatch(_sha(manifest_bytes)):
        raise ValueError("FULL_CONFORMANCE_MANIFEST_INVALID")
    bundle_id = _sha(manifest_bytes)
    if (full.get("bundle_id") != bundle_id
            or full.get("manifest", {}).get("sha256") != bundle_id
            or Path(full.get("manifest", {}).get("path", "")).resolve() != manifest_path.resolve()):
        raise ValueError("FULL_CONFORMANCE_MANIFEST_IDENTITY_MISMATCH")
    if set(p.name for p in root.iterdir()) != {*manifest.keys(), "manifest.json"}:
        raise ValueError("FULL_CONFORMANCE_FILE_SET_MISMATCH")
    hashes = {"manifest.json": bundle_id}
    for name, expected in sorted(manifest.items()):
        relative = PurePosixPath(name)
        if (not isinstance(name, str) or relative.is_absolute() or ".." in relative.parts
                or len(relative.parts) != 1 or not isinstance(expected, str)
                or not HEX64.fullmatch(expected)):
            raise ValueError("FULL_CONFORMANCE_MANIFEST_ENTRY_INVALID")
        path = root / name
        observed = _file_sha(path)
        if observed != expected:
            raise ValueError("FULL_CONFORMANCE_DIGEST_MISMATCH:" + name)
        hashes[name] = observed
    return root, {"bundle_id": bundle_id, "manifest": dict(sorted(manifest.items()))}, hashes


def _validate_semantic(repo: Path, semantic: dict, result_sha: str,
                       suite: Path) -> tuple[dict, dict, dict]:
    contract = _read_json(repo / "lib" / "ithkuil" / "ingestion_contract.json")
    materialize = contract.get("stages", {}).get("materialize", {})
    readback = contract.get("stages", {}).get("readback", {})
    if (contract.get("schema") != "bilqis.ithkuil.ingestion-contract/v1"
            or contract.get("governance", {}).get("authority_mode") != "public_only"
            or materialize.get("write_class") != "graph_write"
            or materialize.get("modules") != [MODULES["materialize_receipt"]]
            or materialize.get("explicit_graph_authorization") is not True
            or readback.get("write_class") != "read_only"
            or readback.get("modules") != [MODULES["akasha_readback"]]):
        raise ValueError("GRAPH_CONTRACT_AUTHORITY_OR_MODULE_MAP_INVALID")
    if (semantic.get("schema") != "bilqis.ithkuil.semantic-stage-result/v1"
            or semantic.get("status") != "SUCCEEDED"):
        raise ValueError("SEMANTIC_STAGE_NOT_SUCCESSFUL")
    if semantic.get("graph_eligibility", {}).get("eligible") is not True:
        raise ValueError("SEMANTIC_GRAPH_ELIGIBILITY_FALSE")
    full = semantic.get("artifacts", {}).get("full_conformance_bundle")
    if not isinstance(full, dict) or full.get("status") != "complete":
        raise ValueError("FULL_CONFORMANCE_BUNDLE_NOT_COMPLETE")
    if full.get("coverage_status") not in {"complete", "partial"}:
        raise ValueError("FULL_CONFORMANCE_COVERAGE_STATUS_INVALID")
    root, manifest, bundle_hashes = _bundle_identity(full)
    conformance = _read_json(root / "conformance.json")
    from .skos.conformance import GATES

    if (conformance.get("status") != "complete"
            or conformance.get("coverage_status") != full.get("coverage_status")
            or tuple(item.get("gate") for item in conformance.get("gates", [])) != GATES
            or any(item.get("status") != "passed" for item in conformance["gates"])
            or full.get("gates") != conformance["gates"]):
        raise ValueError("FULL_CONFORMANCE_GATES_NOT_PASSED")
    required_files = {"canonical.nt", "comparison.nt", "coverage.json", "source-rows.json",
                      "conformance.json", "admitted-mappings.nt",
                      *(f"gate-{gate}.json" for gate in GATES)}
    if set(manifest["manifest"]) != required_files:
        raise ValueError("FULL_CONFORMANCE_ARTIFACT_SET_INVALID")
    coverage = _read_json(root / "coverage.json")
    if (coverage.get("build_status") != full.get("coverage_status")
            or coverage.get("canonical_rdf", {}).get("triple_count")
            != full.get("canonical", {}).get("triple_count")):
        raise ValueError("FULL_CONFORMANCE_COVERAGE_IDENTITY_MISMATCH")
    conformance_meta = full.get("conformance", {})
    if (conformance_meta.get("path") != str(root / "conformance.json")
            or conformance_meta.get("sha256") != _file_sha(root / "conformance.json")
            or conformance_meta.get("status") != "complete"):
        raise ValueError("FULL_CONFORMANCE_REPORT_IDENTITY_MISMATCH")
    coverage_meta = full.get("coverage", {})
    if (coverage_meta.get("path") != str(root / "coverage.json")
            or coverage_meta.get("sha256") != _file_sha(root / "coverage.json")
            or coverage_meta.get("status") != full.get("coverage_status")):
        raise ValueError("FULL_COVERAGE_ARTIFACT_IDENTITY_MISMATCH")
    gate_refs = full.get("gate_artifacts", {})
    if set(gate_refs) != set(GATES):
        raise ValueError("FULL_GATE_ARTIFACT_SET_INVALID")
    for gate in GATES:
        ref = gate_refs[gate]
        gate_path = root / f"gate-{gate}.json"
        if (ref.get("path") != str(gate_path) or ref.get("sha256") != _file_sha(gate_path)
                or _read_json(gate_path) != next(item for item in conformance["gates"]
                                                if item.get("gate") == gate)):
            raise ValueError("FULL_GATE_ARTIFACT_IDENTITY_MISMATCH:" + gate)
    canonical = root / "canonical.nt"
    canonical_sha = bundle_hashes.get("canonical.nt")
    canonical_meta = full.get("canonical", {})
    if (canonical_meta.get("path") != str(canonical)
            or canonical_meta.get("sha256") != canonical_sha
            or conformance.get("canonical_sha256") != canonical_sha):
        raise ValueError("FULL_CANONICAL_IDENTITY_MISMATCH")
    # Canonical artifact owner recomputes all four gates from the immutable evidence.
    from .skos.falkor_import import load_conformant_bundle

    projection = load_conformant_bundle(root)
    if projection["canonical_sha256"] != canonical_sha:
        raise ValueError("FULL_CANONICAL_READBACK_MISMATCH")
    suite_sha = _file_sha(suite)
    code = {}
    for relative in FINGERPRINTS:
        path = repo / relative
        code[relative] = _file_sha(path)
    identity = {
        "semantic_result_sha256": result_sha,
        "semantic_run_identity": semantic.get("run_identity"),
        "full_conformance_bundle_id": manifest["bundle_id"],
        "full_conformance_status": full["status"],
        "coverage_status": full["coverage_status"],
        "canonical_rdf_sha256": canonical_sha,
        "canonical_triple_count": canonical_meta.get("triple_count"),
        "suite_sha256": suite_sha,
        "core_canonical_sha256": semantic.get("artifacts", {}).get(
            "core_generation_bundle", {}).get("canonical", {}).get("sha256"),
        "owner_implementation_sha256": code,
    }
    snapshot = {"bundle": bundle_hashes, "suite": suite_sha, "code": code}
    return identity, snapshot, {"root": root, "full": full, "manifest": manifest}


def _verify_snapshot(repo: Path, detail: dict, snapshot: dict, suite: Path) -> None:
    root = detail["root"]
    current = {"manifest.json": _file_sha(root / "manifest.json")}
    for name in detail["manifest"]["manifest"]:
        current[name] = _file_sha(root / name)
    if current != snapshot["bundle"] or _file_sha(suite) != snapshot["suite"]:
        raise ValueError("GRAPH_INPUT_IDENTITY_CHANGED")
    semantic_result = snapshot.get("semantic_result", {})
    if semantic_result.get("path") and _file_sha(Path(semantic_result["path"])) != semantic_result["sha256"]:
        raise ValueError("SEMANTIC_RESULT_IDENTITY_CHANGED")
    code = {relative: _file_sha(repo / relative) for relative in FINGERPRINTS}
    if code != snapshot["code"]:
        raise ValueError("GRAPH_OWNER_IMPLEMENTATION_CHANGED")


def _safe_env() -> dict[str, str]:
    env = _safe_environment()
    for name in ("BILQIS_FALKOR_USERNAME", "BILQIS_FALKOR_PASSWORD"):
        if name in os.environ:
            env[name] = os.environ[name]
    return env


def _unavailable(error: Exception) -> bool:
    if isinstance(error, ModuleNotFoundError):
        return error.name in {"falkordb", "redis"}
    if type(error).__name__ in {"ConnectionError", "TimeoutError", "ConnectionRefusedError", "ConnectTimeout"}:
        return True
    return isinstance(error, OSError) and getattr(error, "errno", None) in {61, 111, 110, 113}


def _check_output(repo: Path, output_root: str | Path | None, run_id: str,
                  protected_inputs: list[Path]) -> Path:
    raw = (Path(output_root).expanduser().absolute() if output_root is not None else
           repo / ".local" / "ingestion" / "graph" / run_id)
    if raw.is_symlink():
        raise ValueError("GRAPH_OUTPUT_SYMLINK_FORBIDDEN")
    target = raw.resolve()
    protected = [repo / ".git", repo / "runs", repo / "students",
                 repo / "lib" / "ithkuil" / "src", repo / "lib" / "ithkuil" / "_data",
                 repo / "lib" / "ithkuil" / "_raw"]
    for path in protected + protected_inputs:
        candidate = path.resolve()
        if target == candidate or target.is_relative_to(candidate) or candidate.is_relative_to(target):
            raise ValueError("GRAPH_OUTPUT_PROTECTED_OR_INPUT_OVERLAP")
    if target.exists():
        raise ValueError("GRAPH_OUTPUT_MUST_BE_NEW")
    return target


def _record_result(record: dict) -> dict:
    return {
        "schema": RESULT_SCHEMA,
        "run_identity": record["run_identity"],
        "status": record["status"],
        "semantic_status": record.get("semantic_status"),
        "target": record.get("target"),
        "input": record.get("input", {}),
        "preflight": record.get("preflight"),
        "commands": record.get("commands", []),
        "artifacts": record.get("artifacts", {}),
        "canonical_rdf_unchanged": record.get("canonical_rdf_unchanged"),
        "failed_stage": record.get("failed_stage"),
        "error_code": record.get("error_code"),
        "run_record": record.get("run_record"),
    }


def _finish(record_path: Path, record: dict, status: str, *, stage: str | None = None,
            code: str | None = None) -> dict:
    record.update({"status": status, "active_stage": None,
                   "failed_stage": stage, "error_code": code})
    _write_atomic(record_path, _bytes(record))
    return _record_result(record)


def _json_log(command: dict) -> dict | None:
    try:
        return json.loads(Path(command["stdout_log_ref"]).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None


def _raw_log(command: dict) -> bytes:
    try:
        return Path(command["stdout_log_ref"]).read_bytes()
    except OSError:
        return b""


def _run_command(record: dict, record_path: Path, repo: Path, python: Path,
                 stage: str, args: list[str], runner: Callable | None) -> dict:
    record.update({"status": "RUNNING", "active_stage": stage})
    _write_atomic(record_path, _bytes(record))
    command = _execute([str(python), "-B", "-m", MODULES[stage], *args], repo,
                       _safe_env(), record_path.parent / "logs", len(record["commands"]) + 1, runner)
    command["stage"] = stage
    record["commands"].append(command)
    record["active_stage"] = stage
    _write_atomic(record_path, _bytes(record))
    return command


def run_graph(repo_root: str | Path, python_executable: str | Path,
              semantic_result: dict | str | Path, output_root: str | Path | None = None, *,
              enabled: bool = False, required: bool = False, graph: str | None = None,
              owner: str | None = None, host: str | None = None, port: int | None = None,
              suite: str | Path | None = None, notation: str | None = None,
              datatype: str | None = None, expected_iri: str | None = None,
              command_runner: Callable | None = None) -> dict:
    """Optionally materialize one exact semantic bundle, then prove one read.

    A skipped optional graph outcome never changes the independent semantic result.
    No graph is reset, deleted, inferred, or selected by fallback.
    """
    semantic_hint = semantic_result.get("status") if isinstance(semantic_result, dict) else None
    if not enabled and isinstance(semantic_result, (str, Path)):
        try:
            semantic_hint = _semantic_input(semantic_result)[0].get("status")
        except Exception:
            pass
    if not enabled:
        return {"schema": RESULT_SCHEMA, "run_identity": "", "status":
                "BLOCKED" if required else "DISABLED", "semantic_status": semantic_hint,
                "target": None, "commands": [], "artifacts": {},
                "canonical_rdf_unchanged": None, "failed_stage": None,
                "error_code": "GRAPH_REQUIRED_BUT_DISABLED" if required else None,
                "run_record": None}

    run_id = uuid.uuid4().hex
    try:
        repo = Path(repo_root).expanduser().resolve()
        if repo != Path(__file__).resolve().parents[3]:
            raise ValueError("REPOSITORY_MODULE_MISMATCH:invoke-the-selected-checkout-module")
        python = Path(python_executable).expanduser().absolute()
        if not python.is_file() or not os.access(python, os.X_OK):
            raise ValueError("PYTHON_EXECUTABLE_INVALID")
        if (not isinstance(graph, str) or not GRAPH_NAME.fullmatch(graph) or graph.lower() == "default"
                or not isinstance(owner, str) or not OWNER_NAME.fullmatch(owner)
                or not isinstance(host, str) or not host.strip()
                or not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535
                or not isinstance(notation, str) or not notation
                or not isinstance(datatype, str) or not datatype
                or not isinstance(expected_iri, str) or not expected_iri):
            raise ValueError("EXPLICIT_GRAPH_TARGET_REQUIRED")
        suite_path = Path(suite).expanduser().absolute() if suite is not None else None
        if suite_path is None or suite_path.is_symlink() or not suite_path.is_file():
            raise ValueError("EXPLICIT_SMOKE_SUITE_REQUIRED")
        semantic, semantic_sha, semantic_path = _semantic_input(semantic_result)
        artifact_inputs = semantic.get("artifacts", {})
        full_input = artifact_inputs.get("full_conformance_bundle", {}).get("path")
        core_input = artifact_inputs.get("core_generation_bundle", {}).get("path")
        input_identity = semantic.get("input_identity", {})
        protected = [Path(item) for item in (full_input, core_input, input_identity.get("csv_root"),
                                             input_identity.get("frontier_path"))
                     if isinstance(item, str) and item]
        protected.extend(path for path in (suite_path, semantic_path) if path is not None)
        output = _check_output(repo, output_root, run_id, protected)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.mkdir(mode=0o700, exist_ok=False)
    except Exception as exc:
        return {"schema": RESULT_SCHEMA, "run_identity": run_id, "status": "BLOCKED",
                "semantic_status": semantic_hint, "target": {"graph": graph, "owner": owner,
                "host": host, "port": port}, "commands": [], "artifacts": {},
                "canonical_rdf_unchanged": None, "failed_stage": "inspect",
                "error_code": str(exc), "run_record": None}

    record_path = output / "run.json"
    record = {
        "schema": "bilqis.ithkuil.graph-run/v1", "run_identity": run_id,
        "status": "READY", "active_stage": "inspect", "attempt": 1,
        "semantic_status": semantic_hint,
        "target": {"graph": graph, "owner": owner, "host": host, "port": port},
        "commands": [], "artifacts": {}, "preflight": None,
        "canonical_rdf_unchanged": None, "failed_stage": None, "error_code": None,
        "run_record": str(record_path), "output_root": str(output),
    }
    _write_atomic(record_path, _bytes(record))
    try:
        record["semantic_status"] = semantic.get("status")
        identity, snapshot, detail = _validate_semantic(repo, semantic, semantic_sha, suite_path)
        snapshot["semantic_result"] = {"path": str(semantic_path) if semantic_path else None,
                                        "sha256": semantic_sha}
        record["input"] = identity
        record["canonical_rdf_unchanged"] = None
        _write_atomic(record_path, _bytes(record))
    except ModuleNotFoundError as exc:
        if _unavailable(exc):
            status = "FAILED" if required else "SKIPPED_UNAVAILABLE"
            record.update({"semantic_status": semantic_hint, "error_code": "GRAPH_RUNTIME_DEPENDENCY_UNAVAILABLE"})
            return _finish(record_path, record, status, stage="semantic_bundle_validation",
                           code=record["error_code"])
        return _finish(record_path, record, "BLOCKED", stage="semantic_bundle_validation", code=type(exc).__name__)
    except Exception as exc:
        return _finish(record_path, record, "BLOCKED", stage="semantic_bundle_validation", code=str(exc))

    if semantic.get("status") != "SUCCEEDED":
        return _finish(record_path, record, "BLOCKED", stage="semantic_preflight", code="SEMANTIC_STAGE_NOT_SUCCESSFUL")

    try:
        from .skos.falkor_import import connect

        # Read-only endpoint/graph inventory probe. It never chooses another graph.
        db = connect(host, port)
        graph_exists = graph in db.list_graphs()
        record["preflight"] = {"runtime_available": True, "graph_exists": graph_exists,
                               "current_canonical_sha256": None, "reset_required": False,
                               "reset_plan": None, "reset_executed": False}
        _write_atomic(record_path, _bytes(record))
    except Exception as exc:
        if _unavailable(exc):
            status = "FAILED" if required else "SKIPPED_UNAVAILABLE"
            return _finish(record_path, record, status, stage="runtime_preflight",
                           code="GRAPH_RUNTIME_UNAVAILABLE" if not required else "GRAPH_RUNTIME_REQUIRED_UNAVAILABLE")
        return _finish(record_path, record, "FAILED", stage="runtime_preflight",
                       code="GRAPH_RUNTIME_PREFLIGHT_FAILED:" + type(exc).__name__)

    if graph_exists:
        try:
            _verify_snapshot(repo, detail, snapshot, suite_path)
        except Exception as exc:
            return _finish(record_path, record, "BLOCKED", stage="pre_reset_fence", code=str(exc))
        reset = _run_command(record, record_path, repo, python, "reset_plan", [
            "--graph", graph, "--owner", owner, "--host", host, "--port", str(port),
        ], command_runner)
        plan = _json_log(reset)
        record["preflight"]["reset_plan"] = plan
        if isinstance(plan, dict) and plan.get("schema") == "bilqis.skos.reset-plan/v1":
            reset_required = (plan.get("state") != "empty"
                              and plan.get("canonical_sha256") != identity["canonical_rdf_sha256"])
            record["preflight"]["current_canonical_sha256"] = plan.get("canonical_sha256")
            record["preflight"]["reset_required"] = reset_required
        try:
            _verify_snapshot(repo, detail, snapshot, suite_path)
            record["canonical_rdf_unchanged"] = True
        except Exception as exc:
            return _finish(record_path, record, "BLOCKED", stage="post_reset_plan_fence", code=str(exc))
        _write_atomic(record_path, _bytes(record))
        if reset["exit_code"] != 0 or not isinstance(plan, dict):
            return _finish(record_path, record, "BLOCKED", stage="reset_plan",
                           code=(plan or {}).get("code", "RESET_PLAN_FAILED"))
        if plan.get("status") == "refused":
            return _finish(record_path, record, "BLOCKED", stage="reset_plan",
                           code=plan.get("code", "RESET_PLAN_REFUSED"))
        if plan.get("graph") != graph or plan.get("owner") != owner:
            return _finish(record_path, record, "BLOCKED", stage="reset_plan", code="RESET_PLAN_TARGET_MISMATCH")
        if plan.get("blockers"):
            return _finish(record_path, record, "BLOCKED", stage="reset_plan", code="FOREIGN_BOUNDARY")
        if plan.get("state") not in {"empty", "incomplete", "complete"}:
            return _finish(record_path, record, "BLOCKED", stage="reset_plan", code="RESET_PLAN_STATE_INVALID")
        if plan.get("state") == "empty":
            if plan.get("canonical_sha256") not in {"", None}:
                return _finish(record_path, record, "BLOCKED", stage="reset_plan", code="RESET_PLAN_EMPTY_DIGEST_INVALID")
        elif plan.get("canonical_sha256") != identity["canonical_rdf_sha256"]:
            return _finish(record_path, record, "BLOCKED", stage="reset_plan", code="RESET_REQUIRED")

    try:
        _verify_snapshot(repo, detail, snapshot, suite_path)
    except Exception as exc:
        return _finish(record_path, record, "BLOCKED", stage="pre_materialize_fence", code=str(exc))
    receipt_command = _run_command(record, record_path, repo, python, "materialize_receipt", [
        "--bundle", str(detail["root"]), "--suite", str(suite_path), "--graph", graph,
        "--owner", owner, "--host", host, "--port", str(port),
    ], command_runner)
    receipt = _json_log(receipt_command)
    receipt_path = output / "materialization_receipt.json"
    if receipt is not None:
        _write_atomic(receipt_path, _raw_log(receipt_command))
    try:
        _verify_snapshot(repo, detail, snapshot, suite_path)
        record["canonical_rdf_unchanged"] = True
    except Exception as exc:
        record["canonical_rdf_unchanged"] = False
        record["diagnostics"] = {"materialization_receipt": receipt}
        return _finish(record_path, record, "FAILED", stage="post_materialization_fence", code=str(exc))
    if receipt_command["exit_code"] != 0 or not isinstance(receipt, dict):
        record["diagnostics"] = {"materialization_receipt": receipt}
        return _finish(record_path, record, "FAILED", stage="materialize_receipt",
                       code=(receipt or {}).get("reason", "MATERIALIZATION_FAILED"))
    try:
        from .skos.falkor_receipt import validate_receipt

        validate_receipt(receipt)
        if (receipt.get("status") != "complete" or receipt.get("graph") != graph
                or receipt.get("owner") != owner
                or receipt.get("canonical_rdf_sha256") != identity["canonical_rdf_sha256"]
                or receipt.get("coverage_status") != identity["coverage_status"]
                or receipt.get("smoke_suite", {}).get("suite_sha256") != identity["suite_sha256"]
                or receipt.get("smoke_suite", {}).get("passed") is not True):
            raise ValueError("MATERIALIZATION_RECEIPT_BINDING_MISMATCH")
        _verify_snapshot(repo, detail, snapshot, suite_path)
        receipt_sha = _file_sha(receipt_path)
        record["artifacts"]["materialization_receipt"] = {
            "path": str(receipt_path), "sha256": receipt_sha, "receipt": receipt,
        }
        _write_atomic(record_path, _bytes(record))
    except Exception as exc:
        return _finish(record_path, record, "FAILED", stage="materialization_receipt_validation", code=str(exc))

    readback_command = _run_command(record, record_path, repo, python, "akasha_readback", [
        "--graph", graph, "--owner", owner, "--receipt", str(receipt_path),
        "--bundle", str(detail["root"]), "--suite", str(suite_path), "--notation", notation,
        "--datatype", datatype, "--expected-iri", expected_iri, "--host", host, "--port", str(port),
    ], command_runner)
    readback = _json_log(readback_command)
    readback_path = output / "akasha_readback.json"
    if readback is not None:
        _write_atomic(readback_path, _raw_log(readback_command))
    try:
        _verify_snapshot(repo, detail, snapshot, suite_path)
        record["canonical_rdf_unchanged"] = True
        if readback_command["exit_code"] != 0 or not isinstance(readback, dict):
            raise ValueError((readback or {}).get("code", "AKASHA_READBACK_FAILED"))
        if (readback.get("schema") != "bilqis.akasha.skos-read/v1"
                or readback.get("graph") != graph or readback.get("owner") != owner
                or readback.get("canonical_rdf_sha256") != identity["canonical_rdf_sha256"]
                or readback.get("concept_iri") != expected_iri
                or readback.get("notation") != {"lexical": notation, "datatype": datatype}
                or expected_iri not in readback.get("candidate_iris", [])):
            raise ValueError("AKASHA_READBACK_BINDING_MISMATCH")
        _verify_snapshot(repo, detail, snapshot, suite_path)
        if _file_sha(receipt_path) != receipt_sha:
            raise ValueError("MATERIALIZATION_RECEIPT_CHANGED_DURING_READBACK")
        readback_sha = _file_sha(readback_path)
        record["artifacts"]["readback"] = {"path": str(readback_path), "sha256": readback_sha,
                                            "result": readback}
        record["canonical_rdf_unchanged"] = _file_sha(detail["root"] / "canonical.nt") == identity["canonical_rdf_sha256"]
        if not record["canonical_rdf_unchanged"]:
            raise ValueError("CANONICAL_RDF_CHANGED_DURING_GRAPH_STAGE")
        return _finish(record_path, record, "SUCCEEDED")
    except Exception as exc:
        record["diagnostics"] = {"readback": readback}
        return _finish(record_path, record, "FAILED", stage="akasha_readback", code=str(exc))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--semantic-result", type=Path, required=True)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--enable-graph", action="store_true")
    parser.add_argument("--required", action="store_true")
    parser.add_argument("--graph")
    parser.add_argument("--owner")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--suite", type=Path)
    parser.add_argument("--notation")
    parser.add_argument("--datatype")
    parser.add_argument("--expected-iri")
    args = parser.parse_args(argv)
    result = run_graph(args.repo, args.python, args.semantic_result, args.output_root,
                       enabled=args.enable_graph, required=args.required, graph=args.graph,
                       owner=args.owner, host=args.host, port=args.port, suite=args.suite,
                       notation=args.notation, datatype=args.datatype, expected_iri=args.expected_iri)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] in {"SUCCEEDED", "DISABLED", "SKIPPED_UNAVAILABLE"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
