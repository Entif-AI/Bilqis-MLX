from dataclasses import replace
import unittest

from bilqis_mlx.factory.autonomy import (
    compile_autonomy_plan, initial_evidence_ledger)
from bilqis_mlx.factory.candidate_frontier import (
    Candidate, CandidateFrontierRelease, CandidateSense)
from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.factory.executable_release import compile_executable_factory_release
from bilqis_mlx.factory.execution import CurriculumProfile
from bilqis_mlx.factory.jit_curriculum import (
    CandidateBinding, ProposalDisposition, propose_curriculum_delta)
from bilqis_mlx.factory.tests.test_executable_release import (
    ExecutableFactoryReleaseTests)


class JitCurriculumTests(unittest.TestCase):
    def setUp(self):
        fixture = ExecutableFactoryReleaseTests()
        fixture.setUp()
        self.fixture = fixture
        self.current = fixture.compile()
        grade = fixture.course.grades[0]
        added = replace(
            grade.capabilities[-1], id="Z.C6",
            taught_roots=("fixture.op.6",), examined_roots=("fixture.op.6",))
        expanded_course = replace(
            fixture.course, grades=(replace(
                grade,
                capabilities=(*grade.capabilities, added),
                exam_item_counts=(*grade.exam_item_counts, ("Z.C6", 4))),))
        curriculum, bindings = from_legacy_course(expanded_course)
        graph = {"tokens": [
            *fixture.graph["tokens"], "fixture.appended.identity"]}
        self.successor = compile_executable_factory_release(
            curriculum, bindings, CurriculumProfile.full(),
            fixture.registry_with_revised_roots({"Z.C6": "fixture.op.6"}),
            fixture.answers, source_root=None, graph=graph,
            verification_seed=20261019,
            predecessor=self.current)
        target = self.successor.execution_plan.capability_map["Z.C6"]
        sense = CandidateSense(
            "LEXSENSE-z-c6", "LEXROOT-z-c6", "ROOT-C6", "", "",
            "synthetic exact source sense", "a" * 64, "SELECTED", "Z.C6")
        selected = Candidate(
            "candidate-z-c6", "CORE_D_O", "Z.C6", "D", "ROOT-C6",
            "LEXROOT-z-c6", sense.sense_id, ("EVIDENCE-z-c6",), (),
            "smallest legal semantic delta", "unlocks fixture successor",
            "binary", "fixture world", "", ("FACTORY_ADMISSION_REQUIRED",),
            (), "PROPOSED_NOT_ADMITTED")
        reserve = Candidate(
            "candidate-reserve", "NEXT_96", "", "", "ROOT-RESERVE",
            "LEXROOT-reserve", "", (), (), "reserve source candidate",
            "future breadth", "binary", "fixture world", "",
            ("FACTORY_ADMISSION_REQUIRED",), (), "CANDIDATE_RESERVE")
        provisional = CandidateFrontierRelease(
            "b" * 64, "c" * 64, "d" * 64,
            (selected, reserve), (sense,), "0" * 64)
        self.frontier = replace(
            provisional, release_sha256=provisional.expected_digest())
        self.binding = CandidateBinding(
            selected.candidate_id, "Z.C6", sense.sense_id,
            target.source_anchor, self.successor)

    def test_exact_bound_successor_emits_proposal_without_admitting_it(self):
        plan = compile_autonomy_plan(self.current)
        ledger = initial_evidence_ledger(self.current, plan=plan)
        proposal = propose_curriculum_delta(
            self.frontier, self.current, ledger, plan,
            "e" * 64, 0, candidate_bindings=(self.binding,))
        self.assertEqual(proposal.disposition, ProposalDisposition.PROPOSAL)
        self.assertEqual(proposal.selected_candidate_ids, ("candidate-z-c6",))
        self.assertEqual(
            proposal.selected_successor_sha256, self.successor.release_sha256)
        self.assertEqual(
            self.current.release_sha256, proposal.current_release_sha256)
        proposal.verify()

    def test_unbound_frontier_requests_source_development(self):
        plan = compile_autonomy_plan(self.current)
        ledger = initial_evidence_ledger(self.current, plan=plan)
        proposal = propose_curriculum_delta(
            self.frontier, self.current, ledger, plan, "e" * 64, 0)
        self.assertEqual(
            proposal.disposition, ProposalDisposition.SOURCE_DEVELOPMENT)
        self.assertEqual(proposal.selected_candidate_ids, ())

    def test_binding_cannot_smuggle_unselected_capability_in_successor(self):
        grade = self.fixture.course.grades[0]
        added_six = replace(
            grade.capabilities[-1], id="Z.C6",
            taught_roots=("fixture.op.6",), examined_roots=("fixture.op.6",))
        added_seven = replace(
            grade.capabilities[-1], id="Z.C7",
            taught_roots=("fixture.op.7",), examined_roots=("fixture.op.7",))
        expanded_course = replace(
            self.fixture.course, grades=(replace(
                grade,
                capabilities=(*grade.capabilities, added_six, added_seven),
                exam_item_counts=(
                    *grade.exam_item_counts, ("Z.C6", 4), ("Z.C7", 4))),))
        curriculum, bindings = from_legacy_course(expanded_course)
        graph = {"tokens": [
            *self.fixture.graph["tokens"],
            "fixture.appended.identity.6", "fixture.appended.identity.7"]}
        overbroad = compile_executable_factory_release(
            curriculum, bindings, CurriculumProfile.full(),
            self.fixture.registry_with_revised_roots({
                "Z.C6": "fixture.op.6", "Z.C7": "fixture.op.7"}), self.fixture.answers,
            source_root=None, graph=graph, verification_seed=20261019,
            predecessor=self.current)
        target = overbroad.execution_plan.capability_map["Z.C6"]
        binding = replace(
            self.binding, source_anchor=target.source_anchor,
            staged_successor=overbroad)
        plan = compile_autonomy_plan(self.current)
        ledger = initial_evidence_ledger(self.current, plan=plan)
        proposal = propose_curriculum_delta(
            self.frontier, self.current, ledger, plan,
            "e" * 64, 0, candidate_bindings=(binding,))
        self.assertEqual(
            proposal.disposition, ProposalDisposition.SOURCE_DEVELOPMENT)
        gate = next(
            item for item in proposal.candidate_gates
            if item.candidate_id == "candidate-z-c6")
        self.assertIn(
            "SUCCESSOR_DELTA_SCOPE_MISMATCH", gate.required_source_work)


if __name__ == "__main__":
    unittest.main()
