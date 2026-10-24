from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from bilqis_mlx.compatibility.executable_projection import compile_projected_executable_release
from bilqis_mlx.factory.candidate_frontier import load_candidate_frontier
from bilqis_mlx.factory.autonomy import (
    compile_autonomy_plan, initial_evidence_ledger, obligations_for_capability,
    EvidenceReceipt, record_evidence,
)
from bilqis_mlx.factory.evidence import draw_evidence_rows
from bilqis_mlx.source_adapters.copular_curriculum import (
    proposed_graph, expanded_graph, stage_identity, token_admission, VERSION, REGISTRY_ID,
)
from bilqis_mlx.factory.jit_curriculum import propose_curriculum_delta, ProposalDisposition
from bilqis_mlx.factory.live_answers import live_answer_registry
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.live_grade_c import registry_graph
from bilqis_mlx.semantics.abi import HISTORICAL_PREFIX_SIZE
from bilqis_mlx.source_adapters.school import live_source_registry
from bilqis_mlx.source_adapters.copular import CAPABILITY, check
from bilqis_mlx.token_atlas import COLUMNS, rows_for_graph
from bilqis_mlx.vocabulary_growth import digest


ROOT = Path(__file__).resolve().parents[3]
LEGACY = ROOT / "vendor/legacy-v16"


class IthkuilIdentityFactoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        output = Path(cls.temp.name)
        builder = ROOT / "lib/ithkuil/src/build_curriculum_frontier.py"
        subprocess.run([sys.executable, str(builder)], check=True, capture_output=True,
            env={**os.environ, "BILQIS_CURRICULUM_FRONTIER_OUT": str(output)})
        cls.frontier = load_candidate_frontier(output, ROOT / "lib/ithkuil/_data/csv",
            expected_builder_sha256=hashlib.sha256(builder.read_bytes()).hexdigest())
        registered = registry_graph()
        names = registered["tokens"][:HISTORICAL_PREFIX_SIZE]
        cls.parent_graph = {**registered, "tokens": names,
            "nodes": registered["nodes"][:HISTORICAL_PREFIX_SIZE],
            "row_contract_sha256": {t: registered["row_contract_sha256"][t] for t in names}}
        course = accepted_grade_a(json.loads(
            (ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text()))
        cls.current, _, _ = compile_projected_executable_release(
            course, course, LEGACY, cls.parent_graph)
        cls.graph = proposed_graph(cls.parent_graph)
        cls.registry = live_source_registry()
        cls.staged = stage_identity(cls.frontier, cls.current, cls.graph,
            source_root=LEGACY, source_registry=cls.registry,
            answer_registry=live_answer_registry())

    def test_registered_source_meanings_cannot_be_rebound(self):
        from bilqis_mlx.factory.candidate_realizations import REALIZATIONS
        with self.assertRaises(TypeError):
            REALIZATIONS["unqualified-sense"] = object()

    def test_source_realization_compiles_one_thin_grade_through_factory(self):
        self.staged.verify(self.frontier, self.current)
        successor = self.staged.successor
        self.assertEqual(successor.transition.added_capabilities, (CAPABILITY,))
        self.assertEqual(tuple(g.grade_id for g in successor.execution_plan.grades), ("A", "D"))
        self.assertEqual(successor.execution_plan.grade_map["D"].capabilities, (CAPABILITY,))
        self.assertEqual(successor.semantic_catalog[:len(self.parent_graph["tokens"])],
                         tuple(self.parent_graph["tokens"]))
        self.assertEqual(len(successor.semantic_catalog), 228)
        self.assertEqual(successor.semantic_catalog[222:227],
                         ("school.op.COUNT", "school.op.SUCC", "school.op.DIV",
                          "school.syntax.number_set", "school.syntax.number_groups"))

    def test_ordinary_lesson_draw_uses_v2_source_without_legacy_grade_membership(self):
        from bilqis_mlx.runtime.assessment import _draw_live_rows
        rows = _draw_live_rows(LEGACY, self.graph, seed=12,
            capability=CAPABILITY, each=32, executable_release=self.staged.successor)
        self.assertEqual(len(rows), 32)
        self.assertTrue(all(check(row, graph=self.graph) for row in rows))

    def test_pure_host_packet_can_prepare_a_new_source_from_its_release(self):
        from bilqis_mlx.runtime.source_prefetch import prepare_step_sources
        request = dict(identity="d" * 64, source_root=str(LEGACY), graph=self.graph,
            course=None, executable_release=self.staged.successor, capability=CAPABILITY,
            batch_size=32, fresh_seed=42, prior_capability=None, prior_seed=None,
            fragile_fixed_rows=(), fragile_requested=(), fragile_seeds={},
            fragile_rotation=0, retention_support_capability=None,
            retention_support_seed=None, retention_support_rotation=0,
            teaching_seed=43, teaching_enrichment_enabled=True)
        packet = prepare_step_sources(request)
        self.assertEqual(packet["identity"], request["identity"])
        self.assertEqual(len(packet["fresh"]), 32)
        self.assertTrue(all(check(row, graph=self.graph) for row in packet["fresh"]))
        self.assertEqual(packet["retention_support"], [])
        self.assertEqual(packet["teaching_enrichment_rows"], [])

    def test_prefetch_checks_the_complete_requested_footprint_before_drawing(self):
        from unittest.mock import patch
        from bilqis_mlx.runtime.source_execution import SourceExecutionContext
        from bilqis_mlx.runtime.source_prefetch import prepare_step_sources

        request = dict(identity="d" * 64, source_root=str(LEGACY), graph=self.graph,
            course=None, executable_release=self.staged.successor, capability=CAPABILITY,
            batch_size=32, fresh_seed=42, prior_capability=None, prior_seed=None,
            fragile_fixed_rows=(), fragile_requested=(), fragile_seeds={},
            fragile_rotation=0, retention_support_capability=None,
            retention_support_seed=None, retention_support_rotation=0,
            teaching_seed=43, teaching_enrichment_enabled=True)
        for change in ({"capability": "D.UNADMITTED"},
                       {"prior_capability": "D.UNADMITTED"},
                       {"fragile_requested": ("D.UNADMITTED",)},
                       {"retention_support_capability": "D.UNADMITTED"}):
            with self.subTest(change=change), patch.object(
                    SourceExecutionContext, "draw_rows",
                    side_effect=AssertionError("provider call before packet validation")) as draw:
                with self.assertRaisesRegex(ValueError, "UNKNOWN_CAPABILITY"):
                    prepare_step_sources({**request, **change})
                draw.assert_not_called()

    def test_proposal_requires_both_current_prerequisites(self):
        plan = compile_autonomy_plan(self.current)
        ledger = initial_evidence_ledger(self.current, plan=plan)
        def propose(sha="e" * 64, step=0):
            return propose_curriculum_delta(self.frontier, self.current, ledger, plan,
                sha, step, candidate_bindings=(self.staged.binding,))
        self.assertEqual(propose().disposition, ProposalDisposition.SOURCE_DEVELOPMENT)
        for capability in ("A.IDENTITY", "A.MAPS"):
            for obligation in obligations_for_capability(self.current, capability, plan=plan):
                ledger = record_evidence(self.current, ledger, EvidenceReceipt(
                    obligation_id=obligation.obligation_id, evidence_id=obligation.obligation_id,
                    checkpoint_sha256="e" * 64, optimizer_step=0, cohort_sha256="d" * 64,
                    specimen_count=obligation.minimum_specimens, passed=True), plan=plan,
                    current_checkpoint_sha256="e" * 64, current_optimizer_step=0)
        self.assertEqual(propose().disposition, ProposalDisposition.PROPOSAL)
        self.assertEqual(propose("f" * 64, 1).disposition, ProposalDisposition.SOURCE_DEVELOPMENT)

    def test_every_declared_transfer_obligation_has_a_checked_nontrivial_witness(self):
        release = self.staged.successor
        plan = compile_autonomy_plan(release)
        for obligation in obligations_for_capability(release, CAPABILITY, plan=plan):
            rows = draw_evidence_rows(LEGACY, self.graph, release, self.registry,
                                     obligation, seed=20261020)
            self.assertTrue(all(check(r, graph=self.graph) for r in rows))
            if obligation.kind.value != "DIRECT":
                self.assertTrue(all(r["reference_pattern"] != "same-reference" for r in rows))

    def test_source_compilation_cannot_replace_native_vocabulary_evidence(self):
        with self.assertRaisesRegex(ValueError, "NATIVE_REGISTRY_ADMISSION_NOT_VERIFIED"):
            expanded_graph(self.parent_graph, {})
        # This local fixture tests the readback contract; it is not native proof.
        rows = [list(COLUMNS), *rows_for_graph(self.graph)]
        evidence = dict(release=VERSION, spreadsheet_id=REGISTRY_ID, rows=rows,
                        native_rows_sha256=digest(rows),
                        admission_receipts=[token_admission().admission_receipt])
        self.assertEqual(expanded_graph(self.parent_graph, evidence), self.graph)
        tampered = json.loads(json.dumps(evidence))
        tampered["rows"][-1][2] = "unrelated-meaning"
        tampered["native_rows_sha256"] = digest(tampered["rows"])
        with self.assertRaisesRegex(ValueError, "IDENTITY_CONFLICT"):
            expanded_graph(self.parent_graph, tampered)

    def test_allocation_birth_source_is_reproducible_and_independent_of_later_provider_layout(self):
        from bilqis_mlx.source_adapters.copular import verify_source
        from bilqis_mlx.source_adapters.copular_curriculum import REGISTRY_PATH
        archive = json.loads((REGISTRY_PATH.parent / "copular_allocation_source_v1.json").read_text())
        implementation = digest(dict(source=verify_source(ROOT), files={
            name: hashlib.sha256(source.encode()).hexdigest()
            for name, source in archive["files"].items()}))
        contract = json.loads((REGISTRY_PATH.parent / "copular_admission_v1.json").read_text())
        self.assertEqual(implementation, contract["provider"]["implementation_sha256"])
        self.assertEqual(token_admission().admission_receipt, digest(contract))
        self.assertNotEqual(implementation, self.registry.require(
            "bilqis.ithkuil-reference-identity-constructor/v1",
            "bilqis.ithkuil-reference-identity-oracle/v1").descriptor.implementation_sha256)

    def test_live_boundary_automatically_stages_registered_source_without_teaching(self):
        from unittest.mock import patch
        from bilqis_mlx.learning.champions import Checkpoint
        from bilqis_mlx.runtime.autonomy_live import LiveAutonomySession
        from bilqis_mlx.runtime.candidate_staging import load_staged_candidates
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            session = LiveAutonomySession.open(root, LEGACY, self.current)
            with patch("bilqis_mlx.factory.candidate_frontier.load_candidate_frontier",
                       return_value=self.frontier), patch(
                       "bilqis_mlx.runtime.source_development.prepare_source_frontier"), patch(
                       "bilqis_mlx.runtime.source_development.persist_source_development"):
                proposal, _ = session.propose_source_frontier_work(
                    Checkpoint("e" * 64, "bundles/fixture", 0, True), self.parent_graph)
            self.assertEqual(proposal.disposition, ProposalDisposition.SOURCE_DEVELOPMENT)
            self.assertEqual(load_staged_candidates(root, self.frontier, self.current),
                             (self.staged,))
            self.assertEqual(session.ledger.receipts, ())

    def test_ready_catalog_proposal_uses_existing_student_transaction(self):
        from unittest.mock import Mock, patch
        from bilqis_mlx.curriculum.scheduler import start_new
        from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
        from bilqis_mlx.learning.champions import Checkpoint
        from bilqis_mlx.trainer import _adopt_jit_proposal
        checkpoint = Checkpoint("e" * 64, "bundles/fixture", 7, True)
        program = schedule_program_from_executable_release(self.current)
        school = replace(start_new(program, checkpoint), stage="AWAITING_NEXT_GRADE", queue=())
        expected = {cap.id: {"correct": cap.exam_item_count, "total": cap.exam_item_count}
                    for grade in program.grades for cap in grade.capabilities}
        receipt = dict(school={}, last_exam=dict(student_sha256=checkpoint.sha256,
                       optimizer_step=7, scores=expected))
        session = Mock()
        session.resolve_ready_proposal.return_value = self.staged
        parameters, optimizer = object(), object()
        with patch('bilqis_mlx.runtime.admission._require_executable_factory_admission', return_value=self.current), \
                patch('bilqis_mlx.runtime.state._state_from_json', return_value=school), \
                patch('bilqis_mlx.runtime.release_adoption._adopt_catalog_profile', return_value="adopted") as adopt:
            self.assertEqual(_adopt_jit_proposal(None, Path("unused"), receipt, None,
                LEGACY, self.parent_graph, parameters, optimizer, session, object(),
                reserve_gib=0), "adopted")
            self.assertIs(adopt.call_args.args[7], optimizer)
            self.assertEqual(adopt.call_args.args[8].graph, self.graph)
            self.assertEqual(adopt.call_args.kwargs["compiled_successor"], self.staged.successor)
            adopt.reset_mock()
            receipt["last_exam"] = {}
            with self.assertRaisesRegex(ValueError, "COMPLETE_PERFECT_PREFIX"):
                _adopt_jit_proposal(None, Path("unused"), receipt, None, LEGACY,
                    self.parent_graph, parameters, optimizer, session, object(), reserve_gib=0)
            adopt.assert_not_called()


if __name__ == "__main__":
    unittest.main()
