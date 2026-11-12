"""Wire and call-shape compatibility for versioned candidate-step proofs."""
from __future__ import annotations

import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_candidate import CandidateStepProof
from bilqis_mlx.learning._retention._atlas_candidate.common import (
    LOGICAL_BATCH_STEP_PROOF_SCHEMA, STEP_PROOF_SCHEMA,
)


class CandidateStepProofCompatibilityTests(unittest.TestCase):
    def test_v3_old_positional_schema_argument_remains_compatible(self):
        proof = CandidateStepProof(
            1, "1" * 64, "2" * 64, "3" * 64, ("identity.bank.0",), True,
            "4" * 64, "5" * 64, "A.TEST", "6" * 64,
            "family:a", "episode:a", STEP_PROOF_SCHEMA,
        )
        self.assertEqual(proof.schema_version, STEP_PROOF_SCHEMA)
        self.assertEqual(proof.training_authority_members, ())
        record = proof.to_record()
        self.assertNotIn("training_authority_members", record)
        self.assertEqual(CandidateStepProof.from_record(record), proof)

    def test_v4_rejects_duplicate_member_authority_digests(self):
        with self.assertRaises(BilqisError):
            CandidateStepProof(
                1, "1" * 64, "2" * 64, "3" * 64,
                ("identity.bank.0",), True,
                source_release_sha256="4" * 64,
                training_batch_sha256="5" * 64,
                target_capability_id="A.TEST",
                training_authority_sha256="6" * 64,
                schema_version=LOGICAL_BATCH_STEP_PROOF_SCHEMA,
                training_authority_members=(
                    ("7" * 64, "family:a", "episode:a"),
                    ("7" * 64, "family:b", "episode:b"),
                ),
            )

    def test_v4_rejects_mixed_source_families(self):
        with self.assertRaises(BilqisError):
            CandidateStepProof(
                1, "1" * 64, "2" * 64, "3" * 64,
                ("identity.bank.0",), True,
                source_release_sha256="4" * 64,
                training_batch_sha256="5" * 64,
                target_capability_id="A.TEST",
                training_authority_sha256="6" * 64,
                schema_version=LOGICAL_BATCH_STEP_PROOF_SCHEMA,
                training_authority_members=(
                    ("7" * 64, "family:a", "episode:a"),
                    ("8" * 64, "family:b", "episode:b"),
                ),
            )


if __name__ == "__main__":
    unittest.main()
