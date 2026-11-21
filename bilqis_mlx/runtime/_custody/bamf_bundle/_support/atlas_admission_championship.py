"""Championship-sidecar invariants for C07 semantic admission."""
from __future__ import annotations

from bilqis_mlx.learning.capability_championship_state import (
    validate_championship_state,
)
from bilqis_mlx.semantics.domains import contract_digest


def cleared_championship_state_valid(value) -> bool:
    """Return whether one initialized sidecar carries zero live authority."""
    if value is None:
        return False
    state = dict(value)
    validate_championship_state(state)
    return state.get("active_roles") == {} and state.get("settled_matchups") == {}


def semantic_admission_championship_reset_valid(
        parent_state, candidate_state, *, parent_manifest_sha256: str,
        parent_generation: int) -> bool:
    """Validate the exact championship reset implied by one semantic admission.

    A live role or settled matchup is real authority and MUST be archived before
    it is cleared. An initialized epoch that already has neither contains no live
    authority to archive, so its history must be preserved unchanged rather than
    fabricating a NEW_SEMANTIC_ADMISSION reference.
    """
    if parent_state is None:
        return candidate_state is None
    if candidate_state is None:
        return False
    parent = dict(parent_state)
    candidate = dict(candidate_state)
    validate_championship_state(parent)
    validate_championship_state(candidate)
    if not cleared_championship_state_valid(candidate):
        return False
    parent_history = tuple(parent.get("epoch_history", ()))
    candidate_history = tuple(candidate.get("epoch_history", ()))
    live_authority = bool(parent.get("active_roles") or parent.get("settled_matchups"))
    if not live_authority:
        return candidate_history == parent_history
    if (len(candidate_history) != len(parent_history) + 1
            or candidate_history[:-1] != parent_history):
        return False
    reference = candidate_history[-1]
    return (
        reference.get("source_manifest_sha256") == parent_manifest_sha256
        and reference.get("source_generation") == parent_generation
        and reference.get("championship_state_sha256") == contract_digest(parent)
        and reference.get("reason") == "NEW_SEMANTIC_ADMISSION"
    )


__all__ = (
    "cleared_championship_state_valid",
    "semantic_admission_championship_reset_valid",
)
