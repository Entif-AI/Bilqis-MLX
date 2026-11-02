"""Observation storage is replayable and has no authority over learner behavior."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.runtime.teacher_observation_capture import store_sidecar, read_sidecar


class ObservationSidecarTests(unittest.TestCase):
    def test_content_addressing_is_idempotent_and_preserves_order(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {"rows": [{"id": "one"}, {"id": "one"}, {"id": "two"}]}
            reference = store_sidecar(root, payload)
            self.assertEqual(store_sidecar(root, payload), reference)
            self.assertEqual(read_sidecar(root, reference), payload)
            self.assertNotEqual(store_sidecar(root, {"rows": list(reversed(payload["rows"]))}), reference)
            path = root / reference["file"]
            path.write_text(json.dumps({"rows": []}))
            with self.assertRaises(ValueError):
                read_sidecar(root, reference)
