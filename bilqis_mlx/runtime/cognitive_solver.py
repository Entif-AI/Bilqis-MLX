"""C04.1 source-bound exact/cache/neural DAG routing without grade branches."""
from ._cognitive_solver.common import (
    CAPABILITY_RESULT_SCHEMA, GENERATION_BINDING_SCHEMA, MAX_CACHED_COMPOSITIONS,
    MAX_NEURAL_CALLS, NEURAL_PROPOSAL_SCHEMA, NEURAL_REQUEST_SCHEMA,
    QUALIFIED_COMPOSITION_SCHEMA, SOLVE_BUDGET_SCHEMA, SOLVE_CONTEXT_SCHEMA,
    SOLVE_REPLAY_SCHEMA,
)
from ._cognitive_solver.records import (
    CapabilityResult, GenerationBinding, NeuralProposal, NeuralRequest,
    QualifiedComposition, SolveBudget, SolveContext,
)
from ._cognitive_solver.execution import solve_task
from .operator_registry import RouteKind

__all__ = (
    "CAPABILITY_RESULT_SCHEMA", "GENERATION_BINDING_SCHEMA",
    "MAX_CACHED_COMPOSITIONS", "MAX_NEURAL_CALLS", "NEURAL_PROPOSAL_SCHEMA",
    "NEURAL_REQUEST_SCHEMA", "QUALIFIED_COMPOSITION_SCHEMA",
    "SOLVE_BUDGET_SCHEMA", "SOLVE_CONTEXT_SCHEMA", "SOLVE_REPLAY_SCHEMA",
    "CapabilityResult", "GenerationBinding", "NeuralProposal", "NeuralRequest",
    "QualifiedComposition", "SolveBudget", "SolveContext", "solve_task",
    "RouteKind",
)
