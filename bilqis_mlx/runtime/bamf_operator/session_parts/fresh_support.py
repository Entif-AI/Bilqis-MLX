"""Learning-first depth support materialization with exact local source custody."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import random

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.source_selection import COMPOSITION_DEPTH_POLICY_THRESHOLD
from bilqis_mlx.learning.teacher_strategy_population import effective_policy_key
from bilqis_mlx.runtime.source_execution import SourceBatchAuthority, source_content_digest
from bilqis_mlx.semantic_sampling import DEFAULT_BINARY_BALANCE


DEEP_FRESH_SUPPORT_CONTROL = "SOURCE_TOKEN_LENGTH_PROXY_FRESH_SUPPORT"
SHALLOW_FRESH_SUPPORT_CONTROL = "UNBIASED_FRESH_SUPPORT_SOURCE_GROUPS"
NO_REPLAY_CONTEXT = "NOT_AVAILABLE_NO_REPLAY_CONTEXT"
MULTIROW_SOURCE_FAMILY = "NOT_AVAILABLE_MULTIROW_SOURCE_FAMILY"
DISTINCT_SOURCE_EXHAUSTED = "NOT_AVAILABLE_DISTINCT_SOURCE_EXHAUSTED"
_SOURCE_DRAW_EACH = DEFAULT_BINARY_BALANCE.minimum_total
_MAX_ATTEMPTS = 4


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_CURRICULUM.INVALID, reason=reason)


@dataclass(frozen=True)
class FreshSupportSpecimen:
    rows: tuple[dict, ...] = ()
    binding: dict | None = None
    authority: SourceBatchAuthority | None = None
    depth_control: str | None = None
    unavailable_reason: str | None = None


def _replay_context_available(plan) -> bool:
    if plan is None:
        return False
    return bool(
        tuple(getattr(plan, "prior_capability_ids", ()))
        or tuple(getattr(plan, "retention_support_capability_ids", ()))
        or tuple(getattr(plan, "weakness_records", ()))
    )


def _seed(selection, capability: str, ordinal: int, attempt: int) -> int:
    visit_id = selection.visit.identity.visit_id
    policy_key = effective_policy_key(selection.policy)
    wire = "|".join((
        visit_id, policy_key, capability, str(ordinal), "fresh_support", str(attempt)))
    return int(hashlib.sha256(wire.encode("utf-8")).hexdigest()[:16], 16)


def _unavailable(reason: str) -> FreshSupportSpecimen:
    return FreshSupportSpecimen(unavailable_reason=reason)


def _binding(row, authority: SourceBatchAuthority) -> dict:
    return {
        "row_id": row["id"],
        "role": "fresh_support",
        "release_sha256": authority.release_sha256,
        "capability": authority.capability_id,
        "provider_id": authority.provider_id,
        "provider_implementation_sha256": authority.provider_implementation_sha256,
        "seed": authority.seed,
        "each": authority.each,
        "source_family_id": authority.source_family_id,
        "episode_id": authority.episode_ids[0],
        "source_content_sha256": authority.content_sha256,
    }


def materialize_fresh_support(
        source_context, selection, rehearsal_plan, ordinal: int, *,
        reserved_rows) -> FreshSupportSpecimen:
    """Draw one distinct current-capability support specimen for a replay lesson."""
    if type(ordinal) is not int or ordinal < 1:
        _invalid("BAMF_FRESH_SUPPORT_STEP_INVALID")
    if not _replay_context_available(rehearsal_plan):
        return _unavailable(NO_REPLAY_CONTEXT)
    capability = selection.offer.capability_id
    reserved_ids = {
        row.get("id") for row in tuple(reserved_rows)
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    deep = float(selection.policy.get("depth", 1)) >= COMPOSITION_DEPTH_POLICY_THRESHOLD
    if not deep:
        return FreshSupportSpecimen(depth_control=SHALLOW_FRESH_SUPPORT_CONTROL)
    control = DEEP_FRESH_SUPPORT_CONTROL
    for attempt in range(_MAX_ATTEMPTS):
        seed = _seed(selection, capability, ordinal, attempt)
        rows, parent_authority = source_context.draw_bound_rows(
            seed=seed, capability=capability, each=_SOURCE_DRAW_EACH)
        rows = tuple(rows)
        if (len(rows) != _SOURCE_DRAW_EACH
                or any(type(row) is not dict or row.get("capability") != capability
                       for row in rows)):
            _invalid("BAMF_FRESH_SUPPORT_SOURCE_DRAW_INVALID")
        groups = {}
        for row in rows:
            groups.setdefault(row.get("source_id", row.get("id")), []).append(row)
        if any(len(group) != 1 for group in groups.values()):
            return _unavailable(MULTIROW_SOURCE_FAMILY)
        eligible = [row for row in rows if row.get("id") not in reserved_ids]
        if not eligible:
            continue
        if deep:
            eligible.sort(key=lambda row: (-len(row.get("tokens", ())), row["id"]))
            selected = eligible[0]
        else:
            eligible.sort(key=lambda row: row["id"])
            selected = random.Random(seed).choice(eligible)
        authority = source_context.bind_authorized_subset_rows(
            rows, (selected,), parent_authority)
        return FreshSupportSpecimen(
            rows=(selected,), binding=_binding(selected, authority),
            authority=authority, depth_control=control)
    return _unavailable(DISTINCT_SOURCE_EXHAUSTED)


def require_fresh_support_authority(source_context, specimen: FreshSupportSpecimen):
    """Fail closed if row, binding, and process-live singleton authority diverge."""
    if (not isinstance(specimen, FreshSupportSpecimen)
            or len(specimen.rows) != 1
            or not isinstance(specimen.binding, dict)
            or type(specimen.authority) is not SourceBatchAuthority):
        _invalid("BAMF_FRESH_SUPPORT_AUTHORITY_INVALID")
    row = specimen.rows[0]
    authority = source_context.require_bound_rows(specimen.rows, specimen.authority)
    expected = _binding(row, authority)
    if specimen.binding != expected or source_content_digest(specimen.rows) != authority.content_sha256:
        _invalid("BAMF_FRESH_SUPPORT_AUTHORITY_INVALID")
    return authority


__all__ = (
    "DEEP_FRESH_SUPPORT_CONTROL", "DISTINCT_SOURCE_EXHAUSTED",
    "FreshSupportSpecimen", "MULTIROW_SOURCE_FAMILY", "NO_REPLAY_CONTEXT",
    "SHALLOW_FRESH_SUPPORT_CONTROL", "materialize_fresh_support",
    "require_fresh_support_authority",
)
