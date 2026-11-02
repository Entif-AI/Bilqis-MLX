"""Binding of source-owned partial forest authority."""
from __future__ import annotations
from ..frame_compiler import _closure_end, _invalid
from .authority import _validate_hidden_parent_current_authority
from .provenance import _hidden_parent_provenance


def _bind_hidden_parent(
    frame, compiled, source_frames, envelopes, schemas, compiler_config,
):
    parent_occurrence = frame.parent_occurrence_id
    parent = source_frames.get(parent_occurrence)
    if parent is None:
        _invalid("BAMF_PREFIX_PARTIAL_PARENT_ORPHAN")
    parent_envelope = envelopes.get(parent_occurrence)
    if (parent_envelope is None
            or parent_envelope.frame != parent
            or parent.source_instance_id != compiled.source_instance_id
            or parent_envelope.semantic_release != compiled.semantic_release
            or parent_envelope.scope != compiled.scope):
        _invalid("BAMF_PREFIX_PARTIAL_AUTHORITY_DRIFT")
    _validate_hidden_parent_current_authority(
        parent_envelope, compiler_config)
    if _closure_end(parent, envelopes) <= compiled.visible_end:
        _invalid("BAMF_PREFIX_PARTIAL_VISIBILITY_DRIFT")
    return _hidden_parent_provenance(
        frame, parent, parent_envelope, schemas)


def _bind_visible_frames(
    visible_frames, compiled, source_frames, source_parents,
    envelopes, schemas, compiler_config,
):
    visible_handles = []
    hidden_parents = []
    visible_occurrences = {frame.occurrence_id for frame in visible_frames}
    for frame in visible_frames:
        source_frame = source_frames.get(frame.occurrence_id)
        if source_frame is None:
            _invalid("BAMF_PREFIX_PARTIAL_SOURCE_DRIFT")
        actual_parent = source_parents[frame.occurrence_id]
        if frame.parent_occurrence_id != actual_parent:
            _invalid("BAMF_PREFIX_PARTIAL_PARENT_ORPHAN")
        if source_frame != frame:
            _invalid("BAMF_PREFIX_PARTIAL_SOURCE_DRIFT")
        envelope = envelopes.get(frame.occurrence_id)
        if (envelope is None
                or envelope.frame != source_frame
                or envelope.semantic_release != compiled.semantic_release
                or envelope.scope != compiled.scope
                or envelope.frame.source_instance_id != compiled.source_instance_id
                or _closure_end(frame, envelopes) > compiled.visible_end):
            _invalid("BAMF_PREFIX_PARTIAL_AUTHORITY_DRIFT")
        visible_handles.append((frame.occurrence_id, envelope.frame_handle))

        parent_occurrence = frame.parent_occurrence_id
        if (parent_occurrence is None
                or parent_occurrence in visible_occurrences):
            continue
        hidden_parents.append(_bind_hidden_parent(
            frame, compiled, source_frames, envelopes, schemas, compiler_config))
    return visible_handles, hidden_parents
