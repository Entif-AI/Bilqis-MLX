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


from .contracts import (GenerationBinding, QualifiedComposition, SolveBudget, NeuralRequest, NeuralProposal, SolveContext, _invalid)
from .results import CapabilityResult
from .policy import _goal_allowed


from .session import _SolveSession
from . import routes


def _solve_task(
    task: TaskGoal, context: SolveContext,
    generation: GenerationBinding, budget: SolveBudget,
) -> CapabilityResult:
    """Exact first, qualified cached second, one bounded neural DAG last."""
    if (not isinstance(task, _public().TaskGoal)
            or not isinstance(context, _public().SolveContext)
            or not isinstance(generation, _public().GenerationBinding)
            or not isinstance(budget, _public().SolveBudget)):
        _public()._invalid("BAMF_C04_SOLVE_ARGUMENT_INVALID")
    binding = context.binding
    source_digest = _public().contract_digest(binding)
    if (task.semantic_release != binding.task.semantic_release
            or task.scope != binding.task.scope
            or generation.semantic_release != task.semantic_release
            or generation.source_binding_digest != source_digest
            or not _public()._goal_allowed(task, task, budget)):
        _public()._invalid("BAMF_C04_SOLVE_SOURCE_DRIFT")
    if len(context.qualified_compositions) > budget.max_cached_candidates:
        _public()._invalid("BAMF_C04_CACHED_CANDIDATE_BUDGET_EXCEEDED")
    session = _SolveSession(task, context, generation, budget, binding, source_digest)
    for route in context.route_registry.specs:
        if route.kind is _public().RouteKind.EXACT:
            solved = routes.exact(session)
        elif route.kind is _public().RouteKind.CACHED_COMPOSITION:
            solved = routes.cached(session)
        elif route.kind is _public().RouteKind.NEURAL_COMPOSITION:
            solved = routes.neural(session)
        elif route.kind is _public().RouteKind.DETERMINISTIC_FALLBACK:
            solved = routes.fallback(session)
        else:
            return session.result(
                session.unresolved_answer, _public().RouteKind.UNRESOLVED,
                session.neural_calls)
        if solved is not routes._CONTINUE:
            return solved
    _public()._invalid("BAMF_C04_ROUTE_REGISTRY_INCOMPLETE")
