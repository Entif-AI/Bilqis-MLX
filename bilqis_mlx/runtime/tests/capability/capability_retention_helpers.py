"""Complete-solver assessment and advisory retention with source fixtures."""
from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.capability_retention import (
    AssessmentPair, CompleteSolver, EvaluationCase, EvaluationCohort,
    EvidenceKind, PairedRetentionEvidence, RetentionPolicy,
    candidate_work_disposition, case_census_digest, configuration_outcome, evaluate_capabilities, retain_candidate,
)
from bilqis_mlx.runtime.cognitive_solver import NeuralProposal, SolveBudget, SolveContext
from bilqis_mlx.semantics.cognitive_dag import DAGBudget, DAGNode
from bilqis_mlx.semantics.cognitive_operators import TypedValue
from bilqis_mlx.semantics.tests.test_cognitive_dag import _goal, _literal, _program, _result
from bilqis_mlx.semantics.tests.test_cognitive_operators import RELEASE, SCOPE, _case, _with_frame, _grant
from bilqis_mlx.semantics.context_eligibility import frame_evidence_digest, member_evidence_digest
from bilqis_mlx.semantics.frame_schema import FrameSchema, RoleSpec, make_frame_instance

PARENT = "a" * 64
CANDIDATE = "b" * 64


def _cases(capability, group, count, prefix):
    cases, contexts = [], {}
    for index in range(count):
        left, right = (index // 3) % 4 + 1, index % 3 + 1
        binding, values = _case(("Number", left), ("Number", right))
        node = DAGNode("answer", None, tuple(_literal(v) for v in values),
                       "Number", SCOPE, candidate_operator_ids=("ADD", "SUB"))
        goal = replace(_goal(_program(node), binding), goal_id=f"{prefix}:{index}")
        cases.append(EvaluationCase(
            goal.goal_id, capability, group, f"held-family:{prefix}",
            f"held-episode:{prefix}:{index}", goal,
            TypedValue("Number", left + right, RELEASE)))
        contexts[goal.goal_id] = binding
    return tuple(cases), contexts

def _solver(contexts, correct):
    def context_for(goal, generation):
        binding = contexts[goal.goal_id]
        def propose(request):
            node = goal.expression_or_holes.nodes[0]
            op = "ADD" if goal.goal_id in correct else "SUB"
            proposal = replace(goal, expression_or_holes=_program(replace(
                node, operator_id=op, candidate_operator_ids=())))
            return NeuralProposal(proposal, request.source_binding_digest,
                                  request.generation_digest,
                                  request.unresolved_signature, "c" * 64)
        return SolveContext(binding, neural_proposer=propose)
    return CompleteSolver(context_for, SolveBudget(DAGBudget()))

def _evidence(protected_loss=2, labels=("amber", "violet")):
    census = (("target", labels[0]), ("protected", labels[0]), ("other", labels[1]))
    target, a = _cases("target", labels[0], 3, "target")
    protected, b = _cases("protected", labels[0], 12, "protected")
    fresh, d = _cases("protected", labels[0], 3, "fresh")
    other, c = _cases("other", labels[1], 1, "other")
    required = ((EvidenceKind.FRESH_TARGET, case_census_digest(target)),
                (EvidenceKind.FRESH_LESSON, case_census_digest(target + fresh)),
                (EvidenceKind.FIXED_SCHOOL, case_census_digest(target + protected + other)))
    policy = RetentionPolicy(census, (labels[0], labels[1]),
                             (("other", 1), ("protected", 1)), 6, required)
    contexts = {**a, **b, **c, **d}
    before = {case.case_id for case in protected + fresh + other}
    after = ({case.case_id for case in target + fresh + other}
             | {case.case_id for case in protected[protected_loss:]})
    parent_solver, candidate_solver = _solver(contexts, before), _solver(contexts, after)
    def pair(kind, cases, groups):
        cohort = EvaluationCohort(
            kind, cases, groups, "d" * 64, "e" * 64, "f" * 64,
            policy.digest(), ("trained-family",), ("trained-episode",),
            dict(required)[kind])
        return AssessmentPair(
            evaluate_capabilities(parent_solver, cohort, PARENT),
            evaluate_capabilities(candidate_solver, cohort, CANDIDATE))
    return PairedRetentionEvidence(
        "target", policy,
        pair(EvidenceKind.FRESH_TARGET, target, (("target", labels[0]),)),
        pair(EvidenceKind.FRESH_LESSON, target + fresh, census[:2]),
        pair(EvidenceKind.FIXED_SCHOOL, target + protected + other, census))

def _rescore(pair, before, after):
    contexts = {}
    for case in pair.parent.cohort.cases:
        index = int(case.case_id.rsplit(":", 1)[1])
        contexts[case.case_id] = _case(("Number", (index // 3) % 4 + 1),
                                     ("Number", index % 3 + 1))[0]
    def selected(counts):
        result = set()
        for capability, _ in pair.parent.cohort.capability_groups:
            rows = [case for case in pair.parent.cohort.cases
                    if case.capability_id == capability]
            result.update(case.case_id for case in rows[:counts.get(capability, 0)])
        return result
    return AssessmentPair(
        evaluate_capabilities(_solver(contexts, selected(before)), pair.parent.cohort, PARENT),
        evaluate_capabilities(_solver(contexts, selected(after)), pair.parent.cohort, CANDIDATE))

def _repolicy(evidence, policy):
    def update(pair):
        cohort = replace(pair.parent.cohort, policy_sha256=policy.digest())
        return AssessmentPair(replace(pair.parent, cohort=cohort),
                              replace(pair.candidate, cohort=cohort))
    return replace(evidence, policy=policy, target=update(evidence.target),
                   fresh_lesson=update(evidence.fresh_lesson),
                   fixed_school=update(evidence.fixed_school))
