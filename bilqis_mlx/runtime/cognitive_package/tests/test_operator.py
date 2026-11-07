"""The C12 operator composes existing owners without minting acceptance."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from bilqis_mlx.runtime.cognitive_package import operator as subject


class CognitivePackageOperatorTests(unittest.TestCase):
    def test_receive_screen_publish_uses_exact_owner_chain(self):
        binding = object()
        package = object()
        exchange = SimpleNamespace(
            package=package,
            plan=SimpleNamespace(disposition="EXACT_BINDING"),
        )
        parent = object()
        candidate = object()
        screened = object()
        published = object()
        source = object()
        receipt = object()
        selection = object()
        frontier = object()
        registry = object()
        receive = Mock(return_value=exchange)
        verify = Mock(return_value="clearance")
        apply = Mock(return_value=candidate)
        screen = Mock(return_value=screened)
        publish = Mock(return_value=published)

        with patch.multiple(
                subject,
                current_receiver_binding=Mock(return_value=binding),
                receive_package=receive,
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
                source_frontier=frontier, authority_registry=registry,
                reserve_gib=123.0)

        self.assertIs(result, published)
        receive.assert_called_once_with(
            "sender", "staging", "a" * 64, binding, max_wire_bytes=4096)
        verify.assert_called_once_with(
            package, parent, receipt, selection, frontier, registry)
        apply.assert_called_once_with(package, Path("run"))
        screen.assert_called_once_with(
            candidate, source, "artifact", "C.TARGET", run_dir=Path("run"))
        publish.assert_called_once_with(
            screened, Path("run"), export_clearance=receipt,
            atlas_selection=selection, source_frontier=frontier,
            authority_registry=registry, reserve_gib=123.0)

    def test_caller_cannot_supply_acceptance_boolean(self):
        with self.assertRaises(TypeError):
            subject.receive_screen_and_publish_package(
                "sender", "staging", "a" * 64, Path("run"),
                max_wire_bytes=4096, source_context=object(),
                artifact_path="artifact", target_capability="C.TARGET",
                export_clearance=object(), atlas_selection=object(),
                source_frontier=object(), authority_registry=object(),
                accepted=True)


if __name__ == "__main__":
    unittest.main()
