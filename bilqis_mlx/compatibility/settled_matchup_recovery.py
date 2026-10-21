"""Prove recovery of a settlement ledger erased by the bad rubric repair.

This module is deliberately read-only.  It does not merge championship state or
write a repaired generation.  It returns only the exact ledger sealed in the
immutable source epoch plus a proof describing why that ledger is recoverable.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path


REPAIR_EVENT = "SCHOOL_SCOPE_RUBRIC_EVIDENCE_REPAIRED"
PROOF_SCHEMA = "bilqis.mlx.settled-matchup-recovery-proof/v1"
_SETTLED_DECISIONS = frozenset(("TITLE_WON", "TITLE_DEFENDED"))
_RESET_CUSTODY_KEYS = (
    "active_championship_reset",
    "administrative_empty_reset",
    "school_identity_history",
    "superseded_active_championships",
)
_EPOCH_CUSTODY_KEYS = (
    "schema",
    "introduced_grade",
    "source_graph_sha256",
    "baseline",
    "previous_graduate",
    "previous_boundary_checkpoint",
    "championship_school_identity",
)


def _sha(value) -> bool:
    return (isinstance(value, str) and len(value) == 64 and
            all(char in "0123456789abcdef" for char in value))


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _state_path(run_dir: Path, generation: int) -> Path:
    if type(generation) is not int or generation < 0:
        raise ValueError("SETTLED_MATCHUP_RECOVERY_GENERATION_INVALID")
    states = run_dir / "states"
    path = states / f"{generation:07d}.json"
    if states.is_symlink() or path.is_symlink() or not path.is_file():
        raise ValueError("SETTLED_MATCHUP_RECOVERY_IMMUTABLE_STATE_MISSING")
    return path


def _read_state(run_dir: Path, generation: int) -> dict:
    path = _state_path(run_dir, generation)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError("SETTLED_MATCHUP_RECOVERY_IMMUTABLE_STATE_INVALID") from exc
    if not isinstance(state, dict) or state.get("generation") != generation:
        raise ValueError("SETTLED_MATCHUP_RECOVERY_IMMUTABLE_STATE_GENERATION_DRIFT")
    return state


def _read_repair_events(run_dir: Path, current_generation: int):
    path = run_dir / "events.jsonl"
    if path.is_symlink() or not path.is_file():
        raise ValueError("SETTLED_MATCHUP_RECOVERY_EVENT_JOURNAL_MISSING")
    repairs = []
    newer_settlements = []
    try:
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError
                generation = event.get("generation")
                if type(generation) is not int or generation < 0:
                    continue
                if generation > current_generation:
                    continue
                if event.get("event") == REPAIR_EVENT:
                    repairs.append(event)
                championship = event.get("championship_epoch")
                if isinstance(championship, dict):
                    for decision in championship.get("cross_origin_decisions", ()):
                        if (isinstance(decision, dict) and
                                decision.get("decision") in _SETTLED_DECISIONS):
                            newer_settlements.append((generation, line_number, decision))
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("SETTLED_MATCHUP_RECOVERY_EVENT_JOURNAL_INVALID") from exc
    return repairs, newer_settlements


def _identity(state: dict, epoch: dict) -> dict:
    state_identity = state.get("championship_school_identity")
    epoch_identity = epoch.get("championship_school_identity")
    if (not isinstance(state_identity, dict) or
            not _sha(state_identity.get("sha256")) or
            state_identity != epoch_identity):
        raise ValueError("SETTLED_MATCHUP_RECOVERY_SCHOOL_IDENTITY_DRIFT")
    return state_identity


def _student(state: dict) -> dict:
    student = (state.get("school") or {}).get("current_student")
    if (not isinstance(student, dict) or not _sha(student.get("sha256")) or
            type(student.get("optimizer_step")) is not int or
            student["optimizer_step"] < 0):
        raise ValueError("SETTLED_MATCHUP_RECOVERY_STUDENT_CUSTODY_INVALID")
    return student


def _validate_ledger(ledger: dict, *, source_generation: int) -> None:
    if not isinstance(ledger, dict) or not ledger:
        raise ValueError("SETTLED_MATCHUP_RECOVERY_SOURCE_LEDGER_EMPTY")
    for key, settlement in ledger.items():
        if not isinstance(key, str) or not isinstance(settlement, dict):
            raise ValueError("SETTLED_MATCHUP_RECOVERY_SOURCE_LEDGER_INVALID")
        parts = key.split("|")
        capability = settlement.get("capability")
        incumbent = settlement.get("incumbent_sha256")
        challenger = settlement.get("challenger_sha256")
        winner = settlement.get("winner_sha256")
        if (len(parts) != 3 or parts[0] != capability or
                not all(_sha(value) for value in (parts[1], parts[2])) or
                parts[1] == parts[2] or
                parts[1:] != sorted(parts[1:]) or
                {_sha_value for _sha_value in (incumbent, challenger)} !=
                {parts[1], parts[2]} or
                winner not in (parts[1], parts[2]) or
                settlement.get("decision") not in _SETTLED_DECISIONS):
            raise ValueError("SETTLED_MATCHUP_RECOVERY_SOURCE_LEDGER_INVALID")
        settled_at = settlement.get("source_generation")
        if (settled_at is not None and
                (type(settled_at) is not int or not 0 <= settled_at <= source_generation)):
            raise ValueError("SETTLED_MATCHUP_RECOVERY_SOURCE_LEDGER_INVALID")


def _same_epoch_custody(left: dict, right: dict) -> bool:
    return all(left.get(key) == right.get(key) for key in _EPOCH_CUSTODY_KEYS)


def _same_reset_custody(left: dict, right: dict) -> bool:
    return all(left.get(key) == right.get(key) for key in _RESET_CUSTODY_KEYS)


def recover_scope_rubric_settled_matchups(
        run_dir, current_state: dict) -> tuple[dict, dict]:
    """Return the exact pre-repair settlement ledger when recovery is proven.

    The proof requires one immutable source epoch archived verbatim by one
    `SCHOOL_SCOPE_RUBRIC_EVIDENCE_REPAIRED` transition, unchanged school
    identity, an empty post-repair/current ledger, no later epoch reset, and no
    later settled title decision.  Any ambiguity fails closed.
    """
    run_dir = Path(run_dir).expanduser().resolve()
    if not isinstance(current_state, dict):
        raise ValueError("SETTLED_MATCHUP_RECOVERY_CURRENT_STATE_INVALID")
    current_generation = current_state.get("generation")
    if type(current_generation) is not int or current_generation < 0:
        raise ValueError("SETTLED_MATCHUP_RECOVERY_GENERATION_INVALID")
    immutable_current = _read_state(run_dir, current_generation)
    if immutable_current != current_state:
        raise ValueError("SETTLED_MATCHUP_RECOVERY_CURRENT_STATE_NOT_IMMUTABLE")

    current_epoch = current_state.get("mentor_epoch")
    history = current_state.get("championship_epoch_history")
    if (not isinstance(current_epoch, dict) or not isinstance(history, list) or
            not history or not isinstance(history[-1], dict)):
        raise ValueError("SETTLED_MATCHUP_RECOVERY_ARCHIVED_EPOCH_REQUIRED")
    current_ledger = current_epoch.get("settled_matchups")
    if not isinstance(current_ledger, dict):
        raise ValueError("SETTLED_MATCHUP_RECOVERY_CURRENT_LEDGER_INVALID")
    if current_ledger:
        raise ValueError("SETTLED_MATCHUP_RECOVERY_NEWER_SETTLEMENT_PRESENT")
    archived_epoch = history[-1]

    repairs, settlement_events = _read_repair_events(run_dir, current_generation)
    candidates = []
    for event in repairs:
        repair_generation = event.get("generation")
        source_generation = event.get("source_generation")
        if (type(repair_generation) is not int or
                type(source_generation) is not int or
                repair_generation != source_generation + 1):
            continue
        try:
            source = _read_state(run_dir, source_generation)
        except ValueError:
            continue
        if source.get("mentor_epoch") == archived_epoch:
            candidates.append((event, source))
    if len(candidates) != 1:
        raise ValueError("SETTLED_MATCHUP_RECOVERY_TRANSITION_NOT_PROVEN")

    event, source = candidates[0]
    source_generation = event["source_generation"]
    repair_generation = event["generation"]
    repair = _read_state(run_dir, repair_generation)
    source_epoch = source["mentor_epoch"]
    repair_epoch = repair.get("mentor_epoch")
    if not isinstance(repair_epoch, dict):
        raise ValueError("SETTLED_MATCHUP_RECOVERY_REPAIR_EPOCH_INVALID")

    if (event.get("archived_bad_epoch") is not True or
            event.get("actual_neural_updates") != 0 or
            event.get("model_and_own_adamw_unchanged") is not True or
            not _sha(event.get("event_id"))):
        raise ValueError("SETTLED_MATCHUP_RECOVERY_REPAIR_EVENT_INVALID")
    source_student = _student(source)
    repair_student = _student(repair)
    if (source_student != repair_student or
            event.get("student_sha256") != source_student["sha256"] or
            event.get("optimizer_step") != source_student["optimizer_step"]):
        raise ValueError("SETTLED_MATCHUP_RECOVERY_REPAIR_CUSTODY_DRIFT")

    identity = _identity(source, source_epoch)
    if (_identity(repair, repair_epoch) != identity or
            _identity(current_state, current_epoch) != identity):
        raise ValueError("SETTLED_MATCHUP_RECOVERY_SCHOOL_IDENTITY_DRIFT")

    source_history = source.get("championship_epoch_history")
    repair_history = repair.get("championship_epoch_history")
    if (not isinstance(source_history, list) or not isinstance(repair_history, list) or
            repair_history != [*source_history, source_epoch] or
            history != repair_history or
            not _same_epoch_custody(repair_epoch, current_epoch) or
            not _same_reset_custody(repair_epoch, current_epoch)):
        raise ValueError("SETTLED_MATCHUP_RECOVERY_EXTRA_EPOCH_RESET")

    source_ledger = source_epoch.get("settled_matchups")
    _validate_ledger(source_ledger, source_generation=source_generation)
    if repair_epoch.get("settled_matchups") != {}:
        raise ValueError("SETTLED_MATCHUP_RECOVERY_REPAIR_DID_NOT_CLEAR_LEDGER")
    if history[-1].get("settled_matchups") != source_ledger:
        raise ValueError("SETTLED_MATCHUP_RECOVERY_ARCHIVED_LEDGER_DRIFT")

    if any(generation >= repair_generation
           for generation, _, _ in settlement_events):
        raise ValueError("SETTLED_MATCHUP_RECOVERY_NEWER_SETTLEMENT_PRESENT")

    proof = {
        "schema": PROOF_SCHEMA,
        "source_generation": source_generation,
        "repair_generation": repair_generation,
        "current_generation": current_generation,
        "repair_event_id": event["event_id"],
        "championship_school_identity_sha256": identity["sha256"],
        "source_student_sha256": source_student["sha256"],
        "source_optimizer_step": source_student["optimizer_step"],
        "source_epoch_sha256": _digest(source_epoch),
        "settled_matchups_sha256": _digest(source_ledger),
        "settled_matchup_count": len(source_ledger),
        "ledger_source": (
            f"states/{source_generation:07d}.json#mentor_epoch.settled_matchups"),
    }
    return deepcopy(source_ledger), proof
