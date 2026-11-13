from __future__ import annotations

from dataclasses import replace
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ApprovedContextProjection, C09ContextInvalidation,
    ContextEligibility, ContextHold, ContextMember, ContextTransition,
    ContextPolicy, EligibleContext, SourceFrontier, SourceGrant, TaskScope,
    check_context_eligibility, frame_evidence_digest, member_evidence_digest,
    project_context, transition_context,
)
from bilqis_mlx.semantics.frame_adapters import public_formal_context
from bilqis_mlx.semantics.frame_schema import (
    ConceptRef, FrameSchema, RoleOccurrence, RoleSpec, SourceSpan,
    make_frame_instance,
)


RELEASE = "a" * 64
PRINCIPAL = "synthetic:alice"
TENANT = "synthetic:tenant"
REGION = "synthetic:region"
SCOPE = "synthetic:public"


def _frame(name: str, index: int, *, two_roles: bool = False):
    roles = ("subject", "object") if two_roles else ("subject",)
    schema = FrameSchema(
        "frame:synthetic", 1, "source:synthetic",
        tuple(RoleSpec(role, ("Entity",), 1, 1) for role in roles),
        "ORDERED", "synthetic",
    )
    return make_frame_instance(
        schema,
        source_instance_id=name,
        structural_path=(),
        source_span=SourceSpan(0, 8),
        parent_occurrence_id=None,
        bindings=tuple(
            RoleOccurrence(
                role, 0,
                concept=ConceptRef(
                    "formal:entity." + str(index + position),
                    RELEASE, index + position, ("Entity",),
                    "synthetic:source:" + name,
                ),
            )
            for position, role in enumerate(roles)
        ),
        causal_prefix_end=8,
    )


def _case(*, count: int = 2, two_roles: bool = False):
    envelopes = []
    grants = []
    for index in range(count):
        frame = _frame("PUBLIC_FORMAL:" + str(index), index,
                       two_roles=two_roles and index == 0)
        frame_source = "source:frame:" + str(index)
        members = []
        for binding in frame.bindings:
            source = "source:member:" + str(index) + ":" + binding.role_id
            members.append(ContextMember(
                binding.role_id, binding.occurrence_index, source, 8))
        handles = (frame_source, *(member.source_handle for member in members))
        evidence = {frame_source: frame_evidence_digest(frame)}
        evidence.update({
            member.source_handle: member_evidence_digest(frame, member)
            for member in members
        })
        grants.extend(SourceGrant(
            handle, PRINCIPAL, TENANT, PUBLIC_FORMAL,
            RELEASE, evidence[handle],
            ("TRAINING",), (REGION,), (SCOPE,),
            rights_epoch=1, correction_generation=1,
            observed_at=2, effective_from=0,
        ) for handle in handles)
        envelopes.append(ContextEligibility(
            frame_handle="frame:" + str(index),
            frame=frame,
            source_handle=frame_source,
            members=tuple(members),
            principal_id=PRINCIPAL, tenant_id=TENANT, purpose="TRAINING",
            source_regime=PUBLIC_FORMAL, semantic_release=RELEASE,
            jurisdiction=REGION, scope=SCOPE, join_class=PUBLIC_FORMAL,
            policy_epoch=1, rights_epoch=1, correction_generation=1,
            observed_at=2, effective_from=0, effective_until=None,
            causal_prefix_end=8,
        ))
    task = TaskScope(
        PRINCIPAL, TENANT, "TRAINING", RELEASE, REGION, SCOPE,
        observed_frontier=3, effective_time=5, causal_prefix_end=8,
    )
    policy = ContextPolicy(
        "synthetic:policy", 1, 1,
        ("TRAINING",), (PUBLIC_FORMAL,), (REGION,), (SCOPE,),
        (PUBLIC_FORMAL,),
        ((PUBLIC_FORMAL, PUBLIC_FORMAL),),
        ((PUBLIC_FORMAL, PUBLIC_FORMAL, PUBLIC_FORMAL),),
    )
    frontier = SourceFrontier(
        1, 1, tuple(sorted(grants, key=lambda grant: grant.source_handle)))
    return tuple(envelopes), task, frontier, policy


    # C09 boundary records are checked independently of transition orchestration.


class ContextEligibilityTests(unittest.TestCase):
    """Shared test base; behavior cases live beside their owners."""
