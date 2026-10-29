"""C04.3 minimal replay receipts, with no assessment/gold dependency."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

from ..errors import ErrorBus, SCHOOL
from ..semantics.cognitive_dag import DAGReceipt
from ..semantics.cognitive_operators import TypedValue, ValueState
from ..semantics.domains import contract_digest
from .operator_registry import RouteKind


SOLVE_REPLAY_SCHEMA = "bilqis.c04.solve-replay-receipt/v1"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_SOLVER.INVALID, reason=reason)


def _sha(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))


def _canonical(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SolveReplayReceipt:
    goal_id: str
    route: RouteKind
    selected_bindings: tuple[tuple[int, str, str, tuple[str, ...]], ...]
    operation_count: int
    lookup_count: int
    memo_hit_count: int
    neural_calls: int
    local_refinement_calls: int
    source_binding_digest: str
    generation_digest: str
    semantic_release: str
    rights_epoch: int
    correction_generation: int
    outcome_type: str
    outcome_state: ValueState
    outcome_digest: str
    score: float | None
    fallback_reason: str | None
    receipt_digest: str
    visibility: str = "INTERNAL_ONLY"
    schema_version: str = SOLVE_REPLAY_SCHEMA

    def _identity(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "goal_id": self.goal_id,
            "route": self.route.value,
            "selected_bindings": self.selected_bindings,
            "operation_count": self.operation_count,
            "lookup_count": self.lookup_count,
            "memo_hit_count": self.memo_hit_count,
            "neural_calls": self.neural_calls,
            "local_refinement_calls": self.local_refinement_calls,
            "source_binding_digest": self.source_binding_digest,
            "generation_digest": self.generation_digest,
            "semantic_release": self.semantic_release,
            "rights_epoch": self.rights_epoch,
            "correction_generation": self.correction_generation,
            "outcome_type": self.outcome_type,
            "outcome_state": self.outcome_state.value,
            "outcome_digest": self.outcome_digest,
            "score": self.score,
            "fallback_reason": self.fallback_reason,
            "visibility": self.visibility,
        }

    def __post_init__(self) -> None:
        if (not isinstance(self.goal_id, str) or not self.goal_id
                or not isinstance(self.route, RouteKind)
                or not isinstance(self.selected_bindings, tuple)
                or any(not isinstance(item, tuple) or len(item) != 4
                       or type(item[0]) is not int or item[0] < 0
                       or not isinstance(item[1], str) or not item[1]
                       or not isinstance(item[2], str) or not item[2]
                       or not isinstance(item[3], tuple)
                       or any(not isinstance(ref, str) or not ref
                              for ref in item[3])
                       for item in self.selected_bindings)
                or any(type(value) is not int or value < 0 for value in (
                    self.operation_count, self.lookup_count,
                    self.memo_hit_count, self.neural_calls,
                    self.local_refinement_calls, self.rights_epoch,
                    self.correction_generation))
                or not all(_sha(item) for item in (
                    self.source_binding_digest, self.generation_digest,
                    self.semantic_release, self.outcome_digest,
                    self.receipt_digest))
                or not isinstance(self.outcome_type, str)
                or not self.outcome_type
                or not isinstance(self.outcome_state, ValueState)
                or (self.fallback_reason is not None
                    and (not isinstance(self.fallback_reason, str)
                         or not self.fallback_reason))
                or self.visibility != "INTERNAL_ONLY"
                or self.schema_version != SOLVE_REPLAY_SCHEMA
                or self.receipt_digest != _digest(self._identity())):
            _invalid("BAMF_C04_REPLAY_RECEIPT_INVALID")

    @property
    def canonical_json(self) -> str:
        return _canonical({
            **self._identity(), "receipt_digest": self.receipt_digest})


def make_replay_receipt(
    *, goal_id: str, route: RouteKind,
    receipts: tuple[DAGReceipt, ...], answer: TypedValue,
    neural_calls: int, local_refinement_calls: int,
    source_binding_digest: str, generation_digest: str,
    rights_epoch: int, correction_generation: int,
    score: float | None, fallback_reason: str | None,
) -> SolveReplayReceipt:
    if (not isinstance(receipts, tuple) or not receipts
            or any(not isinstance(item, DAGReceipt) for item in receipts)
            or not isinstance(answer, TypedValue)):
        _invalid("BAMF_C04_REPLAY_ARGUMENT_INVALID")
    selected = tuple(
        (index, node_id, operator_id, refs)
        for index, receipt in enumerate(receipts)
        for node_id, operator_id, refs in receipt.selected_bindings)
    fields = {
        "goal_id": goal_id,
        "route": route,
        "selected_bindings": selected,
        "operation_count": sum(item.operation_count for item in receipts),
        "lookup_count": sum(item.lookup_count for item in receipts),
        "memo_hit_count": sum(item.memo_hit_count for item in receipts),
        "neural_calls": neural_calls,
        "local_refinement_calls": local_refinement_calls,
        "source_binding_digest": source_binding_digest,
        "generation_digest": generation_digest,
        "semantic_release": answer.semantic_release,
        "rights_epoch": rights_epoch,
        "correction_generation": correction_generation,
        "outcome_type": answer.type_name,
        "outcome_state": answer.state,
        "outcome_digest": contract_digest(answer),
        "score": score,
        "fallback_reason": fallback_reason,
    }
    identity = {
        **fields,
        "route": route.value,
        "outcome_state": answer.state.value,
        "visibility": "INTERNAL_ONLY",
        "schema_version": SOLVE_REPLAY_SCHEMA,
    }
    return SolveReplayReceipt(
        **fields, receipt_digest=_digest(identity))
