"""Contracts for Atlas projection snapshots."""
import unittest
from bilqis_mlx.semantics.tests.atlas.projection.helpers import (
    AtlasArtifactSelection,
    BilqisError,
    PRIOR_ABI,
    Path,
    _bindings,
    _fixture_bundle,
    _rewrite_artifact,
    compile_atlas_release,
    json,
    load_atlas_snapshot,
    load_pinned_atlas_snapshot,
    persist_atlas_release,
    shutil,
    tempfile,
)


class AtlasProjectionSnapshotsTests(unittest.TestCase):
    def test_pinned_selection_revalidates_mutated_fields(self):
        class WrappedText(str):
            pass

        with self.assertRaises(BilqisError) as wrapped:
            AtlasArtifactSelection(
                "nonexistent", WrappedText("0" * 64),
                "1" * 64, "2" * 64)
        self.assertEqual(
            wrapped.exception.context["reason"],
            "ATLAS_SOURCE_SELECTION_INVALID")
        selection = AtlasArtifactSelection(
            "nonexistent", "0" * 64, "1" * 64, "2" * 64)
        object.__setattr__(selection, "bundle_id", 123)
        with self.assertRaises(BilqisError) as caught:
            load_pinned_atlas_snapshot(selection)
        self.assertEqual(
            caught.exception.context["reason"],
            "ATLAS_SOURCE_SELECTION_INVALID")
        with self.assertRaises(BilqisError) as invalid_expected:
            load_atlas_snapshot("nonexistent", expected_bundle_id=123)
        self.assertEqual(
            invalid_expected.exception.context["reason"],
            "ATLAS_SNAPSHOT_EXPECTED_PIN_INVALID")

    def test_pinned_atlas_selection_rejects_repacked_same_family_substitutions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, coverage, *_ = _fixture_bundle(root)
            release = compile_atlas_release(bundle, coverage, PRIOR_ABI, _bindings())
            receipt = persist_atlas_release(release, root / "artifacts")
            pin = AtlasArtifactSelection(
                receipt.path, receipt.bundle_id, release.digest,
                release.source_bundle_id)
            issued = load_atlas_snapshot(
                receipt.path, expected_bundle_id=receipt.bundle_id,
                expected_release_sha256=release.digest,
                expected_source_bundle_id=release.source_bundle_id)
            self.assertEqual(
                issued.formal_domain_bindings,
                release.formal_domain_bindings)
            with self.assertRaises(BilqisError) as unpinned:
                load_pinned_atlas_snapshot(pin)
            self.assertEqual(
                unpinned.exception.context["reason"],
                "ATLAS_SOURCE_PIN_NOT_REGISTERED")
            with self.assertRaises(BilqisError) as wrong_release:
                load_atlas_snapshot(
                    receipt.path, expected_bundle_id=receipt.bundle_id,
                    expected_release_sha256="0" * 64,
                    expected_source_bundle_id=release.source_bundle_id)
            self.assertEqual(
                wrong_release.exception.context["reason"],
                "ATLAS_SNAPSHOT_EXPECTED_RELEASE_MISMATCH")

            for replacement in (
                    ("legacy:cogal.operator.OR",),
                    ("legacy:cogal.operator.OR", "legacy:cogal.operator.XOR")):
                with self.subTest(replacement=replacement):
                    trial_root = root / ("trial-" + str(len(replacement)))
                    trial_root.mkdir()
                    copy = trial_root / receipt.bundle_id
                    shutil.copytree(receipt.path, copy)
                    atlas = json.loads((copy / "atlas.json").read_text())
                    atlas["formal_domain_bindings"][0]["semantic_ids"] = list(
                        replacement)
                    repacked = _rewrite_artifact(copy, "atlas.json", atlas)
                    self.assertNotEqual(repacked.name, receipt.bundle_id)
                    with self.assertRaises(BilqisError) as caught:
                        load_atlas_snapshot(
                            repacked, expected_bundle_id=receipt.bundle_id,
                            expected_release_sha256=release.digest,
                            expected_source_bundle_id=release.source_bundle_id)
                    self.assertEqual(
                        caught.exception.context["reason"],
                        "ATLAS_SNAPSHOT_EXPECTED_BUNDLE_MISMATCH")
                    with self.assertRaises(BilqisError) as self_attested:
                        load_pinned_atlas_snapshot(AtlasArtifactSelection(
                            str(repacked), repacked.name, release.digest,
                            release.source_bundle_id))
                    self.assertEqual(
                        self_attested.exception.context["reason"],
                        "ATLAS_SOURCE_PIN_NOT_REGISTERED")

    def test_database_free_snapshot_rejects_tamper_missing_identity_and_latest_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, coverage, *_ = _fixture_bundle(root)
            release = compile_atlas_release(bundle, coverage, PRIOR_ABI, _bindings())
            receipt = persist_atlas_release(release, root / "artifacts")
            artifact = Path(receipt.path)

            with self.assertRaises(BilqisError) as mismatch:
                load_atlas_snapshot(
                    artifact,
                    expected_release_sha256="0" * 64,
                    expected_source_bundle_id=release.source_bundle_id,
                )
            self.assertIn("ATLAS_SNAPSHOT_EXPECTED_RELEASE_MISMATCH",
                          str(mismatch.exception.context.get("reason")))

            with self.assertRaises(BilqisError) as source_mismatch:
                load_atlas_snapshot(
                    artifact,
                    expected_release_sha256=release.digest,
                    expected_source_bundle_id="0" * 64,
                )
            self.assertIn("ATLAS_SNAPSHOT_EXPECTED_SOURCE_RELEASE_MISMATCH",
                          str(source_mismatch.exception.context.get("reason")))

            latest = artifact.parent / "latest"
            artifact.rename(latest)
            with self.assertRaises(BilqisError) as alias:
                load_atlas_snapshot(latest)
            self.assertIn("ATLAS_SNAPSHOT_BUNDLE_PATH_INVALID",
                          str(alias.exception.context.get("reason")))
            latest.rename(artifact)

            atlas = json.loads((artifact / "atlas.json").read_text())
            atlas.pop("source_bundle_id")
            artifact = _rewrite_artifact(artifact, "atlas.json", atlas)
            with self.assertRaises(BilqisError) as missing:
                load_atlas_snapshot(artifact)
            self.assertIn("ATLAS_SNAPSHOT_ATLAS_INVALID",
                          str(missing.exception.context.get("reason")))

    def test_database_free_snapshot_rejects_payload_digest_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, coverage, *_ = _fixture_bundle(root)
            release = compile_atlas_release(bundle, coverage, PRIOR_ABI, _bindings())
            receipt = persist_atlas_release(release, root / "artifacts")
            artifact = Path(receipt.path)
            manifest_before = (artifact / "manifest.json").read_bytes()
            with (artifact / "concepts.jsonl").open("ab") as output:
                output.write(b" ")
            with self.assertRaises(BilqisError) as caught:
                load_atlas_snapshot(artifact)
            self.assertEqual((artifact / "manifest.json").read_bytes(), manifest_before)
        self.assertIn("ATLAS_SNAPSHOT_FILE_DIGEST_MISMATCH:concepts.jsonl",
                      str(caught.exception.context.get("reason")))
