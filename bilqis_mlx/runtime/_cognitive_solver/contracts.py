"""C04.1 source-bound exact/cache/neural DAG routing without grade branches."""
from __future__ import annotations
from ...semantics._public_identity.facade_dependency import public_facade as _public_facade


def _public():
    return _public_facade("bilqis_mlx.runtime.cognitive_solver")


from dataclasses import asdict, dataclass, field
import re
from typing import Callable

from ...errors import BilqisError, ErrorBus, SCHOOL
from ...semantics.cognitive_dag import (
    DAGBudget, DAGReceipt, TaskGoal, execute_dag,
)
from ...semantics.cognitive_operators import (
    OperatorBinding, TypedValue, ValueState,
)
from ...semantics.domains import contract_digest
from ...semantics.memo import PureOperationMemo
from ..operator_registry import (
    RouteKind, RouteRegistry, default_route_registry,
)
from ..cognitive_artifact_owner import CognitiveArtifactOwner


GENERATION_BINDING_SCHEMA = "bilqis.c04.generation-binding/v1"
QUALIFIED_COMPOSITION_SCHEMA = "bilqis.c04.qualified-composition/v1"
SOLVE_BUDGET_SCHEMA = "bilqis.c04.solve-budget/v2"
SOLVE_CONTEXT_SCHEMA = "bilqis.c04.solve-context/v2"
NEURAL_REQUEST_SCHEMA = "bilqis.c04.neural-request/v1"
NEURAL_PROPOSAL_SCHEMA = "bilqis.c04.neural-proposal/v1"
CAPABILITY_RESULT_SCHEMA = "bilqis.c04.capability-result/v3"
SOLVE_REPLAY_SCHEMA = "bilqis.c04.solve-replay/v1"
MAX_CACHED_COMPOSITIONS = 16
MAX_NEURAL_CALLS = 1
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _invalid(reason: str) -> None:
    _public().ErrorBus.raise_(_public().SCHOOL.BAMF_SOLVER.INVALID, reason=reason)


def _sha(value: object) -> bool:
    return isinstance(value, str) and bool(_public()._SHA256.fullmatch(value))


def _name(value: object) -> bool:
    return isinstance(value, str) and bool(value)


@dataclass(frozen=True)
class GenerationBinding:
    generation_digest: str
    semantic_release: str
    source_binding_digest: str
    schema_version: str = GENERATION_BINDING_SCHEMA

    def __post_init__(self) -> None:
        if (not all(_public()._sha(item) for item in (
                self.generation_digest, self.semantic_release,
                self.source_binding_digest))
                or self.schema_version != _public().GENERATION_BINDING_SCHEMA):
            _public()._invalid("BAMF_C04_GENERATION_BINDING_INVALID")


@dataclass(frozen=True)
class QualifiedComposition:
    goal: TaskGoal
    source_binding_digest: str
    rights_epoch: int
    correction_generation: int
    qualification_receipt_sha256: str
    schema_version: str = QUALIFIED_COMPOSITION_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.goal, _public().TaskGoal)
                or not _public()._sha(self.source_binding_digest)
                or any(type(item) is not int or item < 0 for item in (
                    self.rights_epoch, self.correction_generation))
                or not _public()._sha(self.qualification_receipt_sha256)
                or self.schema_version != _public().QUALIFIED_COMPOSITION_SCHEMA):
            _public()._invalid("BAMF_C04_QUALIFIED_COMPOSITION_INVALID")


@dataclass(frozen=True)
class SolveBudget:
    dag_budget: DAGBudget
    max_neural_calls: int = MAX_NEURAL_CALLS
    max_cached_candidates: int = MAX_CACHED_COMPOSITIONS
    max_local_refinements: int = 0
    schema_version: str = SOLVE_BUDGET_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.dag_budget, _public().DAGBudget)
                or type(self.max_neural_calls) is not int
                or not 0 <= self.max_neural_calls <= _public().MAX_NEURAL_CALLS
                or type(self.max_cached_candidates) is not int
                or not 0 <= self.max_cached_candidates
                <= _public().MAX_CACHED_COMPOSITIONS
                or type(self.max_local_refinements) is not int
                or not 0 <= self.max_local_refinements
                <= self.dag_budget.max_decisions
                or self.schema_version != _public().SOLVE_BUDGET_SCHEMA):
            _public()._invalid("BAMF_C04_SOLVE_BUDGET_INVALID")


@dataclass(frozen=True)
class NeuralRequest:
    goal_id: str
    unresolved_signature: str
    source_binding_digest: str
    generation_digest: str
    allowed_operator_ids: tuple[str, ...]
    schema_version: str = NEURAL_REQUEST_SCHEMA

    def __post_init__(self) -> None:
        if (not _public()._name(self.goal_id)
                or not _public()._name(self.unresolved_signature)
                or not _public()._sha(self.source_binding_digest)
                or not _public()._sha(self.generation_digest)
                or not isinstance(self.allowed_operator_ids, tuple)
                or not self.allowed_operator_ids
                or tuple(sorted(set(self.allowed_operator_ids)))
                != self.allowed_operator_ids
                or self.schema_version != _public().NEURAL_REQUEST_SCHEMA):
            _public()._invalid("BAMF_C04_NEURAL_REQUEST_INVALID")


@dataclass(frozen=True)
class NeuralProposal:
    goal: TaskGoal
    source_binding_digest: str
    generation_digest: str
    unresolved_signature: str
    proposal_receipt_sha256: str
    schema_version: str = NEURAL_PROPOSAL_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.goal, _public().TaskGoal)
                or not _public()._sha(self.source_binding_digest)
                or not _public()._sha(self.generation_digest)
                or not _public()._name(self.unresolved_signature)
                or not _public()._sha(self.proposal_receipt_sha256)
                or self.schema_version != _public().NEURAL_PROPOSAL_SCHEMA):
            _public()._invalid("BAMF_C04_NEURAL_PROPOSAL_INVALID")


@dataclass(frozen=True)
class SolveContext:
    binding: OperatorBinding
    qualified_compositions: tuple[QualifiedComposition, ...] = ()
    qualification_verifier: Callable[[QualifiedComposition], bool] | None = None
    neural_proposer: Callable[[NeuralRequest], NeuralProposal | None] | None = None
    local_refiner: Callable[[NeuralRequest, int], NeuralProposal | None] | None = None
    deterministic_fallback: QualifiedComposition | None = None
    memo: PureOperationMemo | None = None
    artifact_owner: CognitiveArtifactOwner | None = None
    route_registry: RouteRegistry = field(default_factory=default_route_registry)
    schema_version: str = SOLVE_CONTEXT_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.binding, _public().OperatorBinding)
                or not isinstance(self.qualified_compositions, tuple)
                or any(not isinstance(item, _public().QualifiedComposition)
                       for item in self.qualified_compositions)
                or (self.qualification_verifier is not None
                    and not callable(self.qualification_verifier))
                or (self.neural_proposer is not None
                    and not callable(self.neural_proposer))
                or (self.local_refiner is not None
                    and not callable(self.local_refiner))
                or (self.deterministic_fallback is not None
                    and not isinstance(self.deterministic_fallback,
                                       _public().QualifiedComposition))
                or (self.memo is not None
                    and not isinstance(self.memo, _public().PureOperationMemo))
                or (self.artifact_owner is not None
                    and not isinstance(self.artifact_owner, CognitiveArtifactOwner))
                or not isinstance(self.route_registry, _public().RouteRegistry)
                or self.schema_version != _public().SOLVE_CONTEXT_SCHEMA):
            _public()._invalid("BAMF_C04_SOLVE_CONTEXT_INVALID")


