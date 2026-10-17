"""Pure state transitions for a competence-gated two-domain curriculum.

No model, optimizer, or teacher is mutated by this module. It distinguishes
candidate incubation from a *measured* grade improvement and from an entire
qualified domain. A saturated prefix must be rechecked from its start.
"""
from __future__ import annotations

from dataclasses import dataclass

VERSION = "bilqis.school50.mastery-control/v1"
NUMERIC = tuple(f"M{i:02d}" for i in range(1, 9))
LOGIC = tuple(f"G{i:02d}" for i in range(1, 23))


@dataclass(frozen=True)
class Limits:
    max_attempts_per_frontier: int = 12
    min_grade_gain: int = 1
    old_grade_max_loss: int = 1


def initialize() -> dict:
    return {"version": VERSION, "phase": "NUMERIC", "prefix": 1,
            "position": 0, "frontier_failures": 0, "prefix_qualified": [],
            "numeric_prefix_receipts": [], "logic_prefix_receipts": [],
            "numeric_champion": None, "logic_champion": None,
            "numeric_soup": None, "logic_soup": None,
            "hybrid_soup": None, "halt_reason": None}


def grades(stage: dict) -> tuple[str, ...]:
    return NUMERIC if stage["phase"] == "NUMERIC" else LOGIC


def next_grade(stage: dict) -> str | None:
    if stage["phase"] not in ("NUMERIC", "LOGIC"):
        return None
    return grades(stage)[stage["position"]]


def advance(stage: dict, *, improved: bool, prefix_safe: bool,
            parent_step: int, surviving_step: int, limits: Limits) -> str:
    """Advance only on a real improvement; stop if a frontier cannot learn.

    `prefix_safe` means every admitted earlier grade retains its independently
    measured floor. A candidate may pass a *local* teaching gate while failing
    this stricter expanding-prefix graduation check.
    """
    if stage["phase"] not in ("NUMERIC", "LOGIC"):
        raise ValueError("MASTERY_TRANSITION_AFTER_TERMINAL")
    if not (1 <= stage["prefix"] <= len(grades(stage)) and
            0 <= stage["position"] < stage["prefix"]):
        raise ValueError("MASTERY_INVALID_PREFIX_CURSOR")
    grade = next_grade(stage)
    if improved and surviving_step <= parent_step:
        raise ValueError("MASTERY_GAIN_WITHOUT_PERSISTED_STUDENT")
    if not prefix_safe:
        stage["position"] = 0
        stage["frontier_failures"] += 1
        verdict = "PREFIX_RETENTION_RETRY"
    elif stage["position"] == stage["prefix"] - 1:
        if improved:
            stage["frontier_failures"] = 0
            stage["prefix_qualified"].append(grade)
            state_key = ("numeric_prefix_receipts" if stage["phase"] == "NUMERIC"
                         else "logic_prefix_receipts")
            stage[state_key].append({"grade": grade, "step": surviving_step,
                                      "prefix": stage["prefix"]})
            if stage["prefix"] == len(grades(stage)):
                stage["phase"] = "NUMERIC_QUALIFICATION" if stage["phase"] == "NUMERIC" else "LOGIC_QUALIFICATION"
                stage["position"] = 0
                return "DOMAIN_PREFIX_COMPLETE"
            stage["prefix"] += 1
            stage["position"] = 0
            return "PREFIX_EXPANDED"
        stage["frontier_failures"] += 1
        stage["position"] = 0
        verdict = "FRONTIER_NO_GAIN_RETRY"
    else:
        stage["position"] += 1
        return "PREFIX_REHEARSAL_CONTINUE"
    if stage["frontier_failures"] >= limits.max_attempts_per_frontier:
        stage["halt_reason"] = "NO_MEASURED_PREREQUISITE_PROGRESS"
        stage["phase"] = "STOPPED"
        return "BOUNDED_PREREQUISITE_STALL"
    return verdict


def next_phase(stage: dict, *, qualified: bool, checkpoint: dict | None) -> str:
    if stage["phase"] == "NUMERIC_QUALIFICATION":
        if not qualified or not checkpoint:
            stage["phase"] = "STOPPED"
            stage["halt_reason"] = "NUMERIC_DOMAIN_FLOOR_NOT_MET"
            return stage["halt_reason"]
        stage["numeric_champion"] = checkpoint
        stage["phase"] = "LOGIC"
        stage["prefix"] = 1
        stage["position"] = 0
        stage["frontier_failures"] = 0
        stage["prefix_qualified"] = []
        return "LOGIC_DOMAIN_INITIALIZED"
    if stage["phase"] == "LOGIC_QUALIFICATION":
        if not qualified or not checkpoint:
            stage["phase"] = "STOPPED"
            stage["halt_reason"] = "LOGIC_DOMAIN_FLOOR_NOT_MET"
            return stage["halt_reason"]
        stage["logic_champion"] = checkpoint
        stage["phase"] = "SOUP_QUALIFICATION"
        return "SOUP_QUALIFICATION_READY"
    raise ValueError("MASTERY_QUALIFICATION_INVALID_PHASE")
