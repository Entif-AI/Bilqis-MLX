import hashlib
from dataclasses import replace
import unittest

from bilqis_mlx.factory import candidate_realizations
from bilqis_mlx.factory.atlas_frontier import (
    AtlasCoverageEpoch,
    bind_realized_snapshot,
    next_atlas_delta,
    staged_selection_receipt,
)
from bilqis_mlx.factory.atlas_frontier_closure import resolve_frontier_closure
from bilqis_mlx.factory.atlas_frontier_events import FactoryAdmissionEvent, reconcile
from bilqis_mlx.factory.atlas_frontier_progress import plan_frontier_progress
from bilqis_mlx.factory.atlas_frontier_progress_contracts import FrontierStatus
from bilqis_mlx.factory.atlas_frontier_progress_validation import requested_keys
from bilqis_mlx.factory.atlas_frontier_selection import select_frontier_delta_for_projection
from bilqis_mlx.factory.autonomy import (
    EvidenceReceipt,
    compile_autonomy_plan,
    initial_evidence_ledger,
    obligations_for_capability,
    record_evidence,
)
from bilqis_mlx.factory.jit_curriculum import CurriculumDeltaProposal
from bilqis_mlx.factory.tests._event_candidate_realization_support import (
    EventCandidateRealizationFixture,
    LEGACY,
)
from bilqis_mlx.source_adapters import event_frames


class EventCandidateAtlasIntegrationTests(EventCandidateRealizationFixture, unittest.TestCase):
    def test_atlas_adapter_proposes_three_real_source_qualified_successors(self):
        candidate, source_frontier, policy = self.atlas_fixture()
        current = self.current
        graph = self.parent_graph
        observed = []
        mastered = {"A.IDENTITY"}
        prior = None
        admitted_snapshot = None

        for capability in event_frames.SOURCE_SPECS:
            semantic_id = event_frames.atlas_semantic_id(capability)
            staged = candidate_realizations.prepare_realized_candidate(
                self.frontier, current, graph, semantic_id,
                source_root=LEGACY, source_registry=self.source_registry,
                answer_registry=self.answer_registry,
            )
            snapshot = (
                self.build_snapshot(candidate, source_frontier, policy, current, staged)
                if admitted_snapshot is None else admitted_snapshot
            )
            snapshot = bind_realized_snapshot(
                snapshot, candidate, self.frontier, current, (staged,))

            translated = {
                (edge.semantic_id, edge.prerequisite_semantic_id, edge.status)
                for edge in snapshot.prerequisite_edges
            }
            if capability == "D.COMMENCEMENT":
                self.assertIn((
                    semantic_id,
                    event_frames.atlas_semantic_id("D.EVENT_OCCURRENCE"),
                    "FRONTIER_HYPOTHESIS_UNVERIFIED",
                ), translated)
            if capability == "D.TERMINATION":
                self.assertIn((
                    semantic_id,
                    event_frames.atlas_semantic_id("D.COMMENCEMENT"),
                    "FRONTIER_HYPOTHESIS_UNVERIFIED",
                ), translated)

            plan, checkpoint, step, ledger, learner = self.learner_evidence(
                current, mastered, capability)
            closure = resolve_frontier_closure(
                snapshot, candidate.census,
                current_release=current,
                evidence_ledger=ledger,
                autonomy_plan=plan,
                checkpoint_sha256=checkpoint,
                optimizer_step=step,
            )
            if prior is not None:
                prior = plan_frontier_progress(snapshot, closure, prior=prior)
                self.assertIs(prior.status, FrontierStatus.REPLAN_REQUIRED)
                snapshot = prior.planning_snapshot
                closure = resolve_frontier_closure(
                    snapshot, candidate.census,
                    current_release=current,
                    evidence_ledger=ledger,
                    autonomy_plan=plan,
                    checkpoint_sha256=checkpoint,
                    optimizer_step=step,
                )

            epoch = AtlasCoverageEpoch(
                snapshot=snapshot,
                closure=closure,
                candidate_frontier=self.frontier,
                current_release=current,
                staged_candidates=(staged,),
                prior=prior,
            )
            proposal = next_atlas_delta(epoch, learner, plan)
            self.assertIsInstance(proposal, CurriculumDeltaProposal)
            self.assertEqual(proposal.selected_candidate_ids, (staged.candidate_id,))
            self.assertEqual(
                proposal.selected_successor_sha256, staged.successor.release_sha256)

            rows = tuple(item for item in closure.candidates if item.semantic_id == semantic_id)
            requested = tuple(sorted(requested_keys(
                prior.staged_receipts if prior is not None else ())))
            projection = candidate_realizations.project_authoritative_target(
                semantic_id, current, rows)
            selection = select_frontier_delta_for_projection(
                snapshot, closure, current, projection, requested)
            receipt = staged_selection_receipt(epoch, selection, projection, staged)
            pending = plan_frontier_progress(
                snapshot, closure, selection,
                current_release=current,
                selected_projection=projection,
                prior=prior,
                staged_receipt=receipt,
            )
            self.assertIs(pending.status, FrontierStatus.LEASE_REQUIRED)

            admission = FactoryAdmissionEvent(
                predecessor_sha256=snapshot.snapshot_sha256,
                generation=snapshot.event_generation + 1,
                source_provenance_sha256=snapshot.source_coverage_sha256,
                factory_release_sha256=staged.successor.release_sha256,
                admission_receipt_sha256=hashlib.sha256(
                    f"test-admission:{capability}".encode()).hexdigest(),
                accepted=True,
                event_sha256="0" * 64,
            )
            admission = replace(admission, event_sha256=admission.expected_digest())
            admitted_snapshot = reconcile(snapshot, admission)
            prior = pending
            observed.append(capability)
            graph = candidate_realizations.admitted_candidate_graph(staged, graph)
            current = staged.successor
            mastered.add(capability)

        self.assertEqual(tuple(observed), tuple(event_frames.SOURCE_SPECS))
        final_snapshot = bind_realized_snapshot(
            admitted_snapshot, candidate, self.frontier, current, ())
        final_plan = compile_autonomy_plan(current)
        final_checkpoint = "e" * 64
        final_ledger = initial_evidence_ledger(current, plan=final_plan)
        final_index = 0
        for prerequisite in sorted(mastered):
            for obligation in obligations_for_capability(current, prerequisite, plan=final_plan):
                final_index += 1
                final_ledger = record_evidence(
                    current,
                    final_ledger,
                    EvidenceReceipt(
                        obligation.obligation_id,
                        f"final-event-prerequisite-{final_index}",
                        final_checkpoint,
                        0,
                        hashlib.sha256(f"final:{final_index}".encode()).hexdigest(),
                        obligation.minimum_specimens,
                        True,
                    ),
                    plan=final_plan,
                    current_checkpoint_sha256=final_checkpoint,
                    current_optimizer_step=0,
                )
        final_closure = resolve_frontier_closure(
            final_snapshot, candidate.census,
            current_release=current,
            evidence_ledger=final_ledger,
            autonomy_plan=final_plan,
            checkpoint_sha256=final_checkpoint,
            optimizer_step=0,
        )
        final_progress = plan_frontier_progress(final_snapshot, final_closure, prior=prior)
        event_ids = {
            event_frames.atlas_semantic_id(capability)
            for capability in event_frames.SOURCE_SPECS
        }
        self.assertTrue(all(
            row.implementation_status == "FACTORY_PROGRAM_BOUND_UNADMITTED"
            for row in final_snapshot.coverage_rows if row.semantic_id in event_ids
        ))
        self.assertEqual(final_progress.requested_semantic_ids, tuple(sorted(event_ids)))
        self.assertIs(final_progress.status, FrontierStatus.IMPLEMENTATION_UNCOVERED)
        self.assertEqual(final_progress.implementation_uncovered_count, 6)


if __name__ == "__main__":
    unittest.main()

