"""Stable capability identity from semantic family + typed operator signature."""
from __future__ import annotations

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.semantics.cognitive_operators import OperatorRegistry
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
from bilqis_mlx.factory.model import FactoryRelease
from bilqis_mlx.factory.curriculum.formal_constructive import (
    resolve_formal_source_operators,
)
from bilqis_mlx.factory.skos_curriculum.adapters import SOURCE_FAMILY_ADAPTERS
from bilqis_mlx.factory.skos_curriculum.inventory import (
    assert_family_inventory_current, inventory_source_families,
)
from bilqis_mlx.factory.skos_curriculum.programs.catalog import (
    default_family_program_registry,
)
from bilqis_mlx.factory.skos_curriculum.programs.contracts import (
    FactoryReleaseFamilyBindings,
)
from bilqis_mlx.source_adapters.formal_identity import (
    source_formal_coordinate,
)
from .capability_identity_contracts import (
    CapabilityIdentityInput, ReleaseCapabilityIdentityBinding,
    StableCapabilityIdentity, bind_stable_capability_identity,
    stable_capability_id,
)


_FAMILY_BINDING_DRIFT = "FACTORY_CAPABILITY_IDENTITY_FAMILY_BINDING_DRIFT"
_FAMILY_AUTHORITY_MISSING = "FACTORY_CAPABILITY_IDENTITY_FAMILY_AUTHORITY_MISSING"
_SIGNATURE_AUTHORITY_MISSING = "FACTORY_CAPABILITY_IDENTITY_SIGNATURE_AUTHORITY_MISSING"
_FORMAL_COORDINATE_DRIFT = "FACTORY_CAPABILITY_IDENTITY_FORMAL_COORDINATE_DRIFT"
_SOURCE_AUTHORITY_DRIFT = "FACTORY_CAPABILITY_IDENTITY_SOURCE_AUTHORITY_DRIFT"


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _release_capability(release: FactoryRelease, capability_id: str):
    matches = tuple(
        item for item in release.capabilities
        if item.capability_id == capability_id)
    if len(matches) != 1:
        _fail("FACTORY_CAPABILITY_IDENTITY_RELEASE_CAPABILITY_MISSING")
    return matches[0]


def _canonical_family_program(capability):
    matches = tuple(
        program for program in default_family_program_registry().programs
        if capability.source_adapter_id in program.accepted_source_adapter_ids)
    if len(matches) != 1:
        _fail(_FAMILY_AUTHORITY_MISSING)
    return matches[0]


def _verify_bound_family_row(release, capability, family, program):
    constructions = tuple(
        item for item in release.construction_programs
        if item.capability_id == capability.capability_id)
    if len(constructions) != 1:
        _fail(_FAMILY_BINDING_DRIFT)
    construction = constructions[0]
    source = release.source_adapter_map.get(capability.source_adapter_id)
    expected = (
        program.family_id, capability.capability_id, capability.source_adapter_id,
        construction.generator_id, construction.oracle_id,
        program.constructor_ref, program.checker_ref,
        release.course.capability_map[capability.capability_id].examined_roots,
        None if source is None else source.implementation_sha256,
    )
    actual = (
        family.family_id, family.capability_id, family.source_adapter_id,
        family.generator_id, family.oracle_id, family.constructor_ref,
        family.checker_ref, family.semantic_roots,
        family.source_implementation_sha256,
    )
    if actual != expected:
        _fail(_FAMILY_BINDING_DRIFT)
    return program.family_id, construction, source


def _authoritative_operator(
    capability, construction, source, family_id: str, taught_roots: tuple[str, ...],
    semantic_roots: tuple[str, ...],
    atlas: AtlasArtifactSelection, operator_registry: OperatorRegistry,
):
    adapter = next(
        (item for item in SOURCE_FAMILY_ADAPTERS if item.family_id == family_id),
        None)
    if adapter is None or len(adapter.formal_families) != 1:
        _fail(_SIGNATURE_AUTHORITY_MISSING)
    authority = source_formal_coordinate(
        capability.capability_id, capability.source_adapter_id)
    if authority is None:
        _fail(_SIGNATURE_AUTHORITY_MISSING)
    source_root, operator_id = authority.semantic_root, authority.operator_id
    if (source is None
            or source.generator_id != authority.generator_id
            or source.accepted_oracle_ids != authority.accepted_oracle_ids
            or source.implementation_sha256 != authority.implementation_sha256
            or construction.generator_id != authority.generator_id
            or construction.oracle_id not in authority.accepted_oracle_ids):
        _fail(_SOURCE_AUTHORITY_DRIFT)
    if taught_roots != (source_root,) or semantic_roots != (source_root,):
        _fail(_FORMAL_COORDINATE_DRIFT)
    formal_sources = resolve_formal_source_operators(atlas, operator_registry)
    matches = tuple(
        witness for witness in formal_sources.witnesses
        if witness.family in adapter.formal_families
        and witness.operator.operator_id == operator_id)
    if len(matches) != 1:
        _fail(_SIGNATURE_AUTHORITY_MISSING)
    return matches[0]


def bind_factory_release_capability_identity(
    release: FactoryRelease,
    family_bindings: FactoryReleaseFamilyBindings,
    capability_id: str,
    atlas: AtlasArtifactSelection,
    operator_registry: OperatorRegistry,
) -> ReleaseCapabilityIdentityBinding:
    """Bind identity only from independently replayed family/operator authority."""
    if (type(release) is not FactoryRelease
            or type(family_bindings) is not FactoryReleaseFamilyBindings
            or type(operator_registry) is not OperatorRegistry):
        _fail("FACTORY_CAPABILITY_IDENTITY_RELEASE_REQUIRED")
    release.verify()
    if family_bindings.factory_release_sha256 != release.release_sha256:
        _fail(_FAMILY_BINDING_DRIFT)
    census = inventory_source_families(atlas)
    assert_family_inventory_current(census, atlas)
    if (family_bindings.semantic_release != census.semantic_release
            or family_bindings.census_digest != census.digest):
        _fail(_FAMILY_BINDING_DRIFT)
    capability = _release_capability(release, capability_id)
    family = family_bindings.require(capability_id)
    if capability.source_adapter_id != family.source_adapter_id:
        _fail(_FAMILY_BINDING_DRIFT)
    family_program = _canonical_family_program(capability)
    family_id, construction, source = _verify_bound_family_row(
        release, capability, family, family_program)
    course_capability = release.course.capability_map[capability_id]
    witness = _authoritative_operator(
        capability, construction, source, family_id, course_capability.taught_roots,
        family.semantic_roots, atlas, operator_registry)

    stable = bind_stable_capability_identity(
        witness.semantic_id, family_id, witness.operator.operator_id,
        witness.operator.signature, tuple(sorted(capability.answer_kinds)))
    return ReleaseCapabilityIdentityBinding(
        release.release_sha256, capability.capability_id, stable)
