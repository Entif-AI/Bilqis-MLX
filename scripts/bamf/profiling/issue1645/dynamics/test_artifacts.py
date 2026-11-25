"""A result digest alone must never admit replaceable saved diagnostic tensors."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np
from safetensors.numpy import save_file

from scripts.bamf.profiling.issue1645.dynamics.artifacts import (
    FILES, LEGACY_SCHEMA, admit_reference, sha256_file,
)
from scripts.bamf.profiling.issue1645.reservation import CAPABILITIES


class ArtifactAdmission(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.result = self.root / "result.json"
        self.index = self.root / "legacy-index.json"
        self.reference = {"manifest_sha256": "a" * 64, "capabilities": {}}
        for cap in CAPABILITIES:
            dest = self.root / cap
            dest.mkdir()
            a = np.array([1.], dtype=np.float32)
            save_file({"x": a}, dest / FILES[1])
            update = {f"{kind}/x": a for kind in ("raw", "clipped", "delta", "old_moment", "decay")}
            update["mask/x"] = np.array(True)
            save_file(update, dest / FILES[0])
            self.reference["capabilities"][cap] = {
                "leaves": {"x": {"shape": [1]}},
                "artifact_sha256": {name: sha256_file(dest / name) for name in FILES},
            }
        self.digest = self.write_result()

    def write_result(self):
        self.result.write_text(json.dumps(self.reference))
        return sha256_file(self.result)

    def legacy(self):
        maps = {cap: item.pop("artifact_sha256")
                for cap, item in self.reference["capabilities"].items()}
        self.digest = self.write_result()
        self.index.write_text(json.dumps({
            "schema": LEGACY_SCHEMA, "source_result_sha256": self.digest,
            "manifest_sha256": self.reference["manifest_sha256"], "artifacts": maps,
        }))
        return sha256_file(self.index)

    def test_result_bound_artifacts_and_post_admission_drift(self):
        result, guard = admit_reference(self.root, self.digest)
        self.assertEqual(result, self.reference)
        path = self.root / CAPABILITIES[0] / FILES[1]
        save_file({"x": np.array([2.], dtype=np.float32)}, path)
        with self.assertRaisesRegex(ValueError, "changed during consumption"):
            guard.require_current()
        with self.assertRaisesRegex(ValueError, "artifact digest mismatch"):
            admit_reference(self.root, self.digest)

    def test_legacy_requires_separate_expected_pin(self):
        expected = self.legacy()
        with self.assertRaisesRegex(ValueError, "legacy artifact index required"):
            admit_reference(self.root, self.digest)
        with self.assertRaisesRegex(ValueError, "flags must be paired"):
            admit_reference(self.root, self.digest, self.index)
        result, guard = admit_reference(self.root, self.digest, self.index, expected)
        self.assertEqual(result, self.reference)
        guard.require_current()
        data = json.loads(self.index.read_text())
        data["manifest_sha256"] = "b" * 64
        self.index.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "artifact digest mismatch"):
            admit_reference(self.root, self.digest, self.index, expected)
        with self.assertRaisesRegex(ValueError, "index source mismatch"):
            admit_reference(self.root, self.digest, self.index, sha256_file(self.index))

    def test_partial_map_rejected(self):
        self.reference["capabilities"][CAPABILITIES[0]]["artifact_sha256"].pop(FILES[1])
        with self.assertRaisesRegex(ValueError, "file map mismatch"):
            admit_reference(self.root, self.write_result())

    def test_common_missing_coordinate_is_not_a_smaller_basis(self):
        for cap, item in self.reference["capabilities"].items():
            path = self.root / cap / FILES[1]
            save_file({"foreign": np.array([1.], dtype=np.float32)}, path)
            item["artifact_sha256"][FILES[1]] = sha256_file(path)
        with self.assertRaisesRegex(ValueError, "probe basis mismatch"):
            admit_reference(self.root, self.write_result())

    def test_mixed_receipt_format_rejected(self):
        self.reference["capabilities"][CAPABILITIES[0]].pop("artifact_sha256")
        with self.assertRaisesRegex(ValueError, "mixed artifact receipt"):
            admit_reference(self.root, self.write_result())
