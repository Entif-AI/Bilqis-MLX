"""Factory-owned C05 cases and real B11/B10/C04 complete solvers."""
from __future__ import annotations
from bilqis_mlx.runtime.bamf_bundle import (
    BamfBundleCandidate,
    authenticate_bamf_execution_feature_context,
)
from bilqis_mlx.runtime.capability_retention import CompleteSolver, EvaluationCase
from bilqis_mlx.runtime.source_execution import SourceExecutionContext
from bilqis_mlx.semantics.cognitive_dag import execute_dag

from .capability_evaluation import _invalid
from .factory_evaluation_batching import (
    batched_factory_outputs,
)
from .retention.complete_solver_runtime import build_factory_complete_solver
from .factory_evaluation_compiler import (
    CompiledFactoryEvaluationCase, compile_factory_evaluation_case,
)
from ._complete_solver.support import (
    FactoryEvaluationInstrument, _accepted_solver_feature_context,
    _execution_binding, _factory_gold, factory_evaluation_case_from_source,
)
from .retention.evaluation_binding import (
    bind_factory_evaluation_case, compiled_case_matches_contract,
)
from .factory_compiled_cohort import (
    compiled_cohort_candidates, compiled_cohort_record,
    load_compiled_cohort_cases, seal_compiled_case, seal_compiled_cohort,
)
from .task_goal_readout import (
    b11_task_goal_proposer, proposal_from_task_goal_output, task_goal_route_plan,
)


def _factory_evaluation_instrument(
    source_context: SourceExecutionContext,
    candidate: BamfBundleCandidate,
    artifact_path: str,
    row: dict,
    *,
    source_seed: int,
    source_each: int,
    authenticated=None,
    release_prevalidated: bool = False,
) -> FactoryEvaluationInstrument:
    """Freeze one independent Factory row into a C05 case without solver choice."""
    compiled_case = compile_factory_evaluation_case(
        source_context, candidate, artifact_path, row,
        source_seed=source_seed, source_each=source_each,
        authenticated=authenticated,
        release_prevalidated=release_prevalidated)
    return _instrument_from_compiled(
        source_context, row, compiled_case,
        source_seed=source_seed, source_each=source_each,
        release_prevalidated=release_prevalidated)


def _instrument_from_compiled(
    source_context: SourceExecutionContext,
    row: dict,
    compiled_case: CompiledFactoryEvaluationCase,
    *,
    source_seed: int,
    source_each: int,
    release_prevalidated: bool = False,
) -> FactoryEvaluationInstrument:
    authority = compiled_case.task_template
    execution = source_context.execution_for(authority.capability_id)
    case = EvaluationCase(
        authority.source_row_id, authority.capability_id, execution.grade_id,
        authority.source_family_id, authority.episode_id, authority.goal,
        _factory_gold(source_context, row, authority.goal))
    prevalidated_exact_result = None
    if release_prevalidated:
        from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
            strict_evidence_enabled,
        )
        if not strict_evidence_enabled():
            prevalidated_exact_result = execute_dag(
                authority.goal,
                authority.binding,
                source_binding_digest=authority.source_binding_sha256,
            )
    return FactoryEvaluationInstrument(
        case, compiled_case, row, source_seed, source_each,
        release_prevalidated, prevalidated_exact_result)


def factory_evaluation_instrument(
    source_context: SourceExecutionContext,
    candidate: BamfBundleCandidate,
    artifact_path: str,
    row: dict,
    *,
    source_seed: int,
    source_each: int,
) -> FactoryEvaluationInstrument:
    return _factory_evaluation_instrument(
        source_context, candidate, artifact_path, row,
        source_seed=source_seed, source_each=source_each)


def factory_evaluation_instruments(
    source_context: SourceExecutionContext,
    candidate: BamfBundleCandidate,
    artifact_path: str,
    rows,
    *,
    seed: int,
    each: int | None = None,
    source_cohort_sha256: str | None = None,
    release_prevalidated: bool = False,
    authenticated=None,
) -> tuple[FactoryEvaluationInstrument, ...]:
    """Compile one immutable cohort with one shared feature authentication."""
    rows = tuple(rows)
    if not rows:
        _invalid("BAMF_C05_FACTORY_INSTRUMENTS_REQUIRED")
    authenticated = (
        authenticate_bamf_execution_feature_context(
            candidate, artifact_path, source_context.run_dir)
        if authenticated is None else authenticated)
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_evidence_enabled,
    )
    strict = strict_evidence_enabled()
    learning_first_prevalidated = release_prevalidated and not strict
    if not learning_first_prevalidated:
        authenticated.__post_init__()
    counts = {}
    if each is None:
        for row in rows:
            capability = row.get("capability")
            counts[capability] = counts.get(capability, 0) + 1
    each_values = tuple(
        each if each is not None else counts[row.get("capability")] for row in rows)
    if source_cohort_sha256 is not None and not learning_first_prevalidated:
        candidates = compiled_cohort_candidates(
            source_context.run_dir,
            source_cohort_sha256=source_cohort_sha256,
            factory_release_sha256=source_context.release.release_sha256,
            semantic_catalog_sha256=source_context.release.semantic_catalog_sha256,
            source_seed=seed)
        for record in candidates:
            artifacts = record.get("compiled_case_artifact_sha256")
            if not isinstance(artifacts, list) or not artifacts:
                continue
            cached = load_compiled_cohort_cases(source_context.run_dir, record)
            if (len(cached) == len(rows)
                    and all(compiled_case_matches_contract(
                        source_context, candidate, artifact_path, compiled_case, row,
                        source_seed=seed, source_each=row_each,
                        authenticated=authenticated,
                        release_prevalidated=release_prevalidated)
                        for compiled_case, row, row_each in zip(
                            cached, rows, each_values))):
                return tuple(_instrument_from_compiled(
                    source_context, row, compiled_case,
                    source_seed=seed, source_each=row_each,
                    release_prevalidated=release_prevalidated)
                    for compiled_case, row, row_each in zip(
                        cached, rows, each_values))
    instruments = tuple(_factory_evaluation_instrument(
        source_context, candidate, artifact_path, row,
        source_seed=seed,
        source_each=row_each,
        authenticated=authenticated,
        release_prevalidated=release_prevalidated,
    ) for row, row_each in zip(rows, each_values))
    if source_cohort_sha256 is not None and not learning_first_prevalidated:
        artifacts = tuple(seal_compiled_case(
            source_context.run_dir, item.compiled_case) for item in instruments)
        record = compiled_cohort_record(
            factory_release_sha256=source_context.release.release_sha256,
            semantic_catalog_sha256=source_context.release.semantic_catalog_sha256,
            source_cohort_sha256=source_cohort_sha256,
            source_seed=seed,
            case_records=tuple(
                item.compiled_case.identity_record for item in instruments),
            case_artifacts=artifacts)
        seal_compiled_cohort(source_context.run_dir, record)
    return instruments


def factory_complete_solver(
    source_context: SourceExecutionContext,
    candidate: BamfBundleCandidate,
    artifact_path: str,
    instruments: tuple[FactoryEvaluationInstrument, ...],
    *,
    parameters=None,
    execution_cache=None,
    authenticated=None,
) -> tuple[CompleteSolver, str]:
    """Bind cases to one semantic candidate and one explicit read-only weight view.

    ``parameters`` exists for teacher-only frozen advisers.  It changes only the
    B11 inference weights and generation binding; source, feature, Factory and
    answer authority still come from ``candidate``.  No optimizer moments or
    continuation authority are consumed by this seam.
    """
    if (not instruments or any(type(item) is not FactoryEvaluationInstrument
                               for item in instruments)):
        _invalid("BAMF_C05_FACTORY_INSTRUMENTS_REQUIRED")
    authenticate_context = authenticate_bamf_execution_feature_context
    if execution_cache is not None:
        accepted_context = _accepted_solver_feature_context(source_context, candidate)
        authenticate_context = lambda *_args: accepted_context
    elif authenticated is not None:
        authenticate_context = lambda *_args: authenticated
    return build_factory_complete_solver(
        source_context, candidate, artifact_path, instruments,
        execution_binding=lambda owned, values: _execution_binding(
            owned, values, execution_cache=execution_cache),
        authenticate_context=authenticate_context,
        bind_case=bind_factory_evaluation_case,
        route_plan=task_goal_route_plan,
        scalar_proposer=b11_task_goal_proposer,
        proposal_from_output=proposal_from_task_goal_output,
        batched_outputs=batched_factory_outputs, parameters=parameters,
        invalid=_invalid)


__all__ = (
    "FactoryEvaluationInstrument", "factory_complete_solver",
    "factory_evaluation_instrument", "factory_evaluation_instruments",
)
