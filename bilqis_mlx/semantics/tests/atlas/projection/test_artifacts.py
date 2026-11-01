"""Contracts for Atlas projection artifacts."""
from bilqis_mlx.semantics.tests.atlas.projection.helpers import (
    Counter,
    PRIOR_ABI,
    Path,
    _bindings,
    _sha,
    compile_atlas_release,
    hashlib,
    json,
    load_atlas_snapshot,
    os,
    persist_atlas_release,
    tempfile,
    unittest,
    validate_atlas_release,
)


class AtlasProjectionArtifactsTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("BILQIS_ATLAS_REAL_CORPUS"),
                         "real canonical conformance bundle supplied only at turn-in")
    def test_real_corpus_witness(self):
        bundle = Path(os.environ["BILQIS_ATLAS_REAL_CORPUS"])
        coverage = json.loads((bundle / "coverage.json").read_text())
        release = compile_atlas_release(bundle, coverage, PRIOR_ABI, _bindings())
        validation = validate_atlas_release(release)
        with tempfile.TemporaryDirectory() as directory:
            receipt = persist_atlas_release(release, Path(directory))
            target = Path(receipt.path)
            real_manifest = (target / "manifest.json").read_bytes()
            real_files = {path.name for path in target.iterdir()}
            snapshot = load_atlas_snapshot(
                target,
                expected_bundle_id=receipt.bundle_id,
                expected_release_sha256=release.digest,
                expected_source_bundle_id=release.source_bundle_id,
            )
        self.assertEqual(release.canonical_rdf_sha256,
                         "7a0a0cd04133be41db69ca3fe1e2f09b4efbc8c965610b75c5ac30bc0954b50e")
        self.assertEqual(release.source_row_count, 25692)
        self.assertEqual(len(release.held_mappings), 552)
        self.assertEqual(Counter(item.kind for item in release.concepts),
                         Counter({"concept": 104, "root": 5967, "sense": 3008}))
        self.assertEqual(validation.concept_count, 9079)
        self.assertGreater(sum(len(item.realizations) for item in release.concepts), 0)
        self.assertEqual(validation.formal_binding_count, 2)
        self.assertEqual(release.prior_abi_sha256, _sha(PRIOR_ABI))
        self.assertIn(("prior_abi", "UNVERSIONED"), release.input_schemas)
        self.assertEqual(
            release.digest,
            "58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306",
        )
        self.assertEqual(
            receipt.bundle_id,
            "5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7",
        )
        self.assertEqual(
            release.shape_policy_sha256,
            "72eef37c3d6225a50ed4ace7b389c34d6442e9917facd103d30c726aaa05f197",
        )
        self.assertEqual(
            release.active_set_sha256,
            "173287b6e9ea90e4f9d88dc6ddb136772828a0cafcd47bda952d24f9da433790",
        )
        self.assertEqual(dict(receipt.file_sha256), {
            "atlas.json": "2a90023131aafb803df618f263dff639aa1088175e2138593f4314e8ec45023d",
            "concepts.jsonl": "c10d456a31579d4bf2b5a917f9ffc3e4d2e95f275458fb6dc0403938e28395ab",
            "held.jsonl": "f86f3f94f468abc153f84483bb3380a53f284bc19a2efea98a16fbb3b974fb4c",
            "relations.jsonl": "ac70a12785da4cc201e543ec54c5b02530ee6bcdda57dbc05c92c676cf52c938",
        })
        self.assertEqual(release.counts.abi_entries, 9307)
        self.assertEqual(release.counts.abi_banks, 2)
        self.assertEqual(release.counts.active_abi_indices, 228)
        self.assertEqual(release.counts.trainable_capabilities, 4)
        self.assertEqual(release.counts.source_held, 1052)
        self.assertEqual(release.counts.source_ir_only, 9488)
        self.assertEqual(release.counts.implementation_uncovered, 9079)
        self.assertEqual(release.counts.rdf_terms, 67448)
        self.assertEqual(receipt.bundle_id, hashlib.sha256(real_manifest).hexdigest())
        self.assertEqual(real_files, {"atlas.json", "concepts.jsonl", "relations.jsonl",
                                      "held.jsonl", "manifest.json"})
        self.assertEqual(snapshot.counts, release.counts)
        self.assertEqual(snapshot.source_bundle_id, release.source_bundle_id)
        self.assertEqual(snapshot.abi(8192).index, 8192)
        witness = snapshot.concepts[0]
        self.assertEqual(
            snapshot.concept(witness.concept.semantic_id).abi_index,
            witness.abi_index)
        self.assertEqual(len(snapshot.source_hold_census()), 1052)
