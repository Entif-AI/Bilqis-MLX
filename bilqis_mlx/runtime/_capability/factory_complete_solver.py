"""Factory-owned C05 cases and real B11/B10/C04 complete solvers."""
from __future__ import annotations

from dataclasses import dataclass

from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.bamf_bundle import (
    BamfBundleCandidate, authenticate_bamf_candidate_feature_context,
)
from bilqis_mlx.runtime.capability_retention import CompleteSolver, EvaluationCase
from bilqis_mlx.runtime.cognitive_solver import SolveBudget, SolveContext
from bilqis_mlx.runtime.source_execution import SourceExecutionContext
from bilqis_mlx.semantics.cognitive_dag import DAGBudget
from bilqis_mlx.semantics.cognitive_operators import TypedValue
from bilqis_mlx.semantics.domains import contract_digest

from .capability_evaluation import _invalid
from .factory_evaluation_compiler import compile_factory_evaluation_batch
from .factory_task_authority import factory_task_authority
from .task_goal_readout import b11_task_goal_proposer, task_goal_route_plan


@dataclass(frozen=True)
class FactoryEvaluationInstrument:
    case: EvaluationCase
    row: dict
    source_seed: int
    source_each: int

    def __post_init__(self):
        if (type(self.case) is not EvaluationCase or not isinstance(self.row, dict)
                or self.row.get("id") != self.case.case_id
                or type(self.source_seed) is not int or self.source_seed < 0
                or type(self.source_each) is not int or self.source_each < 1):
            _invalid("BAMF_C05_FACTORY_INSTRUMENT_INVALID")


def _generation(candidate: BamfBundleCandidate) -> str:
    if not isinstance(candidate, BamfBundleCandidate):
        _invalid("BAMF_C05_CANDIDATE_REQUIRED")
    return execution_generation_digest(
        candidate.retained_state.optimizer.parameters,
        spec=candidate.topology, extents=candidate.extents)


def _factory_gold(source_context, row, goal):
    execution = source_context.release.execution_plan.capability_map.get(
        row.get("capability"))
    if execution is None:
        _invalid("BAMF_C05_GOLD_CAPABILITY_MISSING")
    raw = row.get("gold")
    if goal.output_signature != "Number" or type(raw) not in (int, str):
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
    return TypedValue("Number", int(text), goal.semantic_release)


def factory_evaluation_instrument(
    source_context: SourceExecutionContext,
    candidate: BamfBundleCandidate,
    artifact_path: str,
    row: dict,
    *,
    source_seed: int,
    source_each: int,
) -> FactoryEvaluationInstrument:
    """Freeze one independent Factory row into a C05 case without solver choice."""
    generation = _generation(candidate)
    batch = compile_factory_evaluation_batch(
        source_context, candidate, artifact_path, row,
        source_seed=source_seed, source_each=source_each)
    authority = factory_task_authority(
        source_context, batch, generation_binding=generation)
    execution = source_context.release.execution_plan.capability_map[
        authority.capability_id]
    case = EvaluationCase(
        authority.source_row_id, authority.capability_id, execution.grade_id,
        authority.source_family_id, authority.episode_id, authority.goal,
        _factory_gold(source_context, row, authority.goal))
    return FactoryEvaluationInstrument(case, dict(row), source_seed, source_each)


def factory_complete_solver(
    source_context: SourceExecutionContext,
    candidate: BamfBundleCandidate,
    artifact_path: str,
    instruments: tuple[FactoryEvaluationInstrument, ...],
) -> tuple[CompleteSolver, str]:
    """Bind every case to the exact candidate parameters and real B11 proposer."""
    if (not instruments or any(type(item) is not FactoryEvaluationInstrument
                               for item in instruments)):
        _invalid("BAMF_C05_FACTORY_INSTRUMENTS_REQUIRED")
    generation = _generation(candidate)
    contexts = {}
    parameters = candidate.retained_state.optimizer.parameters
    feature_context = authenticate_bamf_candidate_feature_context(
        candidate, artifact_path)
    for instrument in instruments:
        batch = compile_factory_evaluation_batch(
            source_context, candidate, artifact_path, instrument.row,
            source_seed=instrument.source_seed, source_each=instrument.source_each)
        authority = factory_task_authority(
            source_context, batch, generation_binding=generation)
        if (authority.goal != instrument.case.goal
                or authority.source_family_id != instrument.case.source_family_id
                or authority.episode_id != instrument.case.episode_id):
            _invalid("BAMF_C05_FACTORY_INSTRUMENT_DRIFT")
        plan = task_goal_route_plan(
            authority.goal, batch, feature_context.snapshot, generation)
        proposer = b11_task_goal_proposer(
            parameters, batch, plan, authority)
        contexts[authority.goal.goal_id] = SolveContext(
            authority.binding, neural_proposer=proposer)

    def context_for(goal, requested_generation):
        if requested_generation != generation or goal.goal_id not in contexts:
            _invalid("BAMF_C05_FACTORY_SOLVER_GENERATION_OR_TASK_DRIFT")
        context = contexts[goal.goal_id]
        expected = next(item.case.goal for item in instruments
                        if item.case.case_id == goal.goal_id)
        if goal != expected:
            _invalid("BAMF_C05_FACTORY_SOLVER_SOURCE_DRIFT")
        return context

    budget = SolveBudget(DAGBudget(), max_neural_calls=1)
    return CompleteSolver(context_for, budget), generation


__all__ = (
    "FactoryEvaluationInstrument", "factory_complete_solver",
    "factory_evaluation_instrument",
)
