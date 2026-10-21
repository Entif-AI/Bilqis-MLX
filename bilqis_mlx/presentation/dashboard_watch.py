"""Attach a detached, read-only dashboard to the durable School50 event journal.

This observes a run directory, not the trainer's terminal or PID. It continues
to work when an agent launches a trainer with redirected/non-TTY output and
never writes to the student's checkpoint, state, events, or operator lock.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
import time
from typing import Callable

from bilqis_mlx.paths import active_run_dir
from bilqis_mlx.compatibility.telemetry_events import HISTORICAL_EVENT_KINDS
from .dashboard import build, ingest
from .run_discovery import AmbiguousActiveRun, select_run


DEFAULT_REFRESH_SECONDS = 1.0
_SESSION_STOP_EVENTS = frozenset({
    "SCHOOL_SESSION_STOPPED",
    *(event for event, kind in HISTORICAL_EVENT_KINDS.items() if kind == "stop"),
})


class JournalReplaced(Exception):
    """The viewed source changed identity or shrank; reload its entire view."""


@dataclass
class JournalTail:
    """Byte cursor that only publishes newline-complete, decoded journal rows."""

    path: Path
    position: int = 0
    identity: tuple[int, int] | None = None

    def poll(self) -> tuple[dict, ...]:
        try:
            log = self.path.open("rb")
        except FileNotFoundError:
            if self.identity is not None:
                raise JournalReplaced("Journal disappeared during observation") from None
            return ()
        with log:
            metadata = os.fstat(log.fileno())
            identity = (metadata.st_dev, metadata.st_ino)
            if ((self.identity is not None and identity != self.identity) or
                    metadata.st_size < self.position):
                raise JournalReplaced("Journal replaced or truncated during observation")
            self.identity = identity
            log.seek(self.position)
            events = []
            while line := log.readline():
                if not line.endswith(b"\n"):
                    # Leave the cursor at the beginning of a partially written
                    # record, even if the write was interrupted mid-UTF8/JSON.
                    break
                self.position = log.tell()
                try:
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ValueError("Non-object event")
                    events.append(value)
                except (UnicodeDecodeError, ValueError, TypeError) as exc:
                    events.append({"_viewer_error": "Invalid journal record "
                                   f"at byte {self.position}: {exc}"})
            return tuple(events)


def watch(
    run_dir: Path, *, stream=None, follow: bool = True,
    poll_seconds: float = DEFAULT_REFRESH_SECONDS,
    wait: Callable[[float], None] = time.sleep,
    max_polls: int | None = None,
):
    """Replay the chosen run, then follow only append-complete new events."""
    run_dir = Path(run_dir).expanduser().resolve()
    journal = run_dir / "events.jsonl"
    if not journal.is_file() and not (run_dir / "state.json").is_file():
        raise FileNotFoundError(
            f"No Bilqis state or event journal under {run_dir}; "
            "specify the trainer's exact --run-dir (possibly in a Codex worktree).")
    if not 0 < poll_seconds:
        raise ValueError("Dashboard refresh interval must be positive")

    def snapshot():
        board = build(run_dir, stream=stream)
        board.log_hint = str(journal)
        board.mode = "FOLLOW | READ-ONLY" if follow else "SNAPSHOT | READ-ONLY"
        # The compact dashboard does not render .mode; make detached monitoring
        # explicit in its always-visible RUN header instead.
        board.run_name = run_dir.name + " [FOLLOW]" if follow else run_dir.name
        board.push("system", {
            "kind": "VIEWER", "detail": "FOLLOW journal (read-only); never owns neural state",
        }, redraw=False)
        board.draw()
        return board

    board = snapshot()
    if not follow:
        return board
    tail = JournalTail(journal, board.journal_offset, board.journal_identity)
    polls = 0
    while max_polls is None or polls < max_polls:
        # Wait first, so a new console never redraws the same snapshot twice.
        wait(poll_seconds)
        polls += 1
        try:
            updates = tail.poll()
        except JournalReplaced:
            board = snapshot()
            tail = JournalTail(journal, board.journal_offset, board.journal_identity)
            continue
        if not updates:
            continue
        for event in updates:
            if "_viewer_error" in event:
                board.push("system", {"kind": "LOG", "detail": event["_viewer_error"]},
                           redraw=False)
            else:
                try:
                    ingest(board, event)
                except (ValueError, TypeError, KeyError, IndexError) as exc:
                    board.push("system", {"kind": "LOG", "detail":
                               f"Invalid telemetry event: {exc}"}, redraw=False)
                    continue
                if event.get("event") in _SESSION_STOP_EVENTS:
                    board.mode = "STOPPED | READ-ONLY"
                elif event.get("event") == "SCHOOL_SESSION_STARTED":
                    board.mode = "FOLLOW | READ-ONLY"
        board.draw()
    return board


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path,
                        help="Exact student run; otherwise auto-select the sole active trainer")
    parser.add_argument("--once", action="store_true",
                        help="Render one historical snapshot and exit")
    parser.add_argument("--poll-seconds", type=float, default=DEFAULT_REFRESH_SECONDS,
                        help="Refresh interval while following the journal (default: 1s)")
    args = parser.parse_args(argv)
    try:
        if args.run_dir is not None:
            run_dir = args.run_dir
        else:
            run_dir, active = select_run(active_run_dir())
            if not active:
                print("NO ACTIVE TRAINER DETECTED: showing the canonical saved run. "
                      "Specify --run-dir to view a different saved/remote Codex run.",
                      file=sys.stderr, flush=True)
        watch(run_dir, follow=not args.once, poll_seconds=args.poll_seconds)
    except KeyboardInterrupt:
        return 0  # Detach the viewer without signaling or modifying the trainer.
    except (AmbiguousActiveRun, FileNotFoundError, PermissionError, ValueError) as exc:
        print(f"DASHBOARD UNAVAILABLE: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
