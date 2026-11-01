"""Contracts for Atlas projection abi."""
import unittest
from bilqis_mlx.semantics.tests.atlas.projection.helpers import (
    AbiEntry,
    BANK_SIZE,
    BilqisError,
    PRIOR_ABI,
    Path,
    _bindings,
    _fixture_bundle,
    compile_atlas_release,
    hashlib,
    json,
    load_atlas_snapshot,
    persist_atlas_release,
    replace,
    tempfile,
)


class AtlasProjectionAbiTests(unittest.TestCase):
    def test_append_only_abi_and_content_addressed_files_preserve_prior_bytes(self):
        prior_before = PRIOR_ABI.read_bytes()
        prior_rows = json.loads(prior_before)["rows"][1:]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, coverage, root_id, sense_a, sense_b, held_id = _fixture_bundle(root)
            release = compile_atlas_release(bundle, coverage, PRIOR_ABI, _bindings())
            output = root / "artifacts"
            first = persist_atlas_release(release, output)
            second = persist_atlas_release(release, output)
            target = Path(first.path)
            files = {path.name for path in target.iterdir()}
            manifest_bytes = (target / "manifest.json").read_bytes()
            atlas = json.loads((target / "atlas.json").read_text())
            withheld = [json.loads(line) for line in (target / "held.jsonl").read_text().splitlines()]
            snapshot = load_atlas_snapshot(
                target,
                expected_bundle_id=first.bundle_id,
                expected_release_sha256=release.digest,
                expected_source_bundle_id=release.source_bundle_id,
            )

        self.assertEqual(PRIOR_ABI.read_bytes(), prior_before)
        self.assertEqual(first.bundle_id, hashlib.sha256(manifest_bytes).hexdigest())
        self.assertEqual(first, second)
        self.assertEqual(files, {"atlas.json", "concepts.jsonl", "relations.jsonl",
                                 "held.jsonl", "manifest.json"})
        self.assertEqual(len(prior_rows), 228)
        for index, row in enumerate(prior_rows):
            entry = release.abi_entries[index]
            self.assertEqual((entry.index, entry.bank, entry.row),
                             (index, index // BANK_SIZE, index % BANK_SIZE))
            self.assertEqual((entry.symbol, entry.semantic_id), (row[1], row[2]))
            self.assertTrue(entry.active)
        appended = release.abi_entries[len(prior_rows):]
        self.assertEqual([entry.semantic_id for entry in appended],
                         sorted((root_id, sense_a, sense_b)))
        self.assertTrue(all(not entry.active and entry.reason == "IMPLEMENTATION_UNCOVERED"
                            for entry in appended))
        self.assertNotIn(held_id, {entry.semantic_id for entry in release.abi_entries})
        self.assertEqual(atlas["counts"], {
            "abi_banks": 1,
            "abi_entries": 231,
            "active_abi_indices": 228,
            "implementation_uncovered": 3,
            "rdf_terms": release.rdf_term_count,
            "semantic_concepts": 3,
            "source_held": 4,
            "source_ir_only": 1,
            "source_rows": 11,
            "trainable_capabilities": 4,
        })
        held = next(row for row in withheld if row["semantic_id"] == held_id)
        self.assertEqual((held["source_disposition"], held["teaching_reason"]),
                         ("SOURCE_HELD", "MAPPING_REVIEW_PENDING"))
        uncovered = next(row for row in withheld if row["semantic_id"] == root_id)
        self.assertEqual((uncovered["source_disposition"], uncovered["implementation_status"],
                          uncovered["teaching_reason"]),
                         ("SOURCE_ELIGIBLE", "IMPLEMENTATION_UNCOVERED",
                          "IMPLEMENTATION_UNCOVERED"))
        self.assertEqual(snapshot.abi(227).semantic_id, prior_rows[227][2])
        self.assertEqual(snapshot.abi_for_semantic(root_id).semantic_id, root_id)
        self.assertEqual(snapshot.concept(root_id).concept.semantic_id, root_id)
        self.assertEqual(len(snapshot.source_hold_census()), 4)
        self.assertEqual(len({
            row.semantic_id for row in snapshot.implementation_uncovered_census()
            if row.semantic_id}), 3)
        with self.assertRaises(BilqisError):
            snapshot.abi_for_semantic(held_id)

    def test_forged_abi_entry_for_held_identity_is_rejected_without_artifact_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, coverage, *_, held_id = _fixture_bundle(root)
            release = compile_atlas_release(bundle, coverage, PRIOR_ABI, _bindings())
            receipt = persist_atlas_release(release, root / "artifacts")
            manifest = Path(receipt.path) / "manifest.json"
            atlas = Path(receipt.path) / "atlas.json"
            held = Path(receipt.path) / "held.jsonl"
            before = (manifest.read_bytes(), atlas.read_bytes(), held.read_bytes())
            index = len(release.abi_entries)
            forged = replace(release, abi_entries=(*release.abi_entries, AbiEntry(
                index=index,
                bank=index // BANK_SIZE,
                row=index % BANK_SIZE,
                semantic_id=held_id,
                symbol="attacker.requested-held-meaning",
                source="CANONICAL_SKOS",
                active=True,
                teaching_candidate=True,
                reason="REQUESTED_LEARNER_ACTIVATION",
            )))
            with self.assertRaises(BilqisError) as caught:
                persist_atlas_release(forged, root / "artifacts")
            self.assertEqual(
                (manifest.read_bytes(), atlas.read_bytes(), held.read_bytes()), before)
        self.assertIn("ATLAS_HELD_IDENTITY_ADMITTED",
                      str(caught.exception.context.get("reason")))

    def test_prior_atlas_requires_verified_snapshot_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, coverage, *_ = _fixture_bundle(root)
            release = compile_atlas_release(bundle, coverage, PRIOR_ABI, _bindings())
            receipt = persist_atlas_release(release, root / "artifacts")
            snapshot = load_atlas_snapshot(
                receipt.path,
                expected_bundle_id=receipt.bundle_id,
                expected_release_sha256=release.digest,
                expected_source_bundle_id=release.source_bundle_id,
            )

            successor = compile_atlas_release(
                bundle, coverage, snapshot, _bindings())
            self.assertEqual(successor.abi_entries, release.abi_entries)
            self.assertEqual(successor.prior_abi_sha256, receipt.bundle_id)
            self.assertIn(
                ("prior_abi", "bilqis.semantic-atlas-artifact/v1"),
                successor.input_schemas,
            )

            with self.assertRaises(BilqisError) as caught:
                compile_atlas_release(
                    bundle,
                    coverage,
                    Path(receipt.path) / "atlas.json",
                    _bindings(),
                )
        self.assertIn("ATLAS_PRIOR_ABI_PROVENANCE_REQUIRED",
                      str(caught.exception.context.get("reason")))
