"""Stage, validate, and publish pinned source-only Ithkuil ingestion."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable


VERSION = "1.0.0"
HEX = re.compile(r"^[0-9a-f]{64}$")
AFFIX_ID = "NI-AFFIX-PDF"


def _bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _file_sha(path: Path) -> str | None:
    path = Path(path)
    return _sha(path.read_bytes()) if path.is_file() and not path.is_symlink() else None


def _write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if path.read_bytes() != payload:
            raise OSError(f"readback mismatch: {path}")
    finally:
        if temporary.exists():
            temporary.unlink()


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _source_inputs(ithkuil: Path) -> tuple[dict[str, str], str]:
    """Verify manifest and every pinned artifact before any source command runs."""
    data = ithkuil / "_data" / "csv"
    manifest_path = data / "sources" / "source_manifest.csv"
    rows = _csv_rows(manifest_path)
    ids = [row.get("source_id", "") for row in rows]
    if len(rows) != 18 or not all(ids) or len(set(ids)) != len(ids):
        raise ValueError("SOURCE_MANIFEST_IDENTITY_INVALID")
    inputs = {"lib/ithkuil/_data/csv/sources/source_manifest.csv": _file_sha(manifest_path)}
    raw_names: set[str] = set()
    for row in rows:
        name, pinned = row.get("local_name", ""), row.get("sha256", "")
        if not name or Path(name).name != name or not HEX.fullmatch(pinned):
            raise ValueError("SOURCE_MANIFEST_PIN_INVALID")
        if name in raw_names:
            raise ValueError("SOURCE_MANIFEST_LOCAL_NAME_DUPLICATE")
        raw_names.add(name)
        path = ithkuil / "_raw" / name
        observed = _file_sha(path)
        if observed != pinned:
            raise ValueError(f"SOURCE_PIN_MISMATCH:{row['source_id']}:{name}")
        inputs[f"lib/ithkuil/_raw/{name}"] = observed

    pins_path = ithkuil / "src" / "lexicon_frontier_pins.json"
    pins = json.loads(pins_path.read_text(encoding="utf-8"))
    split = pins.get("source_pdfs", {})
    if set(split) != {str(number) for number in range(8)}:
        raise ValueError("SPLIT_PDF_INVENTORY_INVALID")
    for number, pin in sorted(split.items(), key=lambda item: int(item[0])):
        name, pinned = pin.get("filename", ""), pin.get("sha256", "")
        if not name or Path(name).name != name or not HEX.fullmatch(pinned):
            raise ValueError("SPLIT_PDF_PIN_INVALID")
        path = ithkuil / "_data" / "pdf" / name
        observed = _file_sha(path)
        if observed != pinned:
            raise ValueError(f"SPLIT_PDF_PIN_MISMATCH:{number}:{name}")
        inputs[f"lib/ithkuil/_data/pdf/{name}"] = observed
    return dict(sorted(inputs.items())), _file_sha(manifest_path) or ""


def _publishable_files(ithkuil: Path) -> dict[str, bytes]:
    data = ithkuil / "_data" / "csv"
    found: dict[str, bytes] = {}
    for path in sorted(data.glob("*.csv")):
        if path.is_symlink() or not path.is_file():
            raise ValueError("PUBLISH_ARTIFACT_UNSAFE:" + path.name)
        found[path.relative_to(ithkuil).as_posix()] = path.read_bytes()
    for relative in (
        "_data/csv/sources/affix_frontier_manifest.json",
        "_data/csv/sources/affix_frontier_accounting.json",
        "_data/csv/sources/lexicon_frontier_manifest.json",
        "_data/csv/sources/extraction_frontier.json",
    ):
        path = ithkuil / relative
        if path.exists():
            if path.is_symlink() or not path.is_file():
                raise ValueError("PUBLISH_ARTIFACT_UNSAFE:" + relative)
            found[relative] = path.read_bytes()
    accounting = ithkuil / "_data" / "csv" / "sources" / "lexicon_frontier"
    if accounting.exists():
        for path in sorted(accounting.glob("chapter-*-accounting.json")):
            if path.is_symlink() or not path.is_file():
                raise ValueError("PUBLISH_ARTIFACT_UNSAFE:" + str(path))
            found[path.relative_to(ithkuil).as_posix()] = path.read_bytes()
    summary = ithkuil / "EXTRACTION_FRONTIER.md"
    if summary.is_file() and not summary.is_symlink():
        found[summary.relative_to(ithkuil).as_posix()] = summary.read_bytes()
    # The aggregate machine receipt is the publication manifest and must be last.
    manifest = "_data/csv/sources/extraction_frontier.json"
    return {name: payload for name, payload in found.items() if name != manifest} | (
        {manifest: found[manifest]} if manifest in found else {}
    )


def _file_hashes(files: dict[str, bytes]) -> dict[str, str]:
    return {name: _sha(payload) for name, payload in sorted(files.items())}


def _output_identity(ithkuil: Path) -> dict[str, str | None]:
    identity: dict[str, str | None] = _file_hashes(_publishable_files(ithkuil))
    expected = {
        "_data/csv/sources/affix_frontier_manifest.json",
        "_data/csv/sources/affix_frontier_accounting.json",
        "_data/csv/sources/lexicon_frontier_manifest.json",
        "_data/csv/sources/extraction_frontier.json",
        "EXTRACTION_FRONTIER.md",
    }
    expected.update(f"_data/csv/sources/lexicon_frontier/chapter-{n}-accounting.json" for n in range(8))
    for name in expected:
        identity.setdefault(name, None)
    return dict(sorted(identity.items()))


def _dependency_identity(ithkuil: Path, source_inputs: dict[str, str], selection: str,
                         python_executable: Path) -> dict:
    code = {}
    for path in sorted((ithkuil / "src").glob("*.py")):
        code[path.relative_to(ithkuil).as_posix()] = _file_sha(path)
    contracts = {
        "ingestion_contract.json": _file_sha(ithkuil / "ingestion_contract.json"),
        "lexicon_frontier_pins.json": _file_sha(ithkuil / "src" / "lexicon_frontier_pins.json"),
    }
    return {
        "selection": selection,
        "python_executable": str(python_executable),
        "contract_and_pins": contracts,
        "source_code": code,
        "pinned_inputs": source_inputs,
    }


def _load_contract(ithkuil: Path) -> dict:
    contract = json.loads((ithkuil / "ingestion_contract.json").read_text(encoding="utf-8"))
    if (contract.get("schema") != "bilqis.ithkuil.ingestion-contract/v1"
            or contract.get("governance", {}).get("authority_mode") != "public_only"
            or contract.get("stages", {}).get("source", {}).get("write_class") != "repo_write"):
        raise ValueError("INGESTION_CONTRACT_AUTHORITY_INVALID")
    modules = contract["stages"]["source"].get("modules", [])
    names = [module.rsplit(".", 1)[-1] for module in modules]
    if names != ["build_structure", "build_morphology", "build_lexicon_chapters",
                 "validate_dataset", "source_frontier"]:
        raise ValueError("INGESTION_CONTRACT_SOURCE_STAGE_DRIFT")
    return contract


def _result(*, run_identity: str, status: str, source_manifest_sha256: str,
            commands: list[dict], artifacts: dict | None = None, frontier: dict | None = None,
            validator: dict | None = None, debt: dict | None = None, failed_stage: str | None = None,
            error_code: str | None = None, run_record: Path | None = None) -> dict:
    return {
        "schema": "bilqis.ithkuil.source-stage-result/v1",
        "run_identity": run_identity,
        "status": status,
        "source_manifest_sha256": source_manifest_sha256,
        "commands": commands,
        "artifacts": artifacts or {"published": False},
        "frontier": frontier,
        "validator": validator or {"passed": False},
        "debt": debt or {},
        "failed_stage": failed_stage,
        "error_code": error_code,
        "run_record": str(run_record) if run_record else None,
    }


def _safe_environment() -> dict[str, str]:
    allowed = ("PATH", "HOME", "TMPDIR", "TEMP", "TMP", "LANG", "LC_ALL", "SYSTEMROOT")
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env.update({"PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1", "PYTHONUTF8": "1"})
    return env


def _commands(selection: str, python: Path, stage_root: Path, ithkuil: Path,
              contract: dict) -> list[tuple[str, list[str]]]:
    base = [str(python), "-B", "-m"]
    modules = {module.rsplit(".", 1)[-1]: module for module in contract["stages"]["source"]["modules"]}
    commands = [("build_structure", [*base, modules["build_structure"], "--admit-affix"])]
    if selection == "all":
        commands.append(("build_morphology", [*base, modules["build_morphology"]]))
        commands.append(("build_lexicon_chapters_1_2", [*base, modules["build_lexicon_chapters"]]))
        canonical = next(row["local_name"] for row in _csv_rows(
            ithkuil / "_data" / "csv" / "sources" / "source_manifest.csv")
            if row["source_id"] == "NI-LEXICON-CURRICULUM")
        canonical_pdf = str(ithkuil / "_raw" / canonical)
        for chapter in range(3, 8):
            commands.append((f"admit_lexicon_chapter_{chapter}", [
                *base, modules["build_lexicon_chapters"], "--admit-chapter", str(chapter),
                "--canonical-pdf", canonical_pdf,
            ]))
    commands.extend([
        ("validate_dataset", [*base, modules["validate_dataset"]]),
        ("source_frontier", [*base, modules["source_frontier"]]),
    ])
    return commands


def _execute(argv: list[str], cwd: Path, env: dict[str, str], log_dir: Path,
             index: int, command_runner: Callable | None) -> dict:
    stdout_path = log_dir / f"{index:02d}.stdout.log"
    stderr_path = log_dir / f"{index:02d}.stderr.log"
    log_dir.mkdir(parents=True, exist_ok=True)
    try:
        if command_runner is None:
            completed = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=False,
                                       check=False, timeout=600)
            exit_code = completed.returncode
            stdout, stderr = completed.stdout, completed.stderr
        else:
            completed = command_runner(argv, cwd, env, 600)
            exit_code = int(completed["exit_code"])
            stdout = completed.get("stdout", "")
            stderr = completed.get("stderr", "")
        stdout_bytes = stdout if isinstance(stdout, bytes) else str(stdout).encode("utf-8")
        stderr_bytes = stderr if isinstance(stderr, bytes) else str(stderr).encode("utf-8")
        _write_atomic(stdout_path, stdout_bytes)
        _write_atomic(stderr_path, stderr_bytes)
    except Exception as exc:
        exit_code, stdout_bytes, stderr_bytes = 127, b"", str(exc).encode("utf-8")
        _write_atomic(stdout_path, stdout_bytes)
        _write_atomic(stderr_path, stderr_bytes)
    return {
        "argv": argv,
        "exit_code": exit_code,
        "stdout_log_ref": str(stdout_path),
        "stderr_log_ref": str(stderr_path),
    }


def _copy_stage(source_root: Path, stage_root: Path, source_inputs: dict[str, str]) -> Path:
    stage_root.mkdir(parents=True, exist_ok=False)
    lib_source = source_root / "lib"
    source_ithkuil = lib_source / "ithkuil"
    for parent, directories, files in os.walk(source_ithkuil):
        for name in directories + files:
            if (Path(parent) / name).is_symlink():
                raise ValueError("SOURCE_TREE_SYMLINK_UNSUPPORTED:" + str(Path(parent) / name))
    lib_stage = stage_root / "lib"
    lib_stage.mkdir()
    init = lib_source / "__init__.py"
    if init.is_file():
        shutil.copy2(init, lib_stage / "__init__.py")
    shutil.copytree(
        lib_source / "ithkuil", lib_stage / "ithkuil",
        ignore=shutil.ignore_patterns("_raw", "_private", ".local", "pdf", "__pycache__", "*.pyc"),
    )
    staged_ithkuil = lib_stage / "ithkuil"
    raw = staged_ithkuil / "_raw"
    raw.mkdir()
    for relative in source_inputs:
        path = Path(relative)
        if path.parts[:3] == ("lib", "ithkuil", "_raw"):
            name = path.name
            shutil.copy2(source_root / relative, raw / name)
    pins = json.loads((staged_ithkuil / "src" / "lexicon_frontier_pins.json").read_text(encoding="utf-8"))
    pdf_dir = staged_ithkuil / "_data" / "pdf"
    pdf_dir.mkdir(parents=True)
    for pin in pins["source_pdfs"].values():
        source = source_root / "lib" / "ithkuil" / "_data" / "pdf" / pin["filename"]
        shutil.copy2(source, pdf_dir / pin["filename"])
    for relative, expected in source_inputs.items():
        if relative.startswith("lib/ithkuil/_raw/") or relative.startswith("lib/ithkuil/_data/pdf/"):
            if _file_sha(stage_root / relative) != expected:
                raise ValueError("STAGE_INPUT_COPY_MISMATCH:" + relative)
    return staged_ithkuil


def _frontier(ithkuil: Path) -> dict:
    path = ithkuil / "_data" / "csv" / "sources" / "extraction_frontier.json"
    receipt = json.loads(path.read_text(encoding="utf-8"))
    unsigned = dict(receipt)
    received_sha = unsigned.pop("receipt_sha256", None)
    if received_sha != _sha(_bytes(unsigned)):
        raise ValueError("FRONTIER_RECEIPT_DIGEST_INVALID")
    if receipt.get("schema") != "bilqis.ithkuil.extraction-frontier/v1":
        raise ValueError("FRONTIER_RECEIPT_SCHEMA_INVALID")
    if receipt.get("reconciliation") != {
        "source_manifest_entries": 18, "split_chapter_entries": 8, "entry_count": 26,
    }:
        raise ValueError("FRONTIER_RECONCILIATION_INVALID")
    if receipt.get("claims") != {
        "full_new_ithkuil_coverage": False, "semantic_admission": False,
        "curriculum_admission": False,
    }:
        raise ValueError("FRONTIER_AUTHORITY_CLAIMS_INVALID")
    return {
        "path": str(path), "sha256": _file_sha(path), "receipt_sha256": received_sha,
        "entry_count": len(receipt["entries"]), "debt_by_reason": receipt["aggregates"]["debt"]["by_reason"],
    }


def _publish(repo_root: Path, stage_ithkuil: Path, run_dir: Path,
             original_identity: dict[str, str | None]) -> tuple[dict, str | None]:
    staged = _publishable_files(stage_ithkuil)
    final = repo_root / "lib" / "ithkuil"
    missing = [name for name, digest in original_identity.items()
               if digest is not None and name not in staged]
    if missing:
        raise RuntimeError("STAGED_OUTPUT_MISSING:" + ",".join(missing))
    changes = {name: payload for name, payload in staged.items()
               if _file_sha(final / name) != _sha(payload)}
    current = _output_identity(final)
    if current != original_identity:
        raise RuntimeError("CANONICAL_BASELINE_CHANGED_DURING_STAGE")
    backup_root = run_dir / "backup"
    backup: dict[str, dict] = {}
    for name in changes:
        path = final / name
        exists = path.is_file() and not path.is_symlink()
        backup[name] = {"exists": exists, "sha256": _file_sha(path) if exists else None}
        if exists:
            target = backup_root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            if _file_sha(target) != backup[name]["sha256"]:
                raise OSError("PUBLICATION_BACKUP_READBACK:" + name)
    manifest = "_data/csv/sources/extraction_frontier.json"
    record = {"changes": sorted(changes), "backup": backup,
              "expected": {name: _sha(payload) for name, payload in changes.items()},
              "manifest_last": manifest}
    _write_atomic(run_dir / "publication.json", _bytes(record))
    try:
        for name, payload in changes.items():
            if name == manifest:
                continue
            target = final / name
            if target.is_symlink() or (target.exists() and not target.is_file()) or \
                    _file_sha(target) != original_identity.get(name):
                raise RuntimeError("CANONICAL_ARTIFACT_CHANGED_DURING_PUBLICATION:" + name)
            _write_atomic(final / name, payload)
        if manifest in changes:
            target = final / manifest
            if target.is_symlink() or (target.exists() and not target.is_file()) or \
                    _file_sha(target) != original_identity.get(manifest):
                raise RuntimeError("CANONICAL_ARTIFACT_CHANGED_DURING_PUBLICATION:" + manifest)
            _write_atomic(final / manifest, changes[manifest])
        observed = {name: _file_sha(final / name) for name in changes}
        expected = record["expected"]
        if observed != expected:
            raise OSError("PUBLICATION_READBACK_MISMATCH")
        return {"published": bool(changes), "files": sorted(changes),
                "sha256": observed, "readback_verified": True}, None
    except Exception as exc:
        try:
            for name, item in backup.items():
                path = final / name
                observed = _file_sha(path)
                new_digest = record["expected"][name]
                old_digest = item["sha256"] if item["exists"] else None
                if observed == old_digest:
                    continue
                if observed != new_digest:
                    raise RuntimeError("ROLLBACK_REFUSES_CONCURRENT_CHANGE:" + name)
                if item["exists"]:
                    _write_atomic(path, (backup_root / name).read_bytes())
                elif path.exists():
                    path.unlink()
            restored = {name: _file_sha(final / name) for name, item in backup.items() if item["exists"]}
            expected_old = {name: item["sha256"] for name, item in backup.items() if item["exists"]}
            if restored != expected_old or any(not item["exists"] and
                                               ((final / name).exists() or (final / name).is_symlink())
                                               for name, item in backup.items()):
                raise OSError("ROLLBACK_READBACK_MISMATCH")
            return {"published": False, "rolled_back": True, "files": sorted(changes)}, str(exc)
        except Exception as rollback_error:
            return {"published": False, "reconcile_required": True,
                    "files": sorted(changes), "backup": str(backup_root)}, str(rollback_error)


def run_source(repo_root: str | Path, python_executable: str, selection: str = "affix",
               *, command_runner: Callable | None = None) -> dict:
    """Run source owners in isolated staging; publish only verified source artifacts."""
    root = Path(repo_root).expanduser().resolve()
    if selection not in {"affix", "all"}:
        return _result(run_identity="", status="BLOCKED", source_manifest_sha256="", commands=[],
                       failed_stage="inspect", error_code="SELECTION_UNSUPPORTED")
    # Do not resolve the venv shim: its location selects the venv site-packages.
    python = Path(python_executable).expanduser().absolute()
    if not python.is_file() or not os.access(python, os.X_OK):
        return _result(run_identity="", status="BLOCKED", source_manifest_sha256="", commands=[],
                       failed_stage="inspect", error_code="PYTHON_EXECUTABLE_INVALID")
    source_ithkuil = root / "lib" / "ithkuil"
    if not source_ithkuil.is_dir() or source_ithkuil.is_symlink():
        return _result(run_identity="", status="BLOCKED", source_manifest_sha256="", commands=[],
                       failed_stage="inspect", error_code="REPOSITORY_ROOT_INVALID")

    commands: list[dict] = []
    source_manifest_sha = ""
    try:
        source_inputs, source_manifest_sha = _source_inputs(source_ithkuil)
        contract = _load_contract(source_ithkuil)
        deps = _dependency_identity(source_ithkuil, source_inputs, selection, python)
    except Exception as exc:
        run_id = _sha(_bytes({"repo": str(root), "selection": selection, "error": str(exc)}))
        return _result(run_identity=run_id, status="BLOCKED", source_manifest_sha256=source_manifest_sha,
                       commands=commands, failed_stage="inspect", error_code=str(exc))

    authority_identity = _sha(_bytes(deps))
    run_id = authority_identity[:24]
    base = root / ".local" / "ingestion"
    run_dir = base / run_id
    latest = run_dir / "run.json"
    lock = base / ".writer.lock"
    base.mkdir(parents=True, exist_ok=True)
    try:
        lock.mkdir()
    except FileExistsError:
        return _result(run_identity=run_id, status="BLOCKED", source_manifest_sha256=source_manifest_sha,
                       commands=[], failed_stage="inspect", error_code="WRITER_LOCK_HELD", run_record=latest)

    try:
        locked_inputs, locked_manifest_sha = _source_inputs(source_ithkuil)
        locked_deps = _dependency_identity(source_ithkuil, locked_inputs, selection, python)
        if (locked_manifest_sha != source_manifest_sha
                or _sha(_bytes(locked_deps)) != authority_identity):
            return _result(run_identity=run_id, status="BLOCKED", source_manifest_sha256=locked_manifest_sha,
                           commands=[], failed_stage="inspect", error_code="INPUT_CHANGED_BEFORE_STAGE",
                           run_record=latest)
        # Capture the complete publish surface before staging; absent candidate outputs
        # are fenced too, so a concurrent writer cannot have its new file overwritten.
        original_identity = _output_identity(source_ithkuil)
        current_outputs = _publishable_files(source_ithkuil)
        current_hashes = _file_hashes(current_outputs)
        prior = json.loads(latest.read_text(encoding="utf-8")) if latest.is_file() else None
        if prior and prior.get("status") in {
                "READY", "RUNNING", "PUBLISHING", "RECONCILE_REQUIRED", "REVALIDATING_CACHE"}:
            # An interrupted attempt may have staged or partially published output.
            # Preserve its durable evidence and require explicit reconciliation.
            return _result(run_identity=run_id, status="RECONCILE_REQUIRED",
                           source_manifest_sha256=source_manifest_sha, commands=[],
                           failed_stage=prior.get("active_stage", "recovery"),
                           error_code="PRIOR_ATTEMPT_REQUIRES_RECONCILIATION", run_record=latest)
        if (prior and prior.get("authority_identity") == authority_identity
                and prior.get("status") in {"SUCCEEDED", "REUSED"}
                and prior.get("published_artifact_hashes") == current_hashes):
            # Cache only exact current output bytes after re-running the source validators.
            attempt_number = int(prior.get("attempt", 0)) + 1
            attempt = run_dir / f"attempt-{attempt_number:03d}"
            run_dir.mkdir(parents=True, exist_ok=True)
            record = {
                "schema": "bilqis.ithkuil.source-run/v1", "run_identity": run_id,
                "authority_identity": authority_identity, "dependency_identity": deps,
                "selection": selection, "attempt": attempt_number, "status": "REVALIDATING_CACHE",
                "source_manifest_sha256": source_manifest_sha,
                "published_artifact_hashes": current_hashes,
            }
            _write_atomic(latest, _bytes(record))
            stage_root = attempt / "stage"
            stage_ithkuil = _copy_stage(root, stage_root, source_inputs)
            logs = attempt / "logs"
            env = _safe_environment()
            for index, (name, argv) in enumerate([
                    ("validate_dataset", [str(python), "-B", "-m",
                                           contract["stages"]["source"]["modules"][3]]),
                    ("source_frontier_check", [str(python), "-B", "-m",
                                                contract["stages"]["source"]["modules"][4], "--check"]),
            ], 1):
                record.update({"status": "REVALIDATING_CACHE", "active_stage": name,
                               "commands": commands})
                _write_atomic(latest, _bytes(record))
                command = _execute(argv, stage_root, env, logs, index, command_runner)
                command["stage"] = name
                commands.append(command)
                record["commands"] = commands
                if command["exit_code"] != 0:
                    record.update({"status": "FAILED", "failed_stage": name,
                                   "error_code": "CACHE_POSTCONDITION_FAILED"})
                    _write_atomic(latest, _bytes(record))
                    return _result(run_identity=run_id, status="FAILED", source_manifest_sha256=source_manifest_sha,
                                   commands=commands, failed_stage=name, error_code="CACHE_POSTCONDITION_FAILED",
                                   run_record=latest)
                _write_atomic(latest, _bytes(record))
            fresh_inputs, fresh_manifest_sha = _source_inputs(source_ithkuil)
            fresh_deps = _dependency_identity(source_ithkuil, fresh_inputs, selection, python)
            if (fresh_manifest_sha != source_manifest_sha
                    or _sha(_bytes(fresh_deps)) != authority_identity
                    or _output_identity(source_ithkuil) != original_identity
                    or _output_identity(stage_ithkuil) != original_identity):
                record.update({"status": "FAILED", "failed_stage": "cache_postflight",
                               "error_code": "CACHE_IDENTITY_CHANGED"})
                _write_atomic(latest, _bytes(record))
                return _result(run_identity=run_id, status="FAILED", source_manifest_sha256=source_manifest_sha,
                               commands=commands, failed_stage="cache_postflight",
                               error_code="CACHE_IDENTITY_CHANGED", run_record=latest)
            frontier = _frontier(stage_ithkuil)
            frontier["path"] = str(source_ithkuil / "_data/csv/sources/extraction_frontier.json")
            result = _result(run_identity=run_id, status="REUSED", source_manifest_sha256=source_manifest_sha,
                             commands=commands, artifacts={"published": False, "reused": True,
                                                           "canonical_root": str(source_ithkuil),
                                                           "published_artifact_hashes": current_hashes,
                                                           "sha256": current_hashes}, frontier=frontier,
                             validator={"passed": True}, debt=frontier["debt_by_reason"], run_record=latest)
            record.update({**result, "authority_identity": authority_identity,
                           "published_artifact_hashes": current_hashes, "attempt": attempt_number})
            _write_atomic(latest, _bytes(record))
            return result

        attempt_number = int(prior.get("attempt", 0)) + 1 if prior else 1
        attempt = run_dir / f"attempt-{attempt_number:03d}"
        stage_root = attempt / "stage"
        run_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "schema": "bilqis.ithkuil.source-run/v1", "run_identity": run_id,
            "authority_identity": authority_identity, "dependency_identity": deps,
            "selection": selection, "attempt": attempt_number, "status": "READY",
            "source_manifest_sha256": source_manifest_sha,
        }
        _write_atomic(latest, _bytes(record))
        stage_ithkuil = _copy_stage(root, stage_root, source_inputs)
        env = _safe_environment()
        for index, (name, argv) in enumerate(_commands(selection, python, stage_root, stage_ithkuil,
                                                        contract), 1):
            record.update({"status": "RUNNING", "active_stage": name, "commands": commands})
            _write_atomic(latest, _bytes(record))
            command = _execute(argv, stage_root, env, attempt / "logs", index, command_runner)
            command["stage"] = name
            commands.append(command)
            record["commands"] = commands
            if command["exit_code"] != 0:
                record.update({"status": "FAILED", "failed_stage": name, "error_code": "SOURCE_OWNER_FAILED"})
                _write_atomic(latest, _bytes(record))
                return _result(run_identity=run_id, status="FAILED", source_manifest_sha256=source_manifest_sha,
                               commands=commands, failed_stage=name, error_code="SOURCE_OWNER_FAILED",
                               run_record=latest)
        frontier = _frontier(stage_ithkuil)
        staged_outputs = _publishable_files(stage_ithkuil)
        staged_hashes = _file_hashes(staged_outputs)
        # Recheck immutable source/code/contract identity immediately before publication.
        current_inputs, current_manifest_sha = _source_inputs(source_ithkuil)
        current_deps = _dependency_identity(source_ithkuil, current_inputs, selection, python)
        if current_manifest_sha != source_manifest_sha or _sha(_bytes(current_deps)) != authority_identity:
            raise RuntimeError("SOURCE_INPUT_IDENTITY_CHANGED_DURING_STAGE")
        record.update({"status": "PUBLISHING", "active_stage": "publish", "frontier": frontier,
                       "staged_artifact_hashes": staged_hashes})
        _write_atomic(latest, _bytes(record))
        artifacts, publication_error = _publish(root, stage_ithkuil, attempt, original_identity)
        if publication_error:
            status = "RECONCILE_REQUIRED" if artifacts.get("reconcile_required") else "FAILED"
            error_code = "PUBLICATION_RECONCILE_REQUIRED" if status == "RECONCILE_REQUIRED" else "PUBLICATION_ROLLED_BACK"
            record.update({"status": status, "artifacts": artifacts, "error_code": error_code,
                           "publication_error": publication_error})
            _write_atomic(latest, _bytes(record))
            return _result(run_identity=run_id, status=status, source_manifest_sha256=source_manifest_sha,
                           commands=commands, artifacts=artifacts, frontier=frontier,
                           validator={"passed": True}, debt=frontier["debt_by_reason"],
                           failed_stage="publish", error_code=error_code, run_record=latest)
        published = _publishable_files(source_ithkuil)
        published_hashes = _file_hashes(published)
        if published_hashes != staged_hashes:
            raise RuntimeError("PUBLISHED_ARTIFACT_SET_MISMATCH")
        frontier["path"] = str(source_ithkuil / "_data/csv/sources/extraction_frontier.json")
        result = _result(run_identity=run_id, status="SUCCEEDED", source_manifest_sha256=source_manifest_sha,
                         commands=commands,
                         artifacts={**artifacts, "canonical_root": str(source_ithkuil),
                                    "published_artifact_hashes": published_hashes}, frontier=frontier,
                         validator={"passed": True, "stage": next(c["stage"] for c in commands
                                                                   if c["stage"] == "validate_dataset")},
                         debt=frontier["debt_by_reason"], run_record=latest)
        record.update({**result, "authority_identity": authority_identity,
                       "published_artifact_hashes": published_hashes, "attempt": attempt_number})
        _write_atomic(latest, _bytes(record))
        return result
    except Exception as exc:
        record = json.loads(latest.read_text(encoding="utf-8")) if latest.is_file() else {}
        stage = record.get("active_stage", "source")
        status = "FAILED"
        error_code = str(exc)
        if record.get("status") == "PUBLISHING":
            try:
                observed = _output_identity(source_ithkuil)
                if observed != original_identity:
                    status = "RECONCILE_REQUIRED"
                    error_code = "PUBLICATION_RECONCILE_REQUIRED"
                    record["publication_observed_identity"] = observed
                    record["publication_expected_identity"] = original_identity
            except Exception as readback_error:
                status = "RECONCILE_REQUIRED"
                error_code = "PUBLICATION_READBACK_UNAVAILABLE"
                record["publication_readback_error"] = str(readback_error)
        record.update({"status": status, "failed_stage": stage,
                       "error_code": error_code, "commands": commands})
        _write_atomic(latest, _bytes(record))
        return _result(run_identity=run_id, status=status, source_manifest_sha256=source_manifest_sha,
                       commands=commands, failed_stage=stage, error_code=error_code, run_record=latest)
    finally:
        try:
            lock.rmdir()
        except OSError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--python", required=True)
    parser.add_argument("--selection", choices=("affix", "all"), required=True)
    args = parser.parse_args(argv)
    try:
        result = run_source(args.repo, args.python, args.selection)
    except ValueError as exc:
        result = _result(run_identity="", status="BLOCKED", source_manifest_sha256="", commands=[],
                         failed_stage="inspect", error_code=str(exc))
    sys.stdout.buffer.write(_bytes(result))
    return 0 if result["status"] in {"SUCCEEDED", "REUSED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
