"""Issue #1168 cold-reuse parity and throughput regressions."""
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from bilqis_mlx.runtime.capability_retention import (
    CompleteSolver, EvidenceKind, EvidenceStage, EvaluationCase, EvaluationCohort,
    case_census_digest,
)
from bilqis_mlx.runtime.capability_retention_foundation import (
    FoundationRetentionPolicy, evaluate_foundation_fixed_school_candidate,
)
from bilqis_mlx.runtime.cognitive_solver import (
    GenerationBinding, SolveBudget, SolveContext, solve_task,
)
from bilqis_mlx.runtime.factory_compiled_cohort import (
    load_compiled_case, seal_compiled_case,
)
from bilqis_mlx.runtime.factory_complete_solver import FactoryEvaluationInstrument
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.semantics.cognitive_dag import DAGBudget
from bilqis_mlx.semantics.cognitive_operators import TypedValue
from bilqis_mlx.semantics.domains import contract_digest
from bilqis_mlx.semantics.tests.test_frame_compiler import RELEASE
import bilqis_mlx.runtime.factory_complete_solver as complete_solver
import bilqis_mlx.runtime.factory_evaluation_compiler as evaluation_compiler
import bilqis_mlx.runtime._factory_retention_support as retention_support
import bilqis_mlx.runtime.retention.evaluation_binding as evaluation_binding
import bilqis_mlx.runtime.factory_task_authority as task_authority_module
from bilqis_mlx.runtime.source_execution import SourceExecutionContext
from bilqis_mlx.runtime.atlas_model_contracts import BamfCompiledBatch

from .compiled_evaluation_fixtures import compiled_case


def _cold_case(compiled):
    directory = tempfile.TemporaryDirectory()
    root = Path(directory.name)
    artifact = seal_compiled_case(root, compiled)
    return directory, load_compiled_case(root, artifact, compiled.identity_sha256)


class CompiledEvaluationReuseTests(unittest.TestCase):
    def test_cohort_compile_authenticates_once_and_compiles_each_row_once(self):
        rows = tuple({
            "id": f"row-{index}", "capability": "A.IDENTITY",
            "tokens": [1], "gold": "TRUE",
        } for index in range(4))
        source_context = SimpleNamespace(run_dir=Path("."))

        class Authenticated:
            def __post_init__(self):
                return None

        with (
            patch.object(complete_solver, "authenticate_bamf_execution_feature_context",
                         return_value=Authenticated()) as authenticate,
            patch.object(complete_solver, "_factory_evaluation_instrument",
                         side_effect=lambda *args, **kwargs: args[3]["id"]) as compile_case,
        ):
            actual = complete_solver.factory_evaluation_instruments(
                source_context, object(), "artifact", rows, seed=19, each=1)
        self.assertEqual(actual, tuple(row["id"] for row in rows))
        self.assertEqual(authenticate.call_count, 1)
        self.assertEqual(compile_case.call_count, len(rows))

    def test_parent_candidate_solvers_add_two_generation_authentications_only(self):
        compiled = compiled_case()
        goal = compiled.task_template.goal
        from bilqis_mlx.semantics.cognitive_dag import execute_dag
        preflight = execute_dag(
            goal, compiled.task_template.binding,
            source_binding_digest=compiled.task_template.source_binding_sha256)
        case = EvaluationCase(
            "row-1", "A.IDENTITY", "A", "family-1", "episode-1", goal,
            TypedValue("Boolean", True, RELEASE))
        instrument = FactoryEvaluationInstrument(
            case, compiled, {"id": "row-1", "capability": "A.IDENTITY",
                             "tokens": [1], "gold": "TRUE"}, 17, 1,
            True, preflight)

        class SourceContext:
            run_dir = Path(".")

            def register_solve_context(self, _context):
                return None

        class Authenticated:
            snapshot = object()

            def __post_init__(self):
                return None

        candidate = SimpleNamespace(
            retained_state=SimpleNamespace(optimizer=SimpleNamespace(parameters={})))
        with evidence_mode(strict=False):
            with (
                patch.object(
                    complete_solver, "_execution_binding",
                    side_effect=(
                        SimpleNamespace(generation_digest="8" * 64),
                        SimpleNamespace(generation_digest="9" * 64),
                    ),
                ),
                patch.object(complete_solver, "authenticate_bamf_execution_feature_context",
                             return_value=Authenticated()) as authenticate,
                patch.object(complete_solver, "bind_factory_evaluation_case",
                             return_value=(object(), compiled.task_template)) as bind,
                patch.object(complete_solver, "task_goal_route_plan", return_value=object()),
                patch.object(complete_solver, "b11_task_goal_proposer",
                             return_value=lambda _request: None),
            ):
                parent_solver, parent_generation = complete_solver.factory_complete_solver(
                    SourceContext(), candidate, "artifact", (instrument,))
                candidate_solver, candidate_generation = complete_solver.factory_complete_solver(
                    SourceContext(), candidate, "artifact", (instrument,))
                parent_context = parent_solver.context_for(goal, parent_generation)
                candidate_context = candidate_solver.context_for(goal, candidate_generation)
        self.assertNotEqual(parent_generation, candidate_generation)
        self.assertIs(parent_context.prevalidated_exact_result, preflight)
        self.assertIs(candidate_context.prevalidated_exact_result, preflight)
        self.assertTrue(parent_context.prevalidated_source_authority)
        self.assertTrue(candidate_context.prevalidated_source_authority)
        self.assertIs(
            parent_context.prevalidated_exact_result,
            candidate_context.prevalidated_exact_result,
        )
        self.assertEqual(authenticate.call_count, 2)
        self.assertEqual(bind.call_count, 2)

    def test_complete_solver_source_does_not_recompile_evaluation_rows(self):
        source = Path(complete_solver.__file__).read_text()
        solver = source[source.index("def factory_complete_solver("):]
        self.assertNotIn("compile_factory_evaluation_batch(", solver)
        self.assertNotIn("factory_task_authority(", solver)


if __name__ == "__main__":
    unittest.main()
