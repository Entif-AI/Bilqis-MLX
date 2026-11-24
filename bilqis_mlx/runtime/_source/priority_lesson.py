"""Select a complete primary lesson under one existing source authority."""

from collections import Counter
from dataclasses import dataclass
import hashlib
import json

from bilqis_mlx.errors import BilqisError, SOURCE
from bilqis_mlx.factory.generation import runtime_adapter_for_release
from bilqis_mlx.learning.native_lesson_selection import select_group_lesson
from bilqis_mlx.learning.source_selection import COMPOSITION_DEPTH_POLICY_THRESHOLD
from bilqis_mlx.runtime.source_execution import _invalid_source_batch
from bilqis_mlx.source_adapters.lesson_geometry import (
    complete_groups, distinct_groups, geometry_for_adapter,
)
from .priority_source_offer import (
    prepare_priority_source_offer, reissue_selected_priority_source_offer,
)


class LessonShapeUnavailable(ValueError):
    """A lawful baseline has no complete, disjoint construction budget."""


@dataclass(frozen=True)
class LessonPool:
    baseline: tuple
    groups: tuple
    rows: tuple
    authority: object
    reason: str | None = None


def _key(group):
    return len(group.rows), group.stratum


def _can_fill(baseline, pool):
    needed = Counter(map(_key, baseline))
    available = Counter(map(_key, pool))
    return all(available[key] >= count for key, count in needed.items())


def _capacity_failure(error, geometry, capability):
    if isinstance(error, BilqisError):
        return (geometry.provider == "predicate"
                and error.spec is SOURCE.GRADE_A.MICRO_CONTEXT_EXHAUSTED)
    message = str(error)
    if geometry.provider == "predicate":
        return message in (
            "LIVE_GRADE_A_SEMANTIC_VARIANTS_EXHAUSTED:" + capability,
            "GRADE_A_EXHAUSTED_DISTINCT_SEMANTIC_RECORDS:" + capability,
        )
    if geometry.provider == "boolean":
        return message in (
            "GRADE_B_OPERATOR_VARIATION_EXHAUSTED:" + capability.rsplit(".", 1)[-1],
            "GRADE_B_COMPOSITE_VARIATION_EXHAUSTED",
            "GRADE_B_IDBOOLOPS_VARIATION_EXHAUSTED",
        )
    if geometry.layout == "copular":
        return message == "COPULAR_VARIATION_EXHAUSTED"
    if geometry.layout == "event-pair":
        return message == "Sample larger than population or is negative"
    return False


def prepare_lesson_pool(source_context, offer):
    """Find one feasible baseline before any expansion or teacher RNG use."""
    capability = offer.capability_id
    execution = source_context.release.execution_plan.capability_map[capability]
    adapter = runtime_adapter_for_release(
        source_context.source_root, source_context.graph, source_context.release,
        source_context.source_registry, execution)
    geometry = geometry_for_adapter(adapter)
    rows = offer.rows()
    if geometry is None:
        return LessonPool((), (), rows, offer.source_authority, "unsupported_source_geometry")
    complete = complete_groups(rows, geometry)
    baseline = distinct_groups(complete)
    if (not baseline
            or set(map(_key, baseline)) != set(map(_key, complete))
            or (geometry.layout != "numeric" and len(baseline) != len(complete))):
        raise LessonShapeUnavailable("complete baseline unavailable")
    fallback = LessonPool(baseline, baseline, rows, offer.source_authority,
                          "baseline_only")
    count = geometry.expanded_count(offer.source_each)
    if count <= offer.source_each:
        return fallback
    try:
        expanded_rows, authority = source_context.draw_bound_rows(
            seed=offer.source_seed, capability=capability, each=count)
    except ValueError as error:
        if _capacity_failure(error, geometry, capability):
            return fallback
        raise
    if any(getattr(authority, key) != getattr(offer.source_authority, key)
           for key in ("release_sha256", "capability_id", "provider_id",
                       "provider_implementation_sha256", "seed", "source_family_id")):
        raise ValueError("BAMF_PRIORITY_LESSON_POOL_AUTHORITY_DRIFT")
    groups = distinct_groups(complete_groups(expanded_rows, geometry))
    if not _can_fill(baseline, groups):
        return fallback
    return LessonPool(baseline, groups, expanded_rows, authority)


def _controls(rows, selected, baseline):
    patterns = {tuple(row["operand_truths"]) for row in rows if "operand_truths" in row}
    required = {tuple(row["operand_truths"]) for group in baseline
                for row in group.rows if "operand_truths" in row}
    return {
        "depth_control": selected.depth_control if selected else None,
        "contrast_control": selected.contrast_control if selected else None,
        "current_semantic_patterns_delivered": len(patterns),
        "current_semantic_patterns_required": len(required) if selected else len(patterns),
        "selected_answer_kinds": sorted({row.get("answer_kind", "binary") for row in rows}),
    }


def shape_priority_lesson(source_context, parent, offer, pool, policy):
    """Bind only the chosen source rows and their realized primary controls."""
    selected = None
    rows = pool.rows
    if pool.baseline:
        selected = select_group_lesson(
            pool.baseline, pool.groups, seed=offer.source_seed,
            deep=policy.get("depth", 1) >= COMPOSITION_DEPTH_POLICY_THRESHOLD,
            contrast=policy.get("contrast", 0.) >= .5)
        rows = selected.rows
    metadata = {
        "requested_rows": offer.source_each,
        "delivered_rows": len(rows),
        "token_count": sum(len(row["tokens"]) for row in rows),
        "signature_count": selected.signature_count if selected else None,
        "reason": pool.reason,
        "controls": _controls(rows, selected, pool.baseline),
    }
    original = offer.rows()
    baseline_rows = tuple(row for group in pool.baseline for row in group.rows)
    if rows == original:
        return offer, metadata
    # Baseline and expanded variants are complete, independently issued
    # draws. Never combine grants or rebind an unchanged baseline to a
    # different draw just because that draw happens to include its rows.
    parent_rows, authority = ((original, offer.source_authority)
                              if rows == baseline_rows else (pool.rows, pool.authority))
    shaped = reissue_selected_priority_source_offer(
        offer, source_context, parent, parent_rows, rows, authority)
    return shaped, metadata


_STEP_LESSON_ISSUER = object()


@dataclass(frozen=True)
class StepPrimaryLesson:
    """One process-live, source-owned primary lesson for a later optimizer step."""
    offer: object
    visit_id: str
    ordinal: int
    metadata_json: str
    _issuer: object


def step_primary_seed(selection, ordinal):
    identity = selection.visit.identity.visit_id
    return int(hashlib.sha256(
        f"{identity}|{selection.offer.source_seed}|target|{ordinal}".encode()
    ).hexdigest()[:16], 16)


def prepare_step_primary_lesson(source_context, parent, selection, ordinal, seed):
    if type(ordinal) is not int or ordinal < 2 or seed != step_primary_seed(selection, ordinal):
        _invalid_source_batch("BAMF_PRIORITY_STEP_LESSON_COORDINATES_INVALID")
    original = selection.offer
    offer = prepare_priority_source_offer(
        source_context, parent, None, capability=original.capability_id,
        source_seed=seed, source_each=original.source_each,
        planning_generation=original._planning_generation)
    shaped, metadata = shape_priority_lesson(
        source_context, parent, offer, prepare_lesson_pool(source_context, offer),
        selection.policy)
    return StepPrimaryLesson(
        shaped, selection.visit.identity.visit_id, ordinal,
        json.dumps(metadata, sort_keys=True, allow_nan=False), _STEP_LESSON_ISSUER)


def require_step_primary_lesson(lesson, source_context, selection, rows, step):
    original = selection.offer
    if (type(lesson) is not StepPrimaryLesson
            or lesson._issuer is not _STEP_LESSON_ISSUER
            or lesson.visit_id != selection.visit.identity.visit_id
            or lesson.ordinal != step - original._planning_generation._parent.retained_state.optimizer_step):
        _invalid_source_batch("BAMF_PRIORITY_STEP_LESSON_COORDINATES_INVALID")
    offer = lesson.offer
    if (offer._planning_generation is not original._planning_generation
            or offer.source_seed != step_primary_seed(selection, lesson.ordinal)
            or offer.capability_id != original.capability_id
            or offer.source_each != original.source_each
            or offer.release_sha256 != original.release_sha256
            or tuple(rows) != offer.rows()):
        _invalid_source_batch("BAMF_PRIORITY_STEP_LESSON_AUTHORITY_DRIFT")
    offer.require_current_parent(source_context)
    return offer, json.loads(lesson.metadata_json)
