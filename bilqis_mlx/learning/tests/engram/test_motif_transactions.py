"""MotifTransactionTests through the existing engram owner contracts."""
from bilqis_mlx.learning.tests.test_atlas_engram_allocation import (
    BilqisError, CandidateMotifSnapshot, INITIAL_MOTIF_CAPACITY, MOTIF_PAGE_STATE_BYTES,
    MotifAliasArtifact, MotifAllocationSnapshot, MotifBudget, MotifManifest,
    MotifSlot, RELEASE, TestCase, full_first_page,
    motif_keys, prepare_candidate_motif_snapshot, replace, source,
    verify_candidate_motif_snapshot,
)


class MotifTransactionTests(TestCase):
    def test_rejection_preserves_parent_slots_counters_and_replay_is_deterministic(self):
        parent = MotifAllocationSnapshot(MotifManifest(RELEASE))
        before = parent.digest
        observations = (source(), source(actor="urn:actor:carol"))
        first = prepare_candidate_motif_snapshot(
            observations, parent, MotifBudget(4))
        second = prepare_candidate_motif_snapshot(
            observations, parent, MotifBudget(4))
        self.assertIsInstance(first, CandidateMotifSnapshot)
        self.assertEqual(first, second)
        self.assertEqual(first.digest, second.digest)
        self.assertEqual(len(first.proposed.manifest.slots), 3)
        self.assertEqual(len(first.proposed.observed_uses), 3)
        self.assertEqual(parent.digest, before)
        self.assertEqual(parent.manifest.slots, ())
        self.assertEqual(parent.observed_uses, ())
        verify_candidate_motif_snapshot(
            first, frames=observations, parent=parent, budget=MotifBudget(4))

    def test_prior_accepted_counters_change_priority_without_parent_mutation(self):
        rare = source(actor="urn:actor:rare", occurrence="3" * 64)
        frequent = source(actor="urn:actor:frequent", occurrence="4" * 64)
        rare_exact = motif_keys(rare, RELEASE)[0]
        parent = MotifAllocationSnapshot(
            MotifManifest(RELEASE), ((rare_exact.digest, 100),))
        before = parent.digest
        proposal = prepare_candidate_motif_snapshot(
            (rare, frequent, frequent, frequent), parent, MotifBudget(3))
        allocated = proposal.view.plan.allocated
        self.assertEqual([slot.key.kind for slot in allocated],
                         ["STRUCTURAL", "EXACT", "EXACT"])
        self.assertEqual(allocated[1].key, rare_exact)
        self.assertEqual(dict(proposal.proposed.observed_uses)[rare_exact.digest], 101)
        self.assertEqual(parent.digest, before)
        self.assertEqual(parent.observed_uses, ((rare_exact.digest, 100),))

    def test_replay_rejects_validly_shaped_forged_counters_slots_and_parent(self):
        parent = MotifAllocationSnapshot(MotifManifest(RELEASE))
        frames = (source(),)
        budget = MotifBudget(2)
        candidate = prepare_candidate_motif_snapshot(frames, parent, budget)
        wrong_counts = replace(candidate.proposed, observed_uses=(
            (candidate.proposed.observed_uses[0][0], 999),))
        with self.assertRaises(BilqisError):
            verify_candidate_motif_snapshot(
                replace(candidate, proposed=wrong_counts),
                frames=frames, parent=parent, budget=budget)
        foreign_parent = MotifAllocationSnapshot(
            MotifManifest(RELEASE, (candidate.proposed.manifest.slots[0],)))
        with self.assertRaises(BilqisError):
            verify_candidate_motif_snapshot(
                candidate, frames=frames, parent=foreign_parent, budget=budget)
        changed_slot = replace(
            candidate.proposed.manifest.slots[1],
            key=motif_keys(source(actor="urn:actor:other"), RELEASE)[0])
        forged_manifest = replace(
            candidate.proposed.manifest,
            slots=(candidate.proposed.manifest.slots[0], changed_slot))
        with self.assertRaises(BilqisError):
            verify_candidate_motif_snapshot(
                replace(candidate, proposed=replace(
                    candidate.proposed, manifest=forged_manifest)),
                frames=frames, parent=parent, budget=budget)

    def test_alias_is_explicit_attested_artifact_not_an_implicit_slot_remap(self):
        exact = motif_keys(source(), RELEASE)[0]
        parent = MotifAllocationSnapshot(
            MotifManifest(RELEASE, (MotifSlot(0, exact),)))
        alias = MotifAliasArtifact(
            "9" * 64, "8" * 64, RELEASE, exact.digest, "7" * 64)
        proposal = prepare_candidate_motif_snapshot(
            (source(),), parent, MotifBudget(0), source_aliases=(alias,))
        self.assertEqual(proposal.proposed.aliases, (alias,))
        self.assertEqual(proposal.proposed.manifest.slots, parent.manifest.slots)
        self.assertEqual(proposal.proposed.manifest.lookup(exact), 0)
        self.assertEqual(parent.aliases, ())
        verify_candidate_motif_snapshot(
            proposal, frames=(source(),), parent=parent,
            budget=MotifBudget(0), source_aliases=(alias,))
        with self.assertRaises(BilqisError):
            prepare_candidate_motif_snapshot(
                (source(),), parent, MotifBudget(0),
                source_aliases=(alias, replace(alias, source_attestation_digest="6"*64)))
        with self.assertRaises(BilqisError):
            prepare_candidate_motif_snapshot(
                (source(),), parent, MotifBudget(0),
                source_aliases=(replace(alias, new_key_digest="5"*64),))

    def test_full_capacity_and_no_budget_keep_parent_state_unchanged(self):
        parent = MotifAllocationSnapshot(full_first_page())
        before = parent.digest
        candidate = prepare_candidate_motif_snapshot(
            (source(),), parent, MotifBudget(0))
        self.assertEqual(candidate.proposed.manifest, parent.manifest)
        self.assertEqual(candidate.view.plan.allocated, ())
        self.assertEqual(len(candidate.view.plan.pending), 2)
        self.assertEqual(len(candidate.proposed.pending_keys), 2)
        self.assertEqual(parent.digest, before)
        self.assertNotEqual(candidate.proposed.observed_uses, parent.observed_uses)

    def test_pending_keys_survive_candidate_boundary_and_allocate_without_reobservation(self):
        parent = MotifAllocationSnapshot(MotifManifest(RELEASE))
        observed = prepare_candidate_motif_snapshot(
            (source(),), parent, MotifBudget(0))
        self.assertEqual(len(observed.proposed.pending_keys), 2)
        self.assertEqual(len(observed.proposed.manifest.slots), 0)
        # Treat this snapshot only as a hypothetical B13-retained input.
        # No operation in this module publishes or accepts it.
        next_candidate = prepare_candidate_motif_snapshot(
            (), observed.proposed, MotifBudget(2))
        self.assertEqual(len(next_candidate.view.plan.allocated), 2)
        self.assertEqual(next_candidate.proposed.pending_keys, ())
        self.assertEqual(
            tuple(slot.key for slot in next_candidate.proposed.manifest.slots),
            observed.proposed.pending_keys)
        self.assertEqual(
            next_candidate.proposed.observed_uses,
            observed.proposed.observed_uses)
        self.assertEqual(parent.manifest.slots, ())
        self.assertEqual(parent.pending_keys, ())

    def test_candidate_page_growth_preserves_every_old_slot_and_parent_counter(self):
        parent = MotifAllocationSnapshot(
            full_first_page(), (("f" * 64, 7),))
        before = parent.digest
        candidate = prepare_candidate_motif_snapshot(
            (source(),), parent,
            MotifBudget(2, page_growth_bytes=MOTIF_PAGE_STATE_BYTES))
        self.assertEqual(candidate.view.page_growth.added_pages, 1)
        self.assertEqual(candidate.proposed.manifest.capacity, 32768)
        self.assertEqual(
            candidate.proposed.manifest.slots[:INITIAL_MOTIF_CAPACITY],
            parent.manifest.slots)
        self.assertEqual(
            [slot.slot_id for slot in candidate.view.plan.allocated],
            [16384, 16385])
        self.assertEqual(
            dict(candidate.proposed.observed_uses)["f" * 64], 7)
        self.assertEqual(parent.digest, before)

    def test_canonical_counter_validation_rejects_forged_state(self):
        parent = MotifManifest(RELEASE)
        for counts in (
            (("a" * 64, True),),
            (("a" * 64, 0),),
            (("b" * 64, 1), ("a" * 64, 2)),
            (("a" * 64, 1), ("a" * 64, 2)),
            (("not-a-digest", 1),),
        ):
            with self.subTest(counts=counts), self.assertRaises(BilqisError):
                MotifAllocationSnapshot(parent, counts)
