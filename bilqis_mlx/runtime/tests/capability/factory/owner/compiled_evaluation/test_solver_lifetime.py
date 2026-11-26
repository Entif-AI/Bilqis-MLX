"""Assessment callbacks must not retain a discarded candidate until cyclic GC."""
import gc
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import weakref

import pytest

from bilqis_mlx.runtime import factory_complete_solver as complete_solver
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.capability_retention import EvaluationCase
from bilqis_mlx.runtime.retention import complete_solver_runtime
from bilqis_mlx.semantics.cognitive_operators import TypedValue
from bilqis_mlx.semantics.tests.test_frame_compiler import RELEASE
from .compiled_evaluation_fixtures import compiled_case


class Candidate:
    def __init__(self):
        self.retained_state = SimpleNamespace(
            optimizer=SimpleNamespace(parameters={}))


@pytest.mark.parametrize("batched", [False, True])
def test_discarded_assessment_releases_candidate_without_cyclic_gc(batched):
    compiled = compiled_case()
    template = compiled.task_template
    goal = template.goal
    case = EvaluationCase(
        "row-1", "A.IDENTITY", "A", "family-1", "episode-1", goal,
        TypedValue("Boolean", True, RELEASE))
    instrument = complete_solver.FactoryEvaluationInstrument(
        case, compiled, {"id": "row-1", "capability": "A.IDENTITY",
                         "tokens": [1], "gold": "TRUE"}, 17, 1)
    candidate = Candidate()
    reference = weakref.ref(candidate)
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        with (
            evidence_mode(strict=False),
            patch.object(complete_solver, "_execution_binding",
                         new=lambda *_args, **_kwargs: SimpleNamespace(
                             generation_digest="8" * 64)),
            patch.object(complete_solver, "authenticate_bamf_execution_feature_context",
                         new=lambda *_args: SimpleNamespace(snapshot=object())),
            patch.object(complete_solver, "bind_factory_evaluation_case",
                         new=lambda *_args, **_kwargs: (object(), template)),
            patch.object(complete_solver, "task_goal_route_plan",
                         new=lambda *_args: object()),
            patch.object(complete_solver, "b11_task_goal_proposer",
                         new=lambda *_args, **_kwargs: lambda _request: None),
            patch.object(complete_solver, "batched_factory_outputs",
                         new=lambda _params, prepared, **_kwargs:
                         tuple(object() for _ in prepared)),
            patch.object(complete_solver_runtime, "PreparedFactoryEvaluation",
                         new=lambda batch, plan, authority: SimpleNamespace(
                             batch=batch, plan=plan, authority=authority)),
        ):
            solver, generation = complete_solver.factory_complete_solver(
                SimpleNamespace(run_dir=Path(".")), candidate, "artifact", (instrument,))
            context = (solver.contexts_for((goal,), generation)[0] if batched
                       else solver.context_for(goal, generation))
            assert context.binding == template.binding
            del candidate
            assert reference() is not None
            del context, solver
            assert reference() is None
    finally:
        if gc_was_enabled:
            gc.enable()
        gc.collect()
