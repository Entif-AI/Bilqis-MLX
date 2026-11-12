"""Historical capability retry authority must fail before the live verifier."""

from bilqis_mlx.runtime.tests.admission.atlas.v2.capability.capability_support import *
from bilqis_mlx.runtime.jit_adoption import _PreparedSuccessorRuntime


class CapabilityHistoricalAuthorityV2Tests(CapabilityV2Support):
    def test_superseded_persisted_v2_lease_fails_before_live_verifier(self):
        handoff = self._handoff()
        approval, lease = self._lease_authority(handoff)
        pure = self._context(handoff, approval)
        current = AtlasAdmissionContextV2(
            pure.legacy,
            pure.run_dir,
            runtime=_PreparedSuccessorRuntime(
                None, pure.run_dir, {"school": {}}, None, None, {},
                object(), object(), 0.),
            source_authority=object(),
        )
        pointer = {
            "generation": 0,
            "manifest_sha256": "a" * 64,
            "acceptance_sha256": "b" * 64,
        }
        accepted = SimpleNamespace(retained_state=SimpleNamespace(
            optimizer_step=pure.legacy.checkpoint.optimizer_step))
        stale = replace(lease, lease_id="superseded-v2-lease")

        with patch(
                "bilqis_mlx.runtime.bamf_bundle.feature.acceptance.accepted_generation",
                return_value=(pointer, accepted)), patch(
                "bilqis_mlx.runtime.atlas_admission.read_accepted_atlas_factory_release",
                return_value=handoff.receipt.predecessor_release), patch(
                "bilqis_mlx.runtime.atlas_admission.read_accepted_atlas_lease_v2",
                return_value=stale), patch(
                "bilqis_mlx.runtime.atlas_adoption_v2.advance_atlas_frontier_v2"
                ) as live_verifier, self.assertRaises(BilqisError) as caught:
            adopt_capability_only_atlas_successor_v2(
                current, AtlasDeltaEnvelopeV2(handoff, None), lease)

        live_verifier.assert_not_called()
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_ATLAS_V2_LEASE_CURRENT_AUTHORITY_DRIFT",
        )
