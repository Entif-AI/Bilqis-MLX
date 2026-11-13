"""Concurrent exact-retry convergence for C07 v2 parameter adoption."""

from bilqis_mlx.runtime.tests.admission.atlas.v2.policy_support import *
from bilqis_mlx.runtime.jit_adoption import _PreparedSuccessorRuntime
from bilqis_mlx.runtime.atlas_parameter_adoption_v2 import (
    accepted_parameter_extension_retry_v2,
)
from bilqis_mlx.runtime.bamf_bundle.atlas_admission import (
    ATLAS_ADMISSION_SCHEMA_V2,
    ParsedAtlasAdmissionBinding,
)
from bilqis_mlx.factory.atlas_frontier_progress_validation import requested_keys


class ParameterRetryRaceV2Tests(PolicyV2Support):
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
                "bilqis_mlx.runtime.atlas_parameter_adoption_v2."
                "_accepted_parameter_extension_retry_once_v2",
                side_effect=classify), self.assertRaises(BilqisError) as caught:
            accepted_parameter_extension_retry_v2(
                current, object(), object(), object())

        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_ATLAS_V2_PARAMETER_RETRY_CONFLICT",
        )

    def test_historical_retry_restarts_when_pointer_moves_after_success(self):
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
        pointer = {"generation": 1, "manifest_sha256": "c" * 64}
        current = SimpleNamespace(run_dir=Path("/accepted/run"))

        with patch(
                "bilqis_mlx.runtime.bamf_bundle.feature.acceptance.accepted_generation",
                side_effect=(
                    (before, object()),
                    (after, object()),
                    (after, object()),
                    (after, object()),
                )), patch(
                "bilqis_mlx.runtime.atlas_parameter_adoption_v2."
                "_accepted_parameter_extension_retry_once_v2",
                side_effect=(None, pointer)) as classify:
            actual = accepted_parameter_extension_retry_v2(
                current, object(), object(), object())

        self.assertEqual(actual, pointer)
        self.assertEqual(classify.call_count, 2)

    def test_historical_retry_restarts_only_when_accepted_pointer_advances(self):
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
        pointer = {"generation": 1, "manifest_sha256": "c" * 64}
        attempts = {"count": 0}

        def classify(*_args):
            attempts["count"] += 1
            if attempts["count"] == 1:
                from bilqis_mlx.runtime.atlas_admission import _invalid
                _invalid("BAMF_C09_SOURCE_AUTHORITY_RUNTIME_INVALID")
            return pointer

        current = SimpleNamespace(run_dir=Path("/accepted/run"))
        with patch(
                "bilqis_mlx.runtime.bamf_bundle.feature.acceptance.accepted_generation",
                side_effect=(
                    (before, object()),
                    (after, object()),
                    (after, object()),
                    (after, object()),
                )), patch(
                "bilqis_mlx.runtime.atlas_parameter_adoption_v2."
                "_accepted_parameter_extension_retry_once_v2",
                side_effect=classify):
            actual = accepted_parameter_extension_retry_v2(
                current, object(), object(), object())

        self.assertEqual(actual, pointer)
        self.assertEqual(attempts["count"], 2)

    def test_exact_retry_restarts_when_custody_advances_during_lease_replay(self):
        _capability, semantic_id, handoff, plan, ledger, checkpoint = self._event_handoff()
        approval, lease = self._authority(handoff)
        native = self._a02_staged(semantic_id)
        pure = self._context(handoff, plan, ledger, checkpoint, approval)
        runtime = _PreparedSuccessorRuntime(
            None, pure.run_dir, {}, None, None, {}, object(), object(), 0.)
        stale_authority = object()
        fresh_authority = object()
        legacy = replace(
            pure.legacy, runtime=runtime, native_staged=native,
            source_authority=stale_authority)
        current = AtlasAdmissionContextV2(legacy, pure.run_dir)
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
        parent = SimpleNamespace(generation=0)
        child = SimpleNamespace(generation=1)
        advanced = {"value": False}

        def accepted_generation(_pointer_path):
            return (
                (child_pointer, child)
                if advanced["value"]
                else (parent_pointer, parent)
            )

        def accepted_lease(_run_dir, *, source_authority):
            if not advanced["value"]:
                self.assertIs(source_authority, stale_authority)
                advanced["value"] = True
                from bilqis_mlx.runtime.atlas_admission import _invalid
                _invalid("BAMF_C09_SOURCE_AUTHORITY_RUNTIME_INVALID")
            self.assertIs(source_authority, fresh_authority)
            return lease

        host = SimpleNamespace(source_authority=lambda: fresh_authority)
        binding = ParsedAtlasAdmissionBinding({
            "schema_version": ATLAS_ADMISSION_SCHEMA_V2,
            "selection_receipt_sha256": handoff.receipt.receipt_sha256,
            "selected_obligation_keys": tuple(requested_keys((handoff.receipt,))),
        })
        with patch(
                "bilqis_mlx.runtime.bamf_bundle.feature.acceptance.accepted_generation",
                side_effect=accepted_generation), \
                patch(
                    "bilqis_mlx.runtime.bamf_bundle.feature.acceptance."
                    "accepted_binding_for_manifest",
                    return_value=binding), \
                patch(
                    "bilqis_mlx.runtime.atlas_admission.read_accepted_atlas_factory_release",
                    side_effect=lambda _run_dir: SimpleNamespace(
                        release_sha256=(successor if advanced["value"] else predecessor))), \
                patch(
                    "bilqis_mlx.runtime.atlas_admission.read_accepted_atlas_lease_v2",
                    side_effect=accepted_lease), \
                patch(
                    "bilqis_mlx.runtime.accepted_corrections.AcceptedRuntimeHost",
                    return_value=host), \
                patch(
                    "bilqis_mlx.runtime.atlas_parameter_adoption_v2._require_exact_atlas_release"), \
                patch(
                    "bilqis_mlx.runtime.atlas_parameter_adoption_v2._accepted_native_retry",
                    side_effect=lambda *_args, **_kwargs:
                        child_pointer if advanced["value"] else None):
            actual = accepted_parameter_extension_retry_v2(
                current, handoff, native, lease)

        self.assertTrue(advanced["value"])
        self.assertEqual(actual, child_pointer)
