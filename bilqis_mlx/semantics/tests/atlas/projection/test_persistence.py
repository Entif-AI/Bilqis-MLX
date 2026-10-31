"""Contracts for Atlas projection persistence."""
import unittest
from bilqis_mlx.semantics.tests.atlas.projection.helpers import (
    BilqisError,
    PRIOR_ABI,
    Path,
    _bindings,
    _fixture_bundle,
    atlas_projection,
    compile_atlas_release,
    patch,
    persist_atlas_release,
    tempfile,
)


class AtlasProjectionPersistenceTests(unittest.TestCase):
    def test_parent_directory_sync_failure_is_unconfirmed_and_retry_reconfirms(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, coverage, *_ = _fixture_bundle(root)
            release = compile_atlas_release(bundle, coverage, PRIOR_ABI, _bindings())
            output_root = root / "artifacts"
            original_sync = atlas_projection._sync_directory

            def fail_parent(path, *, reason):
                if Path(path).resolve() == output_root.resolve():
                    atlas_projection._fail("ATLAS_ARTIFACT_PARENT_SYNC_FAILED:INJECTED")
                return original_sync(path, reason=reason)

            with patch(
                    "bilqis_mlx.semantics.atlas_projection_parts.persistence._sync_directory",
                    side_effect=fail_parent):
                with self.assertRaises(BilqisError) as caught:
                    persist_atlas_release(release, output_root)
            self.assertIn("ATLAS_ARTIFACT_PARENT_SYNC_FAILED:INJECTED",
                          str(caught.exception.context.get("reason")))

            targets = [path for path in output_root.iterdir() if not path.name.startswith(".")]
            self.assertEqual(len(targets), 1)
            self.assertTrue((targets[0] / "manifest.json").is_file())

            receipt = persist_atlas_release(release, output_root)
            self.assertEqual(Path(receipt.path).resolve(), targets[0].resolve())
            self.assertEqual(receipt.bundle_id, targets[0].name)
