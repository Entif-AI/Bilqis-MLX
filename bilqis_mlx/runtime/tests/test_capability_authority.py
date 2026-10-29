"""Uniform Factory preflight with frozen source/rights/lease authority fixtures."""
from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.curriculum import AnswerFamily, BINARY, Capability, Course, Grade
from bilqis_mlx.factory.adapters import RegisteredSourceAdapter, SourceAdapterRegistry
from bilqis_mlx.factory.assessment import assessment_scope_contract
from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.factory.executable_release import compile_executable_factory_release, admit_executable_factory_release
from bilqis_mlx.factory.execution import CurriculumProfile
from bilqis_mlx.factory.model import SourceAdapter
from bilqis_mlx.factory.tests.test_executable_release import _answers
from bilqis_mlx.learning.capability_championship import ReplayBinding
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime.capability_authority import (
    AuthorityKind, AuthorityReceipt, AuthorityStatus, PrerequisiteThreshold,
    ReleasedEvidence, evaluate_progression_authority,
)
from bilqis_mlx.runtime.capability_retention import (
    CompleteSolver, EvaluationCase, EvaluationCohort, EvidenceKind,
    case_census_digest, evaluate_capabilities,
)
from bilqis_mlx.runtime.cognitive_solver import NeuralProposal, SolveBudget, SolveContext
from bilqis_mlx.semantics.cognitive_dag import DAGBudget, DAGNode
from bilqis_mlx.semantics.cognitive_operators import TypedValue
from bilqis_mlx.semantics.domains import contract_digest
from bilqis_mlx.semantics.tests.cognition.test_cognitive_dag import _goal, _literal, _program
from bilqis_mlx.semantics.tests.test_cognitive_operators import RELEASE, SCOPE, _case

GENERATION, POLICY = "a" * 64, "9" * 64
GRAPH = contract_digest({"tokens": ["fixture.padding", "cogal.value.false", "cogal.value.true"]})


def _release(edge=False, labels=("B", "C")):
    capabilities = tuple(Capability(
        name, "fixture", "repo:fixture/" + name, ("root:" + name,), ("root:" + name,),
        ("foundation",) if edge and name == "target" else (), (),
        (AnswerFamily("binary", BINARY),), "fixture.guard.generator", "fixture.guard.oracle")
        for name in ("foundation", "target"))
    grades = tuple(Grade(label, (capability,), "c" * 64, ((capability.id, 4),))
                   for label, capability in zip(labels, capabilities))
    course = Course(grades, "fixture.guard/v1", "b" * 64, "c" * 64)
    def rows(*, capability, seed, each, **kwargs):
        return tuple({"id": f"{capability}:{seed}:{index}", "capability": capability,
                      "left": bool(index % 2), "right": True,
                      "gold": "TRUE" if index % 2 else "FALSE"} for index in range(each))
    def independent(row, **kwargs):
        return row["gold"] == ("TRUE" if row["left"] and row["right"] else "FALSE")
    registry = SourceAdapterRegistry((RegisteredSourceAdapter(
        SourceAdapter("fixture.guard.adapter", "fixture.guard.generator",
                      ("fixture.guard.oracle",), "d" * 64), rows, independent,
        semantic_footprint=lambda row: ("root:" + row["capability"],)),))
    curriculum, bindings = from_legacy_course(course)
    graph = {"tokens": ["fixture.padding", "cogal.value.false", "cogal.value.true"]}
    release = compile_executable_factory_release(
        curriculum, bindings, CurriculumProfile.full(), registry, _answers(),
        source_root=None, graph=graph, verification_seed=17)
    checkpoint = Checkpoint("1" * 64, "bundles/fixture", 3, True)
    admission = admit_executable_factory_release(
        release, student_sha256=checkpoint.sha256, optimizer_step=3,
        semantic_graph_sha256=GRAPH, graph=graph)
    return release, checkpoint, admission


def _evidence(release, capability, correct=True):
    binding, values = _case(("Boolean", False), ("Boolean", True), numbers=False)
    node = DAGNode("answer", None, tuple(_literal(value) for value in values),
                   "Boolean", SCOPE, candidate_operator_ids=("BOOL_AND", "BOOL_OR"))
    goal = replace(_goal(_program(node), binding), goal_id="fixture:" + capability)
    group = release.execution_plan.capability_map[capability].grade_id
    case = EvaluationCase(capability, capability, group, "independent-family:" + capability,
                          "independent-episode:" + capability, goal,
                          TypedValue("Boolean", False, RELEASE))
    scope = assessment_scope_contract(release, (capability,))
    cohort = EvaluationCohort(
        EvidenceKind.FRESH_TARGET, (case,), ((capability, group),),
        scope.rubric_sha256, contract_digest(scope), scope.source_sha256,
        POLICY, (), (), case_census_digest((case,)))
    def context_for(goal, generation):
        def proposal(request):
            filled = replace(goal, expression_or_holes=_program(replace(
                node, operator_id="BOOL_AND" if correct else "BOOL_OR", candidate_operator_ids=())))
            return NeuralProposal(filled, request.source_binding_digest,
                                  request.generation_digest, request.unresolved_signature, "e" * 64)
        return SolveContext(binding, neural_proposer=proposal)
    solver = CompleteSolver(context_for, SolveBudget(DAGBudget()))
    assessment = evaluate_capabilities(solver, cohort, GENERATION)
    evidence = ReleasedEvidence(assessment, scope, POLICY,
                                (case.source_family_id,), cohort.expected_case_digest)
    return solver, evidence


def _authority(kind, status=AuthorityStatus.PERMITTED):
    def verify(request):
        return AuthorityReceipt(kind, request.digest(), "fixture:authority:" + kind.value,
                                status, "Fixture authority verified." if status is AuthorityStatus.PERMITTED
                                else "Fixture authority withheld.")
    return verify


class CapabilityAuthorityTests(unittest.TestCase):
    def gate(self, release, checkpoint, admission, *, proof=True, lease=True,
             rights=True, policy=True, thresholds=(), omit=False, verifiers=None):
        solver, target = _evidence(release, "target")
        _, prerequisite = _evidence(release, "foundation", proof)
        replay = ReplayBinding(solver, GENERATION, checkpoint, "C",
                               tuple(sorted(set(target.assessment.solver_contracts))),
                               lambda generation, pointer: generation == GENERATION and pointer == checkpoint)
        verifiers = verifiers or {}
        return evaluate_progression_authority(
            release, "target", target, () if omit else (prerequisite,), replay,
            admission=admission, semantic_graph_sha256=GRAPH,
            prerequisite_thresholds=thresholds,
            source_rights=verifiers.get(AuthorityKind.SOURCE_RIGHTS, _authority(AuthorityKind.SOURCE_RIGHTS,
                AuthorityStatus.PERMITTED if rights else AuthorityStatus.HELD)),
            promotion_policy=verifiers.get(AuthorityKind.PROMOTION_POLICY, _authority(AuthorityKind.PROMOTION_POLICY,
                AuthorityStatus.PERMITTED if policy else AuthorityStatus.HELD)),
            admission_lease=verifiers.get(AuthorityKind.ADMISSION_LEASE,
                _authority(AuthorityKind.ADMISSION_LEASE) if lease else None))

    def test_unfinished_grade_labels_neither_grant_nor_deny_independent_target(self):
        for labels in (("B", "C"), ("C", "B")):
            release, checkpoint, admission = _release(labels=labels)
            self.assertEqual(self.gate(release, checkpoint, admission, proof=False).status, "ELIGIBLE")
            release, checkpoint, admission = _release(edge=True, labels=labels)
            threshold = (PrerequisiteThreshold("foundation", 1, 1),)
            self.assertEqual(self.gate(release, checkpoint, admission,
                                       thresholds=threshold, proof=False).reason,
                             "PREREQUISITE_EVIDENCE_INSUFFICIENT")
            self.assertEqual(self.gate(release, checkpoint, admission,
                                       thresholds=threshold, omit=True).reason,
                             "PREREQUISITE_EVIDENCE_INSUFFICIENT")
            self.assertEqual(self.gate(release, checkpoint, admission,
                                       thresholds=threshold).status, "ELIGIBLE")

    def test_source_contract_recomputation_and_bound_authority_receipts(self):
        release, checkpoint, admission = _release()
        _, evidence = _evidence(release, "target")
        with self.assertRaises(BilqisError):
            replace(evidence, native_scope=replace(evidence.native_scope,
                                                   factory_release_sha256="0" * 64)).verify(release)
        with self.assertRaises(BilqisError):
            replace(evidence, source_family_ids=("invented-family",)).verify(release)
        forged = lambda request: AuthorityReceipt(
            AuthorityKind.SOURCE_RIGHTS, "0" * 64, "fixture:forged", AuthorityStatus.PERMITTED, "Wrong input.")
        self.assertEqual(self.gate(release, checkpoint, admission,
            verifiers={AuthorityKind.SOURCE_RIGHTS: forged}).reason, "SOURCE_RIGHTS_RECEIPT_DRIFT")
        self.assertEqual(self.gate(release, checkpoint, admission,
            verifiers={AuthorityKind.SOURCE_RIGHTS: None}).reason, "SOURCE_RIGHTS_AUTHORITY_REQUIRED")
        self.assertEqual(self.gate(release, checkpoint, admission,
            verifiers={AuthorityKind.PROMOTION_POLICY: lambda request: {"promoted": True}}).reason,
            "PROMOTION_POLICY_RECEIPT_DRIFT")
        def malformed(request):
            raise ValueError("missing source manifest")
        self.assertEqual(self.gate(release, checkpoint, admission,
            verifiers={AuthorityKind.SOURCE_RIGHTS: malformed}).reason, "SOURCE_RIGHTS_AUTHORITY_REJECTED")

    def test_native_promotion_retry_does_not_rearm_on_changed_cohort(self):
        from bilqis_mlx.curriculum.promotion import _promotion_sweep_due
        from bilqis_mlx.curriculum.scheduler import Assessment, Score, start_new
        from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
        release, checkpoint, _ = _release()
        program = schedule_program_from_executable_release(release)
        state = start_new(program, checkpoint)
        scope = tuple(capability.id for capability in program.grades[0].capabilities)
        state = replace(state, stage="ASSESS_MAIN",
                        promotion_sweep_attempt_student_sha256=checkpoint.sha256,
                        promotion_sweep_attempt_scope=scope)
        assessment = Assessment(checkpoint.sha256, checkpoint.optimizer_step,
                                program.digest(), program.grades[0].assessment_sha256,
                                {capability: Score(4, 4) for capability in scope}, "old-cohort")
        self.assertFalse(_promotion_sweep_due(program, state, assessment))
        self.assertFalse(_promotion_sweep_due(program, state, replace(assessment, evaluation_id="new-cohort")))
        changed = replace(state, current_student=replace(checkpoint, sha256="2" * 64,
                                                       optimizer_step=checkpoint.optimizer_step + 1))
        self.assertTrue(_promotion_sweep_due(program, changed, replace(
            assessment, checkpoint_sha256=changed.current_student.sha256,
            optimizer_step=changed.current_student.optimizer_step)))

    def test_source_rights_lease_policy_and_native_admission_remain_separate(self):
        release, checkpoint, admission = _release()
        for kwargs, expected in (({"rights": False}, "HELD"), ({"lease": False}, "LEASE_REQUIRED"),
                                 ({"policy": False}, "HELD")):
            with self.subTest(kwargs=kwargs):
                self.assertEqual(self.gate(release, checkpoint, admission, **kwargs).status, expected)
        self.assertEqual(self.gate(release, checkpoint, None).status, "HELD")
        self.assertEqual(self.gate(release, checkpoint, {"promoted": True}).status, "HELD")
        with self.assertRaises(ValueError):
            admission.verify_baseline(student_sha256="2" * 64, optimizer_step=3,
                                      semantic_graph_sha256=GRAPH)
        admission.verify_baseline(student_sha256="2" * 64, optimizer_step=4,
                                  semantic_graph_sha256=GRAPH)
        with self.assertRaises(ValueError):
            admission.verify_baseline(student_sha256=checkpoint.sha256, optimizer_step=2,
                                      semantic_graph_sha256=GRAPH)
