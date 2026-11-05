"""Structural variation application for BAMF semantic contrast lessons."""
from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.semantics.frame_schema import BindingState, FrameInstance, RoleOccurrence
from bilqis_mlx.factory.semantic_contrast_models import ContrastVariant
from bilqis_mlx.factory.semantic_contrast_types import AllowedVariation, ContrastFamily, ContrastSourceFrame


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _binding(frame: FrameInstance, role_id: str, index: int = 0) -> RoleOccurrence:
    matches = tuple(item for item in frame.bindings
                    if item.role_id == role_id and item.occurrence_index == index)
    if len(matches) != 1:
        _fail("BAMF_SEMANTIC_CONTRAST_NOT_APPLICABLE")
    return matches[0]


def _target_kwargs(binding: RoleOccurrence) -> dict:
    return {
        "concept": binding.concept,
        "child_frame": binding.child_frame,
        "state": binding.state,
        "alternatives": binding.alternatives,
    }


def _sorted_bindings(source: ContrastSourceFrame, bindings: tuple[RoleOccurrence, ...]) -> tuple[RoleOccurrence, ...]:
    roles = {role.role_id: role for role in source.frame_schema.roles}
    rank = {role.role_id: index for index, role in enumerate(source.frame_schema.roles)}
    if any(item.role_id not in roles for item in bindings):
        _fail("BAMF_SEMANTIC_CONTRAST_NOT_APPLICABLE")
    for role_id, spec in roles.items():
        members = tuple(item for item in bindings if item.role_id == role_id)
        if not spec.min_cardinality <= len(members) <= spec.max_cardinality:
            _fail("BAMF_SEMANTIC_CONTRAST_CARDINALITY_INVALID")
        if tuple(sorted(item.occurrence_index for item in members)) != tuple(range(len(members))):
            _fail("BAMF_SEMANTIC_CONTRAST_OCCURRENCE_SEQUENCE_INVALID")
        for member in members:
            targets = ()
            if member.concept is not None:
                targets = (member.concept,)
            elif member.alternatives:
                targets = member.alternatives
            if any(not set(item.type_ids).intersection(spec.allowed_type_ids) for item in targets):
                _fail("BAMF_SEMANTIC_CONTRAST_ROLE_TYPE_INVALID")
    return tuple(sorted(bindings, key=lambda item: (rank[item.role_id], item.occurrence_index)))


def _role_swap(source: ContrastSourceFrame, variation: AllowedVariation) -> tuple[dict, str]:
    left = _binding(source.frame, variation.role_a, 0)
    right = _binding(source.frame, variation.role_b, 0)
    replaced = []
    for item in source.frame.bindings:
        target = right if item.key == left.key else left if item.key == right.key else None
        replaced.append(RoleOccurrence(item.role_id, item.occurrence_index, **_target_kwargs(target)) if target else item)
    return {"bindings": tuple(replaced)}, "two-present-role-bindings"


def _cardinality(source: ContrastSourceFrame, variation: AllowedVariation) -> tuple[dict, str]:
    bindings = source.frame.bindings
    same_role = tuple(item for item in bindings if item.role_id == variation.role_id)
    if variation.remove:
        target = _binding(source.frame, variation.role_id, variation.occurrence_index)
        bindings = tuple(item for item in bindings if item.key != target.key)
        retained = [item for item in bindings if item.role_id == variation.role_id]
        remapped = {item.key: index for index, item in enumerate(retained)}
        bindings = tuple(replace(item, occurrence_index=remapped[item.key]) if item.role_id == variation.role_id else item for item in bindings)
        return {"bindings": bindings}, "existing-role-occurrence-removal"
    if variation.concept.semantic_release != source.semantic_release:
        _fail("BAMF_SEMANTIC_CONTRAST_RELEASE_MISMATCH")
    next_index = max((item.occurrence_index for item in same_role), default=-1) + 1
    return {"bindings": bindings + (RoleOccurrence(variation.role_id, next_index, concept=variation.concept),)}, "role-cardinality-extension"


def _scope(source: ContrastSourceFrame, variation: AllowedVariation) -> tuple[dict, str]:
    if variation.scope == source.scope and variation.negated == source.negated:
        _fail("BAMF_SEMANTIC_CONTRAST_NOOP")
    return {"scope": variation.scope, "negated": variation.negated}, "scope-or-negation-change"


def _known_unknown(source: ContrastSourceFrame, variation: AllowedVariation) -> tuple[dict, str]:
    target = _binding(source.frame, variation.role_id, variation.occurrence_index)
    if target.state is BindingState.UNKNOWN:
        _fail("BAMF_SEMANTIC_CONTRAST_NOOP")
    bindings = tuple(RoleOccurrence(item.role_id, item.occurrence_index, state=BindingState.UNKNOWN) if item.key == target.key else item for item in source.frame.bindings)
    return {"bindings": bindings}, "known-binding-to-unknown"


def _status(source: ContrastSourceFrame, variation: AllowedVariation) -> tuple[dict, str]:
    if variation.status is source.status:
        _fail("BAMF_SEMANTIC_CONTRAST_NOOP")
    return {"status": variation.status}, "planned-occurred-status-change"


def _observation(source: ContrastSourceFrame, variation: AllowedVariation) -> tuple[dict, str]:
    if variation.observation_state is source.observation_state:
        _fail("BAMF_SEMANTIC_CONTRAST_NOOP")
    return {"observation": variation.observation_state}, "missing-negative-observation-distinction"


def _morphology(source: ContrastSourceFrame, variation: AllowedVariation) -> tuple[dict, str]:
    if variation.morphology not in source.authorized_morphology_alternatives:
        _fail("BAMF_SEMANTIC_CONTRAST_MORPHOLOGY_UNAUTHORIZED")
    if variation.morphology == source.source_morphology:
        _fail("BAMF_SEMANTIC_CONTRAST_NOOP")
    return {"morphology": variation.morphology}, "source-authorized-morphology-alternative"


_TRANSFORMS = MappingProxyType({
    ContrastFamily.ROLE_SWAP: _role_swap,
    ContrastFamily.CARDINALITY_CHANGE: _cardinality,
    ContrastFamily.SCOPE_NEGATION: _scope,
    ContrastFamily.KNOWN_UNKNOWN: _known_unknown,
    ContrastFamily.PLANNED_OCCURRED: _status,
    ContrastFamily.MISSING_NEGATIVE: _observation,
    ContrastFamily.MORPHOLOGY_ALTERNATIVE: _morphology,
)


def apply_variation(source: ContrastSourceFrame, variation: AllowedVariation) -> tuple[ContrastVariant, str]:
    state = {
        "bindings": source.frame.bindings,
        "scope": source.scope,
        "negated": source.negated,
        "status": source.status,
        "observation": source.observation_state,
        "morphology": source.source_morphology,
    }
    changes, applicability = _TRANSFORMS[variation.family](source, variation)
    state.update(changes)
    return ContrastVariant(
        source.frame.occurrence_id,
        source.frame.content_digest,
        _sorted_bindings(source, state["bindings"]),
        state["scope"],
        state["negated"],
        state["status"],
        state["observation"],
        state["morphology"],
    ), applicability
