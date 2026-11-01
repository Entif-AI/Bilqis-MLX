from __future__ import annotations

from dataclasses import replace
import unittest

from bilqis_mlx.factory.curriculum.capability_identity import (
    CapabilityIdentityInput, StableCapabilityIdentity,
    bind_factory_release_capability_identity, bind_stable_capability_identity,
    stable_capability_id,
)
from bilqis_mlx.factory.release import compile_factory_release
from bilqis_mlx.factory.skos_curriculum.programs.contracts import (
    BoundFamilyProgram, FactoryReleaseFamilyBindings, FamilyProgramCoverage,
)
from bilqis_mlx.factory.tests.support import synthetic_release_inputs
from bilqis_mlx.semantics.foundation.core import Signature


def _family_bindings(release, *, family_id="boolean_composition",
                     release_sha256=None):
    capability = release.capabilities[0]
    program = release.construction_programs[0]
    bound = BoundFamilyProgram(
        family_id, capability.capability_id, capability.source_adapter_id,
        program.generator_id, program.oracle_id,
        "fixture.constructor/v1", "fixture.checker/v1")
    coverage = FamilyProgramCoverage(
        release.semantic_release.version, "c" * 64, (), 0)
    return FactoryReleaseFamilyBindings(
        release.release_sha256 if release_sha256 is None else release_sha256,
        release.semantic_release.version, "c" * 64, (bound,), coverage)


class CapabilityIdentityTests(unittest.TestCase):
    def test_semantic_family_signature_and_answer_modality_define_identity(self):
        identity = bind_stable_capability_identity(
            "boolean_composition", Signature(("Boolean", "Boolean"), "Boolean"),
            ("BOOLEAN",))
        self.assertTrue(identity.capability_id.startswith("cap:"))
        self.assertEqual(len(identity.capability_id), 68)
        self.assertEqual(identity.capability_id, stable_capability_id(identity.identity))

    def test_grade_provider_source_path_and_root_ordinal_are_not_identity_inputs(self):
        identity = CapabilityIdentityInput(
            "numeric_composition", Signature(("Number", "Number"), "Number"),
            ("INTEGER",))
        baseline = stable_capability_id(identity)
        # These execution/placement facts are intentionally not accepted arguments.
        placements = (
            {"grade": "C", "provider": "mlx", "source": "row:1", "ordinal": 1},
            {"grade": "Z", "provider": "cpu", "source": "row:999", "ordinal": 999},
        )
        self.assertEqual({stable_capability_id(identity) for _ in placements}, {baseline})

    def test_semantic_change_changes_identity(self):
        base = CapabilityIdentityInput(
            "numeric_composition", Signature(("Number", "Number"), "Number"),
            ("INTEGER",))
        variants = (
            replace(base, family_id="boolean_composition"),
            replace(base, signature=Signature(("Number",), "Number")),
            replace(base, answer_kinds=("INTEGER", "SEMANTIC_TOKEN")),
        )
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertNotEqual(stable_capability_id(base), stable_capability_id(variant))

    def test_forged_digest_and_noncanonical_modalities_fail(self):
        base = CapabilityIdentityInput(
            "boolean_composition", Signature(("Boolean",), "Boolean"),
            ("BOOLEAN",))
        with self.assertRaises(ValueError):
            StableCapabilityIdentity("cap:" + "0" * 64, base)
        for answer_kinds in ((), ("B", "A"), ("A", "A")):
            with self.subTest(answer_kinds=answer_kinds), self.assertRaises(ValueError):
                CapabilityIdentityInput(
                    "boolean_composition", Signature(("Boolean",), "Boolean"),
                    answer_kinds)

    def test_existing_factory_release_supplies_answer_modality_to_stable_identity(self):
        course, registry = synthetic_release_inputs()
        release = compile_factory_release(course, registry)
        bindings = _family_bindings(release)
        binding = bind_factory_release_capability_identity(
            release, bindings, "A.C0",
            Signature(("Boolean", "Boolean"), "Boolean"))
        self.assertEqual(binding.factory_release_sha256, release.release_sha256)
        self.assertEqual(binding.release_capability_id, "A.C0")
        self.assertEqual(binding.stable_identity.identity.answer_kinds, ("binary",))
        self.assertEqual(binding.stable_identity.identity.family_id,
                         "boolean_composition")

    def test_release_binding_rejects_unknown_capability_and_forged_release(self):
        course, registry = synthetic_release_inputs()
        release = compile_factory_release(course, registry)
        bindings = _family_bindings(release)
        signature = Signature(("Boolean",), "Boolean")
        with self.assertRaisesRegex(
                ValueError,
                "FACTORY_CAPABILITY_IDENTITY_RELEASE_CAPABILITY_MISSING"):
            bind_factory_release_capability_identity(
                release, bindings, "A.MISSING", signature)
        forged = replace(release, release_sha256="0" * 64)
        with self.assertRaises(ValueError):
            bind_factory_release_capability_identity(
                forged, bindings, "A.C0", signature)

    def test_release_binding_rejects_family_binding_from_another_release(self):
        course, registry = synthetic_release_inputs()
        release = compile_factory_release(course, registry)
        bindings = _family_bindings(release, release_sha256="d" * 64)
        with self.assertRaisesRegex(
                ValueError, "FACTORY_CAPABILITY_IDENTITY_FAMILY_BINDING_DRIFT"):
            bind_factory_release_capability_identity(
                release, bindings, "A.C0", Signature(("Boolean",), "Boolean"))


if __name__ == "__main__":
    unittest.main()
