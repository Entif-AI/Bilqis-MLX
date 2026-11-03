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


from .contracts import CAPABILITY_RESULT_SCHEMA, SOLVE_REPLAY_SCHEMA, MAX_NEURAL_CALLS, _invalid, _sha, _name


@dataclass(frozen=True)
class CapabilityResult:
    answer: TypedValue
    route: RouteKind
    dag_receipts: tuple[DAGReceipt, ...]
    neural_calls: int
    generation_digest: str
    source_binding_digest: str
    score: float | None
    task_sha256: str
    rights_epoch: int
    correction_generation: int
    operation_limit: int
    reserved_operations: int
    local_refinement_calls: int = 0
    fallback_reason: str | None = None
    schema_version: str = CAPABILITY_RESULT_SCHEMA

    def __post_init__(self) -> None:
        exact = self.route in (
            _public().RouteKind.EXACT, _public().RouteKind.CACHED_COMPOSITION,
            _public().RouteKind.DETERMINISTIC_FALLBACK)
        if (not isinstance(self.answer, _public().TypedValue)
                or not isinstance(self.route, _public().RouteKind)
                or not isinstance(self.dag_receipts, tuple)
                or not self.dag_receipts
                or any(not isinstance(item, _public().DAGReceipt)
                       for item in self.dag_receipts)
                or type(self.neural_calls) is not int
                or self.neural_calls not in (0, _public().MAX_NEURAL_CALLS)
                or type(self.local_refinement_calls) is not int
                or self.local_refinement_calls < 0
                or (self.fallback_reason is not None
                    and not _public()._name(self.fallback_reason))
                or not _public()._sha(self.generation_digest)
                or not _public()._sha(self.source_binding_digest)
                or not _public()._sha(self.task_sha256)
                or any(type(value) is not int or value < 0 for value in (
                    self.rights_epoch, self.correction_generation,
                    self.reserved_operations))
                or type(self.operation_limit) is not int
                or not 1 <= self.operation_limit <= 64
                or sum(item.operation_count for item in self.dag_receipts)
                + self.reserved_operations > self.operation_limit
                or any(item.source_binding_digest != self.source_binding_digest
                       or item.semantic_release != self.answer.semantic_release
                       for item in self.dag_receipts)
                or (exact and (self.score != 1.0
                               or (self.route is not
                                   _public().RouteKind.DETERMINISTIC_FALLBACK
                                   and self.neural_calls != 0)
                               or self.answer.state is not _public().ValueState.VALUE))
                or (self.route is _public().RouteKind.NEURAL_COMPOSITION
                    and (self.neural_calls != 1
                         or self.score is not None
                         or self.answer.state is not _public().ValueState.VALUE))
                or (self.route is _public().RouteKind.UNRESOLVED
                    and (self.answer.state is _public().ValueState.VALUE
                         or self.score is not None))
                or self.schema_version != _public().CAPABILITY_RESULT_SCHEMA):
            _public()._invalid("BAMF_C04_CAPABILITY_RESULT_INVALID")

    def replay_record(self) -> dict:
        """Export replay identities and measured costs without source/gold payloads."""
        return {
            "schema_version": _public().SOLVE_REPLAY_SCHEMA,
            "task_sha256": self.task_sha256,
            "generation_digest": self.generation_digest,
            "source_binding_digest": self.source_binding_digest,
            "semantic_release": self.answer.semantic_release,
            "rights_epoch": self.rights_epoch,
            "correction_generation": self.correction_generation,
            "route": self.route.value,
            "dag_receipts": tuple(_public().asdict(item) for item in self.dag_receipts),
            "costs": {
                "pure_operations": sum(item.operation_count for item in self.dag_receipts),
                "reserved_operations": self.reserved_operations,
                "operation_limit": self.operation_limit,
                "lookups": sum(item.lookup_count for item in self.dag_receipts),
                "memo_hits": sum(item.memo_hit_count for item in self.dag_receipts),
                "backbone_calls": self.neural_calls,
                "local_refinements": self.local_refinement_calls,
                "decoder_decisions": None,
            },
            "outcome": {
                "type": self.answer.type_name,
                "state": self.answer.state.value,
                "sha256": _public().contract_digest(self.answer),
            },
            "fallback_reason": self.fallback_reason,
        }


