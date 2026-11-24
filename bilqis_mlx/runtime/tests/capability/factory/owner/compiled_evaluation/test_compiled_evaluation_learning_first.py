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
    def test_prevalidated_learning_first_bind_skips_strict_revalidation(self):
        compiled = compiled_case()
        source_context = SimpleNamespace(
            run_dir=Path("."),
            release=SimpleNamespace(
                release_sha256="a" * 64,
                semantic_catalog_sha256="b" * 64,
                verify=lambda: (_ for _ in ()).throw(
                    AssertionError("ordinary C05 reverified release")),
                verify_semantic_catalog=lambda _graph: (_ for _ in ()).throw(
                    AssertionError("ordinary C05 reverified catalog")),
            ),
            graph={},
            require_accepted_runtime=lambda _run_dir: (_ for _ in ()).throw(
                AssertionError("ordinary C05 rebound accepted runtime")),
        )
        candidate = SimpleNamespace(
            compiler_features={"compiler_sha256": "3" * 64},
            extents=object(),
        )

        class Authenticated:
            selection = SimpleNamespace(identity=object())
            schema = object()
            features = SimpleNamespace(semantic_release=RELEASE)
            snapshot = object()

            def __post_init__(self):
                raise AssertionError("ordinary C05 revalidated feature context")

        class Batch(SimpleNamespace):
            def __post_init__(self):
                return None

        def batch(*args, **kwargs):
            return Batch(
                compiled=args[0], sources=args[1], feature_schema=args[2],
                active_semantic_rows=args[3], task_authority=kwargs.get("task_authority"))

        authority = object()
        with (
            evidence_mode(strict=False),
            patch.object(
                evaluation_binding.CompiledFactoryEvaluationCase, "__post_init__",
                side_effect=AssertionError("ordinary C05 revalidated compiled case")),
            patch.object(evaluation_binding, "CompiledEncoderInput", return_value="compiled"),
            patch.object(
                evaluation_binding, "_source_atom_row",
                return_value="source") as source_row,
            patch.object(
                evaluation_binding, "BamfCompiledBatch",
                side_effect=batch) as batch_constructor,
            patch.object(
                evaluation_binding, "_reissue_validated_task_authority",
                side_effect=lambda value, task_authority: Batch(**{
                    **value.__dict__, "task_authority": task_authority})),
            patch.object(
                evaluation_binding, "bind_candidate_active_semantic_rows",
                return_value="active"),
            patch.object(
                evaluation_binding, "rebind_factory_task_authority",
                return_value=authority),
        ):
            rebound, actual = evaluation_binding.bind_factory_evaluation_case(
                source_context, candidate, "artifact", compiled,
                {"id": "row-1", "capability": "A.IDENTITY", "tokens": [1]},
                generation="8" * 64, source_seed=17, source_each=1,
                authenticated=Authenticated(), release_prevalidated=True)

        self.assertIs(actual, authority)
        self.assertIs(rebound.task_authority, authority)
        self.assertEqual(batch_constructor.call_count, 1)
        source_row.assert_called_once_with(
            source_context, unittest.mock.ANY,
            {"id": "row-1", "capability": "A.IDENTITY", "tokens": [1]},
            source_seed=17, source_each=1, learning_first=True)

    def test_learning_first_source_row_carries_authenticated_abi_indices(self):
        row = {
            "id": "row-1", "capability": "A.IDENTITY",
            "generator": "fixture", "tokens": [0, 1],
        }
        graph = {
            "tokens": ["ALPHA", "BETA"],
            "nodes": [{"semantic_id": "alpha"}, {"semantic_id": "beta"}],
        }
        source_context = SimpleNamespace(
            source_root=Path("."),
            release=SimpleNamespace(curriculum=None),
            execution_for=lambda _capability: SimpleNamespace(provider_parameters=()),
        )
        selection = object()
        snapshot = SimpleNamespace(
            abi=lambda index: SimpleNamespace(
                symbol=("ALPHA" if index == 0 else "WRONG"), index=index),
            abi_for_semantic=lambda semantic_id: SimpleNamespace(
                symbol=semantic_id.upper(), index=7),
        )
        authenticated = SimpleNamespace(selection=selection, snapshot=snapshot)

        with patch.object(evaluation_binding, "canonical_graph_for", return_value=graph):
            source = evaluation_binding._source_atom_row(
                source_context, authenticated, row,
                source_seed=17, source_each=1, learning_first=True)
            strict_source = evaluation_binding._source_atom_row(
                source_context, authenticated, row,
                source_seed=17, source_each=1, learning_first=False)

        self.assertEqual(source.learning_abi_indices, (0, 7))
        self.assertIsNone(strict_source.learning_abi_indices)

    def test_learning_first_task_rebind_skips_reverification(self):
        compiled = compiled_case()
        template = compiled.task_template
        source_context = object.__new__(SourceExecutionContext)
        object.__setattr__(
            source_context, "release",
            SimpleNamespace(release_sha256=template.release_sha256))
        batch = object.__new__(BamfCompiledBatch)
        object.__setattr__(batch, "sources", (SimpleNamespace(source_row={
            "id": template.source_row_id, "capability": template.capability_id}),))
        object.__setattr__(batch, "compiled", SimpleNamespace(
            features=SimpleNamespace(semantic_release=template.goal.semantic_release)))
        object.__setattr__(batch, "training_authority", None)

        with (
            evidence_mode(strict=False),
            patch.object(
                SourceExecutionContext, "__post_init__",
                side_effect=AssertionError("learning-first rebound source context")),
            patch.object(
                BamfCompiledBatch, "__post_init__",
                side_effect=AssertionError("learning-first revalidated compiled batch")),
            patch.object(
                task_authority_module.FactoryTaskTemplate, "__post_init__",
                side_effect=AssertionError("learning-first revalidated task template")),
            patch.object(
                task_authority_module, "source_content_digest",
                side_effect=AssertionError("learning-first rehashed source row")),
            patch.object(
                task_authority_module, "contract_digest",
                side_effect=AssertionError("learning-first rehashed task binding")),
        ):
            authority = task_authority_module.rebind_factory_task_authority(
                source_context, batch, template, generation_binding="8" * 64)

        self.assertEqual(authority.generation_binding, "8" * 64)
        self.assertEqual(authority.source_binding_sha256, template.source_binding_sha256)
        self.assertEqual(authority.source_row_sha256, template.source_row_sha256)
