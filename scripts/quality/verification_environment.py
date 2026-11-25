"""Bounded content fingerprint of the installed Python verification environment."""
from __future__ import annotations

import hashlib
import importlib.metadata
from pathlib import Path

from .verification_ledger import fingerprint


MAX_ENVIRONMENT_BYTES = 512 * 1024 * 1024


def installed_identity(tools: tuple[Path, ...], *, distributions=None,
                       byte_limit: int = MAX_ENVIRONMENT_BYTES) -> str | None:
    """Bind actual installed artifacts; decline reuse for unbounded environments."""
    distributions = importlib.metadata.distributions() if distributions is None else distributions
    remaining = byte_limit
    seen = {}

    def digest(path: Path):
        nonlocal remaining
        path = path.resolve()
        if path in seen:
            return seen[path]
        if not path.is_file():
            return None
        size = path.stat().st_size
        if size > remaining:
            raise ValueError("verification environment exceeds byte budget")
        remaining -= size
        with path.open("rb") as stream:
            result = hashlib.file_digest(stream, "sha256").hexdigest()
        seen[path] = result
        return result

    try:
        tool_rows = [(str(path.resolve()), digest(path)) for path in tools]
        if any(value is None for _, value in tool_rows):
            return None
        rows = []
        for dist in distributions:
            files = dist.files
            if files is None or not dist.metadata["Name"]:
                return None
            entries = [(str(file), digest(Path(dist.locate_file(file)))) for file in files]
            rows.append((dist.metadata["Name"], dist.version, sorted(entries)))
        return fingerprint(tool_rows, sorted(rows))
    except (OSError, TypeError, ValueError):
        return None
