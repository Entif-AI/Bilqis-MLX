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


from bilqis_mlx.runtime.tests.capability.capability_retention_helpers import (
    _cases, _solver, _evidence, _rescore, _repolicy,
)

class CapabilityEvaluationTests(unittest.TestCase):
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
