"""Compact support contracts for Factory complete-solver construction."""
from __future__ import annotations

from dataclasses import dataclass

from bilqis_mlx.runtime.backbone_identity import issue_execution_generation_binding
from bilqis_mlx.runtime.bamf_bundle import (
    AuthenticatedCheckpointFeatureContext, BamfBundleCandidate,
)
from bilqis_mlx.runtime.capability_retention import EvaluationCase
from bilqis_mlx.runtime.source_execution import SourceExecutionContext
from bilqis_mlx.semantics.cognitive_dag import DAGResult, TaskGoal
from bilqis_mlx.semantics.cognitive_operators import OperatorBinding, TypedValue

from ..capability_evaluation import _invalid
from ..factory_evaluation_compiler import CompiledFactoryEvaluationCase
from ..factory_task_template import _source_task_owner, _source_view


@dataclass(frozen=True)
class FactoryEvaluationInstrument:
    case: EvaluationCase
    compiled_case: CompiledFactoryEvaluationCase
    source_row: dict
    source_seed: int
    source_each: int
    release_prevalidated: bool = False
    prevalidated_exact_result: DAGResult | None = None

    def __post_init__(self):
        if (type(self.case) is not EvaluationCase
                or type(self.compiled_case) is not CompiledFactoryEvaluationCase
                or self.compiled_case.task_template.source_row_id != self.case.case_id
                or not isinstance(self.source_row, dict)
                or self.source_row.get("id") != self.case.case_id
                or type(self.source_seed) is not int or self.source_seed < 0
                or type(self.source_each) is not int or self.source_each < 1
                or type(self.release_prevalidated) is not bool
                or (self.prevalidated_exact_result is not None
                    and (not isinstance(self.prevalidated_exact_result, DAGResult)
                         or self.prevalidated_exact_result.receipt.source_binding_digest
                         != self.compiled_case.task_template.source_binding_sha256
                         or self.prevalidated_exact_result.receipt.semantic_release
                         != self.case.goal.semantic_release
                         or self.prevalidated_exact_result.answer.semantic_release
                         != self.case.goal.semantic_release))):
            _invalid("BAMF_C05_FACTORY_INSTRUMENT_INVALID")


def _execution_binding(
        candidate: BamfBundleCandidate, parameters=None, *, execution_cache=None):
    if not isinstance(candidate, BamfBundleCandidate):
        _invalid("BAMF_C05_CANDIDATE_REQUIRED")
    parameters = (
        candidate.retained_state.optimizer.parameters
        if parameters is None else parameters
    )
    if execution_cache is None:
        from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
            strict_evidence_enabled,
        )
        if not strict_evidence_enabled():
            from bilqis_mlx.runtime.candidate.step_authority import (
                current_learning_first_step_authority_for_parameters,
            )
            token = current_learning_first_step_authority_for_parameters(parameters)
            if token is not None:
                from bilqis_mlx.runtime.backbone_identity import (
                    issue_learning_first_execution_generation_binding,
                )
                return issue_learning_first_execution_generation_binding(
                    parameters, spec=candidate.topology, extents=candidate.extents,
                    generation=token)
            from bilqis_mlx.runtime.candidate.step_authority import (
                record_learning_first_full_proof_fallback,
            )
            record_learning_first_full_proof_fallback()
        return issue_execution_generation_binding(
            parameters, spec=candidate.topology, extents=candidate.extents)
    from bilqis_mlx.runtime.bamf_bundle.execution_cache import (
        bind_execution_generation,
    )
    return bind_execution_generation(
        execution_cache, parameters,
        spec=candidate.topology, extents=candidate.extents)


def _accepted_solver_feature_context(source_context, candidate):
    """Reuse current checkpoint-backed feature authority for an accepted parent."""
    context = getattr(source_context, "_accepted_feature_context", None)
    if type(context) is not AuthenticatedCheckpointFeatureContext:
        from bilqis_mlx.runtime.bamf_bundle.accepted_runtime import (
            bind_accepted_execution_feature_context,
        )
        context = bind_accepted_execution_feature_context(
            source_context.run_dir, candidate, None)
    receipt = context.commitment.receipt
    if (receipt.run_id != candidate.run_id
            or receipt.generation != candidate.generation
            or receipt.feature_sha256 != candidate.extents.factor_map_digest
            or receipt.active_set_sha256 != candidate.extents.active_semantic_digest
            or receipt.implementation_sha256 != candidate.implementation_sha256):
        _invalid("BAMF_C05_ACCEPTED_FEATURE_CONTEXT_DRIFT")
    return context


def _factory_gold(source_context, row, goal):
    try:
        execution = source_context.execution_for(row.get("capability"))
    except Exception:
        _invalid("BAMF_C05_GOLD_CAPABILITY_MISSING")
        raise AssertionError
    raw = row.get("gold")
    if type(raw) not in (int, str):
        _invalid("BAMF_C05_GOLD_MODALITY_UNSUPPORTED")
    text = str(raw)
    matches = []
    for family in execution.answer_families:
        modality = source_context.answer_registry.require(family.kind)
        active = modality.canonicalize(tuple(family.values))
        if text in active:
            matches.append(family.kind)
    if len(matches) != 1:
        _invalid("BAMF_C05_GOLD_MODALITY_AMBIGUOUS")
    family = matches[0]
    if goal.output_signature == "Number" and family == "numeric_active":
        return TypedValue("Number", int(text), goal.semantic_release)
    if goal.output_signature == "Boolean" and family == "binary":
        if text not in {"FALSE", "TRUE"}:
            _invalid("BAMF_C05_GOLD_MODALITY_UNSUPPORTED")
        return TypedValue("Boolean", text == "TRUE", goal.semantic_release)
    if goal.output_signature == "OperatorId" and family == "boolean_operator":
        return TypedValue("OperatorId", text, goal.semantic_release)
    _invalid("BAMF_C05_GOLD_MODALITY_UNSUPPORTED")


def factory_evaluation_case_from_source(
        source_context: SourceExecutionContext, row: dict, *,
        semantic_release: str) -> EvaluationCase:
    """Lower one reference-only C05 case without constructing neural inputs."""
    row_id, capability_id, execution, lowerer, family, episode = (
        _source_task_owner(source_context, row))
    lowered = lowerer.lower(
        _source_view(row),
        semantic_release=semantic_release,
        source_root=source_context.source_root,
        graph=source_context.graph,
        release=source_context.release,
        capability=execution,
    )
    if (not isinstance(lowered, tuple) or len(lowered) != 2
            or type(lowered[0]) is not TaskGoal
            or type(lowered[1]) is not OperatorBinding
            or lowered[0].goal_id != row_id):
        _invalid("BAMF_C04_SOURCE_TASK_LOWERING_INVALID")
    goal = lowered[0]
    return EvaluationCase(
        row_id, capability_id, execution.grade_id, family, episode,
        goal, _factory_gold(source_context, row, goal))
