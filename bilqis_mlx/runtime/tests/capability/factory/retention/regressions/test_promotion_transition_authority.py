"""Authority-only adversaries for the B09.3 retained-state transition."""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.atlas_candidate import issue_promotion_transition_state
from bilqis_mlx.runtime._plasticity_promotion import receipt as receipt_owner
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import accepted_state, parent_state


class PromotionTransitionAuthorityTests(TestCase):
    def test_raw_live_receipt_mint_is_not_module_reachable(self):
        self.assertFalse(hasattr(receipt_owner, "_raw_issue_receipt"))

    def test_foreign_run_receipt_cannot_transition_retained_state(self):
        retained = accepted_state(parent_state())
        custody = retained.custody
        receipt = SimpleNamespace(
            run_id="foreign-run",
            parent_generation=custody.generation,
            candidate_generation=custody.generation + 1,
            parent_manifest_sha256=custody.manifest_sha256,
            candidate_identity_sha256=candidate_identity_digest(retained),
            optimizer_step=retained.optimizer_step,
        )
        with (
            patch(
                "bilqis_mlx.runtime.plasticity_promotion."
                "require_accepted_promotion_transition",
                return_value=receipt,
            ),
            self.assertRaises(BilqisError),
        ):
            issue_promotion_transition_state(retained, receipt)
