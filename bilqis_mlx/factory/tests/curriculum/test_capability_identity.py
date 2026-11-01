from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.adapters import RegisteredSourceAdapter, SourceAdapterRegistry
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


def _release_with_capability_alias(release, source_registry, old_id, new_id):
    def renamed(value):
        return new_id if value == old_id else value

    grades = []
    for grade in release.course.grades:
        capabilities = tuple(replace(
            item,
            id=renamed(item.id),
            prerequisites=tuple(renamed(value) for value in item.prerequisites),
            composed_of=tuple(renamed(value) for value in item.composed_of),
        ) for item in grade.capabilities)
        grades.append(replace(
            grade,
            capabilities=capabilities,
            exam_item_counts=tuple((renamed(name), count)
                                   for name, count in grade.exam_item_counts),
            teaching_stages=tuple(tuple(renamed(name) for name in stage)
                                  for stage in grade.teaching_stages),
        ))
    return compile_factory_release(
        replace(release.course, grades=tuple(grades)), source_registry)


def _registry_with_provider_digest(registry, adapter_id, digest):
    adapters = []
    for adapter in registry._by_generator.values():
        descriptor = adapter.descriptor
        if descriptor.adapter_id == adapter_id:
            descriptor = replace(descriptor, implementation_sha256=digest)
        adapters.append(RegisteredSourceAdapter(
            descriptor, adapter.draw, adapter.check, adapter.enrich,
            adapter.witness, adapter.dependencies, adapter.semantic_footprint))
    return SourceAdapterRegistry(tuple(adapters))


class CapabilityIdentityTests(unittest.TestCase):
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
