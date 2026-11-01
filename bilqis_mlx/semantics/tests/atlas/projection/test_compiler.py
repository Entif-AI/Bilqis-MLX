"""Contracts for Atlas projection compiler."""
import unittest
from bilqis_mlx.semantics.tests.atlas.projection.helpers import (
    BilqisError,
    PRIOR_ABI,
    Path,
    XSD,
    _bindings,
    _fixture_bundle,
    compile_atlas_release,
    json,
    tempfile,
    validate_atlas_release,
)


class AtlasProjectionCompilerTests(unittest.TestCase):
    def test_source_qualified_root_senses_realizations_and_hold_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle, coverage, root_id, sense_a, sense_b, held_id = _fixture_bundle(Path(directory))
            release = compile_atlas_release(bundle, coverage, PRIOR_ABI, _bindings())
            validation = validate_atlas_release(release)

        self.assertEqual(validation.status, "valid")
        self.assertEqual(release.digest, validation.release_sha256)
        self.assertEqual([item.semantic_id for item in release.concepts],
                         sorted(item.semantic_id for item in release.concepts))
        by_id = {item.semantic_id: item for item in release.concepts}
        self.assertEqual(by_id[root_id].kind, "root")
        self.assertEqual({value.value for value in by_id[root_id].realizations}, {"-T-", "-Tʼ-"})
        self.assertEqual([(label.value, label.language) for label in by_id[root_id].labels
                          if label.value == "variant"], [("variant", None), ("variant", "en")])
        self.assertEqual([(value.value, value.datatype) for value in by_id[root_id].realizations
                          if value.value == "-T-"],
                         [("-T-", None), ("-T-", str(XSD.string))])
        self.assertEqual(by_id[sense_a].kind, "sense")
        self.assertEqual(by_id[sense_b].kind, "sense")
        self.assertNotEqual(sense_a, sense_b)
        self.assertNotIn(held_id, by_id)
        held = next(item for item in release.held_mappings if item.semantic_id == held_id)
        self.assertEqual(held.reason_code, "MAPPING_REVIEW_PENDING")
        self.assertEqual({item.family for item in release.formal_domain_bindings},
                         {"boolean", "numeric"})
        self.assertEqual(release.counts.trainable_capabilities, 4)

    def test_same_pinned_inputs_are_byte_identity_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle, coverage, *_ = _fixture_bundle(Path(directory))
            first = compile_atlas_release(bundle, coverage, PRIOR_ABI, _bindings())
            second = compile_atlas_release(bundle, coverage, PRIOR_ABI, tuple(reversed(_bindings())))
        self.assertEqual(first, second)
        self.assertEqual(first.digest, second.digest)
        self.assertEqual(first.abi_entries, second.abi_entries)

    def test_stale_coverage_is_rejected_before_release(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle, coverage, *_ = _fixture_bundle(Path(directory))
            stale = json.loads(json.dumps(coverage))
            stale["canonical_rdf"]["sha256"] = "0" * 64
            with self.assertRaises(BilqisError) as caught:
                compile_atlas_release(bundle, stale, PRIOR_ABI, _bindings())
        self.assertEqual(caught.exception.code, "SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID")
        self.assertIn("ATLAS_COVERAGE_RECEIPT_STALE", str(caught.exception.context.get("reason")))
