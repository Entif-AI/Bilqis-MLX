"""Structural variation application for BAMF semantic contrast lessons."""
from __future__ import annotations

from dataclasses import replace

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


def apply_variation(source: ContrastSourceFrame, variation: AllowedVariation) -> tuple[ContrastVariant, str]:
    bindings = source.frame.bindings
    scope = source.scope
    negated = source.negated
    status = source.status
    observation = source.observation_state
    morphology = source.source_morphology

    if variation.family is ContrastFamily.ROLE_SWAP:
        left = _binding(source.frame, variation.role_a, 0)
        right = _binding(source.frame, variation.role_b, 0)
        replaced = []
        for item in bindings:
            if item.key == left.key:
                replaced.append(RoleOccurrence(item.role_id, item.occurrence_index, **_target_kwargs(right)))
            elif item.key == right.key:
                replaced.append(RoleOccurrence(item.role_id, item.occurrence_index, **_target_kwargs(left)))
            else:
                replaced.append(item)
        bindings = tuple(replaced)
        applicability = "two-present-role-bindings"
    elif variation.family is ContrastFamily.CARDINALITY_CHANGE:
        same_role = tuple(item for item in bindings if item.role_id == variation.role_id)
        if variation.remove:
            target = _binding(source.frame, variation.role_id, variation.occurrence_index)
            bindings = tuple(item for item in bindings if item.key != target.key)
            # Reindex the retained role occurrences canonically after removal.
            retained = [item for item in bindings if item.role_id == variation.role_id]
            remapped = {item.key: index for index, item in enumerate(retained)}
            bindings = tuple(
                replace(item, occurrence_index=remapped[item.key])
                if item.role_id == variation.role_id else item
                for item in bindings)
            applicability = "existing-role-occurrence-removal"
        else:
            if variation.concept.semantic_release != source.semantic_release:
                _fail("BAMF_SEMANTIC_CONTRAST_RELEASE_MISMATCH")
            next_index = max((item.occurrence_index for item in same_role), default=-1) + 1
            bindings = bindings + (RoleOccurrence(
                variation.role_id, next_index, concept=variation.concept),)
            applicability = "role-cardinality-extension"
    elif variation.family is ContrastFamily.SCOPE_NEGATION:
        scope = variation.scope
        negated = variation.negated
        if scope == source.scope and negated == source.negated:
            _fail("BAMF_SEMANTIC_CONTRAST_NOOP")
        applicability = "scope-or-negation-change"
    elif variation.family is ContrastFamily.KNOWN_UNKNOWN:
        target = _binding(source.frame, variation.role_id, variation.occurrence_index)
        if target.state is BindingState.UNKNOWN:
            _fail("BAMF_SEMANTIC_CONTRAST_NOOP")
        bindings = tuple(
            RoleOccurrence(item.role_id, item.occurrence_index, state=BindingState.UNKNOWN)
            if item.key == target.key else item
            for item in bindings)
        applicability = "known-binding-to-unknown"
    elif variation.family is ContrastFamily.PLANNED_OCCURRED:
        status = variation.status
        if status is source.status:
            _fail("BAMF_SEMANTIC_CONTRAST_NOOP")
        applicability = "planned-occurred-status-change"
    elif variation.family is ContrastFamily.MISSING_NEGATIVE:
        observation = variation.observation_state
        if observation is source.observation_state:
            _fail("BAMF_SEMANTIC_CONTRAST_NOOP")
        applicability = "missing-negative-observation-distinction"
    elif variation.family is ContrastFamily.MORPHOLOGY_ALTERNATIVE:
        if variation.morphology not in source.authorized_morphology_alternatives:
            _fail("BAMF_SEMANTIC_CONTRAST_MORPHOLOGY_UNAUTHORIZED")
        morphology = variation.morphology
        if morphology == source.source_morphology:
            _fail("BAMF_SEMANTIC_CONTRAST_NOOP")
        applicability = "source-authorized-morphology-alternative"
    else:
        _fail("BAMF_SEMANTIC_CONTRAST_FAMILY_UNSUPPORTED")

    return ContrastVariant(
        source.frame.occurrence_id,
        source.frame.content_digest,
        _sorted_bindings(source, bindings),
        scope,
        negated,
        status,
        observation,
        morphology,
    ), applicability


