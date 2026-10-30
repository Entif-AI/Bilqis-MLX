"""Issue raw-atom grants through the existing public-formal source policy."""
from __future__ import annotations

from dataclasses import replace

from ...semantics.atlas_snapshot import load_pinned_atlas_snapshot
from ...semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextPolicy, SourceFrontier, SourceGrant, TaskScope,
)
from ...semantics.frame_codec import SchemaTagMap
from ...semantics.frame_compiler import FrameCompilerConfig, atom_evidence_digest
from ...semantics.source_atom_binding.common import invalid
from .authority import project_verified_row, require_canonical_graph


def public_formal_atom_context(
    selection, source_row, graph, *, source_root, source_seed, source_each,
    task: TaskScope, frontier: SourceFrontier, policy: ContextPolicy,
    course=None, source_profile_parameters=None,
):
    """Return a source-owned raw AST and current compiler authority.

    Only atoms visible at the requested prefix receive grants. Existing
    conflicting or revoked grants are never replaced. This neither admits a
    lesson nor changes policy, model parameters or the source's ABI.
    """
    from ..atom_binding import verify_source_row

    snapshot = load_pinned_atlas_snapshot(selection)
    canonical_graph = require_canonical_graph(source_row, graph, source_root)
    witness, reason = verify_source_row(
        source_row, canonical_graph, source_root=source_root,
        source_seed=source_seed, source_each=source_each, course=course,
        source_profile_parameters=source_profile_parameters)
    if witness is None:
        invalid("BAMF_SOURCE_ATOM_SOURCE_ROW_HELD:" + str(reason))
    if (type(task) is not TaskScope or type(frontier) is not SourceFrontier
            or type(policy) is not ContextPolicy
            or task.semantic_release != snapshot.release_sha256
            or task.purpose not in policy.allowed_purposes
            or PUBLIC_FORMAL not in policy.allowed_regimes
            or PUBLIC_FORMAL not in policy.allowed_join_classes
            or policy.rights_epoch != frontier.rights_epoch):
        invalid("SOURCE_ATOM_PUBLIC_FORMAL_POLICY_INVALID")
    source = project_verified_row(source_row, canonical_graph, snapshot, witness)
    if not 0 <= task.causal_prefix_end <= len(source.ast.atoms):
        invalid("SOURCE_ATOM_FUTURE_PREFIX")
    grants = {grant.source_handle: grant for grant in frontier.grants}
    if len(grants) != len(frontier.grants):
        invalid("SOURCE_ATOM_DUPLICATE_GRANT")
    for atom in source.ast.atoms[:task.causal_prefix_end]:
        grant = SourceGrant(
            atom.source_reference, task.principal_id, task.tenant_id,
            PUBLIC_FORMAL, task.semantic_release,
            atom_evidence_digest(source.ast.source_instance_id, atom, task.semantic_release),
            (task.purpose,), (task.jurisdiction,), (task.scope,),
            frontier.rights_epoch, frontier.correction_generation, 0, 0)
        prior = grants.get(atom.source_reference)
        if prior is not None and prior != grant:
            invalid("SOURCE_ATOM_PUBLIC_FORMAL_GRANT_COLLISION")
        grants[atom.source_reference] = grant
    current = replace(frontier, grants=tuple(sorted(
        grants.values(), key=lambda grant: grant.source_handle)))
    config = FrameCompilerConfig(
        (), SchemaTagMap.from_schemas(task.semantic_release, ()),
        None, task, current, policy)
    return source.ast, config
