"""Reusable learner-proof projections, independent of any one source domain."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .autonomy import EvidenceKind, EvidenceObligation
from .development import DevelopmentalTarget, UnderstandingProjection


class ProofAxis(str, Enum):
    """Observable perturbations that distinguish understanding from lookup."""

    SOURCE_EXECUTION = "source-execution"
    NEAREST_NEIGHBOR_CONTRAST = "nearest-neighbor-contrast"
    NONCE_SYMBOL_RENAMING = "nonce-symbol-renaming"
    HELD_OUT_RECOMBINATION = "held-out-recombination"
    REVERSE_MAPPING = "reverse-mapping"
    SINGLE_FACTOR_PERTURBATION = "single-factor-perturbation"
    STRUCTURED_CAUSAL_TRACE = "structured-causal-trace"


@dataclass(frozen=True)
class ProjectionSpec:
    projection: UnderstandingProjection
    minimum_specimens: int
    proof_axes: tuple[ProofAxis, ...]
    failure_signature: str

    def __post_init__(self) -> None:
        if (not isinstance(self.projection, UnderstandingProjection) or
                type(self.minimum_specimens) is not int or
                self.minimum_specimens < 1 or not self.proof_axes or
                len(set(self.proof_axes)) != len(self.proof_axes) or
                any(not isinstance(item, ProofAxis) for item in self.proof_axes) or
                not isinstance(self.failure_signature, str) or
                not self.failure_signature.strip()):
            raise ValueError("UNDERSTANDING_PROJECTION_SPEC_INVALID")


PROJECTION_SPECS = {
    UnderstandingProjection.EXECUTE: ProjectionSpec(
        UnderstandingProjection.EXECUTE, 2,
        (ProofAxis.SOURCE_EXECUTION,),
        "Cannot apply the rule directly on fresh source-valid material."),
    UnderstandingProjection.DISCRIMINATE: ProjectionSpec(
        UnderstandingProjection.DISCRIMINATE, 2,
        (ProofAxis.NEAREST_NEIGHBOR_CONTRAST,),
        "Collapses a concept with its nearest semantic neighbor."),
    UnderstandingProjection.TRANSFER: ProjectionSpec(
        UnderstandingProjection.TRANSFER, 2,
        (ProofAxis.NONCE_SYMBOL_RENAMING,),
        "Succeeds on familiar symbols but fails after irrelevant renaming."),
    UnderstandingProjection.COMPOSE: ProjectionSpec(
        UnderstandingProjection.COMPOSE, 2,
        (ProofAxis.HELD_OUT_RECOMBINATION,),
        "Knows constituents but fails on an unseen legal combination."),
    UnderstandingProjection.INVERT: ProjectionSpec(
        UnderstandingProjection.INVERT, 2,
        (ProofAxis.REVERSE_MAPPING,),
        "Can produce an answer forward but cannot recover the rule or structure."),
    UnderstandingProjection.COUNTERFACTUAL: ProjectionSpec(
        UnderstandingProjection.COUNTERFACTUAL, 2,
        (ProofAxis.SINGLE_FACTOR_PERTURBATION,),
        "Cannot predict what changes when exactly one learned condition changes."),
    UnderstandingProjection.EXPLAIN: ProjectionSpec(
        UnderstandingProjection.EXPLAIN, 1,
        (ProofAxis.STRUCTURED_CAUSAL_TRACE,),
        "Cannot identify the rule, bindings, and result that caused the output."),
}


@dataclass(frozen=True)
class UnderstandingContract:
    capability_id: str
    projections: tuple[ProjectionSpec, ...]

    def __post_init__(self) -> None:
        if (not isinstance(self.capability_id, str) or not self.capability_id or
                not self.projections or
                len({item.projection for item in self.projections}) !=
                len(self.projections) or
                any(not isinstance(item, ProjectionSpec)
                    for item in self.projections)):
            raise ValueError("UNDERSTANDING_CONTRACT_INVALID")


@dataclass(frozen=True)
class UnderstandingEvidencePlan:
    capability_id: str
    obligations: tuple[EvidenceObligation, ...]
    coverage_debt: tuple[str, ...]

    def __post_init__(self) -> None:
        if (not self.capability_id or
                len({item.obligation_id for item in self.obligations}) !=
                len(self.obligations) or
                any(item.capability_id != self.capability_id
                    for item in self.obligations) or
                len(set(self.coverage_debt)) != len(self.coverage_debt)):
            raise ValueError("UNDERSTANDING_EVIDENCE_PLAN_INVALID")

    @property
    def source_supported(self) -> bool:
        return not self.coverage_debt


def contract_for_target(target: DevelopmentalTarget) -> UnderstandingContract:
    if not isinstance(target, DevelopmentalTarget):
        raise TypeError("UNDERSTANDING_TARGET_REQUIRED")
    return UnderstandingContract(
        target.capability_id,
        tuple(PROJECTION_SPECS[item] for item in target.projections),
    )


def plan_understanding_evidence(
    contract: UnderstandingContract, *, generation_axes: tuple[str, ...],
    supported_projections: tuple[UnderstandingProjection, ...],
) -> UnderstandingEvidencePlan:
    """Create obligations only for source-adapter-supported proof projections."""
    if not isinstance(contract, UnderstandingContract):
        raise TypeError("UNDERSTANDING_CONTRACT_REQUIRED")
    if (not generation_axes or len(set(generation_axes)) != len(generation_axes) or
            any(not isinstance(item, str) or not item for item in generation_axes) or
            len(set(supported_projections)) != len(supported_projections) or
            any(not isinstance(item, UnderstandingProjection)
                for item in supported_projections)):
        raise ValueError("UNDERSTANDING_EVIDENCE_SCOPE_INVALID")
    desired = {item.projection: item for item in contract.projections}
    unsupported_claims = set(supported_projections) - set(desired)
    if unsupported_claims:
        raise ValueError("UNDERSTANDING_SUPPORT_OUTSIDE_CONTRACT")

    supported = set(supported_projections)
    obligations = tuple(
        EvidenceObligation(
            obligation_id=(
                f"{contract.capability_id}/projection/{spec.projection.value}"),
            capability_id=contract.capability_id,
            kind=EvidenceKind.PROJECTION,
            key=spec.projection.value,
            minimum_specimens=spec.minimum_specimens,
            generation_axes=generation_axes,
            proof_axes=tuple(item.value for item in spec.proof_axes),
        )
        for spec in contract.projections
        if spec.projection in supported
    )
    debt = tuple(
        f"{contract.capability_id}:{spec.projection.value}:SOURCE_PROJECTION_UNSUPPORTED"
        for spec in contract.projections
        if spec.projection not in supported
    )
    return UnderstandingEvidencePlan(contract.capability_id, obligations, debt)
