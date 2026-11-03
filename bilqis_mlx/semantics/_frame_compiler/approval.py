"""Approval for causal source-prefix compilation."""
from __future__ import annotations
from dataclasses import replace
from ..context_eligibility import ContextHold, project_context
from .contracts import _invalid
from .source import atom_evidence_digest, _grant_allows


def _approved_occurrences(compiler_config):
    approved_by_occurrence = {}
    duplicates = set()
    if compiler_config.approved is not None:
        for envelope in compiler_config.approved.envelopes:
            occurrence = envelope.frame.occurrence_id
            if occurrence in approved_by_occurrence:
                duplicates.add(occurrence)
            else:
                approved_by_occurrence[occurrence] = envelope
        for occurrence in duplicates:
            approved_by_occurrence[occurrence] = None
    return approved_by_occurrence, duplicates


def _approve_visible_frames(
    ast, visible_end, release, compiler_config, closed,
    approved_by_occurrence, duplicates,
):
    grants = {
        grant.source_handle: grant
        for grant in compiler_config.frontier.grants}
    for atom in ast.atoms[:visible_end]:
        if not _grant_allows(
                grants.get(atom.source_reference),
                atom_evidence_digest(ast.source_instance_id, atom, release),
                compiler_config, release):
            _invalid("BAMF_PREFIX_ATOM_SOURCE_UNAUTHORIZED")
    envelopes = []
    for frame in closed:
        if frame.occurrence_id in duplicates:
            _invalid("BAMF_PREFIX_APPROVED_OCCURRENCE_DUPLICATE")
        envelope = approved_by_occurrence.get(frame.occurrence_id)
        if (envelope is None or envelope.frame != frame
                or envelope.causal_prefix_end != frame.causal_prefix_end):
            _invalid("BAMF_PREFIX_FRAME_NOT_APPROVED")
        envelopes.append(envelope)
    context_digest = None
    if envelopes:
        projected = project_context(
            tuple(envelopes),
            replace(compiler_config.task, causal_prefix_end=visible_end),
            compiler_config.frontier, compiler_config.policy)
        if isinstance(projected, ContextHold):
            _invalid("BAMF_PREFIX_CONTEXT_HELD")
        if (len(projected.eligible.frames) != len(envelopes)
                or {item.frame_handle for item in projected.eligible.frames} != {
                item.frame_handle for item in envelopes}):
            _invalid("BAMF_PREFIX_APPROVAL_DRIFT")
        context_digest = projected.digest
    return context_digest
