from dataclasses import replace
from types import SimpleNamespace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.curriculum.capability_identity import bind_factory_release_capability_identity
from bilqis_mlx.factory.release import compile_factory_release
from bilqis_mlx.factory.tests.curriculum.test_capability_identity import (
    _authority_patch, _boolean_witness, _family_bindings, _formal_authority,
    _release_with_capability_alias, _release_with_capability_root,
    _registry_with_provider_digest,
)
from bilqis_mlx.factory.skos_curriculum.programs.tests.real_fixtures import (
    full_boolean_release, numeric_factory_release,
)


class CapabilityIdentityAdversarialTests(unittest.TestCase):
    def test_release_capability_alias_does_not_become_grade_identity(self):
        release, source_registry = full_boolean_release()
        baseline_bindings = _family_bindings(release, capability_id="B.AND")
        moved = _release_with_capability_alias(
            release, source_registry, "B.AND", "Z.AND")
        moved_bindings = _family_bindings(moved, capability_id="Z.AND")
        registry, proposal, census = _formal_authority()
        with _authority_patch(proposal, census):
            baseline = bind_factory_release_capability_identity(
                release, baseline_bindings, "B.AND", object(), registry)
            rebound = bind_factory_release_capability_identity(
                moved, moved_bindings, "Z.AND", object(), registry)
        self.assertEqual(
            rebound.stable_identity.capability_id,
            baseline.stable_identity.capability_id)

    def test_release_cannot_self_attest_forged_source_provider_digest(self):
        release, source_registry = full_boolean_release()
        forged_registry = _registry_with_provider_digest(
            source_registry, "source.micro.boolean-connectives/v1", "f" * 64)
        forged = compile_factory_release(release.course, forged_registry)
        bindings = _family_bindings(forged, capability_id="B.AND")
        registry, proposal, census = _formal_authority()
        with _authority_patch(proposal, census), self.assertRaises(BilqisError) as caught:
            bind_factory_release_capability_identity(
                forged, bindings, "B.AND", object(), registry)
        self.assertEqual(
            caught.exception.context.get("reason"),
            "FACTORY_CAPABILITY_IDENTITY_SOURCE_AUTHORITY_DRIFT")

    def test_release_binding_rejects_forged_census_coordinates(self):
        release, _ = full_boolean_release()
        bindings = _family_bindings(release, capability_id="B.AND")
        registry, proposal, census = _formal_authority()
        forged = replace(
            bindings,
            census_digest="f" * 64,
            coverage=replace(bindings.coverage, census_digest="f" * 64),
        )
        with _authority_patch(proposal, census):
            with self.assertRaises(BilqisError) as caught:
                bind_factory_release_capability_identity(
                    release, forged, "B.AND", object(), registry)
        self.assertEqual(
            caught.exception.context.get("reason"),
            "FACTORY_CAPABILITY_IDENTITY_FAMILY_BINDING_DRIFT")

    def test_distinct_boolean_operators_have_distinct_stable_identities(self):
        release, _ = full_boolean_release()
        registry, _, census = _formal_authority()
        pairs = (
            ("B.AND", "BOOL_AND"), ("B.OR", "BOOL_OR"),
            ("B.XOR", "BOOL_XOR"), ("B.IMPLIES", "BOOL_IMPLIES"),
            ("B.IFF", "BOOL_IFF"),
        )
        stable_ids = []
        for capability_id, operator_id in pairs:
            proposal = SimpleNamespace(witnesses=(
                _boolean_witness(registry, capability_id, operator_id),))
            with _authority_patch(proposal, census):
                stable_ids.append(bind_factory_release_capability_identity(
                    release,
                    _family_bindings(release, capability_id=capability_id),
                    capability_id,
                    object(),
                    registry,
                ).stable_identity.capability_id)
        self.assertEqual(len(set(stable_ids)), len(pairs))

    def test_family_level_formal_binding_resolves_exact_capability_witness(self):
        release, _ = full_boolean_release()
        registry, _, census = _formal_authority()
        shared = ("B.NOT", "B.AND")
        proposal = SimpleNamespace(witnesses=(
            SimpleNamespace(**{
                **vars(_boolean_witness(registry, "B.NOT", "BOOL_NOT")),
                "capability_ids": shared}),
            SimpleNamespace(**{
                **vars(_boolean_witness(registry, "B.AND", "BOOL_AND")),
                "capability_ids": shared}),
        ))
        with _authority_patch(proposal, census):
            binding = bind_factory_release_capability_identity(
                release, _family_bindings(release, capability_id="B.AND"),
                "B.AND", object(), registry)
        self.assertEqual(binding.release_capability_id, "B.AND")

    def test_release_root_cannot_steer_capability_to_another_formal_witness(self):
        release, source_registry = full_boolean_release()
        forged = _release_with_capability_root(
            release, source_registry, "B.AND", "evil.namespace.NOT")
        bindings = _family_bindings(forged, capability_id="B.AND")
        registry, _, census = _formal_authority()
        shared = ("B.NOT", "B.AND")
        proposal = SimpleNamespace(witnesses=(
            SimpleNamespace(**{
                **vars(_boolean_witness(registry, "B.NOT", "BOOL_NOT")),
                "capability_ids": shared}),
            SimpleNamespace(**{
                **vars(_boolean_witness(registry, "B.AND", "BOOL_AND")),
                "capability_ids": shared}),
        ))
        with _authority_patch(proposal, census), self.assertRaises(BilqisError) as caught:
            bind_factory_release_capability_identity(
                forged, bindings, "B.AND", object(), registry)
        self.assertEqual(
            caught.exception.context.get("reason"),
            "FACTORY_CAPABILITY_IDENTITY_FORMAL_COORDINATE_DRIFT")

    def test_release_root_suffix_is_not_formal_identity_authority(self):
        release, source_registry = full_boolean_release()
        forged = _release_with_capability_root(
            release, source_registry, "B.AND", "evil.namespace.AND")
        bindings = _family_bindings(forged, capability_id="B.AND")
        registry, proposal, census = _formal_authority()
        with _authority_patch(proposal, census), self.assertRaises(BilqisError) as caught:
            bind_factory_release_capability_identity(
                forged, bindings, "B.AND", object(), registry)
        self.assertEqual(
            caught.exception.context.get("reason"),
            "FACTORY_CAPABILITY_IDENTITY_FORMAL_COORDINATE_DRIFT")

    def test_release_taught_root_drift_cannot_hide_behind_canonical_exam_root(self):
        release, source_registry = full_boolean_release()
        grades = []
        for grade in release.course.grades:
            capabilities = tuple(
                replace(item, taught_roots=("cogal.operator.AND", "evil.namespace.NOT"))
                if item.id == "B.AND" else item
                for item in grade.capabilities)
            grades.append(replace(grade, capabilities=capabilities))
        forged = compile_factory_release(
            replace(release.course, grades=tuple(grades)), source_registry)
        bindings = _family_bindings(forged, capability_id="B.AND")
        registry, proposal, census = _formal_authority()
        with _authority_patch(proposal, census), self.assertRaises(BilqisError) as caught:
            bind_factory_release_capability_identity(
                forged, bindings, "B.AND", object(), registry)
        self.assertEqual(
            caught.exception.context.get("reason"),
            "FACTORY_CAPABILITY_IDENTITY_FORMAL_COORDINATE_DRIFT")

    def test_numeric_source_coordinate_uses_lesson_operation_not_capability_suffix(self):
        release, _ = numeric_factory_release()
        bindings = _family_bindings(
            release, family_id="numeric_composition", capability_id="C.SUCCESSOR")
        registry, _, census = _formal_authority()
        proposal = SimpleNamespace(witnesses=(SimpleNamespace(
            semantic_id="bilqis.numeric/v1:school.op.SUCC",
            family="numeric", operator=registry.resolve("SUCC"),
            capability_ids=("C.SUCCESSOR",)),))
        with _authority_patch(proposal, census):
            binding = bind_factory_release_capability_identity(
                release, bindings, "C.SUCCESSOR", object(), registry)
        identity = binding.stable_identity.identity
        self.assertEqual(identity.operator_id, "SUCC")
        self.assertEqual(identity.semantic_id, "bilqis.numeric/v1:school.op.SUCC")


if __name__ == "__main__":
    unittest.main()
