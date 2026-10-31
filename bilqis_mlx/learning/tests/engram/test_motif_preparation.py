"""MotifPreparationTests through the existing engram owner contracts."""
from bilqis_mlx.learning.tests.test_atlas_engram_allocation import (
    BilqisError, CandidateMotifView, GenerationExtents, MAX_CANDIDATE_ALLOCATIONS,
    MAX_MOTIF_CAPACITY, MOTIF_PAGE_STATE_BYTES, ModelTopologySpecV2, MotifBudget,
    MotifManifest, MotifPageGrowth, MotifSlot, RELEASE,
    TestCase, _plan_page_growth, candidate_motif_manifest, expected_bamf_shapes,
    full_first_page, hashlib, initialize_bamf_row, initialize_planned_motif_slot,
    motif_keys, np, patch, prepare_motifs,
    replace, source,
)


class MotifPreparationTests(TestCase):
    def test_exact_hit_precedes_structural_hit(self):
        sample = source()
        exact, structural = motif_keys(sample, RELEASE)
        parent = MotifManifest(RELEASE, (
            MotifSlot(0, structural), MotifSlot(1, exact)))
        before = parent.digest
        view = prepare_motifs((sample,), parent, MotifBudget(0))
        self.assertEqual(view.matches[0].disposition, "EXACT")
        self.assertEqual(view.matches[0].slot_id, 1)
        self.assertEqual(view.plan.allocated, ())
        self.assertEqual(view.plan.pending, ())
        self.assertEqual(parent.digest, before)

    def test_structural_first_then_exact_and_deterministic_use_priority(self):
        frequent = source(actor="urn:actor:frequent", occurrence="3" * 64)
        rare = source(actor="urn:actor:rare", occurrence="4" * 64)
        observations = (rare, frequent, frequent, frequent)
        first = prepare_motifs(observations, MotifManifest(RELEASE), MotifBudget(4))
        second = prepare_motifs(observations, MotifManifest(RELEASE), MotifBudget(4))
        self.assertEqual(first, second)
        self.assertEqual([slot.slot_id for slot in first.plan.allocated], [0, 1, 2])
        self.assertEqual(
            [slot.key.kind for slot in first.plan.allocated],
            ["STRUCTURAL", "EXACT", "EXACT"])
        self.assertEqual(first.plan.allocated[1].key,
                         motif_keys(frequent, RELEASE)[0])
        self.assertEqual(first.matches[0].disposition, "EXACT")
        self.assertEqual(first.matches[1].disposition, "EXACT")
        self.assertEqual(first.plan.pending, ())

    def test_at_most_64_new_slots_and_unallocated_keys_remain_pending(self):
        observations = tuple(
            source(actor=f"urn:actor:{i}", occurrence=f"{i:064x}")
            for i in range(70))
        parent = MotifManifest(RELEASE)
        view = prepare_motifs(observations, parent, MotifBudget(64))
        self.assertIsInstance(view, CandidateMotifView)
        self.assertEqual(len(view.plan.allocated), MAX_CANDIDATE_ALLOCATIONS)
        self.assertEqual(len(view.plan.pending), 7)
        self.assertEqual(view.plan.allocated[0].key.kind, "STRUCTURAL")
        self.assertEqual(len(parent.slots), 0)
        self.assertEqual(len(view.matches), 70)
        self.assertEqual(
            sum(item.disposition == "STRUCTURAL" for item in view.matches), 7)

    def test_zero_allocation_budget_keeps_factorized_fallback_and_parent_bytes(self):
        occupied = motif_keys(source(), RELEASE)[0]
        parent = MotifManifest(RELEASE, (MotifSlot(0, occupied),))
        sample = source(types=("Frame",), actor="urn:child:other")
        before = parent.digest
        view = prepare_motifs((sample,), parent, MotifBudget(0))
        self.assertEqual(view.matches[0].disposition, "FACTORIZED_FALLBACK")
        self.assertIsNone(view.matches[0].slot_id)
        self.assertEqual(view.plan.allocated, ())
        self.assertEqual(len(view.plan.pending), 2)
        self.assertEqual(parent.digest, before)

    def test_forced_hash_bucket_collision_never_aliases_full_key(self):
        a = motif_keys(source(), RELEASE)[0]
        b = motif_keys(source(actor="urn:actor:carol"), RELEASE)[0]
        c = motif_keys(source(actor="urn:actor:dan"), RELEASE)[0]
        manifest = MotifManifest(RELEASE, (MotifSlot(0, a), MotifSlot(1, b)))
        with patch("bilqis_mlx.learning.atlas_engram._bucket", return_value="collision"):
            self.assertEqual(manifest.lookup(a), 0)
            self.assertEqual(manifest.lookup(b), 1)
            self.assertIsNone(manifest.lookup(c))

    def test_budget_and_manifest_fail_closed(self):
        for invalid in (-1, 65, True):
            with self.assertRaises(BilqisError):
                MotifBudget(invalid)
        exact = motif_keys(source(), RELEASE)[0]
        with self.assertRaises(BilqisError):
            MotifManifest(RELEASE, (MotifSlot(1, exact),))
        with self.assertRaises(BilqisError):
            MotifManifest(RELEASE, (MotifSlot(0, exact), MotifSlot(1, exact)))
        with self.assertRaises(BilqisError):
            MotifManifest(RELEASE, (MotifSlot(0, exact),), capacity=0)
        with self.assertRaises(BilqisError):
            MotifManifest(RELEASE, (MotifSlot(0, exact),), capacity=1)
        with self.assertRaises(BilqisError):
            MotifManifest(RELEASE, (MotifSlot(0, exact),), capacity=65537)

    def test_full_page_grows_once_only_with_explicit_state_budget(self):
        parent = full_first_page()
        before = parent.digest
        insufficient = prepare_motifs(
            (source(),), parent,
            MotifBudget(2, page_growth_bytes=MOTIF_PAGE_STATE_BYTES - 1))
        self.assertEqual(insufficient.page_growth.added_pages, 0)
        self.assertEqual(insufficient.plan.allocated, ())
        self.assertEqual(len(insufficient.plan.pending), 2)
        self.assertEqual(insufficient.matches[0].disposition, "FACTORIZED_FALLBACK")
        self.assertEqual(parent.digest, before)

        candidate = prepare_motifs(
            (source(),), parent,
            MotifBudget(2, page_growth_bytes=MOTIF_PAGE_STATE_BYTES))
        self.assertEqual(candidate.page_growth.added_pages, 1)
        self.assertEqual(candidate.page_growth.reserved_state_bytes, 25165824)
        self.assertEqual(candidate.page_growth.declared_budget_bytes, 25165824)
        self.assertEqual(candidate.page_growth.candidate_capacity, 32768)
        self.assertEqual([slot.slot_id for slot in candidate.plan.allocated],
                         [16384, 16385])
        self.assertEqual(candidate.plan.pending, ())
        next_manifest = candidate_motif_manifest(parent, candidate)
        self.assertEqual(next_manifest.capacity, 32768)
        self.assertEqual(next_manifest.slots[:16384], parent.slots)
        self.assertEqual(next_manifest.lookup(candidate.plan.allocated[0].key), 16384)
        self.assertEqual(parent.capacity, 16384)
        self.assertEqual(parent.digest, before)

    def test_planned_row_uses_b01_deterministic_seed_and_page_identity(self):
        candidate = prepare_motifs(
            (source(),), full_first_page(),
            MotifBudget(2, page_growth_bytes=MOTIF_PAGE_STATE_BYTES))
        topology = ModelTopologySpecV2()
        extents = GenerationExtents(1, 2, "a" * 64, "b" * 64, "c" * 64)
        slot = candidate.plan.allocated[0]
        first = initialize_planned_motif_slot(
            candidate, slot.slot_id, run_seed=17,
            topology=topology, extents=extents)
        second = initialize_planned_motif_slot(
            candidate, slot.slot_id, run_seed=17,
            topology=topology, extents=extents)
        self.assertEqual(first.shape, (128,))
        self.assertEqual(first.dtype, np.float32)
        self.assertEqual(hashlib.sha256(first.tobytes()).hexdigest(),
                         "b1755e52244d359a20084634c1329b87c09b9786491d8eaad1ac5b58ecc06599")
        np.testing.assert_array_equal(first, second)
        declared = next(item for item in expected_bamf_shapes(topology, extents)
                        if item.name == "motif.page.1")
        np.testing.assert_array_equal(
            first, initialize_bamf_row(
                declared, run_seed=17, row_id=slot.key.digest))
        self.assertFalse(np.array_equal(
            first, initialize_planned_motif_slot(
                candidate, slot.slot_id, run_seed=18,
                topology=topology, extents=extents)))
        with self.assertRaises(BilqisError):
            initialize_planned_motif_slot(
                candidate, 0, run_seed=17, topology=topology, extents=extents)
        with self.assertRaises(BilqisError):
            initialize_planned_motif_slot(
                candidate, slot.slot_id, run_seed=17, topology=topology,
                extents=GenerationExtents(1, 1, "a" * 64, "b" * 64, "c" * 64))

    def test_growth_when_candidate_fills_last_existing_slot(self):
        parent = MotifManifest(RELEASE, full_first_page().slots[:-1])
        without_growth = prepare_motifs(
            (source(),), parent, MotifBudget(2))
        self.assertEqual([slot.slot_id for slot in without_growth.plan.allocated],
                         [16383])
        self.assertEqual(len(without_growth.plan.pending), 1)
        self.assertEqual(without_growth.page_growth.added_pages, 0)
        with_growth = prepare_motifs(
            (source(),), parent,
            MotifBudget(2, page_growth_bytes=MOTIF_PAGE_STATE_BYTES))
        self.assertEqual([slot.slot_id for slot in with_growth.plan.allocated],
                         [16383, 16384])
        self.assertEqual(with_growth.page_growth.added_pages, 1)
        self.assertEqual(with_growth.plan.pending, ())
        self.assertEqual(parent.capacity, 16384)

    def test_page_growth_never_exceeds_four_pages_or_forges_parent(self):
        self.assertEqual(MAX_MOTIF_CAPACITY, 65536)
        with self.assertRaises(BilqisError):
            MotifPageGrowth(65536, 81920, 1, MOTIF_PAGE_STATE_BYTES,
                            MOTIF_PAGE_STATE_BYTES)
        with self.assertRaises(BilqisError):
            MotifPageGrowth(16384, 49152, 2, MOTIF_PAGE_STATE_BYTES * 2,
                            MOTIF_PAGE_STATE_BYTES * 2)
        with self.assertRaises(BilqisError):
            MotifPageGrowth(16384, 32768, 1, MOTIF_PAGE_STATE_BYTES,
                            MOTIF_PAGE_STATE_BYTES - 1)
        self.assertEqual(
            _plan_page_growth(65536, 65536, 2, MOTIF_PAGE_STATE_BYTES * 2).added_pages,
            0)
        self.assertEqual(
            _plan_page_growth(16384, 16383, 2, MOTIF_PAGE_STATE_BYTES).added_pages,
            1)
        for bad in (-1, True, 1.5):
            with self.assertRaises(BilqisError):
                MotifBudget(1, page_growth_bytes=bad)
        parent = MotifManifest(RELEASE)
        candidate = prepare_motifs((source(),), parent, MotifBudget(2))
        foreign = MotifManifest("9" * 64)
        with self.assertRaises(BilqisError):
            candidate_motif_manifest(foreign, candidate)
        forged = replace(candidate, page_growth=MotifPageGrowth(
            16384, 32768, 1, MOTIF_PAGE_STATE_BYTES, MOTIF_PAGE_STATE_BYTES))
        with self.assertRaises(BilqisError):
            candidate_motif_manifest(parent, forged)
