"""Source-bound context admission before packing, attention or motif lookup."""
from ._context_eligibility.authority import (
    ContextEligibility, ContextMember, ContextPolicy, SourceFrontier, SourceGrant,
    TaskScope,
)
from ._context_eligibility.common import PUBLIC_FORMAL
from ._context_eligibility.results import ApprovedFrame, ContextHold, EligibleContext
from ._context_eligibility.evidence import frame_evidence_digest, member_evidence_digest
from ._context_eligibility.admission import check_context_eligibility
from ._context_eligibility.projection import ApprovedContextProjection, project_context
from ._context_eligibility.transition import (
    C09ContextInvalidation, ContextTransition, transition_context,
)

__all__ = [
    "ApprovedContextProjection", "ApprovedFrame", "C09ContextInvalidation",
    "ContextEligibility", "ContextHold", "ContextMember", "ContextPolicy",
    "ContextTransition", "EligibleContext", "SourceFrontier", "SourceGrant",
    "TaskScope", "PUBLIC_FORMAL", "check_context_eligibility", "frame_evidence_digest",
    "member_evidence_digest", "project_context", "transition_context",
]
