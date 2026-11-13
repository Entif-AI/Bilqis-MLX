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
    _verify_anchor_proofs, retained_closure_nodes,
)
from bilqis_mlx.semantics.cognitive_dependencies import (
    ArtifactKind, ArtifactNode, DependencyKind, DependencyRef,
)
from bilqis_mlx.semantics.dependencies.closure import (
    closure_digest, encode_closure_nodes,
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


def _anchor(authority_digest, *, family="family:1", episode="episode:1",
            row="row:test", dependencies=None):
    dependencies = (
        ((DependencyKind.SOURCE.value, row),)
        if dependencies is None else dependencies
    )
    return (
        "A.TEST", row, "d" * 64, family, episode,
        "4" * 64, "5" * 64, "7" * 64, authority_digest,
        dependencies,
    )


class CapabilitySupportProofIndexTests(unittest.TestCase):
    def test_duplicate_scalar_authority_digest_rejects(self):
        duplicate = "6" * 64
        with self.assertRaises(BilqisError) as caught:
            _verify_anchor_proofs(
                SimpleNamespace(source_anchors=(_anchor(duplicate),)),
                _student(_scalar(duplicate, step=1), _scalar(duplicate, step=2)),
                "A.TEST",
            )
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_CAPABILITY_SUPPORT_PROOF_DRIFT",
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
        with self.assertRaises(BilqisError) as caught:
            _verify_anchor_proofs(
                SimpleNamespace(source_anchors=(_anchor(shared),)),
                _student(_scalar(shared, step=1), grouped),
                "A.TEST",
            )
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_CAPABILITY_SUPPORT_PROOF_DRIFT",
        )

    def test_logical_batch_closure_nodes_survive_accepted_cold_support(self):
        node = ArtifactNode(
            "salience-labels:logical-batch",
            ArtifactKind.SALIENCE_EVIDENCE,
            "e" * 64,
            True,
            (DependencyRef(DependencyKind.SOURCE, "source:salience"),),
            2,
            1,
        )
        digest = closure_digest((node,))
        logical_digest = "b" * 64
        members = (
            ("6" * 64, "family:b", "episode:b"),
            ("c" * 64, "family:b", "episode:c"),
        )
        proof = SimpleNamespace(
            step_index=1,
            schema_version="bilqis.mlx.candidate-step-proof/v6",
            target_capability_id="A.TEST",
            training_authority_sha256=logical_digest,
            artifact_closure_sha256=digest,
            training_authority_members=members,
        )
        dependency = ((DependencyKind.ARTIFACT.value, node.artifact_id),)
        binding = SimpleNamespace(
            source_anchors=(
                _anchor(
                    members[0][0], family=members[0][1], episode=members[0][2],
                    row="row:b", dependencies=dependency,
                ),
                _anchor(
                    members[1][0], family=members[1][1], episode=members[1][2],
                    row="row:c", dependencies=dependency,
                ),
            ),
            artifact_closures=({
                "step_index": 1,
                "training_authority_sha256": logical_digest,
                "artifact_closure_sha256": digest,
                "nodes": encode_closure_nodes((node,)),
            },),
        )

        self.assertEqual(
            retained_closure_nodes(binding, _student(proof), "A.TEST"),
            (node,),
        )


if __name__ == "__main__":
    unittest.main()
