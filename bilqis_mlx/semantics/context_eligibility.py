"""Source-bound context admission before packing, attention or motif lookup."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re

from ..errors import ErrorBus, SEMANTIC_FRAME
from .domains import contract_digest
from .frame_schema import AtomicFrame, FrameInstance, RoleOccurrence


ELIGIBILITY_SCHEMA = "bilqis.context-eligibility/v1"
MEMBER_SCHEMA = "bilqis.context-member/v1"
GRANT_SCHEMA = "bilqis.context-source-grant/v1"
FRONTIER_SCHEMA = "bilqis.context-source-frontier/v1"
TASK_SCHEMA = "bilqis.context-task-scope/v1"
POLICY_SCHEMA = "bilqis.context-policy/v1"
APPROVED_FRAME_SCHEMA = "bilqis.context-approved-frame/v1"
ELIGIBLE_CONTEXT_SCHEMA = "bilqis.eligible-context/v1"
CONTEXT_HOLD_SCHEMA = "bilqis.context-hold/v1"
PROJECTION_SCHEMA = "bilqis.context-approved-projection/v1"
C09_INVALIDATION_SCHEMA_V1 = "bilqis.c09-context-invalidation/v1"
C09_INVALIDATION_SCHEMA_V2 = "bilqis.c09-context-invalidation/v2"
C09_INVALIDATION_SCHEMA = C09_INVALIDATION_SCHEMA_V1
CONTEXT_TRANSITION_SCHEMA = "bilqis.context-transition/v1"
PUBLIC_FORMAL = "PUBLIC_FORMAL"
MAX_CONTEXT_HOLD_DIAGNOSTICS = 16
JOIN_PAIR_ARITY = 2
MIN_JOIN_SET_ARITY = 3
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


from ._context_eligibility.evidence import (
    _invalid,
    _digest,
    _name,
    _epoch,
    _names,
    frame_evidence_digest,
    member_evidence_digest,
    _envelope_projection,
    _frame_release_matches,
)
from ._context_eligibility.members import (
    ContextMember,
    ContextEligibility,
)
from ._context_eligibility.sources import (
    SourceGrant,
    SourceFrontier,
    TaskScope,
)
from ._context_eligibility.results import (
    ContextPolicy,
    ApprovedFrame,
    EligibleContext,
    ContextHold,
)
from ._context_eligibility.gate import (
    check_context_eligibility,
)
from ._context_eligibility.projection import (
    ApprovedContextProjection,
    project_context,
)
from ._context_eligibility.transition import (
    C09ContextInvalidation,
    ContextTransition,
    transition_context,
)

# Resolve postponed annotations after all facade identities exist.
from ._context_eligibility import (
    evidence as _evidence,
    members as _members,
    sources as _sources,
    results as _results,
    gate as _gate,
    projection as _projection,
    transition as _transition,
)
_evidence.__dict__.update({
    "AtomicFrame": AtomicFrame,
    "ContextEligibility": ContextEligibility,
    "ContextMember": ContextMember,
    "FrameInstance": FrameInstance,
})
_members.__dict__.update({
    "AtomicFrame": AtomicFrame,
    "ContextMember": ContextMember,
    "FrameInstance": FrameInstance,
})
_sources.__dict__.update({
    "SourceGrant": SourceGrant,
})
_results.__dict__.update({
    "ApprovedFrame": ApprovedFrame,
})
_gate.__dict__.update({
    "ContextEligibility": ContextEligibility,
    "ContextHold": ContextHold,
    "ContextPolicy": ContextPolicy,
    "EligibleContext": EligibleContext,
    "SourceFrontier": SourceFrontier,
    "TaskScope": TaskScope,
})
_projection.__dict__.update({
    "ApprovedContextProjection": ApprovedContextProjection,
    "AtomicFrame": AtomicFrame,
    "ContextEligibility": ContextEligibility,
    "ContextHold": ContextHold,
    "ContextPolicy": ContextPolicy,
    "EligibleContext": EligibleContext,
    "FrameInstance": FrameInstance,
    "RoleOccurrence": RoleOccurrence,
    "SourceFrontier": SourceFrontier,
    "TaskScope": TaskScope,
})
_transition.__dict__.update({
    "ApprovedContextProjection": ApprovedContextProjection,
    "C09ContextInvalidation": C09ContextInvalidation,
    "ContextEligibility": ContextEligibility,
    "ContextHold": ContextHold,
    "ContextPolicy": ContextPolicy,
    "ContextTransition": ContextTransition,
    "SourceFrontier": SourceFrontier,
    "TaskScope": TaskScope,
})
del _evidence, _members, _sources, _results, _gate, _projection, _transition

# Keep public introspection and pickle paths stable after extraction.
from types import FunctionType as _FunctionType

for _public_object in (
    _invalid, _digest, _name, _epoch, _names,
    frame_evidence_digest, member_evidence_digest, _envelope_projection,
    _frame_release_matches, ContextMember, ContextEligibility, SourceGrant,
    SourceFrontier, TaskScope, ContextPolicy, ApprovedFrame, EligibleContext,
    ContextHold, check_context_eligibility, ApprovedContextProjection,
    project_context, C09ContextInvalidation, ContextTransition,
    transition_context,
):
    _public_object.__module__ = __name__
    if isinstance(_public_object, type):
        for _member in vars(_public_object).values():
            if isinstance(_member, (classmethod, staticmethod)):
                _member = _member.__func__
            elif isinstance(_member, property):
                _member = _member.fget
            if isinstance(_member, _FunctionType):
                _member.__module__ = __name__
del _public_object, _member, _FunctionType
