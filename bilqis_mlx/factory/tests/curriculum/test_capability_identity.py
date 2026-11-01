from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.curriculum.capability_identity import (
    CapabilityIdentityInput, StableCapabilityIdentity,
    bind_factory_release_capability_identity, bind_stable_capability_identity,
    stable_capability_id,
)
from bilqis_mlx.factory.curriculum.formal_constructive import _resolve_from_bindings
from bilqis_mlx.factory.release import compile_factory_release
from bilqis_mlx.factory.skos_curriculum.inventory import _inventory_source_families
from bilqis_mlx.factory.skos_curriculum.programs.contracts import (
    BoundFamilyProgram, FactoryReleaseFamilyBindings, FamilyProgramCoverage,
)
from bilqis_mlx.factory.tests.sources.test_skos_curriculum import _snapshot
from bilqis_mlx.factory.skos_curriculum.programs.tests.real_fixtures import (
    full_boolean_release, numeric_factory_release,
)
from bilqis_mlx.semantics.cognitive_operators import default_registry
from bilqis_mlx.semantics.foundation.core import Signature


def _family_bindings(release, *, family_id="boolean_composition",
                     release_sha256=None, capability_id=None):
    capability = next(
        item for item in release.capabilities
        if capability_id is None or item.capability_id == capability_id)
    program = next(
        item for item in release.construction_programs
        if item.capability_id == capability.capability_id)
    snapshot = _snapshot()
    census = _inventory_source_families(snapshot)
    bound = BoundFamilyProgram(
        family_id, capability.capability_id, capability.source_adapter_id,
        program.generator_id, program.oracle_id,
        "bilqis.factory.formal-lesson/v1", "bilqis.factory.formal-checker/v1",
        semantic_roots=release.course.capability_map[capability.capability_id].examined_roots,
        source_implementation_sha256=release.source_adapter_map[
            capability.source_adapter_id].implementation_sha256)
    coverage = FamilyProgramCoverage(
        census.semantic_release, census.digest, (), census.counts.source_held_rows)
    return FactoryReleaseFamilyBindings(
        release.release_sha256 if release_sha256 is None else release_sha256,
        census.semantic_release, census.digest, (bound,), coverage)


def _formal_authority(capability_id="B.AND"):
    snapshot = _snapshot()
    census = _inventory_source_families(snapshot)
    registry = default_registry(snapshot.release_sha256)
    proposal = _resolve_from_bindings(
        snapshot.formal_domain_bindings, snapshot.abi_entries, registry,
        semantic_release=snapshot.release_sha256,
        atlas_bundle_id=snapshot.bundle_id)
    assert any(capability_id in item.capability_ids for item in proposal.witnesses)
    return registry, proposal, census


def _authority_patch(proposal, census):
    return patch.multiple(
        "bilqis_mlx.factory.curriculum.capability_identity",
        resolve_formal_source_operators=lambda *_args: proposal,
        inventory_source_families=lambda _atlas: census,
        assert_family_inventory_current=lambda *_args: None,
    )


def _boolean_witness(registry, capability_id, operator_id):
    suffix = operator_id.removeprefix("BOOL_")
    return SimpleNamespace(
        semantic_id="legacy:cogal.operator." + suffix,
        family="boolean",
        operator=registry.resolve(operator_id),
        capability_ids=(capability_id,),
    )


def _release_with_capability_root(release, source_registry, capability_id, root):
    grades = []
    for grade in release.course.grades:
        capabilities = tuple(
            replace(item, taught_roots=(root,), examined_roots=(root,))
            if item.id == capability_id else item
            for item in grade.capabilities)
        grades.append(replace(grade, capabilities=capabilities))
    return compile_factory_release(
        replace(release.course, grades=tuple(grades)), source_registry)


class CapabilityIdentityTests(unittest.TestCase):
    def test_semantic_family_signature_and_answer_modality_define_identity(self):
        identity = bind_stable_capability_identity(
            "legacy:cogal.operator.AND", "boolean_composition", "BOOL_AND",
            Signature(("Boolean", "Boolean"), "Boolean"),
            ("BOOLEAN",))
        self.assertTrue(identity.capability_id.startswith("cap:"))
        self.assertEqual(len(identity.capability_id), 68)
        self.assertEqual(identity.capability_id, stable_capability_id(identity.identity))

    def test_grade_provider_source_path_and_root_ordinal_are_not_identity_inputs(self):
        identity = CapabilityIdentityInput(
            "bilqis.numeric/v1:school.op.ADD", "numeric_composition", "ADD",
            Signature(("Number", "Number"), "Number"),
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
            "bilqis.numeric/v1:school.op.ADD", "numeric_composition", "ADD",
            Signature(("Number", "Number"), "Number"),
            ("INTEGER",))
        variants = (
            replace(base, family_id="boolean_composition"),
            replace(base, semantic_id="bilqis.numeric/v1:school.op.SUB"),
            replace(base, operator_id="SUB"),
            replace(base, signature=Signature(("Number",), "Number")),
            replace(base, answer_kinds=("INTEGER", "SEMANTIC_TOKEN")),
        )
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertNotEqual(stable_capability_id(base), stable_capability_id(variant))

    def test_forged_digest_and_noncanonical_modalities_fail(self):
        base = CapabilityIdentityInput(
            "legacy:cogal.operator.NOT", "boolean_composition", "BOOL_NOT",
            Signature(("Boolean",), "Boolean"),
            ("BOOLEAN",))
        with self.assertRaises(ValueError):
            StableCapabilityIdentity("cap:" + "0" * 64, base)
        for answer_kinds in ((), ("B", "A"), ("A", "A")):
            with self.subTest(answer_kinds=answer_kinds), self.assertRaises(ValueError):
                CapabilityIdentityInput(
                    "legacy:cogal.operator.NOT", "boolean_composition", "BOOL_NOT",
                    Signature(("Boolean",), "Boolean"),
                    answer_kinds)

    def test_existing_factory_release_supplies_answer_modality_to_stable_identity(self):
        release, _ = full_boolean_release()
        bindings = _family_bindings(release, capability_id="B.AND")
        registry, proposal, census = _formal_authority()
        with _authority_patch(proposal, census):
            binding = bind_factory_release_capability_identity(
                release, bindings, "B.AND", object(), registry)
        self.assertEqual(binding.factory_release_sha256, release.release_sha256)
        self.assertEqual(binding.release_capability_id, "B.AND")
        self.assertEqual(binding.stable_identity.identity.answer_kinds, ("binary",))
        self.assertEqual(binding.stable_identity.identity.family_id,
                         "boolean_composition")
        self.assertEqual(
            binding.stable_identity.identity.signature,
            Signature(("Boolean", "Boolean"), "Boolean"))

    def test_release_binding_rejects_unknown_capability_and_forged_release(self):
        release, _ = full_boolean_release()
        bindings = _family_bindings(release, capability_id="B.AND")
        registry, proposal, census = _formal_authority()
        with _authority_patch(proposal, census):
            with self.assertRaises(BilqisError) as caught:
                bind_factory_release_capability_identity(
                    release, bindings, "A.MISSING", object(), registry)
        self.assertEqual(
            caught.exception.context.get("reason"),
            "FACTORY_CAPABILITY_IDENTITY_RELEASE_CAPABILITY_MISSING")
        forged = replace(release, release_sha256="0" * 64)
        with self.assertRaises(ValueError):
            bind_factory_release_capability_identity(
                forged, bindings, "B.AND", object(), registry)

    def test_release_binding_rejects_family_binding_from_another_release(self):
        release, _ = full_boolean_release()
        bindings = _family_bindings(
            release, release_sha256="d" * 64, capability_id="B.AND")
        registry, proposal, census = _formal_authority()
        with self.assertRaises(BilqisError) as caught:
            bind_factory_release_capability_identity(
                release, bindings, "B.AND", object(), registry)
        self.assertEqual(
            caught.exception.context.get("reason"),
            "FACTORY_CAPABILITY_IDENTITY_FAMILY_BINDING_DRIFT")

    def test_release_binding_rejects_same_release_family_relabel(self):
        release, _ = full_boolean_release()
        bindings = _family_bindings(
            release, family_id="forged_family", capability_id="B.AND")
        registry, proposal, census = _formal_authority()
        with _authority_patch(proposal, census):
            with self.assertRaises(BilqisError) as caught:
                bind_factory_release_capability_identity(
                    release, bindings, "B.AND", object(), registry)
        self.assertEqual(
            caught.exception.context.get("reason"),
            "FACTORY_CAPABILITY_IDENTITY_FAMILY_BINDING_DRIFT")

    def test_release_binding_has_no_caller_signature_authority(self):
        release, _ = full_boolean_release()
        bindings = _family_bindings(release, capability_id="B.AND")
        registry, proposal, census = _formal_authority()
        with _authority_patch(proposal, census):
            with self.assertRaises(TypeError):
                bind_factory_release_capability_identity(
                    release, bindings, "B.AND", object(), registry,
                    Signature(("Entity", "Entity"), "Boolean"))

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
