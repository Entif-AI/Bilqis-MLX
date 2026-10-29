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
        left, right = index // 3 + 1, index % 3 + 1
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
        contexts[case.case_id] = _case(("Number", index // 3 + 1),
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


class CapabilityRetentionTests(unittest.TestCase):
    def test_fresh_protected_loss_cannot_hide_behind_target_gain(self):
        evidence = _evidence()
        fresh = _rescore(evidence.fresh_lesson,
                         {"target": 0, "protected": 3},
                         {"target": 3, "protected": 2})
        evidence = replace(evidence, fresh_lesson=fresh)
        self.assertEqual(retain_candidate(PARENT, CANDIDATE, evidence).reason,
                         "PROTECTED_CAPABILITY_REGRESSION")

    def test_bilateral_row_truncation_rejects_under_frozen_policy(self):
        evidence = _evidence()
        pair = evidence.fixed_school
        cases = pair.parent.cohort.cases[:4] + pair.parent.cohort.cases[-1:]
        with self.assertRaises(BilqisError):
            replace(pair.parent.cohort, cases=cases)
        truncated = replace(pair.parent.cohort, cases=cases,
                            expected_case_digest=case_census_digest(cases))
        results_before = pair.parent.results[:4] + pair.parent.results[-1:]
        results_after = pair.candidate.results[:4] + pair.candidate.results[-1:]
        contracts = pair.parent.solver_contracts[:4] + pair.parent.solver_contracts[-1:]
        shortened = AssessmentPair(
            replace(pair.parent, cohort=truncated, results=results_before,
                    solver_contracts=contracts),
            replace(pair.candidate, cohort=truncated, results=results_after,
                    solver_contracts=contracts))
        with self.assertRaises(BilqisError):
            replace(evidence, fixed_school=shortened)

    def test_each_aggregate_gate_preserves_native_reason_precedence(self):
        base = _evidence()
        policy = replace(base.policy, protected_reference_losses=(("other", 6), ("protected", 6)))
        base = _repolicy(base, policy)
        fresh = _rescore(base.fresh_lesson, {"protected": 3}, {"target": 1})
        self.assertEqual(retain_candidate(PARENT, CANDIDATE,
            replace(base, fresh_lesson=fresh)).reason, "SAME_GRADE_NET_REGRESSION")
        fixed = _rescore(base.fixed_school, {"protected": 12, "other": 1},
                         {"target": 3, "protected": 7, "other": 1})
        self.assertEqual(retain_candidate(PARENT, CANDIDATE,
            replace(base, fixed_school=fixed)).reason, "FIXED_LESSON_GRADE_REGRESSION")
        fixed = _rescore(base.fixed_school, {"protected": 12, "other": 1},
                         {"target": 3, "protected": 12})
        self.assertEqual(retain_candidate(PARENT, CANDIDATE,
            replace(base, fixed_school=fixed)).reason, "ACTIVE_SCHOOL_GRADE_REGRESSION")
        school = _repolicy(base, replace(policy, protected_groups=("amber",)))
        fixed = _rescore(school.fixed_school, {"protected": 12, "other": 1},
                         {"protected": 12})
        self.assertEqual(retain_candidate(PARENT, CANDIDATE,
            replace(school, fixed_school=fixed)).reason, "WHOLE_SCHOOL_NET_REGRESSION")

    def test_route_full_score_never_substitutes_for_correct_typed_answer(self):
        evidence = _evidence()
        neural = evidence.target.candidate
        cases = tuple(replace(case, goal=replace(case.goal, expression_or_holes=_program(
            replace(case.goal.expression_or_holes.nodes[0], operator_id="SUB",
                    candidate_operator_ids=())))) for case in neural.cohort.cases)
        contexts = {case.case_id: _case(("Number", 1), ("Number", index + 1))[0]
                    for index, case in enumerate(cases)}
        wrong = evaluate_capabilities(
            CompleteSolver(lambda goal, generation: SolveContext(contexts[goal.goal_id]),
                           SolveBudget(DAGBudget())),
            replace(neural.cohort, cases=cases, expected_case_digest=case_census_digest(cases)),
            CANDIDATE)
        self.assertEqual(neural.score("target"), (3, 3))
        self.assertEqual(wrong.score("target"), (0, 3))
        # Some exact SUB results are valid values with route credit1 despite wrong semantics.
        self.assertEqual(wrong.results[0].score, 1.0)
        exact_cases = tuple(replace(case, goal=replace(case.goal, expression_or_holes=_program(
            replace(case.goal.expression_or_holes.nodes[0], operator_id="ADD",
                    candidate_operator_ids=())))) for case in cases)
        exact = evaluate_capabilities(
            CompleteSolver(lambda goal, generation: SolveContext(contexts[goal.goal_id]),
                           SolveBudget(DAGBudget())),
            replace(neural.cohort, cases=exact_cases,
                    expected_case_digest=case_census_digest(exact_cases)), CANDIDATE)
        self.assertEqual(exact.score("target"), neural.score("target"))

    def test_fresh_role_fillers_and_two_node_structure_use_actual_source_operators(self):
        cases, contexts = [], {}
        for index, name in enumerate(("novel-actor-iris", "novel-actor-cedar")):
            binding, values = _case(("FrameHandle", "frame:" + name),
                                    ("RoleId", "subject"), ("Index", 0), numbers=False)
            binding, frame, concept = _with_frame(binding, name=name)
            concept = replace(concept, semantic_id="formal:" + name, abi_index=index + 5,
                              source_reference="synthetic:source:" + name)
            schema = FrameSchema("synthetic:frame", 1, "source:synthetic",
                                 (RoleSpec("subject", ("Entity",), 1, 1),), "ORDERED", SCOPE)
            frame = make_frame_instance(
                schema, source_instance_id=name, structural_path=(),
                source_span=frame.source_span, parent_occurrence_id=None,
                bindings=(replace(frame.bindings[0], concept=concept),), causal_prefix_end=8)
            envelope = replace(binding.frames[0], frame=frame)
            grants = {grant.source_handle: grant for grant in binding.frontier.grants}
            grants[envelope.source_handle] = _grant(
                envelope.source_handle, frame_evidence_digest(frame))
            member = envelope.members[0]
            grants[member.source_handle] = _grant(
                member.source_handle, member_evidence_digest(frame, member))
            binding = replace(binding, frames=(envelope,), frontier=replace(
                binding.frontier, grants=tuple(grants[key] for key in sorted(grants))))
            goal = replace(_goal(_program(DAGNode(
                "answer", "ROLE_LOOKUP", tuple(_literal(value) for value in values),
                "ConceptRef", SCOPE)), binding), goal_id=name)
            cases.append(EvaluationCase(name, "role", "neutral", "held-role-family",
                                        name, goal, TypedValue("ConceptRef", concept, RELEASE)))
            contexts[name] = binding
        binding, values = _case(("Number", 2), ("Number", 3), ("Number", 4))
        goal = replace(_goal(_program(
            DAGNode("multiply", "MUL", tuple(_literal(value) for value in values[:2]),
                    "Number", SCOPE),
            DAGNode("answer", "ADD", (_result("multiply"), _literal(values[2])),
                    "Number", SCOPE)), binding), goal_id="structural-variant")
        cases.append(EvaluationCase("composition", "numeric", "neutral", "held-two-node",
                                    "novel-episode", goal, TypedValue("Number", 10, RELEASE)))
        contexts[goal.goal_id] = binding
        cases = tuple(cases)
        cohort = EvaluationCohort(
            EvidenceKind.FRESH_LESSON, cases, (("role", "neutral"), ("numeric", "neutral")),
            "d" * 64, "e" * 64, "f" * 64, "0" * 64,
            ("trained-other-family",), ("trained-other-episode",), case_census_digest(cases))
        assessment = evaluate_capabilities(CompleteSolver(
            lambda goal, generation: SolveContext(contexts[goal.goal_id]),
            SolveBudget(DAGBudget())), cohort, PARENT)
        self.assertEqual(assessment.score("role"), (2, 2))
        self.assertEqual(assessment.score("numeric"), (1, 1))
        self.assertEqual(assessment.results[0].answer.value.semantic_id, "formal:novel-actor-iris")
        self.assertEqual(assessment.results[1].answer.value.semantic_id, "formal:novel-actor-cedar")
        self.assertEqual(assessment.results[2].answer.value, 10)
        self.assertEqual(sum(receipt.operation_count
                             for receipt in assessment.results[2].dag_receipts), 2)

    def test_complete_solver_gain_and_scaled_protected_loss_allowance(self):
        evidence = _evidence()
        decision = retain_candidate(PARENT, CANDIDATE, evidence)
        self.assertEqual(decision.status, "ELIGIBLE")
        self.assertEqual(decision.reason, "PAIRED_SCREEN_WITHIN_BUDGET")
        self.assertEqual(evidence.target.parent.score("target"), (0, 3))
        self.assertEqual(evidence.target.candidate.score("target"), (3, 3))
        self.assertEqual(evidence.fixed_school.candidate.score("protected"), (10, 12))
        self.assertEqual(retain_candidate(PARENT, CANDIDATE, _evidence(3)).reason,
                         "PROTECTED_CAPABILITY_REGRESSION")

    def test_configuration_receipt_never_fabricates_optimizer_steps(self):
        evidence = _evidence()
        receipt = configuration_outcome(evidence.target)
        self.assertEqual(receipt.schema_version, "bilqis.c05.configuration-outcome/v1")
        self.assertEqual(receipt.net_correct_delta, 3)
        self.assertEqual(receipt.optimizer_steps, 0)
        self.assertFalse(hasattr(receipt, "retained"))

    def test_label_permutation_preserves_decision(self):
        left = retain_candidate(PARENT, CANDIDATE, _evidence())
        right = retain_candidate(PARENT, CANDIDATE, _evidence(labels=("violet", "amber")))
        self.assertEqual((left.status, left.reason), (right.status, right.reason))

    def test_no_fresh_gain_rejects_without_mutating_evidence(self):
        evidence = _evidence()
        same = replace(evidence.target.candidate,
                       results=tuple(replace(result, generation_digest=CANDIDATE)
                                     for result in evidence.target.parent.results))
        evidence = replace(evidence, target=AssessmentPair(evidence.target.parent, same))
        before = evidence.digest()
        self.assertEqual(retain_candidate(PARENT, CANDIDATE, evidence).reason,
                         "NO_MEASURABLE_TARGET_GAIN")
        self.assertEqual(evidence.digest(), before)

    def test_paraphrase_sibling_and_missing_school_capability_fail_closed(self):
        evidence = _evidence()
        cohort = evidence.target.parent.cohort
        with self.assertRaises(BilqisError):
            replace(cohort, training_family_ids=(cohort.cases[0].source_family_id,))
        with self.assertRaises(BilqisError):
            replace(evidence.fixed_school.parent.cohort,
                    cases=evidence.fixed_school.parent.cohort.cases[:-1])
        with self.assertRaises(BilqisError):
            replace(evidence.fixed_school.parent.cohort,
                    cases=(evidence.fixed_school.parent.cohort.cases[0],) * 16)

    def test_foreign_rubric_and_budget_cannot_pair(self):
        evidence = _evidence()
        with self.assertRaises(BilqisError):
            AssessmentPair(evidence.target.parent, replace(
                evidence.target.candidate,
                cohort=replace(evidence.target.candidate.cohort, rubric_sha256="0" * 64)))
        with self.assertRaises(BilqisError):
            AssessmentPair(evidence.target.parent, replace(
                evidence.target.candidate, solver_contracts=("0" * 64,) * 3))

    def test_perfect_exact_target_skips_optimizer_candidate(self):
        cases, contexts = _cases("target", "any-label", 3, "exact")
        exact = tuple(replace(case, goal=replace(case.goal, expression_or_holes=_program(
            replace(case.goal.expression_or_holes.nodes[0], operator_id="ADD",
                    candidate_operator_ids=())))) for case in cases)
        cohort = EvaluationCohort(
            EvidenceKind.FRESH_TARGET, exact, (("target", "any-label"),),
            "d" * 64, "e" * 64, "f" * 64, "0" * 64, (), (), case_census_digest(exact))
        solver = CompleteSolver(lambda goal, generation: SolveContext(contexts[goal.goal_id]),
                                SolveBudget(DAGBudget()))
        assessment = evaluate_capabilities(solver, cohort, PARENT)
        self.assertEqual(assessment.score("target"), (3, 3))
        self.assertEqual(candidate_work_disposition(assessment, "target"),
                         "REHEARSE_OR_ADVANCE")
        self.assertTrue(all(result.neural_calls == 0 for result in assessment.results))
