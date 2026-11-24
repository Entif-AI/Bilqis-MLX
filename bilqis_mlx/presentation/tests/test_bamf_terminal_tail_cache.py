import json
import os
from pathlib import Path
from unittest.mock import patch

from bilqis_mlx.presentation import bamf_terminal_source as source


def _event(index: int, *, accepted: bool = False):
    how = {
        "attempted_steps": 4,
        "retained_steps": 4 if accepted else 0,
        "context": {"grade": "A"},
    }
    if accepted:
        return {
            "event": "BAMF_C16_3_ACCEPTED",
            "event_id": f"accepted-{index}",
            "visit_id": f"visit-{index}",
            "capability": "A.MAPS",
            "optimizer_step": index * 4,
            "how_outcome": how,
        }
    return {
        "event": "BAMF_CANDIDATE_REJECTED",
        "event_id": f"rejected-{index}",
        "evidence": {
            "visit_id": f"visit-{index}",
            "capability": "A.EDGE",
            "candidate_optimizer_step": index * 4,
            "rejection_attempt_ordinal": index,
            "how_outcome": how,
        },
    }


def _write_line(path: Path, event: dict, *, append: bool = False):
    mode = "a" if append else "w"
    with path.open(mode) as stream:
        stream.write(json.dumps(event) + "\n")


def _clear_cache():
    with source._DURABLE_HISTORY_LOCK:
        source._DURABLE_HISTORY_CACHE.clear()


def test_history_cache_tails_only_new_events(tmp_path):
    _clear_cache()
    events = tmp_path / "events.jsonl"
    _write_line(events, _event(1))

    first = source._read_durable_history(tmp_path, "aspirant")
    _write_line(events, _event(2, accepted=True), append=True)
    second = source._read_durable_history(tmp_path, "aspirant")

    assert [visit["visit_id"] for visit in first] == ["visit-1"]
    assert [visit["visit_id"] for visit in second] == ["visit-1", "visit-2"]


def test_incomplete_tail_is_retried_after_record_finishes(tmp_path):
    _clear_cache()
    events = tmp_path / "events.jsonl"
    complete = _event(1)
    pending = json.dumps(_event(2))
    with events.open("wb") as stream:
        stream.write((json.dumps(complete) + "\n").encode())
        stream.write(pending[: len(pending) // 2].encode())

    first = source._read_durable_history(tmp_path, "aspirant")
    with events.open("ab") as stream:
        stream.write(pending[len(pending) // 2 :].encode() + b"\n")
    second = source._read_durable_history(tmp_path, "aspirant")

    assert [visit["visit_id"] for visit in first] == ["visit-1"]
    assert [visit["visit_id"] for visit in second] == ["visit-1", "visit-2"]


def test_truncation_resets_cached_history(tmp_path):
    _clear_cache()
    events = tmp_path / "events.jsonl"
    _write_line(events, _event(1))
    _write_line(events, _event(2), append=True)
    assert len(source._read_durable_history(tmp_path, "aspirant")) == 2

    _write_line(events, _event(3, accepted=True))
    current = source._read_durable_history(tmp_path, "aspirant")

    assert [visit["visit_id"] for visit in current] == ["visit-3"]


def test_inode_replacement_resets_cached_history(tmp_path):
    _clear_cache()
    events = tmp_path / "events.jsonl"
    replacement = tmp_path / "events.next"
    _write_line(events, _event(1))
    assert len(source._read_durable_history(tmp_path, "aspirant")) == 1

    _write_line(replacement, _event(4, accepted=True))
    os.replace(replacement, events)
    current = source._read_durable_history(tmp_path, "aspirant")

    assert [visit["visit_id"] for visit in current] == ["visit-4"]


def test_unchanged_history_does_not_rescan_prefix(tmp_path):
    _clear_cache()
    events = tmp_path / "events.jsonl"
    _write_line(events, _event(1))
    expected = source._read_durable_history(tmp_path, "aspirant")

    with patch.object(
        source, "_scan_durable_append", side_effect=AssertionError("rescanned")
    ):
        observed = source._read_durable_history(tmp_path, "aspirant")

    assert observed == expected
