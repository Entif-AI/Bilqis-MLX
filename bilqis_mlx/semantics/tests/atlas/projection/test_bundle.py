"""Contracts for Atlas projection bundle."""
import os
import shutil
import unittest
from unittest.mock import patch

from bilqis_mlx.semantics.atlas_projection import (
    ATLAS_SOURCE_BUNDLE_ROOT_ENV,
    resolve_atlas_source_bundle,
)
from bilqis_mlx.semantics.tests.atlas.projection.helpers import (
    BilqisError,
    PRIOR_ABI,
    Path,
    _bindings,
    _fixture_bundle,
    _rewrite_bundle,
    compile_atlas_release,
    json,
    tempfile,
)


class AtlasProjectionBundleTests(unittest.TestCase):
    def test_source_bundle_locator_is_content_addressed_and_relocatable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original_root = root / "original"
            relocated_root = root / "relocated"
            original_root.mkdir()
            relocated_root.mkdir()
            bundle, *_ = _fixture_bundle(original_root)
            source_bundle_id = bundle.name
            relocated = relocated_root / source_bundle_id
            shutil.copytree(bundle, relocated)
            with patch.dict(
                    os.environ,
                    {ATLAS_SOURCE_BUNDLE_ROOT_ENV: str(relocated_root)},
                    clear=False):
                resolved = resolve_atlas_source_bundle(source_bundle_id)
            self.assertEqual(resolved, relocated)

    def test_source_bundle_locator_rejects_identity_substitution_and_path_attacks(self):
        cases = (
            "invalid_id",
            "missing",
            "wrong_id",
            "substituted_bytes",
            "unexpected_member",
            "symlink_bundle",
        )
        for kind in cases:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source_root = root / "source"
                storage_root = root / "storage"
                source_root.mkdir()
                storage_root.mkdir()
                bundle, *_ = _fixture_bundle(source_root)
                source_bundle_id = bundle.name
                requested = source_bundle_id
                if kind == "invalid_id":
                    requested = "../escape"
                elif kind == "missing":
                    requested = "a" * 64
                elif kind == "wrong_id":
                    requested = "b" * 64
                    shutil.copytree(bundle, storage_root / requested)
                elif kind == "symlink_bundle":
                    (storage_root / source_bundle_id).symlink_to(bundle, target_is_directory=True)
                else:
                    candidate = storage_root / source_bundle_id
                    shutil.copytree(bundle, candidate)
                    if kind == "substituted_bytes":
                        (candidate / "canonical.nt").write_bytes(b"substituted")
                    else:
                        (candidate / "unexpected.bin").write_bytes(b"unexpected")
                with patch.dict(
                        os.environ,
                        {ATLAS_SOURCE_BUNDLE_ROOT_ENV: str(storage_root)},
                        clear=False):
                    with self.assertRaises(BilqisError):
                        resolve_atlas_source_bundle(requested)

    def test_bundle_admission_rejects_census_gate_manifest_and_symlink_attacks(self):
        cases = (
            ("census_wrong_identity", "ATLAS_SOURCE_CENSUS_IDENTITY_MISMATCH"),
            ("census_duplicate_identity", "ATLAS_SOURCE_CENSUS_DUPLICATE"),
            ("constituent_gate_disagreement", "ATLAS_CONFORMANCE_GATE_MISMATCH:shacl"),
            ("duplicate_conformance_gate", "ATLAS_CONFORMANCE_GATES_INVALID"),
            ("unexpected_manifest_member", "ATLAS_SOURCE_MANIFEST_INVALID"),
            ("symlink_manifest_member", "ATLAS_SOURCE_BUNDLE_MEMBER_SET_INVALID"),
        )
        for kind, reason in cases:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                bundle, coverage, *_ = _fixture_bundle(Path(directory))
                if kind.startswith("census_"):
                    rows = json.loads((bundle / "source-rows.json").read_text())
                    if kind == "census_wrong_identity":
                        rows[0]["key"] = "ROW-NOT-IN-COVERAGE"
                    else:
                        rows[1] = dict(rows[0])
                    bundle = _rewrite_bundle(bundle, "source-rows.json", rows)
                elif kind == "constituent_gate_disagreement":
                    gate = json.loads((bundle / "gate-shacl.json").read_text())
                    gate["status"] = "failed"
                    gate["evidence"]["conforms"] = False
                    bundle = _rewrite_bundle(bundle, "gate-shacl.json", gate)
                elif kind == "duplicate_conformance_gate":
                    report = json.loads((bundle / "conformance.json").read_text())
                    report["gates"].append(dict(report["gates"][0]))
                    bundle = _rewrite_bundle(bundle, "conformance.json", report)
                elif kind == "unexpected_manifest_member":
                    bundle = _rewrite_bundle(bundle, "unexpected.json", {"note": "undeclared"})
                else:
                    canonical = bundle / "canonical.nt"
                    canonical.unlink()
                    canonical.symlink_to(bundle / "comparison.nt")
                with self.assertRaises(BilqisError) as caught:
                    compile_atlas_release(bundle, coverage, PRIOR_ABI, _bindings())
                self.assertIn(reason, str(caught.exception.context.get("reason")))
