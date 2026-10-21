"""New source families retain readable answer heads on earlier frozen students."""
import unittest

from bilqis_mlx.learning.student_ops import _compatible_answer_config


class CompatibleAnswerConfigTests(unittest.TestCase):
    def test_binary_factory_release_projects_to_frozen_prefix(self):
        graph = {"tokens": ["pad", "false", "true", "prior"]}
        heads = {
            "binary": {
                "values": ["FALSE", "TRUE"], "token_ids": [1, 2],
                "modality_id": "answer.binary/v1", "implementation_sha256": "a" * 64,
            },
            "semantic_token": {
                "values": [*graph["tokens"], "new-event"], "token_ids": list(range(5)),
            },
            "future": {"values": ["new-event"], "token_ids": [4]},
        }
        config = {"heads": 3, "answer_heads": heads}
        result = _compatible_answer_config(config, graph)
        self.assertEqual(result["answer_heads"]["binary"], heads["binary"])
        self.assertEqual(result["answer_heads"]["semantic_token"]["values"], graph["tokens"])
        self.assertEqual(result["answer_heads"]["semantic_token"]["token_ids"], list(range(4)))
        self.assertNotIn("future", result["answer_heads"])
        self.assertEqual(len(heads["semantic_token"]["values"]), 5)

    def test_native_catalog_identity_drift_is_still_rejected(self):
        config = {"answer_heads": {
            "binary": {"values": ["FALSE", "TRUE"], "token_ids": [1, 2]},
            "semantic_token": {
                "values": ["pad", "false", "true"], "token_ids": [0, 1, 2],
            },
        }}
        with self.assertRaisesRegex(ValueError, "UNKNOWN_TYPED_ANSWER_CONFIG"):
            _compatible_answer_config(config, {"tokens": ["pad", "true", "false"]})
