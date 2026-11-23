"""Typed C04 solver request/context contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..semantics.cognitive_dag import DAGBudget, DAGResult, TaskGoal
from ..semantics.cognitive_operators import OperatorBinding
from ..semantics.domains import contract_digest
from ..semantics.memo import PureOperationMemo
from .operator_registry import RouteKind, RouteRegistry, default_route_registry
from .cognitive_solver_common import (
    CAPABILITY_RESULT_SCHEMA, GENERATION_BINDING_SCHEMA,
    MAX_CACHED_COMPOSITIONS, MAX_NEURAL_CALLS, NEURAL_PROPOSAL_SCHEMA,
    NEURAL_REQUEST_SCHEMA, QUALIFIED_COMPOSITION_SCHEMA, SOLVE_BUDGET_SCHEMA,
    SOLVE_CONTEXT_SCHEMA, SOLVE_REPLAY_SCHEMA, _invalid, _name, _sha,
)


@dataclass(frozen=True)
class GenerationBinding:
    generation_digest: str
    semantic_release: str
    source_binding_digest: str
    schema_version: str = GENERATION_BINDING_SCHEMA

    def __post_init__(self) -> None:
        if (not all(_sha(item) for item in (
                self.generation_digest, self.semantic_release,
                self.source_binding_digest))
                or self.schema_version != GENERATION_BINDING_SCHEMA):
            _invalid("BAMF_C04_GENERATION_BINDING_INVALID")


@dataclass(frozen=True)
class QualifiedComposition:
    goal: TaskGoal
    source_binding_digest: str
    generation_digest: str
    rights_epoch: int
    correction_generation: int
    qualification_receipt_sha256: str
    schema_version: str = QUALIFIED_COMPOSITION_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.goal, TaskGoal)
                or not _sha(self.source_binding_digest)
                or not _sha(self.generation_digest)
                or any(type(item) is not int or item < 0 for item in (
                    self.rights_epoch, self.correction_generation))
                or not _sha(self.qualification_receipt_sha256)
                or self.schema_version != QUALIFIED_COMPOSITION_SCHEMA):
            _invalid("BAMF_C04_QUALIFIED_COMPOSITION_INVALID")


@dataclass(frozen=True)
class SolveBudget:
    dag_budget: DAGBudget
    max_neural_calls: int = MAX_NEURAL_CALLS
    max_cached_candidates: int = MAX_CACHED_COMPOSITIONS
    max_local_refinements: int = 0
    schema_version: str = SOLVE_BUDGET_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.dag_budget, DAGBudget)
                or type(self.max_neural_calls) is not int
                or not 0 <= self.max_neural_calls <= MAX_NEURAL_CALLS
                or type(self.max_cached_candidates) is not int
                or not 0 <= self.max_cached_candidates
                <= MAX_CACHED_COMPOSITIONS
                or type(self.max_local_refinements) is not int
                or not 0 <= self.max_local_refinements
                <= self.dag_budget.max_decisions
                or self.schema_version != SOLVE_BUDGET_SCHEMA):
            _invalid("BAMF_C04_SOLVE_BUDGET_INVALID")


@dataclass(frozen=True)
class NeuralRequest:
    goal_id: str
    unresolved_signature: str
    source_binding_digest: str
    generation_digest: str
    allowed_operator_ids: tuple[str, ...]
    schema_version: str = NEURAL_REQUEST_SCHEMA

    def __post_init__(self) -> None:
        if (not _name(self.goal_id)
                or not _name(self.unresolved_signature)
                or not _sha(self.source_binding_digest)
                or not _sha(self.generation_digest)
                or not isinstance(self.allowed_operator_ids, tuple)
                or not self.allowed_operator_ids
                or tuple(sorted(set(self.allowed_operator_ids)))
                != self.allowed_operator_ids
                or self.schema_version != NEURAL_REQUEST_SCHEMA):
            _invalid("BAMF_C04_NEURAL_REQUEST_INVALID")


@dataclass(frozen=True)
class NeuralProposal:
    goal: TaskGoal
    source_binding_digest: str
    generation_digest: str
    unresolved_signature: str
    proposal_receipt_sha256: str
    schema_version: str = NEURAL_PROPOSAL_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.goal, TaskGoal)
                or not _sha(self.source_binding_digest)
                or not _sha(self.generation_digest)
                or not _name(self.unresolved_signature)
                or not _sha(self.proposal_receipt_sha256)
                or self.schema_version != NEURAL_PROPOSAL_SCHEMA):
            _invalid("BAMF_C04_NEURAL_PROPOSAL_INVALID")


@dataclass(frozen=True)
class SolveContext:
    binding: OperatorBinding
    source_binding_digest: str | None = None
    qualified_compositions: tuple[QualifiedComposition, ...] = ()
    qualification_verifier: Callable[[QualifiedComposition], bool] | None = None
    neural_proposer: Callable[[NeuralRequest], NeuralProposal | None] | None = None
    local_refiner: Callable[[NeuralRequest, int], NeuralProposal | None] | None = None
    deterministic_fallback: QualifiedComposition | None = None
    memo: PureOperationMemo | None = None
    route_registry: RouteRegistry = field(default_factory=default_route_registry)
    schema_version: str = SOLVE_CONTEXT_SCHEMA
    retain_validated_compositions: bool = True
    prevalidated_exact_goal: TaskGoal | None = None
    prevalidated_exact_result: DAGResult | None = None
    prevalidated_source_authority: bool = False
    operator_composition_artifact_owner: object = field(init=False, compare=False)

    def __post_init__(self) -> None:
        if (not isinstance(self.binding, OperatorBinding)
                or (self.source_binding_digest is not None
                    and not _sha(self.source_binding_digest))
                or not isinstance(self.qualified_compositions, tuple)
                or any(not isinstance(item, QualifiedComposition)
                       for item in self.qualified_compositions)
                or (self.qualification_verifier is not None
                    and not callable(self.qualification_verifier))
                or (self.neural_proposer is not None
                    and not callable(self.neural_proposer))
                or (self.local_refiner is not None
                    and not callable(self.local_refiner))
                or (self.deterministic_fallback is not None
                    and not isinstance(self.deterministic_fallback,
                                       QualifiedComposition))
                or (self.memo is not None
                    and not isinstance(self.memo, PureOperationMemo))
                or not isinstance(self.route_registry, RouteRegistry)
                or self.schema_version != SOLVE_CONTEXT_SCHEMA
                or type(self.retain_validated_compositions) is not bool
                or type(self.prevalidated_source_authority) is not bool
                or ((self.prevalidated_exact_goal is None)
                    != (self.prevalidated_exact_result is None))
                or (self.prevalidated_exact_goal is not None
                    and (not isinstance(self.prevalidated_exact_goal, TaskGoal)
                         or not isinstance(self.prevalidated_exact_result, DAGResult)
                         or self.source_binding_digest is None
                         or self.prevalidated_exact_result.receipt.source_binding_digest
                         != self.source_binding_digest
                         or self.prevalidated_exact_result.receipt.semantic_release
                         != self.prevalidated_exact_goal.semantic_release
                         or self.prevalidated_exact_result.answer.semantic_release
                         != self.prevalidated_exact_goal.semantic_release))):
            _invalid("BAMF_C04_SOLVE_CONTEXT_INVALID")
        from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
            strict_evidence_enabled,
        )
        if (self.source_binding_digest is not None
                and strict_evidence_enabled()
                and contract_digest(self.binding) != self.source_binding_digest):
            _invalid("BAMF_C04_SOLVE_SOURCE_DRIFT")
        from bilqis_mlx.runtime.operator_composition_owner import (
            OperatorCompositionArtifactOwner,
        )
        reusable = tuple(dict.fromkeys(self.qualified_compositions))
        owner = getattr(self, "operator_composition_artifact_owner", None)
        if owner is None:
            object.__setattr__(
                self, "operator_composition_artifact_owner",
                OperatorCompositionArtifactOwner(
                    self.binding, reusable, self.deterministic_fallback,
                    binding_digest=self.source_binding_digest),
            )
        else:
            owned = (*reusable, *((self.deterministic_fallback,)
                                   if self.deterministic_fallback is not None else ()))
            for composition in owned:
                owner.require(composition, self.binding)


from .cognitive_solver_result_contracts import CapabilityResult, _goal_allowed
