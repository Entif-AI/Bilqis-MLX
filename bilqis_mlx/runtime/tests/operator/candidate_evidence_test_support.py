"""Shared fixtures for persistent BAMF candidate-evidence tests."""
from pathlib import Path
from types import SimpleNamespace
import unittest

from bilqis_mlx.factory.teaching import content_digest
from bilqis_mlx.runtime.bamf_operator.evidence_parts import CandidateEvidenceCapture


class CandidateEvidenceTestCase(unittest.TestCase):
    @staticmethod
    def selection():
        identity = SimpleNamespace(
            visit_id="visit:evidence", policy_key="policy:evidence",
            to_record=lambda: {
                "visit_id": "visit:evidence", "policy_key": "policy:evidence"})
        return SimpleNamespace(
            option_id="option:evidence",
            visit=SimpleNamespace(identity=identity),
            offer=SimpleNamespace(
                capability_id="capability:evidence", source_seed=17,
                release_sha256="b" * 64),
            policy={"lr": 0.001},
        )

    @staticmethod
    def release():
        execution = SimpleNamespace(
            provider_id="provider:evidence",
            provider_implementation_sha256="f" * 64,
            variation_axes=("seed",),
            teaching_option_ids=("option:evidence",),
        )
        return SimpleNamespace(
            release_sha256="b" * 64,
            execution_plan=SimpleNamespace(
                capability_map={"capability:evidence": execution}))

    @classmethod
    def capture(cls, root: Path, *, candidate_attempt_ordinal=1):
        return CandidateEvidenceCapture(
            root, cls.selection(), generation=3,
            accepted_manifest_sha256="a" * 64,
            candidate_attempt_ordinal=candidate_attempt_ordinal,
            parent_optimizer_step=10,
        )

    @classmethod
    def deliver(cls, capture, count=16, *, wall_seconds=0.01):
        row = {
            "id": "row:one", "capability": "capability:evidence",
            "tokens": [1, 2, 3],
        }
        rows = (row, row)
        for ordinal in range(1, count + 1):
            capture.delivery(
                cls.release(), "capability:evidence", 10 + ordinal, rows,
                option_rows=(row,), priority=(row,), seed=ordinal,
                controls={
                    "realized_cost": {
                        "wall_seconds": wall_seconds,
                        "candidate_step_wall_seconds": wall_seconds,
                        "optimizer_steps": 1,
                        "candidate_optimizer_steps": ordinal,
                    },
                    "delivered_content_sha256": content_digest(rows),
                },
            )


__all__ = ("CandidateEvidenceTestCase",)
