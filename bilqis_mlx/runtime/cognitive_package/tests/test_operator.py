"""The C12 operator composes existing owners without minting acceptance."""
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.cognitive_package import operator as subject


class CognitivePackageOperatorTests(unittest.TestCase):
    def test_current_host_bound_staging_uses_resolver_without_outer_registry_lock(self):
        inspected = SimpleNamespace(package=object())
        student = SimpleNamespace(correction_frontier={
            "source_authority_registry_sha256": "b" * 64,
            "source_authority_registry_origin": "HOST_SYSTEM_V1",
        })
        pointer = {"manifest_sha256": "a" * 64}
        registry = SimpleNamespace(digest="b" * 64)
        staged = object()
        stage = Mock(return_value=staged)
        resolver = Mock(return_value=registry)
        outer_lock = Mock(side_effect=AssertionError("unexpected outer registry lock"))

        with patch.object(subject, "stage_received_package", stage), patch(
            "bilqis_mlx.runtime.bamf_bundle.publication._pointer_lock",
            return_value=nullcontext(),
        ), patch(
            "bilqis_mlx.runtime.bamf_bundle.publication._load_generation_locked",
            return_value=(student, pointer),
        ), patch(
            "bilqis_mlx.runtime.bamf_bundle.publication._require_published_acceptance",
            return_value=object(),
        ), patch(
            "bilqis_mlx.runtime.bamf_bundle.source_authority_custody."
            "resolve_source_authority_registry",
            resolver,
        ), patch(
            "bilqis_mlx.runtime.bamf_bundle.source_authority_custody."
            "source_authority_registry_lock",
            outer_lock,
        ):
            result = subject._stage_received_package_if_current(
                inspected, "staging", Path("run"), "a" * 64, "b" * 64)

        self.assertIs(result, staged)
        resolver.assert_called_once_with(Path("run"), student.correction_frontier)
        outer_lock.assert_not_called()
        stage.assert_called_once_with(inspected, "staging")

    def test_host_root_drift_after_clearance_rejects_before_staging(self):
        inspected = SimpleNamespace(package=object())
        student = SimpleNamespace(correction_frontier={
            "source_authority_registry_sha256": "b" * 64,
            "source_authority_registry_origin": "HOST_SYSTEM_V1",
        })
        stage = Mock(side_effect=AssertionError("drifted staging mutation reached"))
        with patch.object(subject, "stage_received_package", stage), patch(
            "bilqis_mlx.runtime.bamf_bundle.publication._pointer_lock",
            return_value=nullcontext(),
        ), patch(
            "bilqis_mlx.runtime.bamf_bundle.publication._load_generation_locked",
            return_value=(student, {"manifest_sha256": "a" * 64}),
        ), patch(
            "bilqis_mlx.runtime.bamf_bundle.publication._require_published_acceptance",
            return_value=object(),
        ), patch(
            "bilqis_mlx.runtime.bamf_bundle.source_authority_custody."
            "resolve_source_authority_registry",
            return_value=SimpleNamespace(digest="c" * 64),
        ):
            with self.assertRaises(BilqisError):
                subject._stage_received_package_if_current(
                    inspected, "staging", Path("run"), "a" * 64, "b" * 64)
        stage.assert_not_called()

    def test_receive_screen_publish_uses_exact_owner_chain(self):
        binding = object()
        package = object()
        inspected = SimpleNamespace(
            package=package,
            plan=SimpleNamespace(disposition="EXACT_BINDING"),
        )
        exchange = SimpleNamespace(package=package, plan=inspected.plan, path=Path("staging/pkg"))
        parent = object()
        candidate = object()
        screened = object()
        published = object()
        source = object()
        receipt = object()
        selection = object()
        frontier = object()
        inspect = Mock(return_value=inspected)
        stage = Mock(return_value=exchange)
        verify = Mock(return_value=("clearance", "m" * 64, "r" * 64))
        lease_stage = Mock(return_value=exchange)
        apply = Mock(return_value=candidate)
        screen = Mock(return_value=screened)
        publish = Mock(return_value=published)

        with patch.multiple(
                subject,
                current_receiver_binding=Mock(return_value=binding),
                inspect_package=inspect,
                stage_received_package=stage,
                _stage_received_package_if_current=lease_stage,
                _load_current_generation=Mock(return_value=(object(), parent)),
                _verify_export_clearance=verify,
                apply_plastic_delta=apply,
                screen_delta_candidate=screen,
                publish_screened_delta_import=publish,
        ):
            result = subject.receive_screen_and_publish_package(
                "sender", "staging", "a" * 64, Path("run"),
                max_wire_bytes=4096, source_context=source,
                artifact_path="artifact", target_capability="C.TARGET",
                export_clearance=receipt, atlas_selection=selection,
                source_frontier=frontier,
                reserve_gib=123.0)

        self.assertIs(result, published)
        inspect.assert_called_once_with(
            "sender", "a" * 64, binding, max_wire_bytes=4096)
        verify.assert_called_once_with(
            package, parent, receipt, selection, frontier, source, Path("run"))
        stage.assert_not_called()
        lease_stage.assert_called_once_with(
            inspected, "staging", Path("run"), "m" * 64, "r" * 64)
        apply.assert_called_once_with(package, Path("run"))
        screen.assert_called_once_with(
            candidate, source, "artifact", "C.TARGET", run_dir=Path("run"))
        publish.assert_called_once_with(
            screened, Path("run"), export_clearance=receipt,
            atlas_selection=selection, source_frontier=frontier,
            source_context=source, reserve_gib=123.0)

    def test_authority_rejection_happens_before_staging(self):
        binding = object()
        inspected = SimpleNamespace(
            package=object(),
            plan=SimpleNamespace(disposition="EXACT_BINDING"),
        )
        stage = Mock(side_effect=AssertionError("staging mutation reached"))
        rejected = RuntimeError("authority rejected")
        with patch.multiple(
                subject,
                current_receiver_binding=Mock(return_value=binding),
                inspect_package=Mock(return_value=inspected),
                stage_received_package=stage,
                _load_current_generation=Mock(return_value=(object(), object())),
                _verify_export_clearance=Mock(side_effect=rejected),
        ):
            with self.assertRaisesRegex(RuntimeError, "authority rejected"):
                subject.receive_screen_and_publish_package(
                    "sender", "staging", "a" * 64, Path("run"),
                    max_wire_bytes=4096, source_context=object(),
                    artifact_path="artifact", target_capability="C.TARGET",
                    export_clearance=object(), atlas_selection=object(),
                    source_frontier=object())
        stage.assert_not_called()

    def test_generation_advance_after_clearance_rejects_before_staging(self):
        inspected = SimpleNamespace(
            package=object(), plan=SimpleNamespace(disposition="EXACT_BINDING"))
        stage = Mock(side_effect=AssertionError("stale staging mutation reached"))
        with patch.multiple(
                subject,
                current_receiver_binding=Mock(return_value=object()),
                inspect_package=Mock(return_value=inspected),
                stage_received_package=stage,
                _load_current_generation=Mock(return_value=(object(), object())),
                _verify_export_clearance=Mock(return_value=(
                    "clearance", "a" * 64, "b" * 64)),
        ), patch(
            "bilqis_mlx.runtime.bamf_bundle.publication._pointer_lock",
            return_value=nullcontext(),
        ), patch(
            "bilqis_mlx.runtime.bamf_bundle.publication._load_generation_locked",
            return_value=(object(), {"manifest_sha256": "c" * 64}),
        ):
            with self.assertRaises(BilqisError):
                subject.receive_screen_and_publish_package(
                    "sender", "staging", "a" * 64, Path("run"),
                    max_wire_bytes=4096, source_context=object(),
                    artifact_path="artifact", target_capability="C.TARGET",
                    export_clearance=object(), atlas_selection=object(),
                    source_frontier=object())
        stage.assert_not_called()

    def test_acceptance_drift_after_clearance_rejects_before_staging(self):
        inspected = SimpleNamespace(
            package=object(), plan=SimpleNamespace(disposition="EXACT_BINDING"))
        stage = Mock(side_effect=AssertionError("uncustodied staging mutation reached"))
        rejected = BilqisError.__new__(BilqisError)
        with patch.multiple(
                subject,
                current_receiver_binding=Mock(return_value=object()),
                inspect_package=Mock(return_value=inspected),
                stage_received_package=stage,
                _load_current_generation=Mock(return_value=(object(), object())),
                _verify_export_clearance=Mock(return_value=(
                    "clearance", "a" * 64, "b" * 64)),
        ), patch(
            "bilqis_mlx.runtime.bamf_bundle.publication._pointer_lock",
            return_value=nullcontext(),
        ), patch(
            "bilqis_mlx.runtime.bamf_bundle.publication._load_generation_locked",
            return_value=(object(), {"manifest_sha256": "a" * 64}),
        ), patch(
            "bilqis_mlx.runtime.bamf_bundle.publication._require_published_acceptance",
            side_effect=rejected,
        ):
            with self.assertRaises(BilqisError):
                subject.receive_screen_and_publish_package(
                    "sender", "staging", "a" * 64, Path("run"),
                    max_wire_bytes=4096, source_context=object(),
                    artifact_path="artifact", target_capability="C.TARGET",
                    export_clearance=object(), atlas_selection=object(),
                    source_frontier=object())
        stage.assert_not_called()

    def test_caller_cannot_supply_authority_registry(self):
        with self.assertRaises(TypeError):
            subject.receive_screen_and_publish_package(
                "sender", "staging", "a" * 64, Path("run"),
                max_wire_bytes=4096, source_context=object(),
                artifact_path="artifact", target_capability="C.TARGET",
                export_clearance=object(), atlas_selection=object(),
                source_frontier=object(), authority_registry=object())

    def test_caller_cannot_supply_acceptance_boolean(self):
        with self.assertRaises(TypeError):
            subject.receive_screen_and_publish_package(
                "sender", "staging", "a" * 64, Path("run"),
                max_wire_bytes=4096, source_context=object(),
                artifact_path="artifact", target_capability="C.TARGET",
                export_clearance=object(), atlas_selection=object(),
                source_frontier=object(), accepted=True)


if __name__ == "__main__":
    unittest.main()
