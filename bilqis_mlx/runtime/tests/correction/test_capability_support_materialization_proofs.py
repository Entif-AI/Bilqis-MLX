"""Fail-closed proof-key indexing for accepted C09 capability support."""
from __future__ import annotations

from types import SimpleNamespace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_candidate import CandidateStepProof
from bilqis_mlx.learning._retention._atlas_candidate.common import (
    LOGICAL_BATCH_STEP_PROOF_SCHEMA, STEP_PROOF_SCHEMA,
)
from bilqis_mlx.runtime.capability_support_materialization import (
    _verify_anchor_proofs,
)


def _scalar(authority_digest, *, step):
    return CandidateStepProof(
        step, f"{step}" * 64, "2" * 64, "3" * 64,
        ("identity.bank.0",), True,
        source_release_sha256="4" * 64,
        training_batch_sha256="5" * 64,
        target_capability_id="A.TEST",
        training_authority_sha256=authority_digest,
        source_family_id=f"family:{step}", episode_id=f"episode:{step}",
        schema_version=STEP_PROOF_SCHEMA,
    )


def _student(*proofs):
    return SimpleNamespace(retained_state=SimpleNamespace(step_proofs=proofs))


class CapabilitySupportProofIndexTests(unittest.TestCase):
    def test_duplicate_scalar_authority_digest_rejects(self):
        duplicate = "6" * 64
        with self.assertRaises(BilqisError):
            _verify_anchor_proofs(
                SimpleNamespace(source_anchors=()),
                _student(_scalar(duplicate, step=1), _scalar(duplicate, step=2)),
                "A.TEST",
            )

    def test_group_member_cannot_overlap_another_proof_top_level_digest(self):
        shared = "6" * 64
        grouped = CandidateStepProof(
            2, "8" * 64, "9" * 64, "a" * 64,
            ("identity.bank.0",), True,
            source_release_sha256="4" * 64,
            training_batch_sha256="5" * 64,
            target_capability_id="A.TEST",
            training_authority_sha256="b" * 64,
            schema_version=LOGICAL_BATCH_STEP_PROOF_SCHEMA,
            training_authority_members=(
                (shared, "family:b", "episode:b"),
                ("c" * 64, "family:b", "episode:c"),
            ),
        )
        with self.assertRaises(BilqisError):
            _verify_anchor_proofs(
                SimpleNamespace(source_anchors=()),
                _student(_scalar(shared, step=1), grouped),
                "A.TEST",
            )


if __name__ == "__main__":
    unittest.main()
