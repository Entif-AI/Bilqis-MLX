"""Lossless housekeeping of old state JSON, never checkpoint tensors."""
import json
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.state_archive import compact_states, read_generation


class StateArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "states").mkdir()
        for generation in range(1, 11):
            doc = {"generation": generation, "teacher": {"events": generation},
                   "payload": "evidence" * 1000}
            (self.root / "states" / f"{generation:07d}.json").write_text(
                json.dumps(doc, sort_keys=True))
        latest = json.loads((self.root / "states/0000010.json").read_text())
        latest["curriculum_history"] = [{"state_file": "states/0000003.json"}]
        (self.root / "states/0000010.json").write_text(json.dumps(latest, sort_keys=True))
        (self.root / "state.json").write_text(json.dumps(latest, sort_keys=True))

    def test_compacts_verifies_and_keeps_active_recovery_and_pinned_history(self):
        before = read_generation(self.root, 1)
        result = compact_states(self.root, max_files=0)
        self.assertEqual(result["compressed_generations"], 5)
        self.assertGreater(result["estimated_saved_bytes"], 0)
        self.assertFalse((self.root / "states/0000001.json").exists())
        self.assertTrue((self.root / "states/0000001.json.gz").exists())
        self.assertEqual(read_generation(self.root, 1), before)
        self.assertTrue((self.root / "states/0000003.json").exists())
        for generation in (7, 8, 9, 10):
            self.assertTrue((self.root / "states" / f"{generation:07d}.json").exists())
        self.assertEqual(compact_states(self.root, max_files=0)["compressed_generations"], 0)

    def test_tampered_archive_fails_closed(self):
        compact_states(self.root, max_files=1)
        proof = self.root / "states/0000001.json.sha256"
        proof.write_text("0" * 64)
        with self.assertRaisesRegex(ValueError, "SHA_DRIFT"):
            read_generation(self.root, 1)

    def test_missing_current_immutable_snapshot_blocks_compaction(self):
        (self.root / "states/0000010.json").unlink()
        with self.assertRaisesRegex(ValueError, "GENERATION_NOT_FOUND"):
            compact_states(self.root)


if __name__ == "__main__":
    unittest.main()
