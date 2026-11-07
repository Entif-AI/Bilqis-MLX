"""Source- and policy-bound finite validity for A13 source contexts."""
from __future__ import annotations

from dataclasses import dataclass, field

from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.context_eligibility import (
    ContextPolicy, SourceFrontier, TaskScope,
)

from .common import _fail


SOURCE_CONTEXT_POLICY_WINDOW_SCHEMA = "bilqis.source-context-policy-window/v1"
_SOURCE_CONTEXT_WINDOW_ISSUER = object()


@dataclass(frozen=True, init=False)
class SourceContextPolicyWindow:
    """Explicit finite policy authority bound to one pinned A01 source selection."""

    atlas_bundle_id: str
    semantic_release: str
    source_bundle_id: str
    principal_id: str
    tenant_id: str
    purpose: str
    jurisdiction: str
    scope: str
    policy_id: str
    policy_epoch: int
    rights_epoch: int
    correction_generation: int
    observed_at: int
    effective_from: int
    effective_until: int
    schema: str = SOURCE_CONTEXT_POLICY_WINDOW_SCHEMA
    _issuance: object = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        _fail("BAMF_SOURCE_CONTEXT_POLICY_WINDOW_CALLER_CONSTRUCTION_FORBIDDEN")

    def __post_init__(self) -> None:
        names = (
            self.atlas_bundle_id, self.semantic_release, self.source_bundle_id,
            self.principal_id, self.tenant_id, self.purpose,
            self.jurisdiction, self.scope, self.policy_id,
        )
        if (getattr(self, "_issuance", None) is not _SOURCE_CONTEXT_WINDOW_ISSUER
                or any(not isinstance(item, str) or not item for item in names)
                or any(type(item) is not int or item < 0 for item in (
                    self.policy_epoch, self.rights_epoch,
                    self.correction_generation, self.observed_at,
                    self.effective_from, self.effective_until))
                or self.effective_until <= self.effective_from
                or self.schema != SOURCE_CONTEXT_POLICY_WINDOW_SCHEMA):
            _fail("BAMF_SOURCE_CONTEXT_POLICY_WINDOW_INVALID")


def declare_source_context_policy_window(
    atlas: AtlasArtifactSelection,
    task: TaskScope,
    policy: ContextPolicy,
    frontier: SourceFrontier,
    *,
    observed_at: int,
    effective_from: int,
    effective_until: int,
) -> SourceContextPolicyWindow:
    """Declare an absolute finite bound; never derive one from clocks or TTLs."""
    if (type(atlas) is not AtlasArtifactSelection
            or type(task) is not TaskScope
            or type(policy) is not ContextPolicy
            or type(frontier) is not SourceFrontier):
        _fail("BAMF_SOURCE_CONTEXT_POLICY_WINDOW_INVALID")
    AtlasArtifactSelection.__post_init__(atlas)
    if (task.semantic_release != atlas.release_sha256
            or task.purpose is None
            or task.purpose not in policy.allowed_purposes
            or task.jurisdiction not in policy.allowed_jurisdictions
            or task.scope not in policy.allowed_scopes
            or policy.rights_epoch != frontier.rights_epoch
            or any(type(item) is not int or item < 0
                   for item in (observed_at, effective_from, effective_until))
            or observed_at > task.observed_frontier
            or not effective_from <= task.effective_time < effective_until):
        _fail("BAMF_SOURCE_CONTEXT_POLICY_WINDOW_INVALID")
    result = object.__new__(SourceContextPolicyWindow)
    for name, value in (
            ("atlas_bundle_id", atlas.bundle_id),
            ("semantic_release", atlas.release_sha256),
            ("source_bundle_id", atlas.source_bundle_id),
            ("principal_id", task.principal_id),
            ("tenant_id", task.tenant_id),
            ("purpose", task.purpose),
            ("jurisdiction", task.jurisdiction),
            ("scope", task.scope),
            ("policy_id", policy.policy_id),
            ("policy_epoch", policy.policy_epoch),
            ("rights_epoch", frontier.rights_epoch),
            ("correction_generation", frontier.correction_generation),
            ("observed_at", observed_at),
            ("effective_from", effective_from),
            ("effective_until", effective_until),
            ("schema", SOURCE_CONTEXT_POLICY_WINDOW_SCHEMA),
            ("_issuance", _SOURCE_CONTEXT_WINDOW_ISSUER)):
        object.__setattr__(result, name, value)
    result.__post_init__()
    return result
