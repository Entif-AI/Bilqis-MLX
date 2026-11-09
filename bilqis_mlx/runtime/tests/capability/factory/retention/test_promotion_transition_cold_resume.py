"""B13 cold-resume witness for the versioned B09.3 policy sidecar."""
from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.learning.atlas_plasticity import (
    ModeTransition, PlasticityPolicy,
    TRANSITIONED_POLICY_STATE_SCHEMA, TRANSITIONED_POLICY_VERSION,
)
from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    accepted_state, candidate, parent_state, publish_candidate, shape_patch,
)


class PromotionTransitionColdResumeTests(TestCase):
    def test_b13_bundle_roundtrips_exact_mode_transition(self):
        with TemporaryDirectory(prefix="b09-466-cold-") as temporary:
            root = Path(temporary)
            run = root / "run"
            with patch.dict(os.environ, {"BILQIS_DATA_PLANE": str(root / "plane.sqlite3")}):
                with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
                    first = publish_candidate(run, candidate(parent_state()))
                    parent = load_bamf_generation(run / "bamf-state.json")
                    proof = ModeTransition(
                        run_id=parent.run_id,
                        parent_generation=parent.generation,
                        candidate_generation=parent.generation + 1,
                        candidate_identity_sha256="1" * 64,
                        optimizer_step=parent.retained_state.optimizer_step,
                        decision_sha256="2" * 64,
                        initial_factory_release_sha256="3" * 64,
                        foundation_capability_ids=("A.ONE", "A.TWO"),
                        promotion_evidence_sha256="4" * 64,
                        assessment_epoch=1,
                        outcome="PROMOTED",
                        carried_debt=(),
                        promotion_receipt_sha256="5" * 64,
                    )
                    accepted = accepted_state(parent.retained_state, parent.extents)
                    policy = PlasticityPolicy(
                        "ADAPTIVE", 0, accepted.policy.row_ages,
                        TRANSITIONED_POLICY_VERSION,
                        TRANSITIONED_POLICY_STATE_SCHEMA,
                        proof,
                    )
                    retained = replace(accepted, policy=policy)
                    publish_candidate(
                        run,
                        candidate(retained, parent.generation + 1, first["manifest_sha256"]),
                    )
                    cold = load_bamf_generation(run / "bamf-state.json")
            self.assertEqual(cold.retained_state.policy.to_record(), policy.to_record())
            self.assertEqual(cold.retained_state.policy.mode_transition, proof)
