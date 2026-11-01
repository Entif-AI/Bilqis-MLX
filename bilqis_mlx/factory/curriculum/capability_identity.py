"""Stable capability identity from semantic family + typed operator signature."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.semantics.foundation.core import Signature
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


CAPABILITY_IDENTITY_SCHEMA = "bilqis.capability-identity/v1"
_CAPABILITY_ID = re.compile(r"cap:[0-9a-f]{64}\Z")
_FAMILY_BINDING_DRIFT = "FACTORY_CAPABILITY_IDENTITY_FAMILY_BINDING_DRIFT"
_FAMILY_AUTHORITY_MISSING = "FACTORY_CAPABILITY_IDENTITY_FAMILY_AUTHORITY_MISSING"
_SIGNATURE_AUTHORITY_MISSING = "FACTORY_CAPABILITY_IDENTITY_SIGNATURE_AUTHORITY_MISSING"
_FORMAL_COORDINATE_DRIFT = "FACTORY_CAPABILITY_IDENTITY_FORMAL_COORDINATE_DRIFT"


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CapabilityIdentityInput:
    """Only semantic/operator meaning participates in stable identity."""

    semantic_id: str
    family_id: str
    operator_id: str
    signature: Signature
    answer_kinds: tuple[str, ...]
    schema: str = CAPABILITY_IDENTITY_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.semantic_id, str) or not self.semantic_id
                or not isinstance(self.family_id, str) or not self.family_id
                or not isinstance(self.operator_id, str) or not self.operator_id
                or type(self.signature) is not Signature
                or not isinstance(self.answer_kinds, tuple)
                or not self.answer_kinds
                or self.answer_kinds != tuple(sorted(set(self.answer_kinds)))
                or any(not isinstance(item, str) or not item
                       for item in self.answer_kinds)
                or self.schema != CAPABILITY_IDENTITY_SCHEMA):
            _fail("FACTORY_CAPABILITY_IDENTITY_INPUT_INVALID")

    def canonical_payload(self) -> tuple:
        return (
            self.schema,
            self.semantic_id,
            self.family_id,
            self.operator_id,
            self.signature.inputs,
            self.signature.output,
            self.answer_kinds,
        )


@dataclass(frozen=True)
class StableCapabilityIdentity:
    capability_id: str
    identity: CapabilityIdentityInput

    def __post_init__(self) -> None:
        if (not isinstance(self.capability_id, str)
                or not _CAPABILITY_ID.fullmatch(self.capability_id)
                or self.capability_id != stable_capability_id(self.identity)):
            _fail("FACTORY_CAPABILITY_IDENTITY_DIGEST_MISMATCH")


@dataclass(frozen=True)
class ReleaseCapabilityIdentityBinding:
    factory_release_sha256: str
    release_capability_id: str
    stable_identity: StableCapabilityIdentity

    def __post_init__(self) -> None:
        if (not isinstance(self.factory_release_sha256, str)
                or not re.fullmatch(r"[0-9a-f]{64}", self.factory_release_sha256)
                or not isinstance(self.release_capability_id, str)
                or not self.release_capability_id
                or type(self.stable_identity) is not StableCapabilityIdentity):
            _fail("FACTORY_CAPABILITY_IDENTITY_RELEASE_BINDING_INVALID")


def stable_capability_id(identity: CapabilityIdentityInput) -> str:
    """Derive identity without grade, provider, source path, or root ordinal."""
    if type(identity) is not CapabilityIdentityInput:
        _fail("FACTORY_CAPABILITY_IDENTITY_REQUIRED")
    CapabilityIdentityInput.__post_init__(identity)
    return "cap:" + _digest(identity.canonical_payload())


def bind_stable_capability_identity(
    semantic_id: str, family_id: str, operator_id: str,
    signature: Signature, answer_kinds: tuple[str, ...],
) -> StableCapabilityIdentity:
    identity = CapabilityIdentityInput(
        semantic_id, family_id, operator_id, signature, answer_kinds)
    return StableCapabilityIdentity(stable_capability_id(identity), identity)


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


def _verify_bound_family_row(release, capability, family, program) -> str:
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
    return program.family_id


def _authoritative_operator(
    capability, family_id: str, semantic_roots: tuple[str, ...],
    atlas: AtlasArtifactSelection, operator_registry: OperatorRegistry,
):
    adapter = next(
        (item for item in SOURCE_FAMILY_ADAPTERS if item.family_id == family_id),
        None)
    if adapter is None or len(adapter.formal_families) != 1:
        _fail(_SIGNATURE_AUTHORITY_MISSING)
    coordinate = source_formal_coordinate(
        capability.capability_id, capability.source_adapter_id)
    if coordinate is None:
        _fail(_SIGNATURE_AUTHORITY_MISSING)
    source_root, operator_id = coordinate
    if semantic_roots != (source_root,):
        _fail(_FORMAL_COORDINATE_DRIFT)
    formal_sources = resolve_formal_source_operators(atlas, operator_registry)
    matches = tuple(
        witness for witness in formal_sources.witnesses
        if capability.capability_id in witness.capability_ids
        and witness.family in adapter.formal_families
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
    family_id = _verify_bound_family_row(
        release, capability, family, family_program)
    witness = _authoritative_operator(
        capability, family_id, family.semantic_roots, atlas, operator_registry)

    stable = bind_stable_capability_identity(
        witness.semantic_id, family_id, witness.operator.operator_id,
        witness.operator.signature, tuple(sorted(capability.answer_kinds)))
    return ReleaseCapabilityIdentityBinding(
        release.release_sha256, capability.capability_id, stable)
