"""Evaluator-side complete-solver measurements and advisory paired eligibility."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Callable

from ..errors import ErrorBus, SCHOOL
from ..learning.retention_policy import retention_reason, scaled_loss_allowance
from ..semantics.cognitive_dag import TaskGoal
from ..semantics.cognitive_operators import TypedValue, ValueState
from ..semantics.foundation.domains import contract_digest
from .cognitive_solver import (
    CapabilityResult, GenerationBinding, SolveBudget, SolveContext, solve_task,
)


def _invalid(reason):
    ErrorBus.raise_(SCHOOL.BAMF_CAPABILITY_EVIDENCE.INVALID, reason=reason)


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _names(values):
    return (isinstance(values, tuple)
            and all(isinstance(value, str) and value for value in values)
            and len(set(values)) == len(values))


class EvidenceKind(str, Enum):
    FRESH_TARGET = "FRESH_TARGET"
    FRESH_LESSON = "FRESH_LESSON"
    FIXED_SCHOOL = "FIXED_SCHOOL"


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    capability_id: str
    group_id: str
    source_family_id: str
    episode_id: str
    goal: TaskGoal
    gold: TypedValue

    def __post_init__(self):
        if (not all(isinstance(value, str) and value for value in (
                self.case_id, self.capability_id, self.group_id,
                self.source_family_id, self.episode_id))
                or not isinstance(self.goal, TaskGoal)
                or not isinstance(self.gold, TypedValue)
                or self.gold.semantic_release != self.goal.semantic_release
                or self.gold.type_name != self.goal.output_signature
                or self.gold.state is ValueState.UNRESOLVED):
            _invalid("BAMF_EVALUATION_CASE_INVALID")


def case_census_digest(cases: tuple[EvaluationCase, ...]) -> str:
    """Bind the independent source draw, including exact rows and evaluator gold."""
    return contract_digest(cases)


@dataclass(frozen=True)
class EvaluationCohort:
    kind: EvidenceKind
    cases: tuple[EvaluationCase, ...]
    capability_groups: tuple[tuple[str, str], ...]
    rubric_sha256: str
    scope_sha256: str
    source_sha256: str
    policy_sha256: str
    training_family_ids: tuple[str, ...]
    training_episode_ids: tuple[str, ...]
    expected_case_digest: str
    schema_version: str = "bilqis.c05.evaluation-cohort/v1"

    def __post_init__(self):
        if (not isinstance(self.kind, EvidenceKind)
                or not isinstance(self.cases, tuple) or not self.cases
                or any(not isinstance(case, EvaluationCase) for case in self.cases)
                or not isinstance(self.capability_groups, tuple)
                or any(not isinstance(pair, tuple) or len(pair) != 2
                       or not all(isinstance(item, str) and item for item in pair)
                       for pair in self.capability_groups)
                or len(dict(self.capability_groups)) != len(self.capability_groups)
                or not all(_sha(value) for value in (
                    self.rubric_sha256, self.scope_sha256, self.source_sha256,
                    self.policy_sha256, self.expected_case_digest))
                or not _names(self.training_family_ids)
                or not _names(self.training_episode_ids)
                or self.schema_version != "bilqis.c05.evaluation-cohort/v1"):
            _invalid("BAMF_EVALUATION_COHORT_INVALID")
        if (case_census_digest(self.cases) != self.expected_case_digest
                or len({case.case_id for case in self.cases}) != len(self.cases)
                or len({case.episode_id for case in self.cases}) != len(self.cases)
                or {(case.capability_id, case.group_id) for case in self.cases}
                != set(self.capability_groups)):
            _invalid("BAMF_EVALUATION_CENSUS_DRIFT")
        if self.kind is not EvidenceKind.FIXED_SCHOOL and (
                {case.source_family_id for case in self.cases}
                & set(self.training_family_ids)
                or {case.episode_id for case in self.cases}
                & set(self.training_episode_ids)):
            _invalid("BAMF_EVALUATION_TRAINING_PROVENANCE_OVERLAP")


@dataclass(frozen=True)
class CompleteSolver:
    """Bind the actual solver to task-local source and one opaque generation ID."""
    context_for: Callable[[TaskGoal, str], SolveContext]
    budget: SolveBudget

    def __post_init__(self):
        if not callable(self.context_for) or not isinstance(self.budget, SolveBudget):
            _invalid("BAMF_COMPLETE_SOLVER_INVALID")

    def evaluate(self, goal: TaskGoal, generation: str):
        context = self.context_for(goal, generation)
        if not isinstance(context, SolveContext):
            _invalid("BAMF_SOLVER_SOURCE_CONTEXT_INVALID")
        binding = GenerationBinding(
            generation, goal.semantic_release, contract_digest(context.binding))
        result = solve_task(goal, context, binding, self.budget)
        tools = contract_digest({
            "budget": self.budget, "routes": context.route_registry,
            "operators": context.binding.registry})
        return result, tools


def _answer_identity(answer):
    return (answer.type_name, answer.state, answer.semantic_release,
            contract_digest(answer.value))


@dataclass(frozen=True)
class Assessment:
    cohort: EvaluationCohort
    generation_digest: str
    results: tuple[CapabilityResult, ...]
    solver_contracts: tuple[str, ...]
    schema_version: str = "bilqis.c05.assessment/v1"

    def __post_init__(self):
        if (not isinstance(self.cohort, EvaluationCohort)
                or not _sha(self.generation_digest)
                or not isinstance(self.results, tuple)
                or len(self.results) != len(self.cohort.cases)
                or any(not isinstance(result, CapabilityResult) for result in self.results)
                or not isinstance(self.solver_contracts, tuple)
                or len(self.solver_contracts) != len(self.results)
                or any(not _sha(value) for value in self.solver_contracts)
                or self.schema_version != "bilqis.c05.assessment/v1"):
            _invalid("BAMF_ASSESSMENT_INVALID")
        if any(result.generation_digest != self.generation_digest
               or result.task_sha256 != contract_digest(case.goal)
               for case, result in zip(self.cohort.cases, self.results)):
            _invalid("BAMF_ASSESSMENT_GENERATION_OR_TASK_DRIFT")

    def score(self, capability: str):
        paired = tuple((case, result) for case, result in zip(self.cohort.cases, self.results)
                       if case.capability_id == capability)
        if not paired:
            _invalid("BAMF_ASSESSMENT_CAPABILITY_ABSENT")
        return (sum(_answer_identity(result.answer) == _answer_identity(case.gold)
                    for case, result in paired), len(paired))

    def digest(self):
        return contract_digest({
            "schema": self.schema_version, "cohort": self.cohort,
            "generation": self.generation_digest, "contracts": self.solver_contracts,
            "results": tuple(result.replay_record() for result in self.results)})


def evaluate_capabilities(solver, cohort, generation) -> Assessment:
    if (not isinstance(solver, CompleteSolver)
            or not isinstance(cohort, EvaluationCohort) or not _sha(generation)):
        _invalid("BAMF_ASSESSMENT_INPUT_INVALID")
    measurements = tuple(solver.evaluate(case.goal, generation) for case in cohort.cases)
    return Assessment(cohort, generation, tuple(item[0] for item in measurements),
                      tuple(item[1] for item in measurements))


@dataclass(frozen=True)
class AssessmentPair:
    parent: Assessment
    candidate: Assessment

    def __post_init__(self):
        if (not isinstance(self.parent, Assessment)
                or not isinstance(self.candidate, Assessment)
                or self.parent.cohort != self.candidate.cohort
                or self.parent.solver_contracts != self.candidate.solver_contracts
                or tuple(result.source_binding_digest for result in self.parent.results)
                != tuple(result.source_binding_digest for result in self.candidate.results)):
            _invalid("BAMF_PAIRED_ASSESSMENT_CONTRACT_DRIFT")

    def delta(self, capability):
        return self.candidate.score(capability)[0] - self.parent.score(capability)[0]


@dataclass(frozen=True)
class RetentionPolicy:
    capability_groups: tuple[tuple[str, str], ...]
    protected_groups: tuple[str, ...]
    protected_reference_losses: tuple[tuple[str, int], ...]
    probe_each: int
    required_census_digests: tuple[tuple[EvidenceKind, str], ...]
    schema_version: str = "bilqis.c05.retention-policy/v1"

    def __post_init__(self):
        if (not isinstance(self.capability_groups, tuple) or not self.capability_groups
                or any(not isinstance(pair, tuple) or len(pair) != 2
                       or not all(isinstance(item, str) and item for item in pair)
                       for pair in self.capability_groups)
                or len(dict(self.capability_groups)) != len(self.capability_groups)
                or not _names(self.protected_groups)
                or not set(self.protected_groups) <= set(dict(self.capability_groups).values())
                or type(self.probe_each) is not int or not 2 <= self.probe_each <= 48
                or not isinstance(self.protected_reference_losses, tuple)
                or any(not isinstance(pair, tuple) or len(pair) != 2
                       or pair[0] not in dict(self.capability_groups)
                       or type(pair[1]) is not int or not 0 <= pair[1] <= self.probe_each
                       for pair in self.protected_reference_losses)
                or len(dict(self.protected_reference_losses)) != len(self.protected_reference_losses)
                or not isinstance(self.required_census_digests, tuple)
                or any(not isinstance(pair, tuple) or len(pair) != 2
                       or not isinstance(pair[0], EvidenceKind) or not _sha(pair[1])
                       for pair in self.required_census_digests)
                or len(self.required_census_digests) != 3
                or set(dict(self.required_census_digests)) != set(EvidenceKind)
                or self.schema_version != "bilqis.c05.retention-policy/v1"):
            _invalid("BAMF_RETENTION_POLICY_INVALID")

    def digest(self):
        return contract_digest(self)


@dataclass(frozen=True)
class PairedRetentionEvidence:
    target_capability: str
    policy: RetentionPolicy
    target: AssessmentPair
    fresh_lesson: AssessmentPair
    fixed_school: AssessmentPair

    def __post_init__(self):
        if (not isinstance(self.policy, RetentionPolicy)
                or not all(isinstance(pair, AssessmentPair) for pair in (
                    self.target, self.fresh_lesson, self.fixed_school))
                or self.target_capability not in dict(self.policy.capability_groups)):
            _invalid("BAMF_RETENTION_EVIDENCE_INVALID")
        target_group = dict(self.policy.capability_groups)[self.target_capability]
        pairs = (self.target, self.fresh_lesson, self.fixed_school)
        cohorts = tuple(pair.parent.cohort for pair in pairs)
        expected = (
            {(self.target_capability, target_group)},
            {item for item in self.policy.capability_groups if item[1] == target_group},
            set(self.policy.capability_groups))
        if (target_group not in self.policy.protected_groups
                or set(dict(self.policy.protected_reference_losses))
                != set(dict(self.policy.capability_groups)) - {self.target_capability}
                or tuple(cohort.kind for cohort in cohorts) != (
                    EvidenceKind.FRESH_TARGET, EvidenceKind.FRESH_LESSON,
                    EvidenceKind.FIXED_SCHOOL)
                or any(set(cohort.capability_groups) != required
                       for cohort, required in zip(cohorts, expected))
                or len({(cohort.rubric_sha256, cohort.scope_sha256,
                         cohort.source_sha256, cohort.policy_sha256)
                        for cohort in cohorts}) != 1
                or any(cohort.policy_sha256 != self.policy.digest()
                       or cohort.expected_case_digest
                       != dict(self.policy.required_census_digests)[cohort.kind]
                       for cohort in cohorts)
                or len({self.fresh_lesson.parent.score(capability)[1]
                        for capability, _ in self.fresh_lesson.parent.cohort.capability_groups}) != 1
                or len({pair.parent.generation_digest for pair in pairs}) != 1
                or len({pair.candidate.generation_digest for pair in pairs}) != 1):
            _invalid("BAMF_RETENTION_COMPLETE_COVERAGE_REQUIRED")

    def digest(self):
        return contract_digest(tuple((pair.parent.digest(), pair.candidate.digest())
                                     for pair in (self.target, self.fresh_lesson,
                                                  self.fixed_school)))


class DecisionStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    REJECT = "REJECT"


class WorkDisposition(str, Enum):
    REHEARSE_OR_ADVANCE = "REHEARSE_OR_ADVANCE"
    OPTIMIZER_CANDIDATE = "OPTIMIZER_CANDIDATE"


@dataclass(frozen=True)
class Decision:
    status: DecisionStatus
    reason: str
    parent_generation: str
    candidate_generation: str
    evidence_sha256: str
    policy_sha256: str
    schema_version: str = "bilqis.c05.retention-decision/v1"

    def __post_init__(self):
        if (not isinstance(self.status, DecisionStatus)
                or not isinstance(self.reason, str) or not self.reason
                or not all(_sha(value) for value in (
                    self.parent_generation, self.candidate_generation,
                    self.evidence_sha256, self.policy_sha256))
                or self.schema_version != "bilqis.c05.retention-decision/v1"):
            _invalid("BAMF_RETENTION_DECISION_INVALID")


@dataclass(frozen=True)
class ConfigurationOutcome:
    parent_assessment_sha256: str
    candidate_assessment_sha256: str
    net_correct_delta: int
    optimizer_steps: int = field(default=0, init=False)
    schema_version: str = field(default="bilqis.c05.configuration-outcome/v1", init=False)


def configuration_outcome(pair: AssessmentPair) -> ConfigurationOutcome:
    if not isinstance(pair, AssessmentPair):
        _invalid("BAMF_CONFIGURATION_ASSESSMENT_REQUIRED")
    return ConfigurationOutcome(
        pair.parent.digest(), pair.candidate.digest(),
        sum(pair.delta(capability) for capability, _ in pair.parent.cohort.capability_groups))


def candidate_work_disposition(parent: Assessment, capability: str) -> WorkDisposition:
    if not isinstance(parent, Assessment):
        _invalid("BAMF_CANDIDATE_PARENT_ASSESSMENT_REQUIRED")
    correct, total = parent.score(capability)
    source_only = all(result.neural_calls == 0
                      for case, result in zip(parent.cohort.cases, parent.results)
                      if case.capability_id == capability)
    return (WorkDisposition.REHEARSE_OR_ADVANCE if correct == total and source_only
            else WorkDisposition.OPTIMIZER_CANDIDATE)


def retain_candidate(parent, candidate, paired_assessment) -> Decision:
    """Return eligibility evidence; B12/B13 alone own actual state publication."""
    evidence = paired_assessment
    if (not isinstance(evidence, PairedRetentionEvidence)
            or parent != evidence.target.parent.generation_digest
            or candidate != evidence.target.candidate.generation_digest):
        _invalid("BAMF_RETENTION_GENERATION_DRIFT")
    target = evidence.target_capability
    census = dict(evidence.policy.capability_groups)
    fixed = evidence.fixed_school
    def net(pair, capabilities):
        return sum(pair.delta(capability) for capability in capabilities)
    lesson = tuple(cap for cap, group in census.items() if group == census[target])
    exceeded = any(
        -pair.delta(capability) > scaled_loss_allowance(
            pair.parent.score(capability)[1], reference, evidence.policy.probe_each)
        for pair in (evidence.fresh_lesson, fixed)
        for capability, reference in evidence.policy.protected_reference_losses
        if capability in dict(pair.parent.cohort.capability_groups))
    reason = retention_reason(
        no_target_gain=evidence.target.delta(target) <= 0,
        same_grade_net_gain=net(evidence.fresh_lesson, lesson),
        fixed_grade_regression=net(fixed, lesson) < 0,
        active_grade_regression=any(
            net(fixed, tuple(cap for cap, group in census.items() if group == protected)) < 0
            for protected in evidence.policy.protected_groups),
        whole_school_regression=net(fixed, census) < 0,
        frontier_measured=True, fragile_losses=False, exceeded=exceeded)
    return Decision(DecisionStatus.ELIGIBLE if reason == "PAIRED_SCREEN_WITHIN_BUDGET"
                    else DecisionStatus.REJECT,
                    reason, parent, candidate, evidence.digest(), evidence.policy.digest())
