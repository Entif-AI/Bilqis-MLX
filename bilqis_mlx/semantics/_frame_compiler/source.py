"""Source for causal source-prefix compilation."""
from __future__ import annotations
from dataclasses import dataclass
from ..context_eligibility import (
    ApprovedContextProjection, ContextPolicy, SourceFrontier, SourceGrant,
    TaskScope,
)
from ..domains import contract_digest
from ..frame_codec import SchemaTagMap
from ..frame_schema import FrameSchema, FrameTree
from .contracts import (
    _invalid, SOURCE_AST_SCHEMA, SOURCE_ATOM_SCHEMA, COMPILER_CONFIG_SCHEMA,
    ATOM_EVIDENCE_SCHEMA, _SHA,
)


def atom_evidence_digest(
    source_instance_id: str, atom: "SourceAtom", release: str,
) -> str:
    """Bind one raw token to source-owned, prefix-stable rights evidence."""
    if (not isinstance(source_instance_id, str) or not source_instance_id
            or not isinstance(atom, SourceAtom)
            or not isinstance(release, str) or not _SHA.fullmatch(release)):
        _invalid("BAMF_PREFIX_ATOM_EVIDENCE_INVALID")
    return contract_digest((
        ATOM_EVIDENCE_SCHEMA, source_instance_id, release,
        atom.index, atom.token, atom.source_reference))



@dataclass(frozen=True)
class SourceAtom:
    """One already-source-visible token at its immutable stream position."""
    index: int
    token: str
    source_reference: str
    schema_version: str = SOURCE_ATOM_SCHEMA

    def __post_init__(self) -> None:
        if (type(self.index) is not int or self.index < 0
                or not isinstance(self.token, str) or not self.token
                or not isinstance(self.source_reference, str)
                or not self.source_reference
                or self.schema_version != SOURCE_ATOM_SCHEMA):
            _invalid("BAMF_PREFIX_ATOM_INVALID")



@dataclass(frozen=True)
class StreamingAST:
    source_instance_id: str
    atoms: tuple[SourceAtom, ...]
    frames: tuple[FrameTree, ...]
    schema_version: str = SOURCE_AST_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.source_instance_id, str)
                or not self.source_instance_id
                or not isinstance(self.atoms, tuple)
                or tuple(atom.index for atom in self.atoms
                         if isinstance(atom, SourceAtom))
                != tuple(range(len(self.atoms)))
                or any(not isinstance(atom, SourceAtom) for atom in self.atoms)
                or not isinstance(self.frames, tuple)
                or any(not isinstance(tree, FrameTree) for tree in self.frames)
                or self.schema_version != SOURCE_AST_SCHEMA):
            _invalid("BAMF_PREFIX_SOURCE_AST_INVALID")



@dataclass(frozen=True)
class FrameCompilerConfig:
    schemas: tuple[FrameSchema, ...]
    schema_map: SchemaTagMap
    approved: ApprovedContextProjection | None
    task: TaskScope
    frontier: SourceFrontier
    policy: ContextPolicy
    schema_version: str = COMPILER_CONFIG_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.schemas, tuple)
                or any(not isinstance(item, FrameSchema)
                       for item in self.schemas)
                or len({item.identity for item in self.schemas})
                != len(self.schemas)
                or not isinstance(self.schema_map, SchemaTagMap)
                or (self.approved is not None
                    and not isinstance(self.approved, ApprovedContextProjection))
                or not isinstance(self.task, TaskScope)
                or not isinstance(self.frontier, SourceFrontier)
                or not isinstance(self.policy, ContextPolicy)
                or self.task.semantic_release != self.schema_map.semantic_release
                or self.schema_version != COMPILER_CONFIG_SCHEMA):
            _invalid("BAMF_PREFIX_CONFIG_INVALID")



def _grant_allows(
    grant: SourceGrant | None, evidence_digest: str,
    config: FrameCompilerConfig, release: str,
) -> bool:
    task, policy, frontier = config.task, config.policy, config.frontier
    return (
        grant is not None and not grant.revoked
        and grant.evidence_digest == evidence_digest
        and grant.semantic_release == release
        and grant.principal_id == task.principal_id
        and grant.tenant_id == task.tenant_id
        and task.purpose in grant.permitted_purposes
        and task.jurisdiction in grant.permitted_jurisdictions
        and task.scope in grant.permitted_scopes
        and grant.source_regime in policy.allowed_regimes
        and task.purpose in policy.allowed_purposes
        and task.jurisdiction in policy.allowed_jurisdictions
        and task.scope in policy.allowed_scopes
        and grant.rights_epoch == frontier.rights_epoch
        and grant.rights_epoch == policy.rights_epoch
        and grant.correction_generation == frontier.correction_generation
        and grant.observed_at <= task.observed_frontier
        and grant.effective_from <= task.effective_time
        and (grant.effective_until is None
             or task.effective_time < grant.effective_until))



def _segment_authority(config: FrameCompilerConfig) -> tuple:
    task = config.task
    return (
        task.principal_id, task.tenant_id, task.purpose,
        task.jurisdiction, task.scope, task.semantic_release,
        task.observed_frontier, task.effective_time,
        config.policy, config.schema_map.digest,
        config.frontier.rights_epoch,
        config.frontier.correction_generation)
