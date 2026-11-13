"""Concurrent exact-retry convergence for C07 v2 capability adoption."""

from bilqis_mlx.runtime.tests.admission.atlas.v2.capability.capability_support import *
from bilqis_mlx.runtime.jit_adoption import _PreparedSuccessorRuntime
from bilqis_mlx.runtime.atlas_capability_adoption_v2 import (
    _accepted_capability_only_retry_state_v2,
)
from bilqis_mlx.factory.atlas_frontier_progress_validation import requested_keys
from bilqis_mlx.runtime.bamf_bundle.factory_release.admission import (
    FACTORY_RELEASE_ADMISSION_SCHEMA_V2,
)


class CapabilityRetryRaceV2Tests(CapabilityV2Support):
    def test_retry_conflict_wins_when_second_attempt_errors_after_pointer_moves(self):
        first = {
            "generation": 0,
            "manifest_sha256": "a" * 64,
            "acceptance_sha256": "b" * 64,
        }
        second = {
            "generation": 1,
            "manifest_sha256": "c" * 64,
            "acceptance_sha256": "d" * 64,
        }
        third = {
            "generation": 2,
            "manifest_sha256": "e" * 64,
            "acceptance_sha256": "f" * 64,
        }
        current = SimpleNamespace(run_dir=Path("/accepted/run"))

        def classify(*_args):
            from bilqis_mlx.runtime.atlas_admission import _invalid
            _invalid("BAMF_C09_SOURCE_AUTHORITY_RUNTIME_INVALID")

        with patch(
                "bilqis_mlx.runtime.bamf_bundle.feature.acceptance.accepted_generation",
                side_effect=((first, object()), (second, object()),
                             (second, object()), (third, object()))), patch(
                "bilqis_mlx.runtime.atlas_capability_adoption_v2."
                "_accepted_capability_only_retry_state_once_v2",
                side_effect=classify), self.assertRaises(BilqisError) as caught:
            _accepted_capability_only_retry_state_v2(current, object(), object())

        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_ATLAS_V2_CAPABILITY_RETRY_CONFLICT",
        )

    def _retry_race_fixture(self):
        handoff = self._handoff()
        approval, lease = self._lease_authority(handoff)
        pure = self._context(handoff, approval)
        stale_authority = object()
        fresh_authority = object()
        current = AtlasAdmissionContextV2(
            pure.legacy, pure.run_dir,
            runtime=_PreparedSuccessorRuntime(
                None, pure.run_dir, {"school": {}}, None, None, {},
                object(), object(), 0.),
            source_authority=stale_authority,
        )
        predecessor = handoff.receipt.predecessor_release.release_sha256
        successor = handoff.staged_candidate.successor.release_sha256
        parent_pointer = {
            "generation": 0,
            "manifest_sha256": "a" * 64,
            "acceptance_sha256": "b" * 64,
        }
        child_pointer = {
            "generation": 1,
            "manifest_sha256": "c" * 64,
            "acceptance_sha256": "d" * 64,
        }
        parent = SimpleNamespace(
            run_id="fixture-v2-capability",
            retained_state=SimpleNamespace(
                optimizer_step=pure.legacy.checkpoint.optimizer_step),
        )
        child = SimpleNamespace(
            run_id=parent.run_id,
            parent_manifest_sha256=parent_pointer["manifest_sha256"],
            retained_state=SimpleNamespace(
                optimizer_step=pure.legacy.checkpoint.optimizer_step),
            transition={"staged_candidate_sha256": handoff.staged_candidate.staged_sha256},
        )

        class ParsedFactoryBinding:
            run_id = child.run_id
            handoff_sha256 = handoff.handoff_sha256
            proposal_sha256 = handoff.proposal.proposal_sha256
            selection_receipt_sha256 = handoff.receipt.receipt_sha256
            lease_sha256 = lease.digest()
            source_approval_sha256 = __import__(
                "bilqis_mlx.semantics.domains", fromlist=["contract_digest"]
            ).contract_digest(lease.source_approval)
            predecessor_factory_release_sha256 = predecessor
            factory_release_sha256 = successor
            schema_version = FACTORY_RELEASE_ADMISSION_SCHEMA_V2
            accepted_obligation_keys = tuple(requested_keys((handoff.receipt,)))

        return SimpleNamespace(
            handoff=handoff, lease=lease, current=current,
            stale_authority=stale_authority, fresh_authority=fresh_authority,
            predecessor=predecessor, successor=successor,
            parent_pointer=parent_pointer, child_pointer=child_pointer,
            parent=parent, child=child, binding_type=ParsedFactoryBinding,
        )

    def test_retry_classification_restarts_when_pointer_moves_after_success(self):
        before = {
            "generation": 0,
            "manifest_sha256": "a" * 64,
            "acceptance_sha256": "b" * 64,
        }
        after = {
            "generation": 1,
            "manifest_sha256": "c" * 64,
            "acceptance_sha256": "d" * 64,
        }
        child_pointer = dict(after)
        current = SimpleNamespace(run_dir=Path("/accepted/run"))

        with patch(
                "bilqis_mlx.runtime.bamf_bundle.feature.acceptance.accepted_generation",
                side_effect=(
                    (before, object()),
                    (after, object()),
                    (after, object()),
                    (after, object()),
                )), patch(
                "bilqis_mlx.runtime.atlas_capability_adoption_v2."
                "_accepted_capability_only_retry_state_once_v2",
                side_effect=((None, before), (child_pointer, None))) as classify:
            actual, parent = _accepted_capability_only_retry_state_v2(
                current, object(), object())

        self.assertEqual(actual, child_pointer)
        self.assertIsNone(parent)
        self.assertEqual(classify.call_count, 2)

    def test_exact_retry_restarts_when_accepted_generation_advances_during_lease_replay(self):
        fixture = self._retry_race_fixture()
        advanced = {"value": False}

        def accepted_generation(_pointer_path):
            return (
                (fixture.child_pointer, fixture.child)
                if advanced["value"]
                else (fixture.parent_pointer, fixture.parent)
            )

        def accepted_lease(_run_dir, *, source_authority):
            if not advanced["value"]:
                self.assertIs(source_authority, fixture.stale_authority)
                advanced["value"] = True
                from bilqis_mlx.runtime.atlas_admission import _invalid
                _invalid("BAMF_C09_SOURCE_AUTHORITY_RUNTIME_INVALID")
            self.assertIs(source_authority, fixture.fresh_authority)
            return fixture.lease

        host = SimpleNamespace(source_authority=lambda: fixture.fresh_authority)
        with patch(
                "bilqis_mlx.runtime.bamf_bundle.feature.acceptance.accepted_generation",
                side_effect=accepted_generation), patch(
                "bilqis_mlx.runtime.atlas_admission.read_accepted_atlas_factory_release",
                side_effect=lambda _run_dir: SimpleNamespace(
                    release_sha256=(fixture.successor if advanced["value"]
                                    else fixture.predecessor))), patch(
                "bilqis_mlx.runtime.atlas_admission.read_accepted_atlas_lease_v2",
                side_effect=accepted_lease), patch(
                "bilqis_mlx.runtime.accepted_corrections.AcceptedRuntimeHost",
                return_value=host), patch(
                "bilqis_mlx.runtime.bamf_bundle.feature.acceptance."
                "accepted_binding_for_manifest",
                return_value=fixture.binding_type()), patch(
                "bilqis_mlx.runtime.bamf_bundle.factory_release.admission."
                "ParsedFactoryReleaseAdmissionBinding",
                fixture.binding_type), patch(
                "bilqis_mlx.runtime.bamf_bundle.feature.acceptance."
                "parent_acceptance_anchor_from_manifest",
                return_value="e" * 64), patch(
                "bilqis_mlx.runtime.bamf_bundle.codec.load_bamf_bundle",
                return_value=fixture.parent), patch(
                "bilqis_mlx.runtime.atlas_capability_adoption_v2."
                "_historical_factory_release_sha256",
                side_effect=lambda _run, _manifest, _acceptance, student:
                    fixture.successor if student is fixture.child else fixture.predecessor), patch(
                "bilqis_mlx.runtime.atlas_capability_adoption_v2."
                "_require_exact_atlas_release"):
            actual = accepted_capability_only_retry_v2(
                fixture.current, fixture.handoff, fixture.lease)

        self.assertTrue(advanced["value"])
        self.assertEqual(actual, fixture.child_pointer)
