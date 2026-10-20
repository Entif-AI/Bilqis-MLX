"""Run one bounded source-only extraction after executable learner exhaustion."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

from .disk import atomic_text


def prepare_source_frontier(repo_root: Path, *, timeout: int = 60) -> dict:
    """The child receives source paths only, with no learner or run-state inputs."""
    script = repo_root / "lib/ithkuil/src/build_lexicon_chapters.py"
    output = repo_root / ".local/issue-349-source-snapshots"
    if any(path.is_symlink() for path in (repo_root / ".local", output)):
        raise ValueError("AUTONOMY_SOURCE_OUTPUT_UNSAFE")
    digest = hashlib.sha256(script.read_bytes()).hexdigest()
    try:
        completed = subprocess.run(
            [sys.executable, "-B", str(script), "--next", "--output", str(output)],
            cwd=repo_root, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return dict(status="SOURCE_PREPARATION_DEFERRED", reason="EXTRACTION_TIMEOUT",
                    builder_sha256=digest)
    if hashlib.sha256(script.read_bytes()).hexdigest() != digest:
        raise ValueError("AUTONOMY_SOURCE_BUILDER_CHANGED_DURING_EXTRACTION")
    if completed.returncode:
        return dict(status="SOURCE_PREPARATION_DEFERRED", reason="EXTRACTION_FAILED",
                    builder_sha256=digest, exit_code=completed.returncode,
                    diagnostic=completed.stderr[-4000:])
    result = json.loads(completed.stdout)
    if result.get("status") not in (
            "SOURCE_SNAPSHOT_EXTRACTED", "TRACKED_SOURCE_QUEUE_EXHAUSTED"):
        raise ValueError("AUTONOMY_SOURCE_RESULT_INVALID")
    if result["status"] == "SOURCE_SNAPSHOT_EXTRACTED":
        path = Path(result["output"])
        if (path.parent != output.resolve() or path.is_symlink() or
                (path / "lexicon_extraction_manifest.json").is_symlink() or
                json.loads((path / "lexicon_extraction_manifest.json").read_text()) !=
                result["manifest"] or
                result["manifest"]["builder_sha256"] != digest):
            raise ValueError("AUTONOMY_SOURCE_RESULT_DRIFT")
        for name, expected in result["manifest"]["output_files"].items():
            if (Path(name).name != name or (path / name).is_symlink() or
                    hashlib.sha256((path / name).read_bytes()).hexdigest() != expected):
                raise ValueError("AUTONOMY_SOURCE_RESULT_DRIFT")
    return {**result, "builder_sha256": digest}


def persist_source_development(run_dir, result, *, proposal, checkpoint) -> Path:
    """Bind source work to its trigger without asserting learner improvement."""
    root = Path(run_dir).resolve(strict=True)
    directory = root / "autonomy" / "source-development"
    if any(path.is_symlink() for path in (root / "autonomy", directory)):
        raise ValueError("AUTONOMY_SOURCE_RECEIPT_PATH_UNSAFE")
    payload = dict(schema="bilqis.mlx.source-development/v1",
                   proposal_sha256=proposal.proposal_sha256,
                   checkpoint_sha256=checkpoint.sha256,
                   optimizer_step=checkpoint.optimizer_step,
                   actual_neural_updates=0, source_work=result)
    content = json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    digest = hashlib.sha256(content.encode()).hexdigest()
    path = directory / (digest + ".json")
    if path.is_symlink():
        raise ValueError("AUTONOMY_SOURCE_RECEIPT_PATH_UNSAFE")
    if not path.exists():
        atomic_text(path, content)
    if path.read_text() != content:
        raise ValueError("AUTONOMY_SOURCE_RECEIPT_DRIFT")
    return path
