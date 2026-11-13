"""Bind C13 candidate summaries to durable C16.3/B13 owner events."""
from __future__ import annotations

import json
from pathlib import Path

from bilqis_mlx.semantics.domains import contract_digest
from bilqis_mlx.source_adapters.c13_episode import CAPABILITY


def event_offset(run_dir: Path) -> int:
    path = Path(run_dir) / "events.jsonl"
    return path.stat().st_size if path.is_file() else 0


def owner_event_after(
    run_dir: Path,
    offset: int,
    outcome: str,
    *,
    generation: int,
    optimizer_step: int,
) -> tuple[str | None, str | None]:
    if outcome not in ("ACCEPTED", "REJECTED"):
        return None, None
    path = Path(run_dir) / "events.jsonl"
    if not path.is_file() or offset < 0 or offset > path.stat().st_size:
        raise ValueError("BAMF_C13_OWNER_EVENT_LEDGER_INVALID")
    with path.open("rb") as stream:
        stream.seek(offset)
        raw = stream.read().decode("utf-8")
    rows = tuple(json.loads(line) for line in raw.splitlines() if line.strip())
    expected = (
        "BAMF_C16_3_ACCEPTED" if outcome == "ACCEPTED"
        else "BAMF_CANDIDATE_REJECTED"
    )
    matches = tuple(row for row in rows if row.get("event") == expected)
    if len(matches) != 1:
        raise ValueError("BAMF_C13_OWNER_EVENT_REQUIRED")
    event = matches[0]
    if outcome == "ACCEPTED":
        if (event.get("optimizer_step") != optimizer_step
                or event.get("capability") != CAPABILITY):
            raise ValueError("BAMF_C13_ACCEPTANCE_OWNER_EVENT_DRIFT")
    else:
        evidence = event.get("evidence")
        if (event.get("generation") != generation
                or event.get("optimizer_step") != optimizer_step
                or not isinstance(evidence, dict)
                or evidence.get("capability") != CAPABILITY
                or not isinstance(event.get("rejection_authority_sha256"), str)):
            raise ValueError("BAMF_C13_REJECTION_OWNER_EVENT_DRIFT")
    return expected, contract_digest(event)


__all__ = ("event_offset", "owner_event_after")
