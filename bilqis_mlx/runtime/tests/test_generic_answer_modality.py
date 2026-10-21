"""V2 answer modalities extend runtime training without a kind switchboard."""
import unittest

from bilqis_mlx.typed_answer_training import prepare_typed_batches


class GenericAnswerModalityTests(unittest.TestCase):
    def test_new_v2_modality_batches_without_runtime_kind_registration(self):
        heads = {
            "semantic_token": {
                "values": ["pad", "fixture.red", "fixture.blue"],
                "token_ids": [0, 1, 2],
            },
            "color": {
                "values": ["RED", "BLUE"],
                "token_ids": [1, 2],
                "modality_id": "answer.color/v1",
                "implementation_sha256": "a" * 64,
            },
        }
        rows = [
            {"id": "red", "tokens": [1], "answer_kind": "color", "gold": "RED"},
            {"id": "blue", "tokens": [2], "answer_kind": "color", "gold": "BLUE"},
        ]
        batches = prepare_typed_batches(rows, heads)
        self.assertEqual(set(batches), {"color"})
        self.assertEqual(batches["color"]["target_indices"], [0, 1])
        self.assertEqual(batches["color"]["answer_ids"], [1, 2])

    def test_unknown_legacy_kind_still_fails_closed(self):
        heads = {
            "semantic_token": {
                "values": ["pad", "fixture.red", "fixture.blue"],
                "token_ids": [0, 1, 2],
            },
            "color": {
                "values": ["RED", "BLUE"],
                "token_ids": [1, 2],
            },
        }
        with self.assertRaisesRegex(
                ValueError, "ANSWER_CASTE_NOT_ADMITTED_FOR_TRAINING"):
            prepare_typed_batches([
                {"id": "red", "tokens": [1],
                 "answer_kind": "color", "gold": "RED"},
            ], heads)


if __name__ == "__main__":
    unittest.main()
