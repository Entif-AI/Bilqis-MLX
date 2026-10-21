"""Immutable custody for source-verified candidate successors awaiting JIT work."""
from pathlib import Path
import json

from ..factory.candidate_staging import StagedCandidate
from .disk import atomic_text

_UNSAFE_PATH = "CANDIDATE_STAGING_PATH_UNSAFE"


def _directory(run_dir: Path) -> Path:
    root = Path(run_dir).resolve(strict=True)
    path = root
    for component in ("autonomy", "staged-candidates"):
        path = path / component
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise ValueError(_UNSAFE_PATH)
    return path


def persist_staged_candidate(run_dir, staged, frontier, current) -> Path:
    staged.verify(frontier, current)
    path = _directory(run_dir) / (staged.staged_sha256 + ".json")
    payload = json.loads(json.dumps(staged.manifest()))
    if path.is_symlink():
        raise ValueError(_UNSAFE_PATH)
    if path.exists():
        if not path.is_file() or json.loads(path.read_text()) != payload:
            raise ValueError("CANDIDATE_STAGING_IMMUTABLE_DRIFT")
    else:
        atomic_text(path, json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False) + "\n")
    restored = StagedCandidate.from_manifest(json.loads(path.read_text()), path.stem)
    restored.verify(frontier, current)
    return path


def load_staged_candidates(run_dir, frontier, current) -> tuple[StagedCandidate, ...]:
    directory = _directory(run_dir)
    if not directory.exists():
        return ()
    result = []
    for path in sorted(directory.iterdir()):
        if path.is_symlink() or not path.is_file() or path.suffix != ".json":
            raise ValueError(_UNSAFE_PATH)
        staged = StagedCandidate.from_manifest(json.loads(path.read_text()), path.stem)
        # Preserve artifacts from older epochs as history, without activating them.
        if (staged.frontier_sha256 != frontier.release_sha256 or
                staged.successor.predecessor_release_sha256 != current.release_sha256):
            continue
        staged.verify(frontier, current)
        result.append(staged)
    if len({item.candidate_id for item in result}) != len(result):
        raise ValueError("CANDIDATE_STAGING_AMBIGUOUS_SUCCESSOR")
    return tuple(result)
