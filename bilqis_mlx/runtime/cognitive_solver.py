"""C04.1 source-bound exact/cache/neural DAG routing without grade branches."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Callable

from ..errors import BilqisError, ErrorBus, SCHOOL
from ..semantics.cognitive_dag import (
    DAGBudget, DAGReceipt, TaskGoal, execute_dag,
)
from ..semantics.cognitive_operators import (
    OperatorBinding, TypedValue, ValueState,
)
from ..semantics.domains import contract_digest
from ..semantics.memo import PureOperationMemo
from .operator_registry import (
    RouteKind, RouteRegistry, default_route_registry,
)


from ._cognitive_solver.contracts import (
    GENERATION_BINDING_SCHEMA, QUALIFIED_COMPOSITION_SCHEMA, SOLVE_BUDGET_SCHEMA, SOLVE_CONTEXT_SCHEMA, NEURAL_REQUEST_SCHEMA, NEURAL_PROPOSAL_SCHEMA, CAPABILITY_RESULT_SCHEMA, SOLVE_REPLAY_SCHEMA, MAX_CACHED_COMPOSITIONS, MAX_NEURAL_CALLS, _SHA256, _invalid, _sha, _name, GenerationBinding, QualifiedComposition, SolveBudget, NeuralRequest, NeuralProposal, SolveContext
)
from ._cognitive_solver.results import CapabilityResult
from ._cognitive_solver.policy import _fills_declared_holes, _goal_allowed
from ._cognitive_solver.execution import _solve_task


for _owned in (GenerationBinding, QualifiedComposition, SolveBudget, NeuralRequest, NeuralProposal, SolveContext, CapabilityResult, _invalid, _sha, _name, _fills_declared_holes, _goal_allowed):
    _owned.__module__ = __name__
del _owned


def solve_task(
    task: TaskGoal, context: SolveContext,
    generation: GenerationBinding, budget: SolveBudget,
) -> CapabilityResult:
    """Exact first, qualified cached second, one bounded neural DAG last."""
    return _solve_task(task, context, generation, budget)
