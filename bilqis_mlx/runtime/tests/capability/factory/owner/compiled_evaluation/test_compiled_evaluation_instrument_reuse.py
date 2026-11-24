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
    def test_learning_first_instrument_compile_skips_feature_revalidation(self):
        rows = ({
            "id": "row-1", "capability": "A.IDENTITY",
            "tokens": [1], "gold": "TRUE",
        },)
        source_context = SimpleNamespace(run_dir=Path("."))

        class Authenticated:
            features = SimpleNamespace(semantic_release=RELEASE)
            selection = SimpleNamespace(identity={"artifact": "selection"})
            schema = {"schema": "feature"}

            def __post_init__(self):
                raise AssertionError("learning-first revalidated feature context")

        with (
            evidence_mode(strict=False),
            patch.object(
                complete_solver, "_factory_evaluation_instrument",
                return_value="instrument") as compile_case,
        ):
            actual = complete_solver.factory_evaluation_instruments(
                source_context, object(), "artifact", rows, seed=19, each=1,
                release_prevalidated=True, authenticated=Authenticated())

        self.assertEqual(actual, ("instrument",))
        compile_case.assert_called_once()

    def test_learning_first_instruments_skip_persistent_compiled_cohort_proof(self):
        rows = ({
            "id": "row-1", "capability": "A.IDENTITY",
            "tokens": [1], "gold": "TRUE",
        },)
        source_context = SimpleNamespace(
            run_dir=Path("."),
            release=SimpleNamespace(
                release_sha256="a" * 64,
                semantic_catalog_sha256="b" * 64,
            ),
        )

        class Authenticated:
            def __post_init__(self):
                raise AssertionError("learning-first revalidated feature context")

        with (
            evidence_mode(strict=False),
            patch.object(
                complete_solver, "compiled_cohort_candidates",
                side_effect=AssertionError(
                    "learning-first scanned persistent compiled cohort proof")),
            patch.object(
                complete_solver, "seal_compiled_case",
                side_effect=AssertionError(
                    "learning-first sealed compiled case proof")),
            patch.object(
                complete_solver, "seal_compiled_cohort",
                side_effect=AssertionError(
                    "learning-first sealed compiled cohort proof")),
            patch.object(
                complete_solver, "_factory_evaluation_instrument",
                return_value="instrument") as compile_case,
        ):
            actual = complete_solver.factory_evaluation_instruments(
                source_context, object(), "artifact", rows, seed=19, each=1,
                source_cohort_sha256="c" * 64,
                release_prevalidated=True, authenticated=Authenticated())

        self.assertEqual(actual, ("instrument",))
        compile_case.assert_called_once()

    def test_learning_first_instruments_skip_dead_compiled_cohort_key(self):
        source_context = SimpleNamespace(release=SimpleNamespace(
            execution_plan=SimpleNamespace(capabilities=(
                SimpleNamespace(capability_id="A.IDENTITY"),
            ))))
        candidate = object()
        authenticated = object()
        rows = ({"id": "row-1", "capability": "A.IDENTITY"},)
        with (
            evidence_mode(strict=False),
            patch.object(
                retention_support, "assessment_scope_contract",
                side_effect=AssertionError("learning-first rebuilt assessment scope")),
            patch.object(
                retention_support, "compiled_source_cohort_digest",
                side_effect=AssertionError("learning-first hashed dead cohort cache key")),
            patch.object(
                retention_support, "factory_evaluation_instruments",
                return_value=("instrument",)) as instruments,
        ):
            actual = retention_support._instruments(
                source_context, candidate, "artifact", rows, seed=19,
                release_prevalidated=True, authenticated=authenticated)

        self.assertEqual(actual, ("instrument",))
        instruments.assert_called_once_with(
            source_context, candidate, "artifact", rows, seed=19, each=None,
            source_cohort_sha256=None, release_prevalidated=True,
            authenticated=authenticated)

    def test_learning_first_compilation_skips_forensic_case_identity(self):
        compiled = compiled_case()
        template = compiled.task_template
        batch = SimpleNamespace(compiled=SimpleNamespace(
            compiled=compiled.compiled_rows,
            compiler_configs=compiled.compiler_configs,
            source_asts=compiled.source_asts,
            partial_forest_receipts=compiled.partial_forest_receipts,
        ))
        candidate = SimpleNamespace(compiler_features={"compiler_sha256": "3" * 64})

        class Authenticated:
            features = SimpleNamespace(semantic_release=RELEASE)
            selection = SimpleNamespace(identity={"artifact": "selection"})
            schema = {"schema": "feature"}

            def __post_init__(self):
                raise AssertionError("learning-first revalidated feature context")

        with (
            evidence_mode(strict=False),
            patch.object(
                evaluation_compiler, "compile_factory_evaluation_batch",
                return_value=batch),
            patch.object(
                evaluation_compiler, "_factory_task_template_from_validated",
                return_value=template),
            patch.object(
                evaluation_compiler, "compiled_case_identity_record",
                side_effect=AssertionError(
                    "learning-first minted forensic compiled-case identity")),
        ):
            actual = evaluation_compiler.compile_factory_evaluation_case(
                SimpleNamespace(
                    run_dir=Path("."),
                    release=SimpleNamespace(
                        release_sha256="a" * 64,
                        semantic_catalog_sha256="b" * 64,
                    ),
                ),
                candidate, "artifact", {},
                source_seed=19, source_each=1, authenticated=Authenticated(),
                release_prevalidated=True)

        self.assertEqual(actual.identity_items, ())
        self.assertEqual(actual.identity_sha256, "")
