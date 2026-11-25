"""Reuse an existing authenticated projection only on its exact historical bytes."""
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from scripts.bamf.profiling.issue1645.reservation import require

KEY = "active-grade-cadence-terminal-attempts"
SCHEMA = "bilqis.mlx.bamf-active-grade-cadence-attempt-projection/v3"


def prefix_digest(path, size):
    digest = sha256()
    with path.open("rb") as stream:
        remaining = size
        while remaining:
            block = stream.read(min(remaining, 1024 * 1024))
            require(bool(block), "truncated ledger prefix")
            digest.update(block)
            remaining -= len(block)
    return digest.hexdigest()


def verify_index(db, run_key, ledger, frontier):
    """Match every indexed line and its content identity, with no missing range."""
    end_of_coverage = 0
    previous = None
    unique = records = 0
    with ledger.open("rb") as stream:
        for start, end, event_id, digest, payload in db.execute(
                "SELECT start_byte,end_byte,event_id,payload_sha256,payload "
                "FROM event_stream WHERE run_dir=? ORDER BY start_byte,end_byte,sequence",
                (run_key,)):
            require(0 <= start < end <= frontier, "index outside captured frontier")
            stream.seek(start)
            line = stream.read(end - start)
            require(line.endswith(b"\n") and line.count(b"\n") == 1,
                    "indexed line boundary mismatch")
            event = json.loads(line)
            canonical = json.dumps(event, sort_keys=True, separators=(",", ":"),
                                   ensure_ascii=False).encode()
            expected_id = event.get("event_id") if isinstance(event, dict) else None
            expected_digest = (sha256(canonical).hexdigest()
                               if isinstance(expected_id, str) and len(expected_id) == 64
                               else None)
            require(bytes(payload) == canonical and event_id == expected_id
                    and digest == expected_digest, "indexed ledger payload mismatch")
            if (start, end) != previous:
                require(start == end_of_coverage, "incomplete indexed ledger prefix")
                end_of_coverage = end
                unique += 1
                previous = (start, end)
            records += 1
    require(end_of_coverage == frontier, "incomplete indexed ledger frontier")
    return {"unique_lines": unique, "indexed_records": records}


def verified_projection(root: Path, target_run: Path):
    """Authenticate the preserved projection against its own frozen DB and ledger.

    The source is a prior operator-authorized witness's frozen custody, not a
    caller-authored cadence. Both the historical prefix and accepted tip must
    match the new disposable run. The native owner authenticates the unseen tail.
    """
    projection_bytes = (root / "projection.json").read_bytes()
    captured = json.loads(projection_bytes)
    frozen = root / "frozen"
    origin = frozen / "run"
    ledger = origin / "events.jsonl"
    frontier = captured["indexed_bytes"]
    require(type(frontier) is int and frontier > 0 and ledger.stat().st_size == frontier,
            "projection/frozen ledger length mismatch")
    pointer_bytes = (origin / "bamf-state.json").read_bytes()
    require(pointer_bytes == (target_run / "bamf-state.json").read_bytes(),
            "projection parent pointer mismatch")
    pointer = json.loads(pointer_bytes)
    payload = captured["payload"]
    require(payload["schema"] == SCHEMA and
            (payload["run_id"], payload["accepted_generation"],
             payload["accepted_manifest_sha256"], payload["accepted_acceptance_sha256"])
            == (pointer["run_id"], pointer["generation"], pointer["manifest_sha256"],
                pointer["acceptance_sha256"]), "projection accepted anchor mismatch")
    digest = prefix_digest(ledger, frontier)
    require(digest == prefix_digest(target_run / "events.jsonl", frontier),
            "target ledger prefix mismatch")
    with sqlite3.connect((frozen / "plane.sqlite3").resolve().as_uri() + "?mode=ro",
                         uri=True) as db:
        db.execute("BEGIN")
        matches = []
        for key, dev, ino, size, raw in db.execute(
                "SELECT run_dir,st_dev,st_ino,indexed_bytes,payload "
                "FROM event_projections WHERE projection_key=? AND schema_version=?",
                (KEY, SCHEMA)):
            if size == frontier and json.loads(raw) == payload:
                matches.append((key, dev, ino, size))
        require(len(matches) == 1, "missing or ambiguous preserved projection authority")
        key, dev, ino, size = matches[0]
        require(db.execute("SELECT st_dev,st_ino,indexed_bytes FROM event_ledgers "
                           "WHERE run_dir=?", (key,)).fetchone() == (dev, ino, size),
                "preserved projection/index identity mismatch")
        index = verify_index(db, key, ledger, frontier)
    require(prefix_digest(ledger, frontier) == digest
            and prefix_digest(target_run / "events.jsonl", frontier) == digest,
            "historical prefix changed during validation")
    return captured, {**index, "indexed_bytes": frontier, "prefix_sha256": digest,
                      "projection_sha256": sha256(projection_bytes).hexdigest(),
                      "accepted_manifest_sha256": pointer["manifest_sha256"]}


def restore_disposable_projection(root, run, plane):
    captured, receipt = verified_projection(root, run)
    # This is the established detached witness's path-rebinding owner. Never
    # use it on sovereign custody or with an unchecked caller-supplied payload.
    from scripts.bamf.profiling.issue1566_teacher_yield_witness import _seed_cadence_projection
    from bilqis_mlx.runtime.active_grade_cadence_replay import authenticated_cadence_attempts
    rebound = _seed_cadence_projection(run, plane, captured)
    attempts = authenticated_cadence_attempts(run)
    return {**receipt, "rebound_frontier": rebound["indexed_bytes"],
            "pending_attempts": len(attempts)}
