from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.factory.autonomy import compile_autonomy_plan, initial_evidence_ledger
from bilqis_mlx.factory.candidate_staging import (
    compile_candidate_successor, candidate_source_anchor,
)
from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.factory.jit_curriculum import ProposalDisposition, propose_curriculum_delta
from bilqis_mlx.factory.tests.test_jit_curriculum import JitCurriculumTests
from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_course


class CandidateStagingFixture:
    def setUp(self):
        fixture = JitCurriculumTests()
        fixture.setUp()
        self.fixture = fixture
        self.frontier = fixture.frontier
        self.current = fixture.current
        self.candidate_id = "candidate-z-c6"
        self.curriculum, bindings = from_legacy_course(_synthetic_course(7))
        anchor = candidate_source_anchor(self.frontier, self.candidate_id)
        self.bindings = replace(bindings, bindings=tuple(
            replace(item, source_anchor=anchor) if item.capability_id == "Z.C6"
            else item for item in bindings.bindings))

    def stage(self, **overrides):
        arguments = dict(
            curriculum=self.curriculum, source_bindings=self.bindings,
            profile=self.current.profile,
            source_registry=self.fixture.fixture.registry,
            answer_registry=self.fixture.fixture.answers,
            source_root=None, graph=self.fixture.fixture.graph,
            verification_seed=31)
        arguments.update(overrides)
        return compile_candidate_successor(
            self.frontier, self.current, self.candidate_id, **arguments)



class CandidateStagingTests(CandidateStagingFixture, unittest.TestCase):
    def test_durable_staging_roundtrips_the_ordinary_executable_release(self):
        from bilqis_mlx.factory.executable_release import ExecutableFactoryRelease
        from bilqis_mlx.runtime.candidate_staging import (
            persist_staged_candidate, load_staged_candidates)

        staged = self.stage()
        self.assertIs(type(staged.successor), ExecutableFactoryRelease)
        self.assertIs(staged.binding.staged_successor, staged.successor)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = persist_staged_candidate(root, staged, self.frontier, self.current)
            payload = json.loads(path.read_text())
            ordinary = ExecutableFactoryRelease.from_manifest(
                payload["successor_manifest"], payload["successor_sha256"])
            restored, = load_staged_candidates(root, self.frontier, self.current)
            self.assertIs(type(restored.successor), ExecutableFactoryRelease)
            self.assertEqual(restored.successor, ordinary)
            self.assertEqual(restored.successor, staged.successor)
            ordinary.verify_successor_of(self.current)
            ordinary.verify_semantic_catalog(self.fixture.fixture.graph)
            self.assertFalse((root / "state.json").exists())
            self.assertFalse((root / "factory-releases").exists())
            self.assertFalse((root / "events.jsonl").exists())

    def test_canonical_horizon_can_be_larger_than_the_single_executable_delta(self):
        from bilqis_mlx.factory.execution import CurriculumProfile, GradeProfile
        curriculum, bindings = from_legacy_course(_synthetic_course(8))
        bindings = replace(bindings, bindings=tuple(
            self.bindings.by_capability.get(item.capability_id, item)
            for item in bindings.bindings))
        profile = CurriculumProfile("one-new-capability", grades=(
            GradeProfile("Z", enabled_capabilities=tuple(f"Z.C{i}" for i in range(7))),))
        staged = self.stage(curriculum=curriculum, source_bindings=bindings, profile=profile)
        self.assertIn("Z.C7", staged.successor.curriculum.capability_map)
        self.assertNotIn("Z.C7", staged.successor.execution_plan.capability_map)
        self.assertEqual(staged.successor.transition.added_capabilities, ("Z.C6",))

    def test_staging_does_not_turn_historical_prerequisite_pass_into_current_mastery(self):
        from bilqis_mlx.factory.autonomy import EvidenceReceipt, record_evidence, obligations_for_capability
        from bilqis_mlx.factory.candidate_frontier import CandidatePrerequisite

        selected, reserve = self.frontier.candidates
        frontier = replace(self.frontier, candidates=(replace(
            selected, prerequisites=(CandidatePrerequisite("Z.C0"),)), reserve))
        self.frontier = replace(frontier, release_sha256=frontier.expected_digest())
        grade = self.curriculum.grades[0]
        curriculum = replace(self.curriculum, grades=(replace(
            grade, capabilities=(*grade.capabilities[:-1], replace(
                grade.capabilities[-1], prerequisites=("Z.C0",))),
            teaching_stages=(tuple(f"Z.C{i}" for i in range(6)), ("Z.C6",))),))
        staged = self.stage(curriculum=curriculum)
        plan = compile_autonomy_plan(self.current)
        ledger = initial_evidence_ledger(self.current, plan=plan)
        for obligation in obligations_for_capability(self.current, "Z.C0", plan=plan):
            ledger = record_evidence(self.current, ledger, EvidenceReceipt(
                obligation_id=obligation.obligation_id, evidence_id=obligation.obligation_id,
                checkpoint_sha256="e" * 64, optimizer_step=0, cohort_sha256="d" * 64,
                specimen_count=obligation.minimum_specimens, passed=True), plan=plan,
                current_checkpoint_sha256="e" * 64, current_optimizer_step=0)
        fresh = propose_curriculum_delta(self.frontier, self.current, ledger, plan,
            "e" * 64, 0, candidate_bindings=(staged.binding,))
        stale = propose_curriculum_delta(self.frontier, self.current, ledger, plan,
            "f" * 64, 1, candidate_bindings=(staged.binding,))
        self.assertEqual(fresh.disposition, ProposalDisposition.PROPOSAL)
        self.assertEqual(stale.disposition, ProposalDisposition.SOURCE_DEVELOPMENT)

    def test_compiles_through_factory_then_jit_without_admission(self):
        staged = self.stage()
        staged.verify(self.frontier, self.current)
        self.assertEqual(staged.binding.staged_successor.transition.added_capabilities,
                         ("Z.C6",))
        plan = compile_autonomy_plan(self.current)
        proposal = propose_curriculum_delta(
            self.frontier, self.current,
            initial_evidence_ledger(self.current, plan=plan), plan,
            "e" * 64, 0, candidate_bindings=(staged.binding,))
        self.assertEqual(proposal.disposition, ProposalDisposition.PROPOSAL)
        self.assertEqual(proposal.selected_candidate_ids, (self.candidate_id,))

    def test_source_anchor_cannot_be_an_unrelated_registered_source(self):
        _, unrelated = from_legacy_course(_synthetic_course(7))
        with self.assertRaisesRegex(ValueError, "CANDIDATE_STAGING_SOURCE_BINDING_MISMATCH"):
            self.stage(source_bindings=unrelated)

    def test_cannot_rewrite_existing_semantics_behind_unchanged_plan_inventory(self):
        grade = self.curriculum.grades[0]
        changed = replace(grade.capabilities[0], taught_roots=("changed",),
                          examined_roots=("changed",))
        curriculum = replace(self.curriculum, grades=(replace(
            grade, capabilities=(changed, *grade.capabilities[1:])),))
        with self.assertRaisesRegex(ValueError, "CANDIDATE_STAGING_EXISTING_AUTHORITY_CHANGED"):
            self.stage(curriculum=curriculum)

    def test_failed_oracle_cannot_create_staged_artifact(self):
        from bilqis_mlx.factory.adapters import RegisteredSourceAdapter, SourceAdapterRegistry
        adapter = self.fixture.fixture.registry.require(
            "fixture.z-generator/v1", "fixture.z-oracle/v1")
        registry = SourceAdapterRegistry((RegisteredSourceAdapter(
            adapter.descriptor, adapter.draw, lambda row, **_: False),))
        with self.assertRaisesRegex(ValueError, "SOURCE_ORACLE_DISAGREEMENT"):
            self.stage(source_registry=registry)


    def test_changed_source_sense_invalidates_even_a_rehashed_frontier(self):
        staged = self.stage()
        frontier = replace(self.frontier, senses=(replace(
            self.frontier.senses[0], source_text_sha256="f" * 64),))
        frontier = replace(frontier, release_sha256=frontier.expected_digest())
        with self.assertRaisesRegex(ValueError, "CANDIDATE_STAGING_FRONTIER_MISMATCH"):
            staged.verify(frontier, self.current)




if __name__ == "__main__":
    unittest.main()
